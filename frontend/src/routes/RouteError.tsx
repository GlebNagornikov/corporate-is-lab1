import { Link, isRouteErrorResponse, useRouteError } from 'react-router'
import { ApiError } from '../api/client'

export default function RouteError() {
  const error = useRouteError()
  let title = 'Что-то пошло не так'
  let message = 'Попробуйте обновить страницу.'

  if (error instanceof ApiError && error.status === 404) {
    title = 'Не найдено'
    message = 'Такого товара нет или он снят с продажи.'
  } else if (error instanceof ApiError) {
    message = error.message
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
