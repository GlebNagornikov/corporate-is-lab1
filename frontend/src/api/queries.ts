import { keepPreviousData, queryOptions } from '@tanstack/react-query'
import type { ProductQuery } from '../lib/catalogParams'
import { api, toApiError } from './client'

function requireData<T>({
  data,
  error,
  response,
}: {
  data?: T
  error?: unknown
  response: Response
}): T {
  if (!response.ok || data === undefined) throw toApiError(response, error)
  return data
}

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
    placeholderData: keepPreviousData,
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
