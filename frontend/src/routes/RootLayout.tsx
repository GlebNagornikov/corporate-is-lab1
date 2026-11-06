import { Link, Outlet, useNavigation } from 'react-router'
import CategoryNav from '../components/CategoryNav'

export default function RootLayout() {
  const navigation = useNavigation()

  return (
    <>
      <header className="header">
        <Link to="/" className="brand">Магазин</Link>
        {navigation.state === 'loading' && <span className="progress" role="status">Загрузка…</span>}
      </header>
      <div className="layout">
        <aside><CategoryNav /></aside>
        <main><Outlet /></main>
      </div>
    </>
  )
}
