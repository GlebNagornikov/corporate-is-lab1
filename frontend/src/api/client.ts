import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Category = components['schemas']['Category']
export type Product = components['schemas']['Product']
export type ProductPage = components['schemas']['PaginatedProductList']
export type Review = components['schemas']['Review']

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // MSW can replace fetch after this module is loaded.
  fetch: (request) => fetch(request),
})

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function toApiError(response: Response, body: unknown): ApiError {
  const detail =
    body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
      ? body.detail
      : `Сервер ответил ошибкой ${response.status}`

  return new ApiError(response.status, detail)
}
