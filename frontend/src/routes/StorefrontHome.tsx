import { Link } from 'react-router'
import type { Product } from '../api/client'
import ProductCard from '../components/ProductCard'

const picks = ['war-of-worlds-1898', 'wonderful-wizard-oz-1900', 'anne-green-gables-1908',
  'peter-pan-kensington-1906', 'story-amulet-1906']

export default function StorefrontHome({ books, loading }: { books: Product[]; loading: boolean }) {
  const selected = picks.flatMap((slug) => books.find((book) => book.slug === slug) ?? []).slice(0, 4)
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
            <div><p className="eyebrow">С полки редакции</p><h2 id="editorial-title">Выбор редакции</h2></div>
            <Link to="/catalog">Все книги <span aria-hidden="true">→</span></Link>
          </div>
          <div className="grid editorial-grid" aria-busy={loading}>
            {loading ? picks.slice(0, 4).map((slug) => <div key={slug} className="card skeleton" aria-hidden="true" />)
              : selected.map((book) => <ProductCard key={book.id} product={book} eager />)}
          </div>
        </section>
      )}
    </>
  )
}
