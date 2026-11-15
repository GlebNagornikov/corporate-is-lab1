import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { api, requireData, type Order, type OrderStatus } from '../api/client'
import { orderQuery } from '../api/orders'
import { tokens } from '../auth/tokens'
import { transitionLabels } from '../lib/statuses'
import { managerOrderQuery } from './queries'

function StatusDialog({ status, trigger, focusFallback, pending, error, close, submit }: {
  status: OrderStatus
  trigger: HTMLButtonElement
  focusFallback: string
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
        else document.getElementById(focusFallback)?.focus()
      })
    }
  }, [trigger, focusFallback])

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

export default function OrderStatusActions({ order, stale = false, focusFallback }: {
  order: Order
  stale?: boolean
  focusFallback: string
}) {
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

  if (!dialog && order.allowed_transitions.length === 0) return null

  return (
    <>
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
        <StatusDialog {...dialog} focusFallback={focusFallback} pending={change.isPending} error={change.error?.message}
          close={() => setDialog(null)}
          submit={(comment) => change.mutate({
            status: dialog.status, comment, version: tokens.version(),
          }, { onSuccess: () => setDialog(null) })} />
      )}
    </>
  )
}
