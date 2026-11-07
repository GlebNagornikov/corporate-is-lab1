import { Link, useSearchParams } from 'react-router'

const PAGE_SIZE = 20

export default function Pagination({ count, page }: { count: number; page: number }) {
  const [searchParams] = useSearchParams()
  const pages = Math.ceil(count / PAGE_SIZE)
  if (pages <= 1) return null

  function hrefFor(target: number) {
    const params = new URLSearchParams(searchParams)
    if (target === 1) params.delete('page')
    else params.set('page', String(target))
    const search = params.toString()
    return search ? `/?${search}` : '/'
  }

  return (
    <nav className="pagination" aria-label="Страницы">
      {Array.from({ length: pages }, (_, index) => index + 1).map((target) => (
        <Link key={target} to={hrefFor(target)} aria-current={target === page ? 'page' : undefined}>
          {target}
        </Link>
      ))}
    </nav>
  )
}
