import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { SessionProvider } from '../auth/SessionProvider'
import { logout, meQuery } from '../auth/session'
import { server } from '../test/server'
import FavoriteButton from './FavoriteButton'
import NotificationsLink from './NotificationsLink'
import { notificationsQuery, wishlistQuery } from './queries'

const buyer = {
  id: 1, username: 'buyer', email: '', first_name: '', last_name: '', is_manager: false,
}
const entry = {
  product_id: 1, product__name: 'Книга', product__slug: 'book', product__is_active: true,
}

function renderPersonal(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(meQuery().queryKey, buyer)
  const view = render(children, { wrapper: ({ children }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter><SessionProvider>{children}</SessionProvider></MemoryRouter>
    </QueryClientProvider>
  ) })
  return { client, ...view }
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

test.each([true, false])('избранное синхронно в двух местах и откатывается при отказе (%s)', async (success) => {
  let finishRequest!: () => void
  const requestGate = new Promise<void>((resolve) => { finishRequest = resolve })
  let stored = false
  server.use(
    http.get('*/api/wishlist/', () => HttpResponse.json(stored ? [entry] : [])),
    http.post('*/api/wishlist/', async () => {
      await requestGate
      stored = success
      return success
        ? HttpResponse.json({ product_id: entry.product_id }, { status: 201 })
        : HttpResponse.json({ detail: 'Сервис недоступен' }, { status: 503 })
    }),
  )
  renderPersonal(<><FavoriteButton entry={entry} /><FavoriteButton entry={entry} /></>)
  const [grid, detail] = screen.getAllByRole('button', { name: 'Избранное: Книга' })
  await waitFor(() => expect(grid).toBeEnabled())
  fireEvent.click(grid)
  try {
    await waitFor(() => {
      expect(grid).toHaveAttribute('aria-pressed', 'true')
      expect(detail).toHaveAttribute('aria-pressed', 'true')
      expect(detail).toBeDisabled()
    })
  } finally {
    finishRequest()
  }
  await waitFor(() => {
    expect(grid).toBeEnabled()
    expect(detail).toHaveAttribute('aria-pressed', String(success))
  })
  if (!success) {
    const alerts = await screen.findAllByRole('alert')
    expect(alerts).toHaveLength(2)
    for (const alert of alerts) expect(alert).toHaveTextContent('Сервис недоступен')
  }
})

test('счётчик обновляется по таймеру и при возврате, всплывают только новые уведомления', async () => {
  let count = 1
  server.use(http.get('*/api/notifications/', () => HttpResponse.json(
    Array.from({ length: count }, (_, index) => ({
      id: index + 1,
      product_name: `Книга ${index + 1}`,
      product_slug: `book-${index + 1}`,
      product_is_active: true,
      notified_at: '2026-01-01T00:00:00Z',
      read_at: null,
    })).reverse(),
  )))
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  const { client, unmount } = renderPersonal(<NotificationsLink userId={buyer.id} />)
  expect(await screen.findByRole('link', { name: 'Уведомления, непрочитанных: 1' })).toBeVisible()
  expect(screen.queryByText('Книга снова в наличии')).not.toBeInTheDocument()
  const invalidate = vi.spyOn(client, 'invalidateQueries')

  count = 2
  act(() => vi.advanceTimersByTime(29_999))
  expect(invalidate).not.toHaveBeenCalled()
  act(() => vi.advanceTimersByTime(1))
  expect(await screen.findByRole('link', { name: 'Уведомления, непрочитанных: 2' })).toBeVisible()
  expect(await screen.findByText('Книга 2')).toBeVisible()
  expect(screen.getByRole('link', { name: 'К книге' })).toHaveAttribute('href', '/products/book-2')
  fireEvent.click(screen.getByRole('button', { name: 'Закрыть' }))
  expect(screen.queryByText('Книга снова в наличии')).not.toBeInTheDocument()

  invalidate.mockClear()
  count = 3
  fireEvent(document, new Event('visibilitychange'))
  expect(invalidate).not.toHaveBeenCalled()
  visibility.mockReturnValue('visible')
  fireEvent(document, new Event('visibilitychange'))
  expect(await screen.findByRole('link', { name: 'Уведомления, непрочитанных: 3' })).toBeVisible()
  expect(await screen.findByText('Книга 3')).toBeVisible()
  expect(screen.queryByText('Ещё уведомлений:', { exact: false })).not.toBeInTheDocument()

  unmount()
  invalidate.mockClear()
  act(() => vi.advanceTimersByTime(30_000))
  fireEvent(document, new Event('visibilitychange'))
  expect(invalidate).not.toHaveBeenCalled()
})

test('выход удаляет уведомления и избранное из кэша пользователя', async () => {
  server.use(http.get('*/api/wishlist/', () => HttpResponse.json([entry])))
  const { client } = renderPersonal(<FavoriteButton entry={entry} />)
  expect(await screen.findByRole('button', { name: 'Избранное: Книга', pressed: true })).toBeVisible()
  client.setQueryData(notificationsQuery(buyer.id).queryKey, [])
  await act(async () => logout(client))
  expect(await screen.findByRole('link', { name: 'В избранное: Книга' })).toBeVisible()
  expect(client.getQueryData(wishlistQuery(buyer.id).queryKey)).toBeUndefined()
  expect(client.getQueryData(notificationsQuery(buyer.id).queryKey)).toBeUndefined()
})

test('ошибка удаления из избранного видна после повторного открытия карточки', async () => {
  server.use(
    http.get('*/api/wishlist/', () => HttpResponse.json([entry])),
    http.delete('*/api/wishlist/1/', () =>
      HttpResponse.json({ detail: 'Сервис недоступен' }, { status: 503 }),
    ),
  )
  const { rerender } = renderPersonal(<FavoriteButton key="first" entry={entry} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Избранное: Книга', pressed: true }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен')
  rerender(<FavoriteButton key="second" entry={entry} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен')
  expect(screen.getByRole('button', { name: 'Избранное: Книга', pressed: true })).toBeEnabled()
})
