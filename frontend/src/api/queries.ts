import { queryOptions } from '@tanstack/react-query'
import type { ProductQuery } from '../lib/catalogParams'
import { api, requireData } from './client'

export const categoriesQuery = () =>
  queryOptions({
    queryKey: ['categories'],
    queryFn: async ({ signal }) => requireData(await api.GET('/api/catalog/categories/', { signal })),
    staleTime: 10 * 60_000,
  })

export const productsQuery = (query: ProductQuery) =>
  queryOptions({
    queryKey: ['products', 'list', query],
    queryFn: async ({ signal }) =>
      requireData(
        await api.GET('/api/catalog/products/', {
          params: { query },
          // Django's OrderingFilter reads a comma-separated value.
          querySerializer: { array: { style: 'form', explode: false } },
          signal,
        }),
      ),
  })

export const productQuery = (slug: string) =>
  queryOptions({
    queryKey: ['products', 'detail', slug],
    queryFn: async ({ signal }) =>
      requireData(
        await api.GET('/api/catalog/products/{slug}/', {
          params: { path: { slug } },
          signal,
        }),
      ),
  })

export const reviewsQuery = (slug: string) =>
  queryOptions({
    queryKey: ['products', 'detail', slug, 'reviews'],
    queryFn: async ({ signal }) =>
      requireData(
        await api.GET('/api/catalog/products/{slug}/reviews/', {
          params: { path: { slug } },
          signal,
        }),
      ),
  })
