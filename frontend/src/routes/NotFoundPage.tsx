import { Link, useLocation } from 'react-router'
import { usePageTitle } from '../lib/usePageTitle'

export default function NotFoundPage() {
  const { pathname } = useLocation()
  usePageTitle('Страница не найдена')

  return (
    <section className="details state-panel">
      <p className="eyebrow">Ошибка 404</p>
      <h1>Страница не найдена</h1>
      <p>Адреса <code>{pathname}</code> в магазине нет.</p>
      <Link className="button" to="/">На главную</Link>
    </section>
  )
}
