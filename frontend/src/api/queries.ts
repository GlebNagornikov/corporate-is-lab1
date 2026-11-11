import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query'
import type { ProductQuery } from '../lib/catalogParams'
import { api, requireData } from './client'

const STOCK_REFRESH_INTERVAL = 10_000

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
