import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { categories, makePage, makeProduct } from './fixtures'

export const handlers = [
  http.get('*/api/auth/session/csrf/', () => HttpResponse.json({ csrf_token: 'csrf-token' })),
  http.post('*/api/auth/session/refresh/', () => HttpResponse.json({}, { status: 401 })),
  http.post('*/api/auth/session/logout/', () => new HttpResponse(null, { status: 204 })),
  http.get('*/api/catalog/categories/', () => HttpResponse.json(categories)),
  http.get('*/api/catalog/editorial/', () => HttpResponse.json([])),
  http.get('*/api/catalog/products/', () =>
    HttpResponse.json(makePage([
      makeProduct(),
      makeProduct({ id: 2, name: 'Книга «Канбан»', slug: 'bk-007', sku: 'BK-007', price: '1190.00' }),
    ])),
  ),
  http.get('*/api/catalog/products/:slug/', () => HttpResponse.json({}, { status: 404 })),
]

export const server = setupServer(...handlers)
