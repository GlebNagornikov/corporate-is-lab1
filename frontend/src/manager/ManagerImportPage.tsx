import { useMutation, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { api, ApiError, requireData } from '../api/client'
import { tokens } from '../auth/tokens'
import FormInput from '../components/FormInput'
import { usePageTitle } from '../lib/usePageTitle'
import { managerCategoriesQuery, refreshCatalog } from './queries'

export default function ManagerImportPage() {
  usePageTitle('Импорт книг из CSV')
  const [file, setFile] = useState<File>()
  const client = useQueryClient()
  const { data: genres } = useSuspenseQuery(managerCategoriesQuery())
  const upload = useMutation({
    mutationFn: async ({ file, dryRun }: { file: File; dryRun: boolean; version: number }) =>
      requireData(await api.POST('/api/manager/catalog/import-csv/', {
        body: { file: file.name, dry_run: dryRun },
        bodySerializer: () => {
          const form = new FormData()
          form.set('file', file)
          form.set('dry_run', String(dryRun))
          return form
        },
      })),
    onSuccess: async ({ dry_run }, { version }) => {
      if (dry_run || version !== tokens.version()) return
      client.removeQueries({ queryKey: ['manager', 'catalog', 'detail'] })
      client.removeQueries({ queryKey: ['products', 'detail'] })
      await refreshCatalog(client)
    },
  })
  const errors = upload.error instanceof ApiError ? upload.error.fields.file : undefined
  const busy = upload.isPending
  function submit(dryRun: boolean) {
    if (file && !busy) upload.mutate({ file, dryRun, version: tokens.version() })
  }

  return (
    <section className="details manager-editor">
      <div className="manager-toolbar">
        <h1>Импорт книг из CSV</h1>
        <Link to="/manager/catalog">К каталогу сотрудника</Link>
      </div>
      <p>Загрузите CSV в кодировке UTF-8. Допускаются запятая и точка с запятой.
        Максимум 1 МБ и 1000 строк с книгами.</p>
      <p>Для новой книги заполните столбцы из шаблона. Поля <code>description</code>, <code>isbn</code> и
        {' '}<code>old_price</code> можно оставить пустыми. Для обновления укажите <code>sku</code> и
        столбцы, которые хотите изменить. Значение <code>true</code> в <code>is_active</code> публикует книгу.</p>
      <p><a href="/manager-books.csv" download>Скачать шаблон CSV</a></p>
      <details>
        <summary>Коды жанров для столбца category</summary>
        <ul>{genres.map((genre) => <li key={genre.id}>{genre.name} · <code>{genre.slug}</code></li>)}</ul>
      </details>
      <div className="form manager-card-actions" aria-busy={busy}>
        <FormInput label="Файл CSV" name="file" type="file" accept=".csv,text/csv" disabled={busy}
          aria-describedby={errors?.length ? 'csv-import-errors' : undefined}
          onChange={({ target }) => {
            upload.reset()
            setFile(target.files?.[0])
          }} />
        {upload.error && (
          <div role="alert" id="csv-import-errors" className="error">
            {errors?.length
              ? <ul>{errors.map((message, index) => <li key={index}>{message}</li>)}</ul>
              : <p>{upload.error.message}</p>}
          </div>
        )}
        {upload.data && (
          <p className="success" role="status">
            {upload.data.dry_run ? 'Строк проверено' : 'Строк импортировано'} — {upload.data.processed}.
          </p>
        )}
        <div className="actions">
          <button type="button" className="secondary" disabled={!file || busy} onClick={() => submit(true)}>
            Проверить CSV
          </button>
          <button type="button" disabled={!file || busy || !upload.data?.dry_run} onClick={() => submit(false)}>
            Импортировать книги
          </button>
        </div>
      </div>
    </section>
  )
}
