import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { useParams } from 'react-router'
import { productQuery } from '../api/queries'
import { meQuery } from '../auth/session'
import AddToCartButton from '../components/AddToCartButton'
import ProductBreadcrumbs from '../components/ProductBreadcrumbs'
import Reviews from '../components/Reviews'
import { formatPrice } from '../lib/format'

const ReviewForm = lazy(() => import('../components/ReviewForm'))

export default function ProductPage() {
  const { slug } = useParams<'slug'>()
  const { data: product } = useSuspenseQuery(productQuery(slug!))
  const { data: me } = useQuery(meQuery())

  return (
    <article className="details">
      <ProductBreadcrumbs category={product.category} name={product.name} />
      <h1>{product.name}</h1>
      {product.book && <p>{product.book.author}</p>}
      <img className="product-image" src={product.image ?? '/no-image.svg'} alt={product.name} />
      <p className="muted">Артикул {product.sku}</p>
      <p className="price">
        {formatPrice(product.price)}
        {product.old_price && <s className="old-price">{formatPrice(product.old_price)}</s>}
      </p>
      <p className={product.in_stock ? 'muted' : 'error'}>
        {product.in_stock ? `В наличии: ${product.stock} шт.` : 'Нет в наличии'}
      </p>
      <AddToCartButton key={product.id} product={product} />
      <p>{product.description}</p>
      {product.book && <section>
        <h2>Об издании</h2>
        <dl>
          <dt>Издательство</dt><dd>{product.book.publisher}</dd>
          <dt>Год</dt><dd>{product.book.year}</dd>
          <dt>Язык</dt><dd>{product.book.language}</dd>
          <dt>Переплёт</dt><dd>{product.book.binding === 'hardcover' ? 'Твёрдый' : 'Мягкий'}</dd>
          <dt>Страниц</dt><dd>{product.book.pages}</dd>
          {product.book.isbn && <><dt>ISBN-13</dt><dd>{product.book.isbn}</dd></>}
        </dl>
      </section>}
      <h2>Отзывы ({product.reviews_count})</h2>
      {me && (
        <Suspense fallback={<p className="muted" role="status">Загрузка формы отзыва…</p>}>
          <ReviewForm key={product.id} slug={product.slug} />
        </Suspense>
      )}
      <Reviews slug={product.slug} />
    </article>
  )
}
