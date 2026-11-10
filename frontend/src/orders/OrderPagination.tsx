import { Link, useSearchParams } from 'react-router'

export default function OrderPagination({ page, previous, next, label = 'Страницы заказов' }: {
  page: number
  previous?: string | null
  next?: string | null
  label?: string
}) {
  const [search] = useSearchParams()
  if (!previous && !next) return null

  function pageLink(target: number) {
    const params = new URLSearchParams(search)
    params.set('page', String(target))
    return { search: params.toString() }
  }

  return (
    <nav className="pagination" aria-label={label}>
      {previous && <Link to={pageLink(page - 1)}>Предыдущая</Link>}
      <span aria-current="page">Страница {page}</span>
      {next && <Link to={pageLink(page + 1)}>Следующая</Link>}
    </nav>
  )
}
