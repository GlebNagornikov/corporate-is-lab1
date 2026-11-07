import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, test } from 'vitest'
import { makePage, makeProduct } from '../test/fixtures'
import { renderRoute } from '../test/render'
import { server } from '../test/server'
import ProductList from './ProductList'

test('показывает товары категории и сумму, рассчитанную сервером по всем страницам', async () => {
  server.use(
    http.get('*/api/catalog/products/', ({ request }) => {
      expect(new URL(request.url).searchParams.get('category')).toBe('books')
      return HttpResponse.json(makePage([makeProduct()], { count: 21, total: '1295.45' }))
    }),
  )
  renderRoute(<ProductList category="books" />)

  const link = await screen.findByRole('link', { name: 'Книга «Чистый код»' })
  expect(link).toHaveAttribute('href', '/products/bk-001')
  expect(screen.getByText('Итого по категории: 1 295,45 ₽')).toBeInTheDocument()
})
