import { queryOptions } from '@tanstack/react-query'
import { data, redirect } from 'react-router'
import {
  api, ApiError, csrfHeaders, requireData, restoreSession, sessionApi, setSessionExpiredHandler, toApiError, type Me,
} from '../api/client'
import { guestCart } from '../cart/guestCart'
import { findPriceChanges, priceChangesQuery } from '../cart/priceChanges'
import { cartQuery } from '../cart/queries'
import { queryClient } from '../queryClient'
import { tokens } from './tokens'

export const meQuery = () =>
  queryOptions({
    queryKey: ['me'],
    queryFn: async ({ signal }): Promise<Me | null> => {
      if (!await restoreSession()) return null
      const version = tokens.version()
      const result = await api.GET('/api/auth/me/', { signal })
      return result.response.status === 401 || version !== tokens.version() ? null : requireData(result)
    },
    staleTime: Infinity,
  })

function resetUserData(cancelProfile: boolean, client = queryClient) {
  const profile = { queryKey: meQuery().queryKey }
  if (cancelProfile) void client.cancelQueries(profile)
  client.setQueryData(profile.queryKey, null)
  client.removeQueries({ queryKey: cartQuery().queryKey })
  client.removeQueries({ queryKey: priceChangesQuery().queryKey })
  client.removeQueries({ queryKey: ['orders'] })
  client.removeQueries({ queryKey: ['manager'] })
  client.removeQueries({ queryKey: ['review-eligibility'] })
  client.removeQueries({ queryKey: ['personal'] })
}

// При истечении токена запрос профиля сам завершится с null.
setSessionExpiredHandler(() => resetUserData(false))

function ensureSession(version: number) {
  if (tokens.version() !== version) throw new ApiError(401, 'Сессия изменилась. Войдите снова.')
}

export async function login(username: string, password: string, client = queryClient) {
  const previousVersion = tokens.version()
  const result = await sessionApi.POST('/api/auth/session/login/', {
    headers: await csrfHeaders(), body: { username, password },
  })
  if (result.response.status === 401) {
    throw new ApiError(401, 'Неверное имя пользователя или пароль')
  }
  const pair = requireData(result)
  ensureSession(previousVersion)
  tokens.save(pair)
  const version = tokens.version()
  resetUserData(true, client)

  try {
    const me = requireData(await api.GET('/api/auth/me/'))
    ensureSession(version)
    const items = guestCart.items()
    const promoCode = guestCart.promoCode()
    if (items.length > 0 || promoCode) {
      const lines = items.map((item) => ({
        product: item.product_id,
        variant: item.variant_id ?? undefined,
        quantity: item.quantity,
      }))
      const cart = requireData(await api.POST('/api/cart/merge/', {
        body: { items: lines, ...(promoCode ? { promo_code: promoCode } : {}) },
      }))
      ensureSession(version)
      guestCart.removeTransferred(items, promoCode)
      client.setQueryData(cartQuery().queryKey, cart)
      client.setQueryData(priceChangesQuery().queryKey, findPriceChanges(items, cart.items))
    }
    client.setQueryData(meQuery().queryKey, me)
  } catch (error) {
    if (tokens.version() === version) await logout(client)
    throw error
  }
}

export async function register(body: { username: string; email: string; password: string }, client = queryClient) {
  const { response, error } = await api.POST('/api/auth/register/', { body })
  if (!response.ok) throw toApiError(response, error)
  await login(body.username, body.password, client)
}

export async function logout(client = queryClient) {
  const { response, error } = await sessionApi.POST('/api/auth/session/logout/', {
    headers: await csrfHeaders(),
  })
  if (!response.ok) throw toApiError(response, error)
  tokens.clear()
  resetUserData(true, client)
}

export function loginPath({ pathname, search }: Pick<URL, 'pathname' | 'search'>) {
  return `/login?next=${encodeURIComponent(pathname + search)}`
}

export async function requireUser(request: Request, client = queryClient): Promise<Me> {
  const me = await client.ensureQueryData(meQuery())
  if (!me) throw redirect(loginPath(new URL(request.url)))
  return me
}

export async function requireManager(request: Request, client = queryClient): Promise<Me> {
  const me = await requireUser(request, client)
  if (!me.is_manager) throw data('Раздел только для менеджеров магазина', { status: 403 })
  return me
}
