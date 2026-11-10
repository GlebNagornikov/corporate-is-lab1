import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { api, ApiError, requireData, type Category } from '../api/client'
import { tokens } from '../auth/tokens'
import FormInput from '../components/FormInput'
import { managerCategoriesQuery } from './queries'

export default function GenreDialog({ close, select }: {
  close: () => void
  select: (id: number) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const client = useQueryClient()
  const create = useMutation({
    mutationFn: async ({ name }: { name: string; version: number }) =>
      requireData(await api.POST('/api/manager/categories/', { body: { name } })),
    onSuccess: async (genre, { version }) => {
      const key = managerCategoriesQuery().queryKey
      await client.cancelQueries({ queryKey: key })
      if (tokens.version() !== version) return
      client.setQueryData(key, (previous: Category[] = []) => [...previous, genre]
        .sort((a, b) => a.name.localeCompare(b.name, 'ru')))
      select(genre.id)
      close()
    },
  })
  useEffect(() => {
    const dialog = ref.current!
    dialog.showModal()
    return () => dialog.close()
  }, [])

  const fieldError = create.error instanceof ApiError ? create.error.fields.name?.join(' ') : undefined
  return (
    <dialog className="status-dialog" ref={ref} aria-labelledby="genre-dialog-title"
      onCancel={(event) => { event.preventDefault(); if (!create.isPending) close() }}>
      <form className="form" aria-busy={create.isPending} onSubmit={(event) => {
        event.preventDefault()
        if (create.isPending) return
        const name = String(new FormData(event.currentTarget).get('name') ?? '').trim()
        create.mutate({ name, version: tokens.version() })
      }}>
        <h2 id="genre-dialog-title">Новый жанр</h2>
        <FormInput name="name" label="Название жанра" required maxLength={100} error={fieldError}
          disabled={create.isPending} />
        {create.error && !fieldError && <p className="error" role="alert">{create.error.message}</p>}
        <div className="actions">
          <button type="submit" disabled={create.isPending}>Сохранить жанр</button>
          <button type="button" className="secondary" disabled={create.isPending} onClick={close}>Отмена</button>
        </div>
      </form>
    </dialog>
  )
}
