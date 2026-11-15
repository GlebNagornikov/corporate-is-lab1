import { Link, isRouteErrorResponse, useParams, useRouteError } from 'react-router'
import { ApiError } from '../api/client'
import { usePageTitle } from '../lib/usePageTitle'

export default function RouteError() {
  const error = useRouteError()
  const { slug, orderId, bookId } = useParams<'slug' | 'orderId' | 'bookId'>()
  let title = 'Что-то пошло не так'
  let message = 'Попробуйте обновить страницу.'

  if (error instanceof ApiError && error.status === 404) {
    title = 'Не найдено'
    if (slug) message = 'Такого товара нет или он снят с продажи.'
    else if (orderId) message = 'Заказ не найден.'
    else if (bookId) message = 'Книга не найдена.'
    else message = error.message
  } else if (error instanceof ApiError) {
    if (error.status === 403) title = 'Нет доступа'
    message = error.message
  } else if (isRouteErrorResponse(error) && error.status === 403) {
    title = 'Нет доступа'
    message = String(error.data)
  } else if (isRouteErrorResponse(error) && error.status === 404) {
    title = 'Не найдено'
    message = String(error.data)
  } else if (isRouteErrorResponse(error)) {
    message = `${error.status} ${error.statusText}`
  }

  usePageTitle(title)
  return (
    <section className="details state-panel" role="alert">
      <p className="eyebrow">Книжная полка</p>
      <h1>{title}</h1>
      <p>{message}</p>
      <Link className="button" to="/">На главную</Link>
    </section>
  )
}
