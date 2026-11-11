import { keepPreviousData, queryOptions, type QueryClient } from '@tanstack/react-query'
import { api, requireData } from '../api/client'
import { readOrderPage } from '../api/orders'
import type { components } from '../api/schema'
import { orderFilters } from './orderFilters'

export type ManagerBook = components['schemas']['ManagerBook']

export async function refreshCatalog(client: QueryClient) {
  await Promise.all([
    client.invalidateQueries({ queryKey: ['manager', 'catalog', 'list'] }),
    client.invalidateQueries({ queryKey: ['products'] }),
    client.invalidateQueries({ queryKey: ['categories'] }),
    client.invalidateQueries({ queryKey: ['cart'] }),
  ])
}

export function catalogFilters(search: URLSearchParams) {
  return { page: readOrderPage(search), q: search.get('q')?.trim() || undefined }
}

export const managerBooksQuery = (query: ReturnType<typeof catalogFilters>) => queryOptions({
  queryKey: ['manager', 'catalog', 'list', query],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/catalog/', {
    params: { query }, signal,
  })),
  placeholderData: keepPreviousData,
})

export const managerBookQuery = (id: number) => queryOptions({
  queryKey: ['manager', 'catalog', 'detail', id],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/catalog/{id}/', {
    params: { path: { id } }, signal,
  })),
})

export const managerCategoriesQuery = () => queryOptions({
  queryKey: ['manager', 'categories'],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/categories/', { signal })),
})

export const managerReviewsQuery = () => queryOptions({
  queryKey: ['manager', 'reviews'],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/reviews/', { signal })),
})

export const managerOrdersQuery = (query: ReturnType<typeof orderFilters>) => queryOptions({
  queryKey: ['manager', 'orders', 'list', query],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/orders/', {
    params: { query }, signal,
  })),
  placeholderData: keepPreviousData,
})

export const managerOrderQuery = (id: number) => queryOptions({
  queryKey: ['manager', 'orders', 'detail', id],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/orders/{id}/', {
    params: { path: { id } }, signal,
  })),
})

export const managerPromosQuery = (page: number) => queryOptions({
  queryKey: ['manager', 'promos', page],
  queryFn: async ({ signal }) => requireData(await api.GET('/api/manager/promos/', {
    params: { query: { page } }, signal,
  })),
})
