import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { expect, test } from 'vitest'
import { createAppRoutes } from '../appRoutes'
import { server } from '../test/server'

test('показывает «Не найдено», если загрузчик получает 404 от API товара', async () => {
  server.use(
    http.get('*/api/catalog/products/nope/', () =>
      HttpResponse.json({ detail: 'Товар не найден' }, { status: 404 }),
    ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(createAppRoutes(client), { initialEntries: ['/products/nope'] })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )

  expect(await screen.findByRole('heading', { name: 'Не найдено' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '← В каталог' })).toHaveAttribute('href', '/')
})
