import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { expect, test, vi } from 'vitest'
import { createAppRoutes } from '../appRoutes'

test('сбой общего каркаса показывает отдельный экран ошибки со ссылкой на главную', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const routes = createAppRoutes(client)
  routes[0].Component = () => { throw new Error('Сбой каркаса') }
  const router = createMemoryRouter(routes, { initialEntries: ['/catalog'] })
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  try {
    render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)
    expect(await screen.findByRole('heading', { name: 'Что-то пошло не так' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'На главную' })).toHaveAttribute('href', '/')
  } finally {
    consoleError.mockRestore()
  }
})
