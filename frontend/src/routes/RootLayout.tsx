import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useNavigate, useNavigation } from 'react-router'
import { logout, meQuery } from '../auth/session'
import { useCart } from '../cart/useCart'
import CategoryNav from '../components/CategoryNav'
import { formatPrice } from '../lib/format'

export default function RootLayout() {
  const navigation = useNavigation()
  const navigate = useNavigate()
  const { data: me } = useQuery(meQuery())
  const cart = useCart()

  return (
    <>
      <header className="header">
        <Link to="/" className="brand">Магазин</Link>
        {navigation.state === 'loading' && <span className="progress" role="status">Загрузка…</span>}
        <nav className="nav" aria-label="Основное меню">
          <NavLink to="/cart">
            Корзина{cart.count > 0 && `: ${cart.count} шт. на ${formatPrice(cart.total)}`}
          </NavLink>
          {me ? (
            <>
              {me.is_manager
                ? <NavLink to="/manager/orders">Заказы магазина</NavLink>
                : <NavLink to="/orders">Мои заказы</NavLink>}
              <span>{me.username}</span>
              <button type="button" className="secondary" onClick={() => {
                logout()
                void navigate('/', { replace: true })
              }}>
                Выйти
              </button>
            </>
          ) : <NavLink to="/login">Войти</NavLink>}
        </nav>
      </header>
      <div className="layout">
        <aside><CategoryNav /></aside>
        <main><Outlet /></main>
      </div>
      <footer className="footer muted">Версия {import.meta.env.VITE_APP_VERSION ?? 'dev'}</footer>
    </>
  )
}
