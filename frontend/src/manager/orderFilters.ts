import type { OrderStatus } from '../api/client'
import { statusLabels } from '../lib/statuses'

export const statuses = Object.keys(statusLabels) as OrderStatus[]

export function orderFilters(search: URLSearchParams) {
  const status = statuses.find((status) => status === search.get('status'))
  const page = Number(search.get('page'))
  return { status, page: Number.isSafeInteger(page) && page > 0 ? page : 1 }
}
