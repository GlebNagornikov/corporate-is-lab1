import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { expect, test, vi } from 'vitest'
import type { Cart, Me } from '../api/client'
import { createAppRoutes } from '../appRoutes'
import { meQuery } from '../auth/session'
import { cartQuery } from '../cart/queries'
import { makeOrder } from '../test/fixtures'
import { server } from '../test/server'

test('оформление проверяет курьерский адрес, показывает ошибку промокода и открывает созданный заказ', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const me: Me = {
    id: 1, username: 'buyer', first_name: 'Анна', last_name: 'Смирнова',
    email: 'buyer@example.test', is_manager: false,
  }
  client.setQueryData(meQuery().queryKey, me)
  const cart: Cart = {
    items: [{
      product_id: 1, variant_id: null, variant_name: '', is_default_variant: true, name: 'Книга', slug: 'book',
      image: null, stock: 3, price: '990.00', quantity: 1, total: '990.00',
    }],
    count: 1,
    total: '990.00',
  }
  const checkout = vi.fn(async ({ request }: { request: Request }) => {
    const payload = await request.json()
    expect(payload).toMatchObject({
      full_name: 'Анна Смирнова', email: me.email, phone: '+7 913 123-45-67',
      address: 'Ленина, 1', delivery_method: 'courier',
    })
    return payload.promo_code
      ? HttpResponse.json({ detail: 'Промокод больше не действует.' }, { status: 400 })
      : HttpResponse.json(makeOrder(), { status: 201 })
  })
  server.use(
    http.get('*/api/cart/', () => HttpResponse.json(cart)),
    http.post('*/api/orders/', checkout),
  )
  const router = createMemoryRouter(createAppRoutes(client), { initialEntries: ['/checkout'] })
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )

  await user.type(await screen.findByLabelText('Телефон', {}, { timeout: 5000 }), '+7 913 123-45-67')
  await user.click(screen.getByLabelText('Курьер'))
  const submit = screen.getByRole('button', { name: 'Подтвердить заказ' })
  await user.click(submit)
  expect(await screen.findByText('Для доставки курьером укажите адрес')).toBeInTheDocument()
  expect(checkout).not.toHaveBeenCalled()

  await user.type(screen.getByLabelText('Адрес доставки'), 'Ленина, 1')
  await user.type(screen.getByLabelText('Промокод'), 'EXPIRED')
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent('Промокод больше не действует.')
  expect(client.getQueryData(cartQuery().queryKey)).toEqual(cart)

  await user.clear(screen.getByLabelText('Промокод'))
  await user.click(submit)
  expect(await screen.findByText('Заказ оформлен. Спасибо!')).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'Книга' })).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/orders/7')
  expect(client.getQueryData(cartQuery().queryKey)).toEqual({ items: [], count: 0, total: '0.00' })
})
