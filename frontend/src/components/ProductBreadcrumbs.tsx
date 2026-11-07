import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import type { Category } from '../api/client'
import { categoriesQuery } from '../api/queries'

export default function ProductBreadcrumbs({ category, name }: { category: Category; name: string }) {
  const { data: categories = [] } = useQuery(categoriesQuery())
  const bySlug = new Map(categories.map((item) => [item.slug, item]))
  const path = [category]
  const visited = new Set([category.slug])
  let parent = category.parent

  while (parent && !visited.has(parent)) {
    const ancestor = bySlug.get(parent)
    if (!ancestor) break
    path.push(ancestor)
    visited.add(parent)
    parent = ancestor.parent
  }

  return (
    <nav aria-label="Хлебные крошки">
      <ol className="breadcrumbs">
        <li><Link to="/">Каталог</Link></li>
        {path.reverse().map(({ slug, name: categoryName }) => (
          <li key={slug}><Link to={`/?category=${encodeURIComponent(slug)}`}>{categoryName}</Link></li>
        ))}
        <li aria-current="page">{name}</li>
      </ol>
    </nav>
  )
}
