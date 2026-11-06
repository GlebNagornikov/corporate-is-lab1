import type { Category } from '../api/client'

export type CategoryNode = Category & { children: CategoryNode[] }

export function buildCategoryTree(categories: Category[]): CategoryNode[] {
  const nodes = new Map<string, CategoryNode>(
    categories.map((category) => [category.slug, { ...category, children: [] }]),
  )
  const roots: CategoryNode[] = []

  for (const node of nodes.values()) {
    const parent = node.parent ? nodes.get(node.parent) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }

  return roots
}
