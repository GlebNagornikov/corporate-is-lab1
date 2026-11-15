import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { api, toApiError } from '../api/client'
import { productQuery } from '../api/queries'
import { tokens } from '../auth/tokens'
import { managerBookQuery, refreshCatalog, type ManagerBook } from './queries'

export default function BookDeleteDialog({ book, close }: { book: ManagerBook; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  const client = useQueryClient()
  const navigate = useNavigate()
  const remove = useMutation({
    mutationFn: async (_version: number) => {
      const { response, error } = await api.DELETE('/api/manager/catalog/{id}/', {
        params: { path: { id: book.id } },
      })
      if (!response.ok) throw toApiError(response, error)
    },
    onSuccess: async (_result, version) => {
      if (version !== tokens.version()) return
      client.removeQueries({ queryKey: productQuery(book.slug).queryKey })
      await refreshCatalog(client)
      if (version !== tokens.version()) return
      await navigate('/manager/catalog?deleted=1', { replace: true })
      client.removeQueries({ queryKey: managerBookQuery(book.id).queryKey })
    },
  })
  useEffect(() => {
    const element = dialog.current!
    const trigger = document.activeElement
    element.showModal()
    cancel.current?.focus()
    return () => {
      element.close()
      requestAnimationFrame(() => {
        if (!element.isConnected && trigger instanceof HTMLElement && trigger.isConnected) trigger.focus()
      })
    }
  }, [])
  return (
    <dialog className="status-dialog" ref={dialog} aria-labelledby="delete-book-title"
      onCancel={(event) => { event.preventDefault(); if (!remove.isPending) close() }}>
      <div className="form" aria-busy={remove.isPending}>
        <h2 id="delete-book-title">Удалить книгу?</h2>
        <p>Если книги «{book.name}» нет ни в одном заказе, её карточка, отзывы и позиции в корзинах будут удалены.</p>
        <p>Если книга уже есть в заказе, её можно снять с продажи в карточке.</p>
        {remove.error && <p className="error" role="alert">{remove.error.message}</p>}
        <div className="actions">
          <button type="button" ref={cancel} className="secondary" disabled={remove.isPending} onClick={close}>
            Отмена
          </button>
          <button type="button" className="manager-delete" disabled={remove.isPending}
            onClick={() => remove.mutate(tokens.version())}>Удалить книгу</button>
        </div>
      </div>
    </dialog>
  )
}
