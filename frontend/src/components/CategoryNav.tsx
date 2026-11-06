import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { categoriesQuery } from '../api/queries'
import { buildCategoryTree, type CategoryNode } from '../lib/categoryTree'

function categoryHref(searchParams: URLSearchParams, slug?: string) {
  const params = new URLSearchParams(searchParams)
  params.delete('page')
  if (slug) params.set('category', slug)
  else params.delete('category')
  const search = params.toString()
  return search ? `/?${search}` : '/'
}

function CategoryLinks({ nodes, searchParams }: {
  nodes: CategoryNode[]
  searchParams: URLSearchParams
}) {
  return (
    <ul>
      {nodes.map((node) => (
        <li key={node.slug}>
          <Link
            to={categoryHref(searchParams, node.slug)}
            aria-current={searchParams.get('category') === node.slug ? 'page' : undefined}
          >
            {node.name}
          </Link>
          {node.children.length > 0 && (
            <CategoryLinks nodes={node.children} searchParams={searchParams} />
          )}
        </li>
      ))}
    </ul>
  )
}

export default function CategoryNav() {
  const [searchParams] = useSearchParams()
  const categories = useQuery(categoriesQuery())

  return (
    <nav aria-label="Категории">
      <Link
        to={categoryHref(searchParams)}
        aria-current={!searchParams.has('category') ? 'page' : undefined}
      >
        Все категории
      </Link>
      {categories.isPending && <p role="status">Загрузка категорий…</p>}
      {categories.isError && <p role="alert">Не удалось загрузить категории.</p>}
      {categories.data && (
        <CategoryLinks nodes={buildCategoryTree(categories.data)} searchParams={searchParams} />
      )}
    </nav>
  )
}
