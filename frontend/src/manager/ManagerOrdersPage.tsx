import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, requireData, type Order, type OrderStatus } from '../api/client'
import { orderQuery } from '../api/orders'
import { tokens } from '../auth/tokens'
import { formatDate, formatPrice } from '../lib/format'
import { statusLabels, transitionLabels } from '../lib/statuses'
import { usePageTitle } from '../lib/usePageTitle'
import OrderPagination from '../orders/OrderPagination'
import { orderFilters, statuses } from './orderFilters'
import { managerOrderQuery, managerOrdersQuery } from './queries'

function StatusDialog({ status, trigger, pending, error, close, submit }: {
  status: OrderStatus
  trigger: HTMLButtonElement
  pending: boolean
  error: string | undefined
  close: () => void
  submit: (comment: string) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const title = useId()
  const [comment, setComment] = useState('')
  const required = status === 'cancelled'

  useEffect(() => {
    const dialog = ref.current!
    dialog.showModal()
    input.current?.focus()
    return () => {
      dialog.close()
      requestAnimationFrame(() => {
        if (dialog.isConnected) return
        if (trigger.isConnected && !trigger.disabled) trigger.focus()
        else document.getElementById('manager-order-status')?.focus()
      })
    }
  }, [trigger])

  return (
    <dialog className="status-dialog" ref={ref} aria-labelledby={title}
      onCancel={(event) => { event.preventDefault(); close() }}>
      <form className="form" onSubmit={(event) => {
        event.preventDefault()
        if (!pending && (!required || comment.trim())) submit(comment.trim())
      }}>
        <h2 id={title}>{transitionLabels[status]} заказ?</h2>
        <label className="form-field">
          {required ? 'Причина отмены (обязательно)' : 'Комментарий'}
          <textarea ref={input} rows={3} value={comment} required={required} maxLength={300}
            onChange={(event) => setComment(event.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="actions">
          <button type="submit" disabled={pending || (required && !comment.trim())}>
            Подтвердить действие
          </button>
          <button type="button" className="secondary" onClick={close}>Закрыть</button>
        </div>
      </form>
    </dialog>
  )
}

function OrderRow({ order, stale }: { order: Order; stale: boolean }) {
  const client = useQueryClient()
  const [dialog, setDialog] = useState<{ status: OrderStatus; trigger: HTMLButtonElement } | null>(null)
  const change = useMutation({
    mutationFn: async ({ status, comment }: { status: OrderStatus; comment: string; version: number }) =>
      requireData(await api.POST('/api/manager/orders/{id}/status/', {
        params: { path: { id: order.id } },
        body: { status, comment },
      })),
    onSuccess: (updated, { version }) => {
      if (version !== tokens.version()) return
      client.setQueryData(managerOrderQuery(order.id).queryKey, updated)
      client.removeQueries({ queryKey: orderQuery(order.id).queryKey })
      return Promise.all([
        client.invalidateQueries({ queryKey: ['manager', 'orders', 'list'] }),
        client.invalidateQueries({ queryKey: ['manager', 'reports'] }),
        client.invalidateQueries({ queryKey: ['orders', 'list'] }),
      ])
    },
  })

  return (
    <tr>
      <th scope="row"><Link to={`/manager/orders/${order.id}`}>№{order.id}</Link></th>
      <td data-label="Дата">{formatDate(order.created_at)}</td>
      <td data-label="Получатель">{order.full_name}</td>
      <td data-label="Сумма">{formatPrice(order.total)}</td>
      <td data-label="Статус">{order.status_display}</td>
      <td>
        <div className="actions">
          {[...order.allowed_transitions].sort((a, b) => Number(a === 'cancelled') - Number(b === 'cancelled')).map((status) => (
            <button type="button" key={status} disabled={stale || change.isPending}
              className={status === 'cancelled' ? 'secondary' : undefined}
              onClick={(event) => {
                change.reset()
                setDialog({ status, trigger: event.currentTarget })
              }}>
              {transitionLabels[status]}
            </button>
          ))}
        </div>
        {dialog && (
          <StatusDialog {...dialog} pending={change.isPending} error={change.error?.message}
            close={() => setDialog(null)}
            submit={(comment) => change.mutate({
              status: dialog.status, comment, version: tokens.version(),
            }, { onSuccess: () => setDialog(null) })} />
        )}
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
        <OrderPagination page={filters.page} previous={orders.data.previous} next={orders.data.next} />
        </>
      )}
    </section>
  )
}
