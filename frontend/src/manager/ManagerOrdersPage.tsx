import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { type Order } from '../api/client'
import { formatDate, formatPrice } from '../lib/format'
import { statusLabels } from '../lib/statuses'
import { usePageTitle } from '../lib/usePageTitle'
import OrderPagination from '../orders/OrderPagination'
import { orderFilters, statuses } from './orderFilters'
import { managerOrdersQuery } from './queries'
import OrderStatusActions from './OrderStatusActions'

function OrderRow({ order, stale }: { order: Order; stale: boolean }) {
  return (
    <tr>
      <th scope="row"><Link to={`/manager/orders/${order.id}`}>№{order.id}</Link></th>
      <td data-label="Дата">{formatDate(order.created_at)}</td>
      <td data-label="Получатель">{order.full_name}</td>
      <td className="order-amount" data-label="Сумма">{formatPrice(order.total)}</td>
      <td className="manager-order-status" data-label="Статус">{order.status_display}</td>
      <td className="manager-order-actions">
        <OrderStatusActions order={order} stale={stale} focusFallback="manager-order-status" />
      </td>
    </tr>
  )
}

export default function ManagerOrdersPage() {
  usePageTitle('Заказы магазина')
  const [search, setSearch] = useSearchParams()
  const filters = orderFilters(search)
  const orders = useQuery(managerOrdersQuery(filters))

  return (
    <section className="details">
      <h1>Заказы магазина</h1>
      <label>
        Статус{' '}
        <select id="manager-order-status" value={filters.status ?? ''} onChange={({ target }) =>
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
        <>
        <div className="table-scroll" aria-busy={orders.isPlaceholderData}>
          <table className={orders.isPlaceholderData ? 'table manager-table stale' : 'table manager-table'}>
            <thead>
              <tr>
                <th scope="col">Заказ</th><th scope="col">Дата</th><th scope="col">Получатель</th>
                <th scope="col" className="order-amount">Сумма</th><th scope="col">Статус</th><th scope="col">Действия</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.results.map((order) => (
                <OrderRow key={order.id} order={order} stale={orders.isPlaceholderData} />
              ))}
            </tbody>
          </table>
        </div>
        <OrderPagination page={filters.page} previous={orders.data.previous} next={orders.data.next} />
        </>
      )}
    </section>
  )
}
