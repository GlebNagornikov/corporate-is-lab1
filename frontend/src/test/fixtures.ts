import type { Category, Product, ProductPage } from '../api/client'

const programming: Category = {
  id: 2,
  name: 'Программирование',
  slug: 'programming',
  parent: 'books',
}

export const categories: Category[] = [
  { id: 1, name: 'Книги', slug: 'books', parent: null },
  programming,
  { id: 3, name: 'Электроника', slug: 'electronics', parent: null },
]

export function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    name: 'Книга «Чистый код»',
    slug: 'bk-001',
    sku: 'BK-001',
    category: programming,
    description: 'Классика',
    variants: [],
    price: '1290.00',
    old_price: null,
    discount_percent: 0,
    stock: 30,
    in_stock: true,
    image: null,
    rating: null,
    reviews_count: 0,
    ...overrides,
  }
}

export function makePage(results: Product[], overrides: Partial<ProductPage> = {}): ProductPage {
  return { count: results.length, next: null, previous: null, total: null, results, ...overrides }
}
