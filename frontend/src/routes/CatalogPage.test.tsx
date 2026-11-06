import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
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
