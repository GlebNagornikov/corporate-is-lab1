import { useQuery } from '@tanstack/react-query'
import { Form, Link, useSearchParams } from 'react-router'
import { ApiError } from '../api/client'
import { formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import OrderPagination from '../orders/OrderPagination'
import { catalogFilters, managerBooksQuery } from './queries'

export default function ManagerCatalogPage() {
  usePageTitle('Каталог сотрудника')
  const [search] = useSearchParams()
  const filters = catalogFilters(search)
  const books = useQuery(managerBooksQuery(filters))
  return (
    <section className="details">
      <h1>Каталог сотрудника</h1>
      <div className="manager-catalog-controls">
        <Form id="manager-catalog-search" className="manager-catalog-search"
          method="get" role="search" key={filters.q ?? ''}>
          <label className="form-field">Поиск по каталогу
            <input name="q" type="search" defaultValue={filters.q} placeholder="Название, автор, SKU или ISBN" />
          </label>
        </Form>
        <div className="manager-catalog-buttons">
          <button type="submit" form="manager-catalog-search">Найти</button>
          <Link className="button" to="/manager/catalog/new">Добавить книгу</Link>
          <Link className="button" to="/manager/catalog/import">Импорт CSV</Link>
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
                <tr><th scope="col">Книга</th><th scope="col">Жанр</th><th scope="col">Цена</th>
                  <th scope="col">Остаток</th><th scope="col">Видимость</th></tr>
              </thead>
              <tbody>{books.data.results.map((book) => (
                <tr key={book.id}>
                  <th scope="row">
                    <Link to={`/manager/catalog/${book.id}/edit`}>{book.name}</Link>
                    <small className="line-variant muted">{[book.book?.author, book.sku].filter(Boolean).join(' · ')}</small>
                  </th>
                  <td data-label="Жанр">{book.category.name}</td>
                  <td data-label="Цена">{formatPrice(book.price)}</td>
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
