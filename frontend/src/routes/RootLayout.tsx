import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useNavigation, useNavigationType } from 'react-router'
import { SessionProvider } from '../auth/SessionProvider'
import { logout } from '../auth/session'
import { useSession } from '../auth/useSession'
import { CartProvider } from '../cart/CartProvider'
import { useCartSnapshot } from '../cart/useCartSnapshot'
import StoreIcon from '../components/StoreIcon'
import { formatPrice } from '../lib/format'
import { useTheme } from '../lib/useTheme'

export default function RootLayout() {
  return <SessionProvider><CartProvider><Storefront /></CartProvider></SessionProvider>
}

function Storefront() {
  const navigation = useNavigation()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const navigationType = useNavigationType()
  const previousPath = useRef(pathname)
  const main = useRef<HTMLElement>(null)
  const client = useQueryClient()
  const { data: me } = useSession()
  const { cart } = useCartSnapshot()
  const { theme, selectTheme } = useTheme()
  const signOut = useMutation({ mutationFn: () => logout(client), onSuccess: () => navigate('/', { replace: true }) })

  useEffect(() => {
    if (previousPath.current !== pathname && navigationType !== 'POP') {
      document.scrollingElement?.scrollTo?.(0, 0)
      main.current?.focus({ preventScroll: true })
    }
    previousPath.current = pathname
  }, [navigationType, pathname])

  return (
    <>
      <a className="skip-link" href="#main">К содержимому</a>
      <header className="header shell">
        <Link to="/" className="brand">Книжная полка</Link>
        <nav className="nav" aria-label="Основное меню">
          <NavLink to="/catalog">Каталог</NavLink>
          <span className="planned" title="Избранное появится позже"><StoreIcon name="heart" />Избранное</span>
          <NavLink to="/cart" className="nav-icon">
            <StoreIcon name="bag" />Корзина{cart.count > 0 && `: ${cart.count} шт. на ${formatPrice(cart.total)}`}
          </NavLink>
          {me ? (
            <>
              {me.is_manager
                ? <NavLink to="/manager/orders">Заказы магазина</NavLink>
                : <NavLink to="/orders" title={me.username}>Мои заказы</NavLink>}
              <span className="planned" title="Уведомления появятся позже"><StoreIcon name="bell" />Уведомления</span>
              <button type="button" className="secondary" disabled={signOut.isPending} onClick={() => signOut.mutate()}>
                {signOut.isPending ? 'Выходим…' : 'Выйти'}
              </button>
            </>
          ) : <NavLink to="/login" onMouseEnter={() => void import('../auth/LoginPage')} onFocus={() => void import('../auth/LoginPage')}>Войти</NavLink>}
        </nav>
        <div className="theme-picker">
          <label htmlFor="shop-theme">Тема</label>
          <select id="shop-theme" value={theme} onChange={({ target }) => {
            if (target.value === 'light' || target.value === 'dark' || target.value === 'system') selectTheme(target.value)
          }}>
            <option value="system">Системная</option>
            <option value="light">Светлая</option>
            <option value="dark">Тёмная</option>
          </select>
        </div>
        {navigation.state !== 'idle' && <span className="progress" role="status">Загрузка…</span>}
        {signOut.error && <p className="error" role="alert">Выход не выполнен. {signOut.error.message}</p>}
      </header>
      <main ref={main} id="main" tabIndex={-1} className="shell layout"><Outlet /></main>
      <footer className="footer shell muted">
        <span className="footer-brand">Книжная полка</span>
        <span>Независимый книжный магазин</span>
        <span>Версия {import.meta.env.VITE_APP_VERSION ?? 'dev'} · Поддержка {window.shopConfig?.supportPhone}</span>
      </footer>
    </>
  )
}
