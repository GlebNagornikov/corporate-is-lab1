import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { api, requireData, type Order, type OrderStatus } from '../api/client'
import { orderQuery, ordersQuery } from '../api/orders'
import { tokens } from '../auth/tokens'
import { formatDate, formatPrice } from '../lib/format'
import { statusLabels, transitionLabels } from '../lib/statuses'
import { orderFilters, statuses } from './orderFilters'

function OrderRow({ order, stale }: { order: Order; stale: boolean }) {
  const client = useQueryClient()
  const change = useMutation({
    mutationFn: async ({ status, comment }: { status: OrderStatus; comment: string; version: number }) =>
      requireData(await api.POST('/api/orders/{id}/status/', {
        params: { path: { id: order.id } },
        body: { status, comment },
      })),
    onSuccess: (updated, { version }) => {
      if (version !== tokens.version()) return
      client.setQueryData(orderQuery(order.id).queryKey, updated)
      return client.invalidateQueries({ queryKey: ['orders', 'list'] })
    },
  })

  function changeStatus(status: OrderStatus) {
    const comment = status === 'cancelled' ? window.prompt('Причина отмены') : ''
    if (comment !== null) change.mutate({ status, comment: comment.trim(), version: tokens.version() })
  }

  return (
    <tr>
      <th scope="row"><Link to={`/orders/${order.id}`}>№{order.id}</Link></th>
      <td>{formatDate(order.created_at)}</td>
      <td>{order.full_name}</td>
      <td>{formatPrice(order.total)}</td>
      <td>{order.status_display}</td>
      <td>
        <div className="actions">
          {[...order.allowed_transitions].sort((a, b) => Number(a === 'cancelled') - Number(b === 'cancelled')).map((status) => (
            <button type="button" key={status} disabled={stale || change.isPending}
              className={status === 'cancelled' ? 'secondary' : undefined}
              onClick={() => changeStatus(status)}>
              {transitionLabels[status]}
            </button>
          ))}
        </div>
        {change.error && <p className="error" role="alert">{change.error.message}</p>}
      </td>
    </tr>
  )
}

export default function ManagerOrdersPage() {
  const [search, setSearch] = useSearchParams()
  const filters = orderFilters(search)
  const orders = useQuery(ordersQuery(filters))

  return (
    <section className="details">
      <h1>Заказы магазина</h1>
      <label>
        Статус{' '}
        <select value={filters.status ?? ''} onChange={({ target }) =>
          setSearch(target.value ? { status: target.value } : {})}>
          <option value="">Все</option>
          {statuses.map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}
        </select>
      </label>
      {orders.isPending ? (
        <p role="status">Загрузка заказов…</p>
      ) : orders.isError ? (
        <p className="error" role="alert">Не удалось загрузить заказы. {orders.error.message}</p>
      ) : orders.data.results.length === 0 ? (
        <p className="muted">Заказов нет.</p>
      ) : (
        <div className="table-scroll">
          <table className={orders.isPlaceholderData ? 'table stale' : 'table'}>
            <thead>
              <tr>
                <th scope="col">Заказ</th><th scope="col">Дата</th><th scope="col">Получатель</th>
                <th scope="col">Сумма</th><th scope="col">Статус</th><th scope="col">Действия</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.results.map((order) => (
                <OrderRow key={order.id} order={order} stale={orders.isPlaceholderData} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
