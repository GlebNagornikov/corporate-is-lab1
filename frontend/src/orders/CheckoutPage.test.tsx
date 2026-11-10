import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { expect, test, vi } from 'vitest'
import type { Cart, CartItem, Me } from '../api/client'
import { createAppRoutes } from '../appRoutes'
import { meQuery } from '../auth/session'
import { cartQuery } from '../cart/queries'
import { makeOrder } from '../test/fixtures'
import { server } from '../test/server'

const me: Me = {
  id: 1, username: 'buyer', first_name: 'Анна', last_name: 'Смирнова',
  email: 'buyer@example.test', is_manager: false,
}
const book: CartItem = {
  product_id: 1, variant_id: null, variant_name: '', is_default_variant: true, name: 'Книга', slug: 'book',
  image: null, stock: 8, price: '990.00', quantity: 1, total: '990.00',
}

function renderStore(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(meQuery().queryKey, me)
  const router = createMemoryRouter(createAppRoutes(client), { initialEntries: [path] })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { client, router, user: userEvent.setup() }
}

test('оформление показывает ошибки DRF, сохраняет поля и открывает созданный заказ после повтора', async () => {
  const cart: Cart = { items: [{ ...book, quantity: 2, total: '1980.00' }], count: 2, total: '1980.00' }
  let attempts = 0
  const checkout = vi.fn(async ({ request }: { request: Request }) => {
    attempts += 1
    const payload = await request.json()
    expect(payload).toMatchObject({
      full_name: 'Анна Смирнова', email: me.email, phone: '+7 913 123-45-67',
      address: 'Ленина, 1', delivery_method: 'courier', comment: 'Позвонить заранее',
    })
    if (payload.promo_code === 'EXPIRED') {
      return HttpResponse.json({ detail: 'Промокод больше не действует.' }, { status: 400 })
    }
    if (payload.promo_code === 'LONG') {
      return HttpResponse.json({ promo_code: ['Проверьте код.'] }, { status: 400 })
    }
    return attempts === 3
      ? HttpResponse.json({ detail: 'Товара «Книга» осталось только 1 шт.' }, { status: 400 })
      : HttpResponse.json(makeOrder(), { status: 201 })
  })
  server.use(
    http.get('*/api/cart/', () => HttpResponse.json(cart)),
    http.post('*/api/orders/', checkout),
  )
  const { client, router, user } = renderStore('/checkout')

  await user.type(await screen.findByLabelText('Телефон', {}, { timeout: 5000 }), '+7 913 123-45-67')
  await user.click(screen.getByLabelText('Курьер'))
  const submit = screen.getByRole('button', { name: 'Подтвердить заказ' })
  await user.click(submit)
  expect(await screen.findByText('Для доставки курьером укажите адрес')).toBeInTheDocument()
  expect(checkout).not.toHaveBeenCalled()

  await user.type(screen.getByLabelText('Адрес доставки'), 'Ленина, 1')
  await user.type(screen.getByLabelText('Комментарий'), 'Позвонить заранее')
  const promo = screen.getByLabelText('Промокод')
  await user.type(promo, 'EXPIRED')
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent('Промокод больше не действует.')
  expect(client.getQueryData(cartQuery().queryKey)).toEqual(cart)
  expect(promo).toHaveValue('EXPIRED')

  await user.clear(promo)
  await user.type(promo, 'LONG')
  await user.click(submit)
  expect(await screen.findByText('Проверьте код.')).toBeInTheDocument()
  expect(promo).toHaveAccessibleDescription('Проверьте код.')
  expect(promo).toHaveValue('LONG')

  await user.clear(promo)
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent('Товара «Книга» осталось только 1 шт.')
  expect(screen.getByLabelText('Телефон')).toHaveValue('+7 913 123-45-67')
  expect(screen.getByLabelText('Курьер')).toBeChecked()
  expect(screen.getByLabelText('Адрес доставки')).toHaveValue('Ленина, 1')
  expect(screen.getByLabelText('Комментарий')).toHaveValue('Позвонить заранее')
  expect(client.getQueryData(cartQuery().queryKey)).toEqual(cart)

  await user.click(submit)
  expect(await screen.findByText('Заказ оформлен. Спасибо!')).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'Книга' })).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/orders/7')
  expect(client.getQueryData(cartQuery().queryKey)).toEqual({ items: [], count: 0, total: '0.00' })
})

test('корзина и оформление суммируют варианты одного издания и разрешают заказ ровно пяти экземпляров', async () => {
  const first = { ...book, variant_id: 1, variant_name: 'Вариант А', is_default_variant: false, quantity: 3, total: '2970.00' }
  const second = { ...first, variant_id: 2, variant_name: 'Вариант Б' }
  // Издание с тем же названием и другим ID учитывается отдельно.
  const other = { ...book, product_id: 2, slug: 'another-edition' }
  let cart: Cart = { items: [first, second, other], count: 7, total: '6930.00' }
  const checkout = vi.fn(() => HttpResponse.json(makeOrder(), { status: 201 }))
  server.use(
    http.get('*/api/cart/', () => HttpResponse.json(cart)),
    http.patch('*/api/cart/items/1/', () => {
      cart = { items: [first, { ...second, quantity: 2, total: '1980.00' }, other], count: 6, total: '5940.00' }
      return HttpResponse.json(cart)
    }),
    http.post('*/api/orders/', checkout),
  )
  const { user } = renderStore('/checkout')
  const limitError = '«Книга»: в корзине 6. Уберите 1 экз.'
  expect(await screen.findByText(limitError)).toBeInTheDocument()
  const submit = screen.getByRole('button', { name: 'Подтвердить заказ' })
  expect(submit).toBeDisabled()
  await user.click(submit)
  expect(checkout).not.toHaveBeenCalled()

  await user.click(screen.getByRole('link', { name: 'Вернуться в корзину' }))
  expect(await screen.findByText(limitError)).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Оформить заказ' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Убрать одну штуку: Книга, Вариант Б' }))
  await user.click(await screen.findByRole('link', { name: 'Оформить заказ' }))
  const allowed = await screen.findByRole('button', { name: 'Подтвердить заказ' })
  expect(allowed).toBeEnabled()
  expect(allowed).toHaveAccessibleDescription(/до 5 экземпляров каждого издания/)
  await user.type(screen.getByLabelText('Телефон'), '+7 913 123-45-67')
  await user.click(allowed)
  expect(await screen.findByText('Заказ оформлен. Спасибо!')).toBeInTheDocument()
  expect(checkout).toHaveBeenCalledTimes(1)
})
