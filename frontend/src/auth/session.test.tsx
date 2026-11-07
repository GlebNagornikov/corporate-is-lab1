import { QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { afterEach, expect, test, vi } from 'vitest'
import { createAppRoutes } from '../appRoutes'
import { guestCart } from '../cart/guestCart'
import { cartQuery } from '../cart/queries'
import { queryClient } from '../queryClient'
import { makeProduct } from '../test/fixtures'
import { server } from '../test/server'
import { login, logout, meQuery, register } from './session'
import { tokens } from './tokens'

const buyer = {
  id: 1, username: 'buyer', email: 'buyer@example.test',
  first_name: '', last_name: '', is_manager: false,
}
const emptyCart = { items: [], count: 0, total: '0.00' }

afterEach(() => {
  cleanup()
  logout()
  guestCart.clear()
  queryClient.clear()
})

function mockLogin() {
  server.use(
    http.post('*/api/auth/token/', () => HttpResponse.json({ access: 'a', refresh: 'r' })),
    http.get('*/api/auth/me/', () => HttpResponse.json(buyer)),
    http.get('*/api/cart/', () => HttpResponse.json(emptyCart)),
  )
}

test('регистрация входит в аккаунт и переносит варианты, разбивая количество по лимиту API', async () => {
  mockLogin()
  const merge = vi.fn(async ({ request }: { request: Request }) => {
    expect(request.headers.get('Authorization')).toBe('Bearer a')
    expect(await request.json()).toEqual({ items: [
      { product: 7, variant: 3, quantity: 99 },
      { product: 7, variant: 3, quantity: 2 },
    ] })
    return HttpResponse.json(emptyCart)
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
  expect(queryClient.getQueryData(cartQuery().queryKey)).toEqual(emptyCart)
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

  expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument()
  expect(router.state.location.search).toBe('?next=%2Forders%2F7%3Ffrom%3Dcart')
  expect(order).not.toHaveBeenCalled()
})

test('запрещает покупателю раздел менеджера', async () => {
  mockLogin()
  tokens.save({ access: 'a', refresh: 'r' })
  renderApp('/manager/orders')
  expect(await screen.findByRole('heading', { name: 'Нет доступа' })).toBeInTheDocument()
})

test('открывает ленивый маршрут заказов для менеджера', async () => {
  tokens.save({ access: 'a', refresh: 'r' })
  server.use(
    http.get('*/api/auth/me/', () => HttpResponse.json({ ...buyer, is_manager: true })),
    http.get('*/api/cart/', () => HttpResponse.json(emptyCart)),
    http.get('*/api/orders/', () => HttpResponse.json({ count: 0, results: [] })),
  )
  renderApp('/manager/orders')
  expect(await screen.findByRole('heading', { name: 'Заказы магазина' })).toBeInTheDocument()
})

test('истёкшая сессия очищает приватный кэш и открывает экран входа', async () => {
  tokens.save({ access: 'expired', refresh: 'expired' })
  queryClient.setQueryData(cartQuery().queryKey, emptyCart)
  queryClient.setQueryData(['orders', 'list'], { results: [] })
  const invalid = () => HttpResponse.json({ detail: 'Токен недействителен' }, { status: 401 })
  server.use(
    http.get('*/api/auth/me/', invalid),
    http.post('*/api/auth/token/refresh/', invalid),
  )

  renderApp('/checkout')
  expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument()
  expect(tokens.access()).toBeNull()
  expect(queryClient.getQueryData(cartQuery().queryKey)).toBeUndefined()
  expect(queryClient.getQueryData(['orders', 'list'])).toBeUndefined()
})
