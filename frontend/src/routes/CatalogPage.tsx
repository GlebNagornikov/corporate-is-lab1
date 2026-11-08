import { useQuery } from '@tanstack/react-query'
import { useLayoutEffect, useRef } from 'react'
import { Link, useLocation, useNavigationType, useSearchParams } from 'react-router'
import { productsQuery } from '../api/queries'
import Filters from '../components/Filters'
import Pagination from '../components/Pagination'
import ProductCard from '../components/ProductCard'
import ProductGridSkeleton from '../components/ProductGridSkeleton'
import CategoryNav from '../components/CategoryNav'
import { parseCatalogParams } from '../lib/catalogParams'
import { usePageTitle } from '../lib/usePageTitle'
import StorefrontHome from './StorefrontHome'

export default function CatalogPage() {
  const [searchParams] = useSearchParams()
  const { pathname } = useLocation()
  const navigationType = useNavigationType()
  const isHome = pathname === '/' && searchParams.size === 0
  usePageTitle(isHome ? undefined : 'Каталог')
  const query = parseCatalogParams(searchParams)
  const page = query.page ?? 1
  const catalog = useRef<HTMLElement>(null)
  const previous = useRef({ pathname, isHome, page })
  useLayoutEffect(() => {
    const before = previous.current
    previous.current = { pathname, isHome, page }
    if (navigationType !== 'POP' && before.pathname === pathname &&
        (before.page !== page || (isHome && !before.isHome))) {
      catalog.current?.scrollIntoView?.()
    }
  }, [pathname, isHome, page, navigationType])

  const { data, isPending, isError, error, refetch, isPlaceholderData } = useQuery(productsQuery(query))
  const suggestion = isPlaceholderData ? null : data?.suggestion
  const suggestedParams = new URLSearchParams(searchParams)
  if (suggestion) {
    suggestedParams.set('q', suggestion)
    suggestedParams.delete('page')
  }

  return (
    <>
      {isHome && <StorefrontHome books={data?.results ?? []} loading={isPending || isPlaceholderData} />}
      <section ref={catalog} className="catalog" id="catalog" aria-labelledby="catalog-title">
        <p className="eyebrow">Книги для вашей полки</p>
        {isHome ? <h2 id="catalog-title">Каталог</h2> : <h1 id="catalog-title">Каталог</h1>}
        <div className="catalog-layout">
          <aside className="genre-panel"><CategoryNav /></aside>
          <div className="catalog-results">
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
                  <p>Возможно, вы искали <Link to={`${pathname}?${suggestedParams}`}>{suggestion}</Link>?</p>
                )}
              </div>
            ) : (
              <>
                <p className="muted" aria-live="polite">Найдено: {data.count}</p>
                <div className={isPlaceholderData ? 'grid stale' : 'grid'} aria-busy={isPlaceholderData}>
                  {data.results.map((product) => <ProductCard key={product.id} product={product} />)}
                </div>
                <Pagination count={data.count} page={page} />
              </>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
