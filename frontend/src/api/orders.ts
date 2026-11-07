import { keepPreviousData, queryOptions } from '@tanstack/react-query'
import { api, requireData, type OrderStatus } from './client'

export const ordersQuery = (params: { page?: number; status?: OrderStatus } = {}) =>
  queryOptions({
    queryKey: ['orders', 'list', params],
    queryFn: async ({ signal }) => requireData(await api.GET('/api/orders/', {
      params: { query: params },
      signal,
    })),
    placeholderData: keepPreviousData,
  })

export const orderQuery = (id: number) =>
  queryOptions({
    queryKey: ['orders', 'detail', id],
    queryFn: async ({ signal }) => requireData(await api.GET('/api/orders/{id}/', {
      params: { path: { id } },
      signal,
    })),
  })
