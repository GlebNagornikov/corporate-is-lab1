import { QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { afterEach, expect, test, vi } from 'vitest'
import { createAppRoutes } from '../appRoutes'
import { guestCart, summarizeCart } from '../cart/guestCart'
import { cartQuery } from '../cart/queries'
import { priceChangesQuery } from '../cart/priceChanges'
import { queryClient } from '../queryClient'
import { makeProduct } from '../test/fixtures'
import { server } from '../test/server'
import { login, meQuery, register } from './session'
import { tokens } from './tokens'

const buyer = {
  id: 1, username: 'buyer', email: 'buyer@example.test',
  first_name: '', last_name: '', is_manager: false,
}
const emptyCart = summarizeCart([])

afterEach(() => {
  cleanup()
  tokens.clear()
  guestCart.clear()
  queryClient.clear()
})

function mockLogin() {
  server.use(
    http.post('*/api/auth/session/login/', () => HttpResponse.json({ access: 'a' })),
    http.get('*/api/auth/me/', () => HttpResponse.json(buyer)),
    http.get('*/api/cart/', () => HttpResponse.json(emptyCart)),
  )
}

test('регистрация входит в аккаунт и переносит каждый вариант одной строкой', async () => {
  mockLogin()
  const updated = {
    items: [{
      product_id: 7, variant_id: 3, variant_name: 'Красный', is_default_variant: false,
      name: 'Книга', slug: 'book', image: null, stock: 110, quantity: 101,
      price: '16.50', total: '1666.50',
    }],
    count: 101,
    total: '1666.50',
  }
  const merge = vi.fn(async ({ request }: { request: Request }) => {
    expect(request.headers.get('Authorization')).toBe('Bearer a')
    expect(await request.json()).toEqual({ items: [
      { product: 7, variant: 3, quantity: 101 },
    ] })
    return HttpResponse.json(updated)
  })
  server.use(
    http.post('*/api/auth/register/', () => HttpResponse.json(buyer, { status: 201 })),
    http.post('*/api/cart/merge/', merge),
  )
  guestCart.add(makeProduct({ id: 7 }), 101, {
    id: 3, name: 'Красный', sku: 'red', stock: 110, price: '15.50', is_default: false,
  })

  await register({ username: buyer.username, email: buyer.email, password: 'secret' })

  expect(merge).toHaveBeenCalledOnce()
  expect(guestCart.items()).toEqual([])
  expect(queryClient.getQueryData(meQuery().queryKey)).toEqual(buyer)
  expect(queryClient.getQueryData(cartQuery().queryKey)).toEqual(updated)
  expect(queryClient.getQueryData(priceChangesQuery().queryKey)).toEqual([
    { item: updated.items[0], before: '15.50' },
  ])
})

test('при отказе переноса вход завершается ошибкой, а гостевые позиции сохраняются', async () => {
  mockLogin()
  server.use(http.post('*/api/cart/merge/', () =>
    HttpResponse.json({ detail: 'Перенос недоступен' }, { status: 400 }),
  ))
  guestCart.add(makeProduct())
  const items = guestCart.items()

  await expect(login('buyer', 'secret')).rejects.toThrow('Перенос недоступен')
  expect(guestCart.items()).toBe(items)
  expect(tokens.access()).toBeNull()
  expect(queryClient.getQueryData(meQuery().queryKey)).toBeNull()
})

function renderApp(initialEntry: string) {
  const router = createMemoryRouter(createAppRoutes(queryClient), { initialEntries: [initialEntry] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

test('перенаправляет гостя на вход, сохраняя адрес заказа и параметры', async () => {
  const order = vi.fn(() => HttpResponse.json({ id: 7 }))
  server.use(http.get('*/api/orders/7/', order))
  const router = renderApp('/orders/7?from=cart')

  expect(await screen.findByRole('heading', { name: 'Вход' }, { timeout: 5000 })).toBeInTheDocument()
  expect(router.state.location.search).toBe('?next=%2Forders%2F7%3Ffrom%3Dcart')
  expect(order).not.toHaveBeenCalled()
})

test('запрещает покупателю раздел менеджера', async () => {
  mockLogin()
  tokens.save({ access: 'a' })
  renderApp('/manager/orders')
  expect(await screen.findByRole('heading', { name: 'Нет доступа' })).toBeInTheDocument()
})

test('открывает ленивый маршрут заказов для менеджера', async () => {
  tokens.save({ access: 'a' })
  server.use(
    http.get('*/api/auth/me/', () => HttpResponse.json({ ...buyer, is_manager: true })),
    http.get('*/api/cart/', () => HttpResponse.json(emptyCart)),
    http.get('*/api/manager/orders/', () => HttpResponse.json({ count: 0, results: [] })),
  )
  renderApp('/manager/orders')
  expect(await screen.findByRole('heading', { name: 'Заказы магазина' })).toBeInTheDocument()
})

test('истёкшая сессия очищает приватный кэш и открывает экран входа', async () => {
  tokens.save({ access: 'expired' })
  queryClient.setQueryData(cartQuery().queryKey, emptyCart)
  queryClient.setQueryData(['orders', 'list'], { results: [] })
  queryClient.setQueryData(['manager', 'catalog', 'list'], { results: [] })
  const invalid = () => HttpResponse.json({ detail: 'Токен недействителен' }, { status: 401 })
  server.use(
    http.get('*/api/auth/me/', invalid),
    http.post('*/api/auth/session/refresh/', invalid),
  )

  renderApp('/checkout')
  expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument()
  expect(tokens.access()).toBeNull()
  expect(queryClient.getQueryData(cartQuery().queryKey)).toBeUndefined()
  expect(queryClient.getQueryData(['orders', 'list'])).toBeUndefined()
  expect(queryClient.getQueryData(['manager', 'catalog', 'list'])).toBeUndefined()
})
