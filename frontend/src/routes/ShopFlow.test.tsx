import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { afterEach, expect, test, vi } from 'vitest'
import type { Me } from '../api/client'
import { orderQuery } from '../api/orders'
import { createAppRoutes } from '../appRoutes'
import { meQuery } from '../auth/session'
import { guestCart } from '../cart/guestCart'
import { makeOrder, makePage, makeProduct } from '../test/fixtures'
import { server } from '../test/server'

const buyer: Me = {
  id: 1, username: 'buyer', first_name: '', last_name: '', email: 'buyer@example.test', is_manager: false,
}

afterEach(() => guestCart.clear())

function renderShop(path: string, me: Me | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(meQuery().queryKey, me)
  if (me) {
    server.use(http.get('*/api/cart/', () => HttpResponse.json({ items: [], count: 0, total: '0.00' })))
  }
  const router = createMemoryRouter(createAppRoutes(client), { initialEntries: [path] })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { client, router }
}

test('гость выбирает вариант, меняет количество в корзине и переходит ко входу для оформления', async () => {
  const product = makeProduct({
    name: 'Рубашка',
    variants: [{ id: 4, name: 'Размер M', sku: 'M', price: '25.50', stock: 2, is_default: false }],
  })
  server.use(http.get('*/api/catalog/products/', () => HttpResponse.json(makePage([product]))))
  const { router } = renderShop('/')
  const user = userEvent.setup()

  const add = await screen.findByRole('button', { name: 'В корзину' })
  expect(add).toBeDisabled()
  await user.selectOptions(screen.getByLabelText('Вариант товара'), '4')
  await user.click(add)
  await user.click(screen.getByRole('link', { name: /Корзина: 1 шт./ }))
  expect(await screen.findByRole('heading', { name: 'Корзина' })).toBeInTheDocument()
  expect(screen.getByText('Размер M')).toBeInTheDocument()

  const plus = screen.getByRole('button', { name: 'Добавить одну штуку: Рубашка, Размер M' })
  await user.click(plus)
  expect(plus).toBeDisabled()
  expect(screen.getByRole('link', { name: /Корзина: 2 шт./ })).toHaveTextContent('51')
  await user.click(screen.getByRole('link', { name: 'Оформить заказ' }))
  expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument()
  expect(router.state.location.search).toBe('?next=%2Fcheckout')
  expect(guestCart.items()).toMatchObject([{ variant_id: 4, quantity: 2 }])
})

