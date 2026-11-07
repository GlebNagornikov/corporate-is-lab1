import { expect, test } from 'vitest'
import { categories } from '../test/fixtures'
import { buildCategoryTree } from './categoryTree'

test('дочерние категории вкладываются в родительские', () => {
  const tree = buildCategoryTree(categories)

  expect(tree.map((node) => node.slug)).toEqual(['books', 'electronics'])
  expect(tree[0].children.map((node) => node.slug)).toEqual(['programming'])
})
