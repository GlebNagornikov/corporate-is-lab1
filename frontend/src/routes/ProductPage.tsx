import { useSuspenseQuery } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'
import { useParams } from 'react-router'
import { productQuery } from '../api/queries'
import { useSession } from '../auth/useSession'
import AddToCartButton from '../components/AddToCartButton'
import ProductBreadcrumbs from '../components/ProductBreadcrumbs'
import Reviews from '../components/Reviews'
import StoreIcon from '../components/StoreIcon'
import { formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'

const ReviewForm = lazy(() => import('../components/ReviewForm'))

function Gallery({ photos }: { photos: { image: string; alt_text: string }[] }) {
  const [index, setIndex] = useState(0)
  const photo = photos[index] ?? photos[0]
  return (
    <div>
      <img className="product-image" src={photo.image} alt={photo.alt_text} width={480} height={720} />
      {photos.length > 1 && <div className="gallery-thumbs" role="group" aria-label="Фотографии издания">
        {photos.map(({ image, alt_text }, i) => (
          <button key={`${image}:${i}`} type="button" aria-label={alt_text} aria-pressed={i === index} onClick={() => setIndex(i)}>
            <img src={image} alt="" width={48} height={64} loading="lazy" />
          </button>
        ))}
      </div>}
    </div>
  )
}

export default function ProductPage() {
  const { slug } = useParams<'slug'>()
  const { data: product } = useSuspenseQuery(productQuery(slug!))
  const { data: me } = useSession()
  usePageTitle(product.name)
  const photos = [
    { image: product.image ?? '/no-image.svg', alt_text: `Обложка: ${product.name}` },
    ...(product.images ?? []).map(({ image, alt_text }, index) => ({
      image, alt_text: alt_text || `Фото ${index + 2}: ${product.name}`,
    })),
  ]

  return (
    <article>
      <ProductBreadcrumbs category={product.category} name={product.name} />
      <div className="product-intro">
        <Gallery key={slug} photos={photos} />
        <div className="product-purchase">
          <p className="eyebrow">{product.category.name}</p>
          <h1>{product.name}</h1>
          {product.book && <p>{product.book.author}</p>}
          <p className="price">
            {formatPrice(product.price)}
            {product.old_price && <s className="old-price">{formatPrice(product.old_price)}</s>}
          </p>
          <p className={product.in_stock ? 'muted' : 'error'}>
            {product.in_stock ? `В наличии: ${product.stock} шт.` : 'Нет в наличии'}
          </p>
          <AddToCartButton key={product.id} product={product} />
          <span className="planned" title="Избранное появится позже"><StoreIcon name="heart" />Избранное</span>
        </div>
      </div>
      <div className="product-notes">
        <section><h2>Аннотация</h2><p>{product.description || 'Аннотация пока отсутствует.'}</p></section>
        <section>
          <h2>Об издании</h2>
          <dl className="specs">
            <dt>Артикул</dt><dd>{product.sku}</dd>
            {product.book && <>
              <dt>Издательство</dt><dd>{product.book.publisher}</dd>
              <dt>Год</dt><dd>{product.book.year}</dd>
              <dt>Язык</dt><dd>{product.book.language}</dd>
              <dt>Переплёт</dt><dd>{product.book.binding === 'hardcover' ? 'Твёрдый' : 'Мягкий'}</dd>
              <dt>Страниц</dt><dd>{product.book.pages}</dd>
              {product.book.isbn && <><dt>ISBN-13</dt><dd>{product.book.isbn}</dd></>}
            </>}
          </dl>
        </section>
      </div>
      <h2>Отзывы ({product.reviews_count})</h2>
      {product.rating !== null && <p className="muted">Средняя оценка: {product.rating} из 5</p>}
      {me && (
        <Suspense fallback={<p className="muted" role="status">Загрузка формы отзыва…</p>}>
          <ReviewForm key={product.id} slug={product.slug} />
        </Suspense>
      )}
      <Reviews slug={product.slug} />
    </article>
  )
}
