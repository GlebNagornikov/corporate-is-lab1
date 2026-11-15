import { useEffect, useEffectEvent, useRef } from 'react'
import { Link, useLocation } from 'react-router'
import Filters from '../components/Filters'
import Pagination from '../components/Pagination'
import ProductCard from '../components/ProductCard'
import ProductGridSkeleton from '../components/ProductGridSkeleton'
import CategoryNav from '../components/CategoryNav'
import { useCatalogPages } from '../lib/useCatalogPages'
import { useCatalogScroll } from '../lib/useCatalogScroll'
import { usePageTitle } from '../lib/usePageTitle'
import StorefrontHome from './StorefrontHome'

export default function CatalogPage() {
  const { pathname } = useLocation()
  const {
    page, start, filters, searchParams, first, results, ready, failed, hasNext, next, canLoadMore, loadMore,
  } = useCatalogPages()
  const onlyPage = searchParams.size === 1 && searchParams.has('page')
  const isHome = pathname === '/' && (searchParams.size === 0 || (start === 1 && start < page && onlyPage))
  usePageTitle(isHome ? undefined : 'Каталог')
  const catalog = useRef<HTMLElement>(null)
  useCatalogScroll(catalog, { page, start, isHome, ready })

  const more = useRef<HTMLButtonElement>(null)
  const onIntersect = useEffectEvent(loadMore)
  useEffect(() => {
    if (!canLoadMore || !more.current || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) onIntersect()
    }, { rootMargin: '0px 0px 160px' })
    observer.observe(more.current)
    return () => observer.disconnect()
  }, [canLoadMore])

  const loadingMore = next && (!next.isError || next.isFetching)
  const suggestion = first?.suggestion
  const suggestedParams = new URLSearchParams(searchParams)
  if (suggestion) {
    suggestedParams.set('q', suggestion)
    suggestedParams.delete('page')
  }

  return (
    <>
      {isHome && <StorefrontHome />}
      <section ref={catalog} className="catalog" id="catalog" aria-labelledby="catalog-title">
        <p className="eyebrow">Книги для вашей полки</p>
        {isHome ? <h2 id="catalog-title">Каталог</h2> : <h1 id="catalog-title">Каталог</h1>}
        <div className="catalog-layout">
          <aside className="genre-panel"><CategoryNav /></aside>
          <div className="catalog-results">
            <Filters key={filters.category ?? ''} />
            {failed?.isError ? (
              <div className="load-error" role="alert">
                <p>Не удалось загрузить каталог: {failed.error.message}</p>
                <button type="button" onClick={() => void failed.refetch()}>Повторить</button>
              </div>
            ) : !ready ? (
              <ProductGridSkeleton />
            ) : results.length === 0 ? (
              <div>
                <p className="muted">Ничего не найдено. Измените условия поиска.</p>
                {suggestion && (
                  <p>Возможно, вы искали <Link to={`${pathname}?${suggestedParams}`}>{suggestion}</Link>?</p>
                )}
              </div>
            ) : (
              <>
                <p className="muted" aria-live="polite">Найдено: {first?.count}</p>
                <div className="grid">
                  {results.map((product) => <ProductCard key={product.id} product={product} />)}
                </div>
                <div className="catalog-more">
                  {loadingMore && <ProductGridSkeleton />}
                  {next?.isError && !loadingMore && (
                    <p className="error" role="alert">Не удалось загрузить следующую страницу: {next.error.message}</p>
                  )}
                  {hasNext ? (
                    <button type="button" className="secondary" ref={more} aria-disabled={loadingMore || undefined}
                      onClick={() => {
                        if (loadingMore) return
                        if (next?.isError) void next.refetch()
                        else loadMore()
                      }}>
                      {loadingMore ? 'Загружаем…' : next?.isError ? 'Повторить загрузку' : 'Показать ещё'}
                    </button>
                  ) : <p className="muted" role="status">Больше книг по этим условиям нет.</p>}
                </div>
                <Pagination count={first?.count ?? 0} page={page} />
              </>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
