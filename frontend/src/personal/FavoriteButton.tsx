import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router'
import { api, toApiError } from '../api/client'
import { loginPath } from '../auth/session'
import { tokens } from '../auth/tokens'
import { useSession } from '../auth/useSession'
import StoreIcon from '../components/StoreIcon'
import { type Favorite, wishlistQuery } from './queries'

export default function FavoriteButton({ entry }: { entry: Favorite }) {
  const { data: me } = useSession()
  const location = useLocation()
  return me
    ? <FavoriteToggle key={`${me.id}:${entry.product_id}`} userId={me.id} entry={entry} />
    : <Link className="favorite-button" to={loginPath(location)} aria-label={`В избранное: ${entry.product__name}`}>
      <StoreIcon name="heart" />В избранное
    </Link>
}

function FavoriteToggle({ userId, entry }: { userId: number; entry: Favorite }) {
  const client = useQueryClient()
  const options = wishlistQuery(userId)
  const wishlist = useQuery(options)
  const productId = entry.product_id
  const mutationKey = ['wishlist-change', userId, productId]
  const latest = useMutationState({
    filters: { mutationKey, exact: true },
    select: ({ state }) => state,
  }).at(-1)
  const current = (latest?.variables as { enabled: boolean; version: number } | undefined)
  const sameSession = current?.version === tokens.version()
  const pending = sameSession && latest?.status === 'pending' ? current?.enabled : undefined
  const error = sameSession && latest?.error instanceof Error ? latest.error : null
  const mutation = useMutation({
    mutationKey,
    mutationFn: async ({ enabled, version }: { enabled: boolean; version: number }) => {
      if (version !== tokens.version()) return
      const result = enabled
        ? await api.POST('/api/wishlist/', { body: { product: productId } })
        : await api.DELETE('/api/wishlist/{id}/', { params: { path: { id: productId } } })
      if (!result.response.ok) throw toApiError(result.response, result.error)
    },
    onMutate: () => client.cancelQueries({ queryKey: options.queryKey }),
    onSuccess: (_, { enabled, version }) => {
      if (tokens.version() !== version) return
      client.setQueryData(options.queryKey, (current) => {
        const others = (current ?? []).filter((item) => item.product_id !== productId)
        return enabled ? [...others, entry] : others
      })
    },
    onSettled: (_, __, { version }) => {
      if (tokens.version() === version && client.isMutating({ mutationKey: ['wishlist-change', userId] }) === 1) {
        void client.invalidateQueries({ queryKey: options.queryKey })
      }
    },
  })
  const favorite = pending ?? Boolean(wishlist.data?.some((item) => item.product_id === productId))
  return (
    <div className="favorite-control">
      <button
        className="secondary favorite-button"
        type="button"
        aria-label={`Избранное: ${entry.product__name}`}
        aria-pressed={favorite}
        disabled={pending !== undefined || !wishlist.data}
        onClick={() => mutation.mutate({ enabled: !favorite, version: tokens.version() })}
      >
        <StoreIcon name="heart" />{favorite ? 'В избранном' : 'В избранное'}
      </button>
      {error && <p className="error" role="alert">Не удалось изменить избранное. {error.message}</p>}
      {wishlist.isError && !wishlist.data && (
        <button className="secondary" type="button" onClick={() => void wishlist.refetch()}>Повторить загрузку избранного</button>
      )}
    </div>
  )
}
