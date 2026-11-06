import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useSearchParams } from 'react-router'
import { categoriesQuery } from '../api/queries'
import { buildCategoryTree, type CategoryNode } from '../lib/categoryTree'

function CategoryItem({ node, active }: { node: CategoryNode; active: string | null }) {
  return (
    <li>
      <Link
        to={`/?category=${encodeURIComponent(node.slug)}`}
        aria-current={node.slug === active ? 'page' : undefined}
      >
        {node.name}
      </Link>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => <CategoryItem key={child.id} node={child} active={active} />)}
        </ul>
      )}
    </li>
  )
}

export default function CategoryNav() {
  const [searchParams] = useSearchParams()
  const { pathname } = useLocation()
  const categories = useQuery(categoriesQuery())
  const isCatalog = pathname === '/'
  const active = isCatalog ? searchParams.get('category') : null

  if (categories.isPending) return <p className="muted" role="status">Категории загружаются…</p>
  if (categories.isError) return <p className="error" role="alert">Не удалось загрузить категории.</p>

  return (
    <nav aria-label="Категории">
      <ul className="categories">
        <li><Link to="/" aria-current={isCatalog && !active ? 'page' : undefined}>Все товары</Link></li>
        {buildCategoryTree(categories.data).map((node) => (
          <CategoryItem key={node.id} node={node} active={active} />
        ))}
      </ul>
    </nav>
  )
}
