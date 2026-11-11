import { queryOptions } from '@tanstack/react-query'
import { api, requireData, type Product } from '../api/client'
import type { components } from '../api/schema'

export type Favorite = components['schemas']['WishlistEntry']

export function favoriteEntry(product: Product): Favorite {
  return {
    product_id: product.id,
    product__name: product.name,
    product__slug: product.slug,
    product__is_active: true,
  }
}

export const wishlistQuery = (userId?: number) => queryOptions({
  queryKey: ['personal', userId, 'wishlist'],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/wishlist/', { signal })),
  enabled: userId !== undefined,
  staleTime: 30_000,
})

export const restockQuery = (userId: number, id: number) => queryOptions({
  queryKey: ['personal', userId, 'restock', id],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/restock/{id}/', {
    params: { path: { id } }, signal,
  })),
})

export const notificationsQuery = (userId: number) => queryOptions({
  queryKey: ['personal', userId, 'notifications'],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/notifications/', { signal })),
  refetchOnWindowFocus: false,
})

export const unreadQuery = (userId: number) => queryOptions({
  queryKey: ['personal', userId, 'unread'],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/notifications/unread/', { signal })),
  refetchOnWindowFocus: false,
})
