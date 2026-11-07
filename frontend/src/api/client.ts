import createClient, { type Middleware } from 'openapi-fetch'
import { tokens } from '../auth/tokens'
import type { components, paths } from './schema'

export type Category = components['schemas']['Category']
export type Product = components['schemas']['Product']
export type Variant = components['schemas']['Variant']
export type ProductPage = components['schemas']['PaginatedProductList']
export type Review = components['schemas']['Review']
export type Me = components['schemas']['Me']
export type Cart = components['schemas']['Cart']
export type CartItem = components['schemas']['CartItem']
export type Order = components['schemas']['Order']
export type OrderStatus = components['schemas']['OrderStatusEnum']
export type CheckoutRequest = components['schemas']['CheckoutRequest']

export class ApiError extends Error {
  readonly status: number
  readonly fields: Record<string, string[]>

  constructor(status: number, message: string, fields: Record<string, string[]> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fields = fields
  }
}

function errorMessages(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(errorMessages)
  if (value && typeof value === 'object') return Object.values(value).flatMap(errorMessages)
  return []
}

export function toApiError(response: Response, body: unknown): ApiError {
  const fallback = `Сервер ответил ошибкой ${response.status}`
  if (Array.isArray(body)) {
    return new ApiError(response.status, errorMessages(body).join(' ') || fallback)
  }
  if (body && typeof body === 'object') {
    const { detail, ...rest } = body as Record<string, unknown>
    const fields = Object.fromEntries(
      Object.entries(rest).map(([field, value]) => [field, errorMessages(value)]),
    )
    const message = errorMessages(detail).join(' ') || Object.values(fields).flat()[0] || fallback
    return new ApiError(response.status, message, fields)
  }
  return new ApiError(response.status, fallback)
}

export function requireData<T>({
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

let onSessionExpired: () => void = () => {}

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler
}

const REFRESH_PATH = '/api/auth/token/refresh/'
const publicAuthPaths = new Set(['/api/auth/token/', REFRESH_PATH, '/api/auth/register/'])
let refreshing: { version: number; promise: Promise<void> } | undefined

async function refreshSession(version: number, refresh: string | null) {
  const result = refresh
    ? await api.POST(REFRESH_PATH, { body: { refresh } }).catch(() => undefined)
    : undefined

  if (tokens.version() !== version || tokens.refresh() !== refresh) return
  const access = result?.data?.access
  if (typeof access === 'string' && access) {
    tokens.save({ access })
  } else {
    tokens.clear()
    onSessionExpired()
  }
}

function refreshAccessToken(version: number, refresh: string | null) {
  if (refreshing?.version === version) return refreshing.promise
  const promise = refreshSession(version, refresh).finally(() => {
    if (refreshing?.promise === promise) refreshing = undefined
  })
  refreshing = { version, promise }
  return promise
}

const pending = new Map<
  string,
  { original: Request; access: string | null; refresh: string | null; version: number }
>()

const authMiddleware: Middleware = {
  onRequest({ request, schemaPath, id }) {
    if (publicAuthPaths.has(schemaPath)) return
    const access = tokens.access()
    const refresh = tokens.refresh()
    if (!access && !refresh) return
    if (access) request.headers.set('Authorization', `Bearer ${access}`)
    pending.set(id, {
      original: request.clone(),
      access,
      refresh,
      version: tokens.version(),
    })
  },
  onError({ id }) {
    pending.delete(id)
  },
  async onResponse({ response, id, options }) {
    const attempt = pending.get(id)
    pending.delete(id)
    if (response.status !== 401 || !attempt) return response

    const { original, access, refresh, version } = attempt
    const sameSession = () => tokens.version() === version && tokens.refresh() === refresh
    // Запоздавший 401 может прийти после завершения общего обновления.
    if (sameSession() && tokens.access() === access) {
      await refreshAccessToken(version, refresh)
    }

    const currentAccess = tokens.access()
    if (currentAccess) {
      if (!sameSession()) return response
      original.headers.set('Authorization', `Bearer ${currentAccess}`)
    } else {
      original.headers.delete('Authorization')
    }
    return options.fetch(original)
  },
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // MSW can replace fetch after this module is loaded.
  fetch: (request) => fetch(request),
})
api.use(authMiddleware)
