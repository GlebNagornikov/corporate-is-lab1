import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import type { Product } from '../api/client'
import { productQuery } from '../api/queries'
import { formatPrice } from '../lib/format'
import FavoriteButton from '../personal/FavoriteButton'
import { favoriteEntry } from '../personal/queries'
import AddToCartButton from './AddToCartButton'

export default function ProductCard({ product, eager = false }: { product: Product; eager?: boolean }) {
  const queryClient = useQueryClient()
  const prefetch = () => void queryClient.prefetchQuery(productQuery(product.slug))

  return (
    <article className="card">
      <img className="card-image" src={product.image ?? '/no-image.svg'} alt="" loading={eager ? 'eager' : 'lazy'} />
      <span className="muted">{product.category.name}</span>
      {product.book && <p className="muted">{product.book.author}</p>}
      <h2>
        <Link
          to={`/products/${encodeURIComponent(product.slug)}`}
          onMouseEnter={prefetch}
          onFocus={prefetch}
        >
          {product.name}
        </Link>
      </h2>
      <p className="price">
        {formatPrice(product.price)}
        {product.old_price && <s className="old-price">{formatPrice(product.old_price)}</s>}
        {product.discount_percent > 0 && <span className="badge">−{product.discount_percent}%</span>}
      </p>
      <p className={product.in_stock ? 'muted' : 'error'}>
        {product.in_stock ? `В наличии: ${product.stock} шт.` : 'Нет в наличии'}
      </p>
      {product.rating !== null && (
        <p className="muted">★ {product.rating} ({product.reviews_count})</p>
      )}
      <AddToCartButton product={product} />
      <FavoriteButton entry={favoriteEntry(product)} />
    </article>
  )
}
