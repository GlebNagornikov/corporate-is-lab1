import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { productsQuery } from '../api/queries'

const totalFormat = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })

export default function ProductList({ category }: { category: string }) {
  const { data, isPending, isError } = useQuery(productsQuery({ category }))
  if (isPending) return <p role="status">Загрузка товаров…</p>
  if (isError) return <p role="alert">Не удалось загрузить товары.</p>

  return (
    <>
      <ul>
        {data.results.map(({ id, slug, name }) => (
          <li key={id}>
            <Link to={`/products/${encodeURIComponent(slug)}`}>{name}</Link>
          </li>
        ))}
      </ul>
      {data.total !== null && <p>Итого по категории: {totalFormat.format(Number(data.total))}</p>}
    </>
  )
}
