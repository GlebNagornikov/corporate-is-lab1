import { queryOptions } from '@tanstack/react-query'
import { api, requireData } from '../api/client'

export const cartQuery = () =>
  queryOptions({
    queryKey: ['cart'],
    queryFn: async ({ signal }) => requireData(await api.GET('/api/cart/', { signal })),
  })
