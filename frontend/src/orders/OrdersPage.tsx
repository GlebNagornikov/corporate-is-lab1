import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { ordersQuery, readOrderPage } from '../api/orders'
import { useSession } from '../auth/useSession'
import { formatDate, formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import OrderPagination from './OrderPagination'

export default function OrdersPage() {
  const { data: me } = useSession()
  const title = me?.is_manager ? 'Заказы' : 'Мои заказы'
  usePageTitle(title)
  const [search] = useSearchParams()
  const page = readOrderPage(search)
  const orders = useQuery(ordersQuery({ page }))

  return (
    <section className="details">
      <p className="eyebrow">Личный кабинет</p>
      <h1>{title}</h1>
      {me && <p className="muted">{me.username} · {me.email}</p>}
      {orders.isPending ? (
        <p role="status">Загрузка заказов…</p>
      ) : orders.isError ? (
        <p className="error" role="alert">Не удалось загрузить заказы. {orders.error.message}</p>
      ) : orders.data.results.length === 0 ? (
        <p className="muted">Заказов пока нет. <Link to="/catalog">В каталог</Link></p>
      ) : (
        <>
        <div className="table-scroll" aria-busy={orders.isPlaceholderData}>
          <table className={orders.isPlaceholderData ? 'table order-table stale' : 'table order-table'}>
            <thead>
              <tr>
                <th scope="col">Заказ</th><th scope="col">Дата</th>
                <th scope="col">Статус</th><th scope="col" className="order-amount">Сумма</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.results.map((order) => (
                <tr key={order.id}>
                  <th scope="row"><Link to={`/orders/${order.id}`}>Заказ №{order.id}</Link></th>
                  <td data-label="Дата">{formatDate(order.created_at)}</td>
                  <td data-label="Статус">{order.status_display}</td>
                  <td className="order-amount" data-label="Сумма">{formatPrice(order.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <OrderPagination page={page} previous={orders.data.previous} next={orders.data.next} />
        </>
      )}
    </section>
  )
}
