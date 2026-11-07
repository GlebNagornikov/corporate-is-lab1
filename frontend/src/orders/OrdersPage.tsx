import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { ordersQuery, readOrderPage } from '../api/orders'
import { meQuery } from '../auth/session'
import { formatDate, formatPrice } from '../lib/format'
import OrderPagination from './OrderPagination'

export default function OrdersPage() {
  const { data: me } = useQuery(meQuery())
  const [search] = useSearchParams()
  const page = readOrderPage(search)
  const orders = useQuery(ordersQuery({ page }))

  return (
    <section className="details">
      <h1>{me?.is_manager ? 'Заказы' : 'Мои заказы'}</h1>
      {orders.isPending ? (
        <p role="status">Загрузка заказов…</p>
      ) : orders.isError ? (
        <p className="error" role="alert">Не удалось загрузить заказы. {orders.error.message}</p>
      ) : orders.data.results.length === 0 ? (
        <p className="muted">Заказов пока нет. <Link to="/">В каталог</Link></p>
      ) : (
        <>
        <div className="table-scroll" aria-busy={orders.isPlaceholderData}>
          <table className={orders.isPlaceholderData ? 'table stale' : 'table'}>
            <thead>
              <tr>
                <th scope="col">Заказ</th><th scope="col">Дата</th>
                <th scope="col">Статус</th><th scope="col">Сумма</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.results.map((order) => (
                <tr key={order.id}>
                  <th scope="row"><Link to={`/orders/${order.id}`}>Заказ №{order.id}</Link></th>
                  <td>{formatDate(order.created_at)}</td>
                  <td>{order.status_display}</td>
                  <td>{formatPrice(order.total)}</td>
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
