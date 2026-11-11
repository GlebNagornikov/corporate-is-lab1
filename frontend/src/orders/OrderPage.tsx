import { useMutation, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { Link, useLocation, useParams } from 'react-router'
import { api, requireData, type Order } from '../api/client'
import { orderQuery } from '../api/orders'
import { tokens } from '../auth/tokens'
import { formatDate, formatPrice } from '../lib/format'
import { statusLabels } from '../lib/statuses'
import { usePageTitle } from '../lib/usePageTitle'
import { managerOrderQuery } from '../manager/queries'

export default function OrderPage({ manager = false }: { manager?: boolean }) {
  const id = Number(useParams<'orderId'>().orderId)
  usePageTitle(`Заказ №${id}`)
  const { state }: { state: unknown } = useLocation()
  const justPlaced = state !== null && typeof state === 'object' &&
    'justPlaced' in state && state.justPlaced === true
  const client = useQueryClient()
  const query = manager ? managerOrderQuery(id) : orderQuery(id)
  const { data: order } = useSuspenseQuery(query)
  function updateOrder(updated: Order, version: number) {
    if (version !== tokens.version()) return
    client.setQueryData(query.queryKey, updated)
    return client.invalidateQueries({ queryKey: ['orders', 'list'] })
  }

  const cancel = useMutation({
    mutationFn: async (_version: number) => requireData(await api.POST('/api/orders/{id}/cancel/', {
      params: { path: { id } },
    })),
    onSuccess: updateOrder,
  })
  const pay = useMutation({
    mutationFn: async ({ outcome }: { outcome: 'success' | 'failed'; version: number }) =>
      requireData(await api.POST('/api/orders/{id}/simulate-payment/', {
        params: { path: { id } },
        body: { outcome },
      })),
    onSuccess: (updated, { version }) => updateOrder(updated, version),
    onError: (_error, { version }) => {
      if (version === tokens.version()) return client.invalidateQueries({ queryKey: query.queryKey })
    },
  })
  const isUpdating = pay.isPending || cancel.isPending

  return (
    <section className="details order-detail">
      {justPlaced && <p className="success" role="status">Заказ оформлен. Спасибо!</p>}
      <h1>Заказ №{order.id}</h1>
      <p>{formatDate(order.created_at)} · <strong>{order.status_display}</strong></p>
      {manager && (
        <dl className="order-totals">
          <dt>Получатель</dt><dd>{order.full_name}</dd>
          <dt>Телефон</dt><dd>{order.phone}</dd>
          <dt>Почта</dt><dd>{order.email}</dd>
          <dt>Доставка</dt><dd>{order.delivery_method === 'courier' ? order.address : 'Самовывоз'}</dd>
          {order.comment && <><dt>Комментарий</dt><dd>{order.comment}</dd></>}
        </dl>
      )}
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Товар</th>
              <th scope="col" className="order-quantity">Количество</th>
              <th scope="col" className="order-amount">Сумма</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={`${item.product}:${item.variant ?? ''}`}>
                <td>
                  {item.product_name}
                  {item.variant_name && <small className="line-variant muted">{item.variant_name}</small>}
                </td>
                <td>{item.quantity} шт.</td>
                <td className="order-amount">{formatPrice(item.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="order-totals order-amounts">
        <dt>Товары</dt><dd>{formatPrice(order.subtotal)}</dd>
        {Number(order.discount) > 0 && (
          <>
            <dt>Скидка{order.promo_code && ` (${order.promo_code})`}</dt>
            <dd>−{formatPrice(order.discount)}</dd>
          </>
        )}
        <dt>Доставка</dt><dd>{formatPrice(order.delivery_cost)}</dd>
        <dt className="price">Итого</dt><dd className="price">{formatPrice(order.total)}</dd>
      </dl>
      {!manager && order.can_pay && (
        <details className="order-payment">
          <summary>Оплатить</summary>
          <p>Учебный платёжный шлюз. Реальные деньги не списываются.</p>
          <div className="actions">
            <button type="button" disabled={isUpdating}
              onClick={() => pay.mutate({ outcome: 'success', version: tokens.version() })}>
              Успех
            </button>
            <button type="button" className="secondary" disabled={isUpdating}
              onClick={() => pay.mutate({ outcome: 'failed', version: tokens.version() })}>
              Отказ
            </button>
          </div>
          {pay.isSuccess && pay.variables.outcome === 'failed' && (
            <p role="status">Учебный платёж отклонён. Можно повторить оплату.</p>
          )}
          {pay.error && <p className="error" role="alert">{pay.error.message}</p>}
        </details>
      )}
      {!manager && order.can_cancel && (
        <button type="button" disabled={isUpdating} onClick={() => cancel.mutate(tokens.version())}>
          Отменить заказ
        </button>
      )}
      {cancel.error && <p className="error" role="alert">{cancel.error.message}</p>}
      <h2>История</h2>
      <ul>
        {order.history.map((entry, index) => (
          <li key={`${entry.created_at}:${index}`}>
            {formatDate(entry.created_at)} · {statusLabels[entry.to_status]}
            {entry.changed_by && ` · ${entry.changed_by}`}
            {entry.comment && ` — ${entry.comment}`}
          </li>
        ))}
      </ul>
      <Link to={manager ? '/manager/orders' : '/orders'}>К списку заказов</Link>
    </section>
  )
}

export function ManagerOrderPage() {
  return <OrderPage manager />
}
