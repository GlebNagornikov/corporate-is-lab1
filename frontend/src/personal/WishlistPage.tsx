import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { useSession } from '../auth/useSession'
import { usePageTitle } from '../lib/usePageTitle'
import FavoriteButton from './FavoriteButton'
import { wishlistQuery } from './queries'

export default function WishlistPage() {
  const { data: me } = useSession()
  const { data, isPending, isError, refetch } = useQuery(wishlistQuery(me?.id))
  usePageTitle('Избранное')
  return (
    <section className="personal-page">
      <h1>Избранное</h1>
      {isPending && <p role="status">Загружаем избранное…</p>}
      {isError && <p className="error" role="alert">Не удалось загрузить избранное.{' '}
        <button className="secondary" type="button" onClick={() => void refetch()}>Повторить</button>
      </p>}
      {data?.length === 0 && <p>Здесь будут книги, которые вы сохранили из <Link to="/catalog">каталога</Link>.</p>}
      {Boolean(data?.length) && <ul className="personal-list">
        {data?.map((entry) => (
          <li key={entry.product_id}>
            <div>
              {entry.product__is_active
                ? <Link to={`/products/${encodeURIComponent(entry.product__slug)}`}>{entry.product__name}</Link>
                : <><strong>{entry.product__name}</strong><p className="muted">Снята с продажи</p></>}
            </div>
            <FavoriteButton entry={entry} />
          </li>
        ))}
      </ul>}
    </section>
  )
}
