import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { categories, makePage, makeProduct } from './fixtures'

export const handlers = [
  http.get('*/api/catalog/categories/', () => HttpResponse.json(categories)),
  http.get('*/api/catalog/products/', () =>
    HttpResponse.json(makePage([
      makeProduct(),
      makeProduct({ id: 2, name: 'Книга «Канбан»', slug: 'bk-007', sku: 'BK-007', price: '1190.00' }),
    ])),
  ),
]

export const server = setupServer(...handlers)