test('покупатель открывает свой заказ, отменяет его и видит обновлённую историю', async () => {
  let order = makeOrder()
  server.use(
    http.get('*/api/orders/', () => HttpResponse.json({ results: [order], count: 1 })),
    http.get('*/api/orders/7/', () => HttpResponse.json(order)),
    http.post('*/api/orders/7/cancel/', () => {
      order = makeOrder({
        can_cancel: false, can_pay: false, status: 'cancelled', status_display: 'Отменён',
        history: [{
          to_status: 'cancelled', changed_by: 'buyer', comment: 'Отменён покупателем',
          created_at: '2026-11-06T12:30:00Z',
        }],
      })
      return HttpResponse.json(order)
    }),
  )
  renderShop('/orders', buyer)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('link', { name: 'Заказ №7' }))
  expect(await screen.findByRole('cell', { name: 'Книга' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Отменить заказ' }))
  expect(await screen.findByText('Отменён')).toBeInTheDocument()
  expect(screen.getByText(/Отменён покупателем/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Отменить заказ' })).not.toBeInTheDocument()
})

test('владелец открывает учебную оплату из заказа и может повторить её после отказа', async () => {
  const order = makeOrder()
  server.use(
    http.get('*/api/orders/7/', () => HttpResponse.json(order)),
    http.post('*/api/orders/7/simulate-payment/', async ({ request }) => {
      const body: unknown = await request.json()
      if (body && typeof body === 'object' && 'outcome' in body && body.outcome === 'failed') {
        return HttpResponse.json(order)
      }
      expect(body).toEqual({ outcome: 'success' })
      return HttpResponse.json(makeOrder({
        status: 'paid', status_display: 'Оплачен', can_pay: false, can_cancel: false,
      }))
    }),
  )
  renderShop('/orders/7', buyer)
  const user = userEvent.setup()
  await user.click(await screen.findByText('Оплатить', { selector: 'summary' }))
  await user.click(screen.getByRole('button', { name: 'Отказ' }))
  expect(await screen.findByText('Учебный платёж отклонён. Можно повторить оплату.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Успех' }))
  expect(await screen.findByText('Оплачен')).toBeInTheDocument()
  expect(screen.queryByText('Оплатить', { selector: 'summary' })).not.toBeInTheDocument()
})

test('менеджер фильтрует заказы и выполняет доступный переход из API', async () => {
  let order = makeOrder({
    status: 'paid', status_display: 'Оплачен', can_cancel: false, can_pay: false,
    allowed_transitions: ['confirmed', 'cancelled'],
  })
  const change = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.json()).toEqual({ status: 'confirmed', comment: '' })
    order = makeOrder({
      status: 'confirmed', status_display: 'Подтверждён', can_cancel: false, can_pay: false,
      allowed_transitions: ['shipped', 'cancelled'],
    })
    return HttpResponse.json(order)
  })
  server.use(
    http.get('*/api/orders/', ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      const results = !status || status === order.status ? [order] : []
      return HttpResponse.json({ results, count: results.length })
    }),
    http.post('*/api/orders/7/status/', change),
  )
  const { client, router } = renderShop('/manager/orders?status=new', { ...buyer, is_manager: true })
  const user = userEvent.setup()
  expect(await screen.findByText('Заказов нет.')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('Статус'), 'paid')
  const confirm = await screen.findByRole('button', { name: 'Подтвердить' })
  expect(router.state.location.search).toBe('?status=paid')
  expect(screen.queryByRole('button', { name: 'Передать в доставку' })).not.toBeInTheDocument()
  await user.click(confirm)
  await user.click(screen.getByRole('button', { name: 'Подтвердить действие' }))
  expect(await screen.findByText('Заказов нет.')).toBeInTheDocument()
  expect(change).toHaveBeenCalledOnce()
  expect(client.getQueryData(orderQuery(7).queryKey)?.status).toBe('confirmed')

  await user.selectOptions(screen.getByLabelText('Статус'), 'confirmed')
  const table = await screen.findByRole('table')
  expect(within(table).getByRole('button', { name: 'Передать в доставку' })).toBeEnabled()
  expect(within(table).getByRole('button', { name: 'Отменить' })).toBeEnabled()
})

test.each(['/orders', '/manager/orders?status=paid'])(
  'список %s хранит страницу в URL и показывает предыдущие строки при загрузке',
  async (path) => {
    let release!: () => void
    const pending = new Promise<void>((resolve) => { release = resolve })
    const isManager = path.startsWith('/manager')
    server.use(http.get('*/api/orders/', async ({ request }) => {
      const search = new URL(request.url).searchParams
      expect(search.get('status')).toBe(isManager ? 'paid' : null)
      if (search.get('page') === '2') {
        await pending
        return HttpResponse.json({
          results: [makeOrder({ id: 8 })], count: 21, previous: '/api/orders/', next: null,
        })
      }
      return HttpResponse.json({
        results: [makeOrder({ id: 7 })], count: 21, previous: null, next: '/api/orders/?page=2',
      })
    }))
    const { router } = renderShop(path, { ...buyer, is_manager: isManager })
    const label = (id: number) => isManager ? `№${id}` : `Заказ №${id}`
    const user = userEvent.setup()
    try {
      await user.click(await screen.findByRole('link', { name: 'Следующая' }))
      expect(router.state.location.search).toBe(isManager ? '?status=paid&page=2' : '?page=2')
      expect(screen.getByRole('link', { name: label(7) })).toBeInTheDocument()
    } finally {
      release()
    }
    expect(await screen.findByRole('link', { name: label(8) })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Предыдущая' })).toBeInTheDocument()
  },
)
