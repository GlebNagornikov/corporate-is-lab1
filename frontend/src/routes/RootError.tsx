import { Link } from 'react-router'
import RouteError from './RouteError'

export default function RootError() {
  return (
    <>
      <header className="header shell"><Link to="/" className="brand">Книжная полка</Link></header>
      <main className="shell layout"><RouteError /></main>
    </>
  )
}
