import { act, fireEvent, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import CatalogPage from '../routes/CatalogPage'
import { makePage, makeProduct } from '../test/fixtures'
import { renderRoute } from '../test/render'
import { server } from '../test/server'

test('отправляет поиск и обе цены одним запросом через 300 мс после последнего ввода', async () => {
  const requests: URLSearchParams[] = []
  server.use(http.get('*/api/catalog/products/', ({ request }) => {
    const params = new URL(request.url).searchParams
    requests.push(params)
    const name = params.has('q') ? 'Отфильтрованный товар' : 'Исходный товар'
    return HttpResponse.json(makePage([makeProduct({ name })]))
  }))
  renderRoute(<CatalogPage />, '/?page=2')
  await screen.findByRole('link', { name: 'Исходный товар' })
  expect(requests).toHaveLength(1)

  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  try {
    fireEvent.change(screen.getByLabelText('Цена от'), { target: { value: '1' } })
    await act(() => vi.advanceTimersByTimeAsync(100))
    fireEvent.change(screen.getByLabelText('Цена от'), { target: { value: '100' } })
    fireEvent.change(screen.getByLabelText('Цена до'), { target: { value: '1500' } })
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'канбан' } })
    await act(() => vi.advanceTimersByTimeAsync(299))
    expect(requests).toHaveLength(1)
    expect(screen.getByTestId('location').textContent).toBe('/?page=2')
    await act(() => vi.advanceTimersByTimeAsync(1))
    await vi.waitFor(() => expect(requests).toHaveLength(2))
    expect(Object.fromEntries(requests[1])).toEqual({
      q: 'канбан', price_min: '100', price_max: '1500',
    })
  } finally {
    vi.useRealTimers()
  }
})
