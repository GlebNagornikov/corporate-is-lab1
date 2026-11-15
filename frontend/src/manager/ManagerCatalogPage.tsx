import { useQuery } from '@tanstack/react-query'
import { useLayoutEffect, useRef } from 'react'
import { Link, useLocation, useNavigationType, useSearchParams } from 'react-router'
import { ApiError } from '../api/client'
import { formatPrice } from '../lib/format'
import { useDebouncedCallback } from '../lib/useDebouncedCallback'
import { usePageTitle } from '../lib/usePageTitle'
import OrderPagination from '../orders/OrderPagination'
import { catalogFilters, managerBooksQuery } from './queries'

export default function ManagerCatalogPage() {
  usePageTitle('Каталог сотрудника')
  const [search, setSearch] = useSearchParams()
  const { key } = useLocation()
  const navigationType = useNavigationType()
  const filters = catalogFilters(search)
  const books = useQuery(managerBooksQuery(filters))
  const searchInput = useRef<HTMLInputElement>(null)
  const { schedule, cancel } = useDebouncedCallback(applySearch, 300)

  function applySearch() {
    const q = searchInput.current?.value.trim() ?? ''
    if (q === (search.get('q') ?? '') && !search.has('page')) return
    setSearch(q ? { q } : {}, { replace: true, preventScrollReset: true })
  }

  useLayoutEffect(() => {
    // Search replaces the URL. Keep any typing that happened while it was updating.
    if (navigationType === 'REPLACE') return
    cancel()
    if (searchInput.current) searchInput.current.value = filters.q ?? ''
  }, [cancel, filters.q, key, navigationType])

  return (
    <section className="details">
      <h1>Каталог сотрудника</h1>
      <div className="manager-catalog-controls">
        <form className="manager-catalog-search"
          role="search" onSubmit={(event) => {
            event.preventDefault()
            cancel()
            applySearch()
          }}>
          <label className="form-field">Поиск по каталогу
            <input ref={searchInput} name="q" type="search" defaultValue={filters.q}
              onChange={schedule} placeholder="Название, автор, SKU или ISBN" />
          </label>
        </form>
        <div className="manager-catalog-buttons">
          <Link className="button" to="/manager/catalog/new">Добавить книгу</Link>
          <Link className="button" to="/manager/catalog/import">Импорт JSON</Link>
        </div>
        {filters.q && <Link className="manager-catalog-reset" to="/manager/catalog">Сбросить</Link>}
      </div>
      {search.has('deleted') && <p className="success" role="status">Книга удалена.</p>}
      {books.isPending && <p role="status">Загрузка книг…</p>}
      {books.isError && (
        <div role="alert">
          <p className="error">Не удалось загрузить каталог. {books.error.message}</p>
          {books.error instanceof ApiError && books.error.status === 404
            ? <Link to={{ search: filters.q ? new URLSearchParams({ q: filters.q }).toString() : '' }}>На первую страницу</Link>
            : <button type="button" onClick={() => void books.refetch()}>Повторить</button>}
        </div>
      )}
      {books.data && books.data.results.length === 0 && <p>Книги не найдены.</p>}
      {books.data && books.data.results.length > 0 && (
        <>
          <div className="table-scroll" aria-busy={books.isPlaceholderData}>
            <table className={books.isPlaceholderData ? 'table manager-table stale' : 'table manager-table'}>
              <thead>
                <tr><th scope="col">Книга</th><th scope="col">Жанр</th><th scope="col" className="order-amount">Цена</th>
                  <th scope="col">Остаток</th><th scope="col">Видимость</th></tr>
              </thead>
              <tbody>{books.data.results.map((book) => (
                <tr key={book.id}>
                  <th scope="row">
                    <Link to={`/manager/catalog/${book.id}/edit`}>{book.name}</Link>
                    <small className="line-variant muted">{[book.book?.author, book.sku].filter(Boolean).join(' · ')}</small>
                  </th>
                  <td data-label="Жанр">{book.category.name}</td>
                  <td className="order-amount" data-label="Цена">{formatPrice(book.price)}</td>
                  <td data-label="Остаток">{book.stock} шт.</td>
                  <td data-label="Видимость">{book.is_active ? 'На витрине' : 'Скрыта'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <OrderPagination {...books.data} page={filters.page} label="Страницы каталога сотрудника" />
        </>
      )}
    </section>
  )
}
