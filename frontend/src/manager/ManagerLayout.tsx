import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigation } from 'react-router'
import { loginPath, logout, meQuery } from '../auth/session'
import { useTheme } from '../lib/useTheme'

export function ManagerLayout() {
  const client = useQueryClient()
  const location = useLocation()
  const navigation = useNavigation()
  const { data: me } = useQuery(meQuery())
  const main = useRef<HTMLElement>(null)
  const { theme, selectTheme } = useTheme()
  const signOut = useMutation({ mutationFn: () => logout(client) })
  useEffect(() => {
    document.scrollingElement?.scrollTo?.(0, 0)
    main.current?.focus({ preventScroll: true })
  }, [location.pathname])

  if (signOut.isSuccess) return <Navigate to="/" replace />
  if (signOut.isPending && !me) return <p className="shell layout" role="status">Выходим…</p>
  if (!me) return <Navigate to={loginPath(location)} replace />
  if (!me.is_manager) return <Navigate to="/" replace />

  return (
    <>
      <a className="skip-link" href="#main">К содержимому</a>
      <header className="header shell">
        <Link to="/manager" className="brand">Кабинет сотрудника</Link>
        <div className="actions manager-account">
          <Link to="/">На витрину</Link>
          <button type="button" className="secondary" disabled={signOut.isPending}
            onClick={() => signOut.mutate()}>Выйти</button>
        </div>
        <label className="theme-picker">
          Тема
          <select value={theme} onChange={({ target: { value } }) => {
            if (value === 'system' || value === 'light' || value === 'dark') selectTheme(value)
          }}>
            <option value="system">Системная</option>
            <option value="light">Светлая</option>
            <option value="dark">Тёмная</option>
          </select>
        </label>
        {navigation.state !== 'idle' && <span className="progress" role="status">Загрузка…</span>}
        {signOut.error && <p className="error" role="alert">{signOut.error.message}</p>}
      </header>
      <nav className="nav shell manager-nav" aria-label="Разделы сотрудника">
        <NavLink to="/manager/orders">Заказы</NavLink>
        <NavLink to="/manager/catalog">Каталог</NavLink>
        <NavLink to="/manager/reviews">Отзывы</NavLink>
        <NavLink to="/manager/promos">Промокоды</NavLink>
        <NavLink to="/manager/reports">Отчёты</NavLink>
      </nav>
      <main className="shell layout" id="main" tabIndex={-1} ref={main}><Outlet /></main>
    </>
  )
}
