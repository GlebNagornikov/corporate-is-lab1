import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { productsQuery } from '../api/queries'
import { parseCatalogParams } from '../lib/catalogParams'
import { formatPrice } from '../lib/format'

export default function CatalogPage() {
  const [searchParams] = useSearchParams()
  const products = useQuery(productsQuery(parseCatalogParams(searchParams)))

  return (
    <section>
      <h1>Каталог</h1>
      {products.isPending && <p role="status">Загрузка товаров…</p>}
      {products.isError && <p role="alert">Не удалось загрузить товары.</p>}
      {products.data?.results.length === 0 && <p>Товары не найдены.</p>}
      {products.data && products.data.results.length > 0 && (
        <ul>
          {products.data.results.map((product) => (
            <li key={product.id}>
              <Link to={`/products/${encodeURIComponent(product.slug)}`}>{product.name}</Link>
              {' · '}{formatPrice(product.price)}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
