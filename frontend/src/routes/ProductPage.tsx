import { useSuspenseQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { productQuery } from '../api/queries'
import Reviews from '../components/Reviews'
import { formatPrice } from '../lib/format'

export default function ProductPage() {
  const { slug } = useParams<'slug'>()
  const { data: product } = useSuspenseQuery(productQuery(slug!))

  return (
    <article className="details">
      <Link to={`/?category=${encodeURIComponent(product.category.slug)}`}>← {product.category.name}</Link>
      <h1>{product.name}</h1>
      <img className="product-image" src={product.image ?? '/no-image.svg'} alt={product.name} />
      <p className="muted">Артикул {product.sku}</p>
      <p className="price">
        {formatPrice(product.price)}
        {product.old_price && <s className="old-price">{formatPrice(product.old_price)}</s>}
      </p>
      <p className={product.in_stock ? 'muted' : 'error'}>
        {product.in_stock ? `В наличии: ${product.stock} шт.` : 'Нет в наличии'}
      </p>
      <p>{product.description}</p>
      <h2>Отзывы ({product.reviews_count})</h2>
      <Reviews slug={product.slug} />
    </article>
  )
}
