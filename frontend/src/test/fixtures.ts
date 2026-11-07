import type { Category, Order, Product, ProductPage } from '../api/client'

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
  return {
    count: results.length, next: null, previous: null, total: null, suggestion: null, results,
    ...overrides,
  }
}

export function makeOrder(overrides: Partial<Order> = {}): Order {
  return {
    id: 7, status: 'new', status_display: 'Новый', full_name: 'Анна Смирнова',
    phone: '+79131234567', email: 'buyer@example.test', delivery_method: 'pickup',
    address: '', comment: '', promo_code: null, subtotal: '990.00',
    discount: '0.00', delivery_cost: '0.00', total: '990.00',
    items: [{ product: 1, product_name: 'Книга', quantity: 1, price: '990.00', total: '990.00' }],
    history: [], created_at: '2026-11-06T12:00:00Z', allowed_transitions: [], can_cancel: true,
    can_pay: true,
    ...overrides,
  }
}
