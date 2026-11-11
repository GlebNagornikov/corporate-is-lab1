import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, requireData, type Cart, type Product, type Variant } from '../api/client'
import { tokens } from '../auth/tokens'
import { useCartSnapshot } from './useCartSnapshot'
import {
  guestCart, limitQuantity, matchesLine, summarizeCart, withQuantity,
} from './guestCart'
import { cartQuery } from './queries'

export { cartQuery } from './queries'

export type CartState = Cart & {
  isGuest: boolean
  isLoading: boolean
  isAdding: boolean
  add: (product: Product, variant?: Variant) => void
  setQuantity: (productId: number, quantity: number, variantId?: number | null) => void
  error: Error | null
}

type CartChange = { productId: number; variantId: number | null; version: number } & (
  { type: 'add' } | { type: 'quantity'; quantity: number }
)

const changeKey = (version: number) => ['cart', 'change', version]

export function useCart(): CartState {
  const client = useQueryClient()
  const snapshot = useCartSnapshot()
  const queryKey = cartQuery().queryKey
  const version = tokens.version()

  const change = useMutation({
    mutationKey: changeKey(version),
    scope: { id: `cart:${version}` },
    mutationFn: async (change: CartChange) => {
      if (change.version !== tokens.version()) throw new ApiError(401, 'Сессия завершена')
      const { productId, variantId } = change
      const variant = variantId ?? undefined
      if (change.type === 'add') {
        return requireData(await api.POST('/api/cart/items/', {
          body: { product: productId, variant, quantity: 1 },
        }))
      }
      return requireData(await api.PATCH('/api/cart/items/{product_id}/', {
        params: { path: { product_id: productId }, query: { variant } },
        body: { quantity: change.quantity },
      }))
    },
    onMutate: async (change) => {
      await client.cancelQueries({ queryKey })
      if (change.type !== 'quantity' || change.version !== tokens.version()) return
      const previous = client.getQueryData(queryKey)
      if (!previous) return
      const index = previous.items.findIndex((item) =>
        matchesLine(item, change.productId, change.variantId),
      )
      if (index === -1) return
      const item = previous.items[index]
      const quantity = limitQuantity(change.quantity, item.stock)
      if (quantity === item.quantity) return
      const items = quantity === 0
        ? previous.items.toSpliced(index, 1)
        : previous.items.with(index, withQuantity(item, quantity))
      const optimistic = client.setQueryData(queryKey, summarizeCart(items, previous.promo_code))
      return { previous, optimistic }
    },
    onError: (_error, change, context) => {
      if (change.version === tokens.version() && context &&
          client.getQueryData(queryKey) === context.optimistic) {
        client.setQueryData(queryKey, context.previous)
      }
    },
    onSuccess: (cart, change) => {
      if (change.version === tokens.version() &&
          client.isMutating({ mutationKey: changeKey(change.version) }) === 1) {
        client.setQueryData(queryKey, cart)
      }
    },
    onSettled: (_cart, _error, change) => {
      if (change.version === tokens.version() &&
          client.isMutating({ mutationKey: changeKey(change.version) }) === 1) {
        return client.invalidateQueries({ queryKey })
      }
    },
  })

  if (snapshot.isGuest) {
    return {
      ...snapshot.cart,
      isGuest: true,
      isLoading: false,
      isAdding: false,
      add: (product, variant) => guestCart.add(product, 1, variant),
      setQuantity: guestCart.setQuantity,
      error: null,
    }
  }

  return {
    ...snapshot.cart,
    isGuest: false,
    isLoading: snapshot.isLoading,
    isAdding: change.isPending && change.variables.version === version && change.variables.type === 'add',
    add: (product, variant) => change.mutate({
      type: 'add', productId: product.id, variantId: variant?.id ?? null, version,
    }),
    setQuantity: (productId, quantity, variantId) => {
      const matching = client.getQueryData(queryKey)?.items.filter((item) => item.product_id === productId)
      const variant = variantId === undefined && matching?.length === 1
        ? matching[0].variant_id
        : variantId ?? null
      change.mutate({
        type: 'quantity', productId, variantId: variant, quantity, version,
      })
    },
    error: (change.variables?.version === version ? change.error : null) ?? snapshot.error,
  }
}
