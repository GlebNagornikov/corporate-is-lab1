import { useSuspenseQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { productQuery } from '../api/queries'
import { formatPrice } from '../lib/format'

export default function ProductPage() {
  const { slug } = useParams<'slug'>()
  const { data: product } = useSuspenseQuery(productQuery(slug!))

  return (
    <section className="details">
      <h1>{product.name}</h1>
      <p>{formatPrice(product.price)}</p>
      <Link to="/">← В каталог</Link>
    </section>
  )
}
