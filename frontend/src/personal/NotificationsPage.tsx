import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api, toApiError } from '../api/client'
import { tokens } from '../auth/tokens'
import { useSession } from '../auth/useSession'
import { formatDate } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import { notificationsQuery, unreadQuery } from './queries'

export default function NotificationsPage() {
  const { data: me } = useSession()
  usePageTitle('Уведомления')
  return me && <Notifications key={me.id} userId={me.id} />
}

function Notifications({ userId }: { userId: number }) {
  const client = useQueryClient()
  const options = notificationsQuery(userId)
  const { data, isPending, isError, refetch } = useQuery(options)
  const change = useMutation({
    mutationFn: async ({ version, id }: { version: number; id?: number }) => {
      if (version !== tokens.version()) return
      const result = id === undefined
        ? await api.POST('/api/notifications/unread/')
        : await api.DELETE('/api/notifications/{id}/', { params: { path: { id } } })
      if (!result.response.ok) throw toApiError(result.response, result.error)
      if (tokens.version() === version) {
        await Promise.all([
          client.invalidateQueries({ queryKey: options.queryKey }),
          client.invalidateQueries({ queryKey: unreadQuery(userId).queryKey }),
        ])
      }
    },
  })
  return (
    <section className="personal-page">
      <h1>Уведомления</h1>
      {data?.some((item) => item.read_at === null) && (
        <button className="secondary" type="button" disabled={change.isPending}
          onClick={() => change.mutate({ version: tokens.version() })}>Прочитать всё</button>
      )}
      {change.error && <p className="error" role="alert">
        {change.variables?.id === undefined ? 'Не удалось прочитать уведомления.' : 'Не удалось удалить уведомление.'}
        {' '}{change.error.message}
      </p>}
      {isPending && <p role="status">Загружаем уведомления…</p>}
      {isError && <p className="error" role="alert">Не удалось загрузить уведомления.{' '}
        <button className="secondary" type="button" onClick={() => void refetch()}>Повторить</button>
      </p>}
      {data?.length === 0 && <p>Здесь появятся сообщения о поступлении книг, на которые вы подписались.</p>}
      {Boolean(data?.length) && <ul className="personal-list">
        {data?.map((item) => (
          <li key={item.id}>
            <div>
              <p>Книга снова в наличии</p>
              {item.product_is_active
                ? <Link to={`/products/${encodeURIComponent(item.product_slug)}`}>{item.product_name}</Link>
                : <strong>{item.product_name}</strong>}
            </div>
            <div className="notification-meta">
              {item.read_at === null && <span className="badge">Новое</span>}
              <time className="muted" dateTime={item.notified_at}>{formatDate(item.notified_at)}</time>
              <button className="secondary" type="button" disabled={change.isPending}
                aria-label={`Удалить уведомление: ${item.product_name}`}
                onClick={() => change.mutate({ version: tokens.version(), id: item.id })}>
                {change.isPending && change.variables?.id === item.id ? 'Удаляем…' : 'Удалить'}
              </button>
            </div>
          </li>
        ))}
      </ul>}
    </section>
  )
}
