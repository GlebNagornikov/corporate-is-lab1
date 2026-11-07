import { queryOptions } from '@tanstack/react-query'
import { data, redirect } from 'react-router'
import {
  api, ApiError, csrfHeaders, requireData, restoreSession, setSessionExpiredHandler, toApiError, type Me,
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

function resetUserData(cancelProfile: boolean) {
  const profile = { queryKey: meQuery().queryKey }
  if (cancelProfile) void queryClient.cancelQueries(profile)
  queryClient.setQueryData(profile.queryKey, null)
  queryClient.removeQueries({ queryKey: cartQuery().queryKey })
  queryClient.removeQueries({ queryKey: priceChangesQuery().queryKey })
  queryClient.removeQueries({ queryKey: ['orders'] })
}

// При истечении токена запрос профиля сам завершится с null.
setSessionExpiredHandler(() => resetUserData(false))

function ensureSession(version: number) {
  if (tokens.version() !== version) throw new ApiError(401, 'Сессия изменилась. Войдите снова.')
}

export async function login(username: string, password: string) {
  const previousVersion = tokens.version()
  const result = await api.POST('/api/auth/session/login/', {
    headers: await csrfHeaders(), body: { username, password },
  })
  if (result.response.status === 401) {
    throw new ApiError(401, 'Неверное имя пользователя или пароль')
  }
  const pair = requireData(result)
  ensureSession(previousVersion)
  tokens.save(pair)
  const version = tokens.version()
  resetUserData(true)

  try {
    const me = requireData(await api.GET('/api/auth/me/'))
    ensureSession(version)
    const items = guestCart.items()
    if (items.length > 0) {
      // API принимает до 99 единиц в одной строке запроса.
      const lines = items.flatMap((item) => Array.from(
        { length: Math.ceil(item.quantity / 99) },
        (_, index) => ({
          product: item.product_id,
          variant: item.variant_id ?? undefined,
          quantity: Math.min(99, item.quantity - index * 99),
        }),
      ))
      const cart = requireData(await api.POST('/api/cart/merge/', { body: { items: lines } }))
      ensureSession(version)
      guestCart.removeTransferred(items)
      queryClient.setQueryData(cartQuery().queryKey, cart)
      queryClient.setQueryData(priceChangesQuery().queryKey, findPriceChanges(items, cart.items))
    }
    queryClient.setQueryData(meQuery().queryKey, me)
  } catch (error) {
    if (tokens.version() === version) await logout()
    throw error
  }
}

export async function register(body: { username: string; email: string; password: string }) {
  const { response, error } = await api.POST('/api/auth/register/', { body })
  if (!response.ok) throw toApiError(response, error)
  await login(body.username, body.password)
}

export async function logout() {
  const { response, error } = await api.POST('/api/auth/session/logout/', {
    headers: await csrfHeaders(),
  })
  if (!response.ok) throw toApiError(response, error)
  tokens.clear()
  resetUserData(true)
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
