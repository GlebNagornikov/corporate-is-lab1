import { useQuery } from '@tanstack/react-query'
import { reviewsQuery } from '../api/queries'

const dateFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long' })

export default function Reviews({ slug }: { slug: string }) {
  const reviews = useQuery(reviewsQuery(slug))

  if (reviews.isPending) return <p className="muted" role="status">Отзывы загружаются…</p>
  if (reviews.isError) return <p className="error" role="alert">Не удалось загрузить отзывы.</p>
  if (reviews.data.length === 0) return <p className="muted">Отзывов пока нет.</p>

  return (
    <ul className="reviews">
      {reviews.data.map((review) => (
        <li key={review.id}>
          <strong aria-label={`Оценка ${review.rating} из 5`}>{'★'.repeat(review.rating)}</strong>
          {' '}{review.author},{' '}
          <time dateTime={review.created_at}>{dateFormat.format(new Date(review.created_at))}</time>
          <p>{review.text}</p>
        </li>
      ))}
    </ul>
  )
}
