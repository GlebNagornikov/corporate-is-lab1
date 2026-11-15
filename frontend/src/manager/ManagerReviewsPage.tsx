import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api, toApiError } from '../api/client'
import type { components } from '../api/schema'
import { usePageTitle } from '../lib/usePageTitle'
import { managerReviewsQuery } from './queries'

type Decision = components['schemas']['ReviewDecisionRequest']['decision']

export default function ManagerReviewsPage() {
  usePageTitle('Модерация отзывов')
  const client = useQueryClient()
  const queueOptions = managerReviewsQuery()
  const queue = useQuery(queueOptions)
  const moderate = useMutation({
    mutationFn: async ({ id, decision }: { id: number; decision: Decision }) => {
      const { response, error } = await api.POST('/api/manager/reviews/{id}/moderate/', {
        params: { path: { id } }, body: { decision },
      })
      if (!response.ok) throw toApiError(response, error)
    },
    onSuccess: (_, { id }) => {
      client.setQueryData(queueOptions.queryKey, (page) => {
        if (!page?.results.some((review) => review.id === id)) return page
        return { ...page, count: page.count - 1, results: page.results.filter((review) => review.id !== id) }
      })
      void client.invalidateQueries({ queryKey: ['products'] })
    },
    onSettled: () => client.invalidateQueries(queueOptions),
  })

  return (
    <section>
      <h1>Модерация отзывов</h1>
      {queue.isPending && <p role="status">Загрузка очереди…</p>}
      {queue.isError && <div>
        <p className="error" role="alert">{queue.error.message}</p>
        <button type="button" className="secondary" onClick={() => void queue.refetch()}>Повторить</button>
      </div>}
      {moderate.error && <p className="error" role="alert">{moderate.error.message}</p>}
      {queue.data && <p role="status">
        {queue.data.count === 0 ? 'Отзывов на модерации нет.' : `Ожидают модерации: ${queue.data.count}`}
      </p>}
      {queue.data?.next && <p className="muted">Следующие отзывы появятся после обработки первых.</p>}
      <ul className="reviews">
        {queue.data?.results.map((review) => (
          <li key={review.id}>
            <h2><Link to={`/products/${review.product_slug}`}>{review.product_name}</Link></h2>
            <p>{review.author} · Оценка {review.rating} из 5</p>
            <p>{review.text}</p>
            <div className="actions">
              <button type="button" disabled={moderate.isPending}
                onClick={() => moderate.mutate({ id: review.id, decision: 'approved' })}>Одобрить</button>
              <button type="button" className="secondary" disabled={moderate.isPending}
                onClick={() => moderate.mutate({ id: review.id, decision: 'rejected' })}>Отклонить</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
