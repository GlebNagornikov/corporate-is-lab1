import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router'
import { api, requireData } from '../api/client'
import { loginPath } from '../auth/session'
import { tokens } from '../auth/tokens'
import { useSession } from '../auth/useSession'
import StoreIcon from '../components/StoreIcon'
import { restockQuery } from './queries'

export default function RestockButton({ productId }: { productId: number }) {
  const { data: me } = useSession()
  const location = useLocation()
  return me
    ? <RestockSubscription key={`${me.id}:${productId}`} userId={me.id} productId={productId} />
    : <Link className="favorite-button" to={loginPath(location)}><StoreIcon name="bell" />Сообщить о поступлении</Link>
}

function RestockSubscription({ productId, userId }: { productId: number; userId: number }) {
  const client = useQueryClient()
  const options = restockQuery(userId, productId)
  const subscription = useQuery(options)
  const subscribe = useMutation({
    mutationFn: async (version: number) => {
      await client.cancelQueries({ queryKey: options.queryKey })
      if (version !== tokens.version()) return
      const result = requireData(await api.POST('/api/restock/{id}/', { params: { path: { id: productId } } }))
      if (version === tokens.version()) client.setQueryData(options.queryKey, result)
    },
  })
  return (
    <div>
      {subscription.data?.subscribed
        ? <p className="muted" role="status">Сообщим, когда книга появится в наличии.</p>
        : <button className="secondary favorite-button" type="button" disabled={subscribe.isPending}
          onClick={() => subscribe.mutate(tokens.version())}>
          <StoreIcon name="bell" />{subscribe.isPending ? 'Подписываемся…' : 'Сообщить о поступлении'}
        </button>}
      {subscribe.error && <p className="error" role="alert">{subscribe.error.message}</p>}
    </div>
  )
}
