import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { editorialQuery } from '../api/queries'
import ProductCard from '../components/ProductCard'

export default function StorefrontHome() {
  const { data: selected = [], isPending: loading } = useQuery(editorialQuery())
  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow">Независимый книжный магазин</p>
          <h1 id="hero-title">Книги, к которым возвращаются</h1>
          <p>Литература с историей. Любимые сказки, классические романы и издания, которые хочется оставить на полке.</p>
          <Link className="button hero-action" to="/catalog">Открыть каталог <span aria-hidden="true">→</span></Link>
        </div>
        <img src="/bookshop-hero.webp" alt="Книги в тканевых переплётах у солнечного окна" width={1280} height={854} fetchPriority="high" />
      </section>
      {(loading || selected.length > 0) && (
        <section className="editorial" aria-labelledby="editorial-title">
          <div className="section-lead">
            <h2 id="editorial-title">Выбор редакции</h2>
            <Link to="/catalog">Все книги <span aria-hidden="true">→</span></Link>
          </div>
          <div className="grid editorial-grid" aria-busy={loading}>
            {loading ? [1, 2, 3, 4].map((slot) => <div key={slot} className="card skeleton" aria-hidden="true" />)
              : selected.map((book) => <ProductCard key={book.id} product={book} eager />)}
          </div>
        </section>
      )}
    </>
  )
}
