import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { productsQuery } from '../api/queries'
import Filters from '../components/Filters'
import Pagination from '../components/Pagination'
import ProductCard from '../components/ProductCard'
import ProductGridSkeleton from '../components/ProductGridSkeleton'
import { parseCatalogParams } from '../lib/catalogParams'

export default function CatalogPage() {
  const [searchParams] = useSearchParams()
  const query = parseCatalogParams(searchParams)
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useQuery(productsQuery(query))
  const suggestion = isPlaceholderData ? null : data?.suggestion
  const suggestedParams = new URLSearchParams(searchParams)
  if (suggestion) {
    suggestedParams.set('q', suggestion)
    suggestedParams.delete('page')
  }

  return (
    <section>
      <h1>Каталог</h1>
      <Filters key={query.category ?? ''} />
      {isPending ? (
        <ProductGridSkeleton />
      ) : isError ? (
        <div className="load-error" role="alert">
          <p>Не удалось загрузить каталог: {error.message}</p>
          <button type="button" onClick={() => void refetch()}>Повторить</button>
        </div>
      ) : data.results.length === 0 ? (
        <div>
          <p className="muted">Ничего не найдено. Измените условия поиска.</p>
          {suggestion && (
            <p>Возможно, вы искали <Link to={`/?${suggestedParams}`}>{suggestion}</Link>?</p>
          )}
        </div>
      ) : (
        <>
          <p className="muted">Найдено: {data.count}</p>
          <div className={isPlaceholderData ? 'grid stale' : 'grid'} aria-busy={isPlaceholderData}>
            {data.results.map((product) => <ProductCard key={product.id} product={product} />)}
          </div>
          <Pagination count={data.count} page={query.page ?? 1} />
        </>
      )}
    </section>
  )
}
