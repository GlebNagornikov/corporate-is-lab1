import { useInfiniteQuery } from '@tanstack/react-query'
import { reviewsQuery } from '../api/queries'

const dateFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long' })

export default function Reviews({ slug }: { slug: string }) {
  const reviews = useInfiniteQuery(reviewsQuery(slug))

  if (reviews.isPending) return <p className="muted" role="status">Отзывы загружаются…</p>
  if (!reviews.data) return (
    <div>
      <p className="error" role="alert">Не удалось загрузить отзывы.</p>
      <button type="button" className="secondary" onClick={() => void reviews.refetch()}>Повторить</button>
    </div>
  )
  const items = reviews.data.pages.flatMap((page) => page.results)
  if (items.length === 0) return <p className="muted">Отзывов пока нет.</p>

  return (
    <>
      <ul className="reviews">
        {items.map((review) => (
          <li key={review.id}>
            <strong aria-label={`Оценка ${review.rating} из 5`}>{'★'.repeat(review.rating)}</strong>
            {' '}{review.author},{' '}
            <time dateTime={review.created_at}>{dateFormat.format(new Date(review.created_at))}</time>
            <p>{review.text}</p>
          </li>
        ))}
      </ul>
      {reviews.isFetchNextPageError && <p className="error" role="alert">Не удалось загрузить следующую страницу.</p>}
      {reviews.hasNextPage && <button type="button" className="secondary" disabled={reviews.isFetching}
        onClick={() => void reviews.fetchNextPage({ cancelRefetch: false })}>
        {reviews.isFetchingNextPage ? 'Загрузка…' : 'Показать ещё'}
      </button>}
    </>
  )
}
