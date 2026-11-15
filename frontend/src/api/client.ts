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

const REFRESH_PATH = '/api/auth/session/refresh/'
const publicAuthPaths = new Set([
  '/api/auth/token/', '/api/auth/token/refresh/', '/api/auth/register/',
  '/api/auth/session/csrf/', '/api/auth/session/login/', REFRESH_PATH, '/api/auth/session/logout/',
])
let refreshing: { version: number; promise: Promise<void> } | undefined

export async function csrfHeaders() {
  const { csrf_token } = requireData(await sessionApi.GET('/api/auth/session/csrf/'))
  return { 'X-CSRFToken': csrf_token }
}

function tokenUser(access: string | null): string | undefined {
  try {
    const payload = access?.split('.')[1]
    if (!payload) return
    const claims: { user_id?: unknown } = JSON.parse(atob(payload.replaceAll('-', '+').replaceAll('_', '/')))
    if (typeof claims.user_id === 'string' || typeof claims.user_id === 'number') {
      return String(claims.user_id)
    }
  } catch {
    // Подпись и содержимое JWT проверяет сервер.
  }
}

async function refreshSession(version: number) {
  const result = await csrfHeaders()
    .then((headers) => sessionApi.POST(REFRESH_PATH, { headers }))
    .catch(() => undefined)

  if (tokens.version() !== version) return
  const previousUser = tokenUser(tokens.access())
  const access = result?.data?.access
  if (typeof access === 'string' && access && (!previousUser || previousUser === tokenUser(access))) {
    tokens.refreshAccess(access)
  } else if (tokens.access()) {
    tokens.clear()
    onSessionExpired()
  }
}

function refreshAccessToken(version: number) {
  if (refreshing?.version === version) return refreshing.promise
  const promise = refreshSession(version).finally(() => {
    if (refreshing?.promise === promise) refreshing = undefined
  })
  refreshing = { version, promise }
  return promise
}

export async function restoreSession() {
  if (!tokens.access()) await refreshAccessToken(tokens.version())
  return Boolean(tokens.access())
}

const pending = new Map<
  string,
  { original: Request; access: string; version: number }
>()

const authMiddleware: Middleware = {
  onRequest({ request, schemaPath, id }) {
    if (publicAuthPaths.has(schemaPath)) return
    const access = tokens.access()
    if (!access) return
    request.headers.set('Authorization', `Bearer ${access}`)
    pending.set(id, {
      original: request.clone(),
      access,
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

    const { original, access, version } = attempt
    const sameSession = () => tokens.version() === version
    // Запоздавший 401 может прийти после завершения общего обновления.
    if (sameSession() && tokens.access() === access) {
      await refreshAccessToken(version)
    }

    const currentAccess = tokens.access()
    if (currentAccess) {
      if (!sameSession()) return response
      original.headers.set('Authorization', `Bearer ${currentAccess}`)
    } else {
      original.headers.delete('Authorization')
      return options.fetch(new Request(original, { credentials: 'omit' }))
    }
    return options.fetch(original)
  },
}

const requestOptions = {
  // MSW can replace fetch after this module is loaded.
  fetch: (request: Request) => fetch(request),
  credentials: 'same-origin' as const,
}

export const sessionApi = createClient<paths>({ ...requestOptions, baseUrl: window.location.origin })
export const api = createClient<paths>({
  ...requestOptions,
  baseUrl: import.meta.env.DEV && import.meta.env.VITE_API_URL?.trim()
    ? new URL(import.meta.env.VITE_API_URL, window.location.origin).origin
    : window.location.origin,
})
api.use(authMiddleware)
