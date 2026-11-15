import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useSearchParams } from 'react-router'
import { categoriesQuery } from '../api/queries'
import { buildCategoryTree, type CategoryNode } from '../lib/categoryTree'

function CategoryItem({ node, active, pathname }: { node: CategoryNode; active: string | null; pathname: string }) {
  return (
    <li>
      <Link
        to={`${pathname}?category=${encodeURIComponent(node.slug)}`}
        aria-current={node.slug === active ? 'page' : undefined}
      >
        {node.name}
      </Link>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => <CategoryItem key={child.id} node={child} active={active} pathname={pathname} />)}
        </ul>
      )}
    </li>
  )
}

export default function CategoryNav() {
  const [searchParams] = useSearchParams()
  const { pathname } = useLocation()
  const categories = useQuery(categoriesQuery())
  const active = searchParams.get('category')

  if (categories.isPending) return <p className="muted" role="status">Категории загружаются…</p>
  if (categories.isError) return <p className="error" role="alert">Не удалось загрузить категории.</p>

  return (
    <nav aria-label="Категории">
      <p className="eyebrow">Жанры</p>
      <ul className="categories">
        <li><Link to={pathname === '/' && !active ? '/catalog' : pathname} aria-current={!active ? 'page' : undefined}>Все книги</Link></li>
        {buildCategoryTree(categories.data).map((node) => (
          <CategoryItem key={node.id} node={node} active={active} pathname={pathname} />
        ))}
      </ul>
    </nav>
  )
}
