import type { OrderStatus } from '../api/client'
import { readOrderPage } from '../api/orders'
import { statusLabels } from '../lib/statuses'

export const statuses = Object.keys(statusLabels) as OrderStatus[]

export function orderFilters(search: URLSearchParams) {
  const status = statuses.find((status) => status === search.get('status'))
  return { status, page: readOrderPage(search) }
}
