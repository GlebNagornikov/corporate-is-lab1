import { Link, useLocation } from 'react-router'

export default function NotFoundPage() {
  const { pathname } = useLocation()

  return (
    <section className="details">
      <h1>Страница не найдена</h1>
      <p>Адреса <code>{pathname}</code> в магазине нет.</p>
      <Link to="/">← В каталог</Link>
    </section>
  )
}
