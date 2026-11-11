import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, ApiError, requireData, toApiError } from '../api/client'
import { readOrderPage } from '../api/orders'
import type { components } from '../api/schema'
import FormInput from '../components/FormInput'
import { formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import { managerPromosQuery } from './queries'

const dateTime = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' })

export default function ManagerPromosPage() {
  usePageTitle('Промокоды')
  const [params, setParams] = useSearchParams()
  const page = readOrderPage(params)
  const promos = useQuery(managerPromosQuery(page))
  const client = useQueryClient()
  const form = useRef<HTMLFormElement>(null)
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ['manager', 'promos'] }),
    client.invalidateQueries({ queryKey: ['cart'] }),
  ])
  const create = useMutation({
    mutationFn: async (body: components['schemas']['ManagerPromoRequest']) =>
      requireData(await api.POST('/api/manager/promos/', { body })),
    onSuccess: async () => {
      form.current?.reset()
      setParams({}, { replace: true })
      await refresh()
    },
  })
  const deactivate = useMutation({
    mutationFn: async (id: number) => {
      const result = await api.POST('/api/manager/promos/{id}/deactivate/', { params: { path: { id } } })
      if (!result.response.ok) throw toApiError(result.response, result.error)
    },
    onSuccess: refresh,
  })
  const fields = create.error instanceof ApiError ? create.error.fields : {}

  return (
    <section>
      <h1>Промокоды</h1>
      <form ref={form} className="details form" onSubmit={(event) => {
        event.preventDefault()
        if (create.isPending) return
        const fields = new FormData(event.currentTarget)
        const read = (name: string) => String(fields.get(name) ?? '').trim()
        create.mutate({
          code: read('code'),
          discount_percent: Number(read('discount_percent')),
          minimum_subtotal: read('minimum_subtotal'),
          valid_from: new Date(read('valid_from')).toISOString(),
          valid_until: new Date(read('valid_until')).toISOString(),
          max_uses: read('max_uses') ? Number(read('max_uses')) : null,
        })
      }}>
        <h2>Новый промокод</h2>
        <div className="manager-fields">
          <FormInput label="Код" name="code" required maxLength={30} error={fields.code?.[0]} />
          <FormInput label="Скидка, %" name="discount_percent" type="number" min="1"
            max="90" required error={fields.discount_percent?.[0]} />
          <FormInput label="Минимальная сумма, ₽" name="minimum_subtotal" type="number" min="0"
            max="9999999999.99" step="0.01" defaultValue="0" required error={fields.minimum_subtotal?.[0]} />
          <FormInput label="Действует с" name="valid_from" type="datetime-local"
            required error={fields.valid_from?.[0]} />
          <FormInput label="Действует по" name="valid_until" type="datetime-local"
            required error={fields.valid_until?.[0]} />
          <FormInput label="Лимит использований" name="max_uses" type="number" min="1"
            max="2147483647" placeholder="Без ограничений" error={fields.max_uses?.[0]} />
        </div>
        {create.error && <p className="error" role="alert">{create.error.message}</p>}
        {create.isSuccess && <p role="status">Промокод создан.</p>}
        <button type="submit" disabled={create.isPending}>Создать промокод</button>
      </form>
      <h2>Список промокодов</h2>
      {promos.isPending && <p role="status">Загрузка промокодов…</p>}
      {promos.error && <p className="error" role="alert">{promos.error.message}</p>}
      {deactivate.error && <p className="error" role="alert">{deactivate.error.message}</p>}
      {deactivate.isSuccess && <p role="status">Промокод деактивирован.</p>}
      {promos.data && promos.data.results.length === 0 && <p>Промокодов пока нет.</p>}
      {promos.data && promos.data.results.length > 0 && (
        <>
          <div className="table-scroll">
            <table>
              <thead><tr>
                <th>Код</th><th>Скидка</th><th>Минимум</th><th>Период</th>
                <th>Использования</th><th>Состояние</th><th>Действие</th>
              </tr></thead>
              <tbody>{promos.data.results.map((promo) => (
                <tr key={promo.id}>
                  <th scope="row">{promo.code}</th>
                  <td>{promo.discount_percent}%</td>
                  <td>{formatPrice(promo.minimum_subtotal ?? '0')}</td>
                  <td>{dateTime.format(new Date(promo.valid_from))} — {dateTime.format(new Date(promo.valid_until))}</td>
                  <td>{promo.used_count}{promo.max_uses == null ? ' · без лимита' : ` / ${promo.max_uses}`}</td>
                  <td>{promo.is_active ? 'Включён' : 'Деактивирован'}</td>
                  <td>{promo.is_active && (
                    <button type="button" className="secondary" disabled={deactivate.isPending}
                      aria-label={`Деактивировать ${promo.code}`}
                      onClick={() => deactivate.mutate(promo.id)}>Деактивировать</button>
                  )}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {(promos.data.previous || promos.data.next) && (
            <nav aria-label="Страницы промокодов" className="actions">
              {promos.data.previous && <Link to={`?page=${page - 1}`}>Назад</Link>}
              {promos.data.next && <Link to={`?page=${page + 1}`}>Дальше</Link>}
            </nav>
          )}
        </>
      )}
    </section>
  )
}
