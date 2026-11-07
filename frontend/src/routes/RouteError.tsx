import { Link, isRouteErrorResponse, useParams, useRouteError } from 'react-router'
import { ApiError } from '../api/client'

export default function RouteError() {
  const error = useRouteError()
  const { slug } = useParams<'slug'>()
  let title = 'Что-то пошло не так'
  let message = 'Попробуйте обновить страницу.'

  if (error instanceof ApiError && error.status === 404) {
    title = 'Не найдено'
    message = slug ? 'Такого товара нет или он снят с продажи.' : error.message
  } else if (error instanceof ApiError) {
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

  return (
    <section className="details" role="alert">
      <h1>{title}</h1>
      <p>{message}</p>
      <Link to="/">← В каталог</Link>
    </section>
  )
}
