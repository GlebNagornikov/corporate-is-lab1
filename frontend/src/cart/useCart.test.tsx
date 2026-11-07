import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { afterEach, expect, test } from 'vitest'
import type { Cart, Me } from '../api/client'
import { meQuery } from '../auth/session'
import { makeProduct } from '../test/fixtures'
import { server } from '../test/server'
import { guestCart } from './guestCart'
import { cartQuery, useCart } from './useCart'

afterEach(() => guestCart.clear())

function wrapperFor(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

test('гостевая корзина обновляет подписчиков и считает сумму по цене добавления', () => {
  const client = new QueryClient()
  const { result } = renderHook(useCart, { wrapper: wrapperFor(client) })
  const product = makeProduct({ stock: 2, price: '12.50' })
  expect(guestCart.items()).toBe(guestCart.items())

  act(() => result.current.add(product))
  act(() => result.current.add({ ...product, price: '20.00' }))
  act(() => result.current.add(product))
  expect(result.current).toMatchObject({ isGuest: true, count: 2, total: '25.00' })
  expect(JSON.parse(localStorage.getItem('shop-guest-cart') ?? '[]')).toEqual(result.current.items)

  act(() => result.current.setQuantity(product.id, 0))
  expect(result.current).toMatchObject({ items: [], count: 0, total: '0.00' })
})

test.each([0, 2])('показывает количество %i сразу и откатывает ошибку сервера', async (quantity) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const cart: Cart = {
    items: [{
      product_id: 1, variant_id: 10, variant_name: 'Стандартный', is_default_variant: true,
      name: 'Книга', slug: 'book', image: null, stock: 3,
      price: '12.50', quantity: 1, total: '12.50',
    }],
    count: 1,
    total: '12.50',
  }
  const buyer: Me = {
    id: 1, username: 'buyer', email: '', first_name: '', last_name: '', is_manager: false,
  }
  client.setQueryData(meQuery().queryKey, buyer)
  client.setQueryData(cartQuery().queryKey, cart)
  let releasePatch!: () => void
  const patchGate = new Promise<void>((resolve) => { releasePatch = resolve })
  let releaseRefetch!: () => void
  const refetchGate = new Promise<void>((resolve) => { releaseRefetch = resolve })
  let refetches = 0
  server.use(
    http.patch('*/api/cart/items/1/', async ({ request }) => {
      expect(new URL(request.url).searchParams.get('variant')).toBe('10')
      expect(await request.json()).toEqual({ quantity })
      await patchGate
      return HttpResponse.json({ detail: 'Ошибка обновления' }, { status: 400 })
    }),
    http.get('*/api/cart/', async () => {
      refetches += 1
      await refetchGate
      return HttpResponse.json(cart)
    }),
  )
  const { result } = renderHook(useCart, { wrapper: wrapperFor(client) })

  try {
    act(() => result.current.setQuantity(1, quantity))
    const total = quantity === 0 ? '0.00' : '25.00'
    await waitFor(() => expect(result.current).toMatchObject({ count: quantity, total }))
    if (quantity === 0) expect(result.current.items).toEqual([])
    else expect(result.current.items[0].total).toBe(total)

    releasePatch()
    await waitFor(() => expect(refetches).toBe(1))
    expect(client.getQueryData(cartQuery().queryKey)).toEqual(cart)
  } finally {
    releasePatch()
    releaseRefetch()
  }
  await waitFor(() => expect(result.current.error?.message).toBe('Ошибка обновления'))
})
