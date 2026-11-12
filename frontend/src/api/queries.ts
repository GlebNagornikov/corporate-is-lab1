import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query'
import type { ProductQuery } from '../lib/catalogParams'
import { api, ApiError, requireData } from './client'

const STOCK_REFRESH_INTERVAL = 10_000
const CATALOG_REQUEST_TIMEOUT = 8_000

export const categoriesQuery = () =>
  queryOptions({
    queryKey: ['categories'],
    queryFn: async ({ signal }) => requireData(await api.GET('/api/catalog/categories/', { signal })),
    staleTime: 10 * 60_000,
  })

export const productsQuery = (query: ProductQuery) =>
  queryOptions({
    queryKey: ['products', 'list', query],
    refetchInterval: STOCK_REFRESH_INTERVAL,
    queryFn: async ({ signal }) => {
      const timeout = AbortSignal.timeout(CATALOG_REQUEST_TIMEOUT)
      try {
        return requireData(await api.GET('/api/catalog/products/', {
          params: { query },
          // Django's OrderingFilter reads a comma-separated value.
          querySerializer: { array: { style: 'form', explode: false } },
          signal: AbortSignal.any([signal, timeout]),
        }))
      } catch (error) {
        if (!signal.aborted && timeout.aborted) {
          throw new ApiError(504, 'Сервер магазина не ответил вовремя.')
        }
        throw error
      }
    },
  })

export const editorialQuery = () => queryOptions({
  queryKey: ['products', 'editorial'],
    refetchInterval: STOCK_REFRESH_INTERVAL,
  queryFn: async ({ signal }) => requireData(await api.GET('/api/catalog/editorial/', { signal })),
})

export const productQuery = (slug: string) =>
  queryOptions({
    queryKey: ['products', 'detail', slug],
    refetchInterval: STOCK_REFRESH_INTERVAL,
    refetchOnWindowFocus: 'always',
    queryFn: async ({ signal }) =>
      requireData(
        await api.GET('/api/catalog/products/{slug}/', {
          params: { path: { slug } },
          signal,
        }),
      ),
  })

export const reviewsQuery = (slug: string) =>
  infiniteQueryOptions({
    queryKey: ['products', 'detail', slug, 'reviews'],
    staleTime: 0,
    initialPageParam: 1,
    queryFn: async ({ pageParam, signal }) =>
      requireData(
        await api.GET('/api/catalog/products/{slug}/reviews/', {
          params: { path: { slug }, query: { page: pageParam } },
          signal,
        }),
      ),
    getNextPageParam: (lastPage, _, lastPageParam) => lastPage.next ? lastPageParam + 1 : undefined,
  })

export const reviewEligibilityQuery = (slug: string, buyerId: number | undefined) =>
  queryOptions({
    queryKey: ['review-eligibility', buyerId, slug],
    enabled: buyerId !== undefined,
    staleTime: 0,
    queryFn: async ({ signal }) =>
      requireData(
        await api.GET('/api/catalog/products/{slug}/review-eligibility/', {
          params: { path: { slug } },
          signal,
        }),
      ),
  })
