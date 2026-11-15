import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import { makePage, makeProduct } from '../test/fixtures'
import { renderRoute } from '../test/render'
import { server } from '../test/server'
import CatalogPage from './CatalogPage'

test('показывает товары, цену и количество результатов', async () => {
  renderRoute(<CatalogPage />)

  expect(await screen.findByRole('link', { name: 'Книга «Канбан»' })).toBeInTheDocument()
  expect(screen.getByText('Найдено: 2')).toBeInTheDocument()
  expect(screen.getByText('1 290 ₽')).toBeInTheDocument()
})

test('передаёт фильтры из адреса в запрос к API', async () => {
  let requested: URLSearchParams | undefined
  server.use(
    http.get('*/api/catalog/products/', ({ request }) => {
      requested = new URL(request.url).searchParams
      return HttpResponse.json(makePage([]))
    }),
  )

  renderRoute(<CatalogPage />, '/?category=books&ordering=-price&in_stock=true')

  expect(await screen.findByText(/Ничего не найдено/)).toBeInTheDocument()
  expect(requested?.get('category')).toBe('books')
  expect(requested?.get('ordering')).toBe('-price')
  expect(requested?.get('in_stock')).toBe('true')
})

test('сортировка меняет адрес и сбрасывает страницу', async () => {
  const user = userEvent.setup()
  renderRoute(<CatalogPage />, '/?page=2')
  await screen.findByRole('link', { name: 'Книга «Канбан»' })

  await user.selectOptions(screen.getByLabelText('Сортировка'), '-price')

  await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/?ordering=-price'))
})

test('после очистки поиска на главной прокручивает страницу к каталогу', async () => {
  const user = userEvent.setup()
  renderRoute(<CatalogPage />)
  const catalog = await screen.findByRole('region', { name: 'Каталог' })
  const scrollIntoView = vi.fn()
  Object.assign(catalog, { scrollIntoView })
  const search = screen.getByRole('searchbox')

  await user.type(search, 'Канбан')
  await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/?q='))
  expect(scrollIntoView).not.toHaveBeenCalled()

  await user.clear(search)
  await waitFor(() => expect(scrollIntoView).toHaveBeenCalledOnce())
  expect(screen.getByTestId('location').textContent).toBe('/')
  expect(search).toHaveFocus()
})

test('при выборе другой страницы прокручивает к началу каталога', async () => {
  const user = userEvent.setup()
  server.use(http.get('*/api/catalog/products/', () =>
    HttpResponse.json(makePage([makeProduct()], { count: 21 })),
  ))
  renderRoute(<CatalogPage />, '/?q=код')
  const catalog = await screen.findByRole('region', { name: 'Каталог' })
  const scrollIntoView = vi.fn()
  Object.assign(catalog, { scrollIntoView })

  await user.click(await screen.findByRole('link', { name: '2' }))

  await waitFor(() => expect(scrollIntoView).toHaveBeenCalledOnce())
  expect(screen.getByRole('link', { name: '2' })).toHaveAttribute('aria-current', 'page')
})

test('отменяет старый поиск и показывает выдачу нового запроса', async () => {
  let oldSignal: AbortSignal | undefined
  let release = () => {}
  const slow = new Promise<void>((resolve) => { release = resolve })
  server.use(http.get('*/api/catalog/products/', async ({ request }) => {
    const q = new URL(request.url).searchParams.get('q')
    if (q === 'старый') {
      oldSignal = request.signal
      await slow
      return HttpResponse.json(makePage([makeProduct({ name: 'Старый результат' })]))
    }
    return HttpResponse.json(makePage([makeProduct({ name: 'Новый результат' })]))
  }))
  const user = userEvent.setup()
  renderRoute(<CatalogPage />, '/?q=старый&page=2')
  try {
    await waitFor(() => expect(oldSignal).toBeDefined())
    expect(screen.getByRole('status', { name: 'Загрузка товаров' })).toBeInTheDocument()
    const search = screen.getByRole('searchbox')
    await user.clear(search)
    await user.type(search, 'новый')

    expect(await screen.findByRole('link', { name: 'Новый результат' })).toBeInTheDocument()
    expect(screen.getByTestId('location').textContent).not.toContain('page=')
    await waitFor(() => expect(oldSignal?.aborted).toBe(true))
    release()
    expect(screen.queryByRole('link', { name: 'Старый результат' })).not.toBeInTheDocument()
  } finally {
    release()
  }
})

test('показывает ошибку сервера и загружает каталог после повтора', async () => {
  const user = userEvent.setup()
  server.use(
    http.get('*/api/catalog/products/', () =>
      HttpResponse.json({ detail: 'Сервис недоступен' }, { status: 503 }),
    ),
  )
  renderRoute(<CatalogPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен')

  server.use(http.get('*/api/catalog/products/', () => HttpResponse.json(makePage([makeProduct()]))))
  await user.click(screen.getByRole('button', { name: 'Повторить' }))

  expect(await screen.findByRole('link', { name: 'Книга «Чистый код»' })).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('показывает сообщение, если сервер каталога не ответил вовремя', async () => {
  const timeout = vi.spyOn(AbortSignal, 'timeout').mockReturnValueOnce(
    AbortSignal.abort(new DOMException('Timed out', 'TimeoutError')),
  )
  try {
    renderRoute(<CatalogPage />, '/?q=код')
    expect(await screen.findByRole('alert')).toHaveTextContent('Сервер магазина не ответил вовремя.')
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeEnabled()
  } finally {
    timeout.mockRestore()
  }
})

test('предлагает исправить опечатку и ищет подсказку в той же категории', async () => {
  const user = userEvent.setup()
  server.use(
    http.get('*/api/catalog/products/', ({ request }) => {
      const params = new URL(request.url).searchParams
      expect(params.get('category')).toBe('books')
      if (params.get('q') === 'канбн') {
        return HttpResponse.json(makePage([], { suggestion: 'Канбан' }))
      }
      expect(params.get('q')).toBe('Канбан')
      return HttpResponse.json(makePage([makeProduct({ name: 'Книга «Канбан»' })]))
    }),
  )
  renderRoute(<CatalogPage />, '/?category=books&q=канбн')

  await user.click(await screen.findByRole('link', { name: 'Канбан' }))

  expect(await screen.findByRole('link', { name: 'Книга «Канбан»' })).toBeInTheDocument()
  expect(screen.getByRole('searchbox')).toHaveValue('Канбан')
})
