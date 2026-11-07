import { http, HttpResponse } from 'msw'
import { afterEach, expect, test, vi } from 'vitest'
import { tokens } from '../auth/tokens'
import { server } from '../test/server'
import { api, setSessionExpiredHandler, toApiError } from './client'

const invalidToken = () => HttpResponse.json({ detail: 'Недействительный токен' }, { status: 401 })

function latch() {
  let release!: () => void
  const promise = new Promise<void>((resolve) => { release = resolve })
  return { promise, release }
}

afterEach(() => {
  tokens.clear()
  setSessionExpiredHandler(() => {})
})

test('обновляет токен один раз и повторяет POST с исходным телом', async () => {
  tokens.save({ access: 'old', refresh: 'refresh-token' })
  const releaseMe = latch()
  const meStarted = latch()
  const checkout = {
    full_name: 'Анна',
    phone: '+79130000000',
    email: 'buyer@example.test',
    delivery_method: 'pickup',
  } as const
  const submitted: unknown[] = []
  const refresh = vi.fn(async ({ request }: { request: Request }) => {
    expect(request.headers.get('Authorization')).toBeNull()
    expect(await request.json()).toEqual({ refresh: 'refresh-token' })
    return HttpResponse.json({ access: 'new' })
  })
  server.use(
    http.post('*/api/auth/token/refresh/', refresh),
    http.get('*/api/auth/me/', async ({ request }) => {
      if (request.headers.get('Authorization') === 'Bearer new') {
        return HttpResponse.json({ username: 'buyer' })
      }
      meStarted.release()
      await releaseMe.promise
      return invalidToken()
    }),
    http.post('*/api/orders/', async ({ request }) => {
      submitted.push(await request.json())
      return request.headers.get('Authorization') === 'Bearer new'
        ? HttpResponse.json({ id: 1 }, { status: 201 })
        : invalidToken()
    }),
  )

  const me = api.GET('/api/auth/me/')
  await meStarted.promise
  try {
    const order = await api.POST('/api/orders/', { body: checkout })
    expect(order.response.status).toBe(201)
    expect(submitted).toEqual([checkout, checkout])
  } finally {
    releaseMe.release()
  }
  expect((await me).data?.username).toBe('buyer')
  expect(refresh).toHaveBeenCalledTimes(1)
  expect(tokens.access()).toBe('new')
  expect(tokens.refresh()).toBe('refresh-token')
})

test('при ошибке обновления завершает сессию один раз и повторяет запросы без JWT', async () => {
  tokens.save({ access: 'expired', refresh: 'expired-refresh' })
  const onExpired = vi.fn()
  setSessionExpiredHandler(onExpired)
  const refresh = vi.fn(invalidToken)
  server.use(
    http.post('*/api/auth/token/refresh/', refresh),
    http.get('*/api/catalog/categories/', ({ request }) =>
      request.headers.has('Authorization') ? invalidToken() : HttpResponse.json([]),
    ),
  )

  const responses = await Promise.all([
    api.GET('/api/catalog/categories/'),
    api.GET('/api/catalog/categories/'),
  ])
  expect(responses.map(({ response }) => response.status)).toEqual([200, 200])
  expect(refresh).toHaveBeenCalledTimes(1)
  expect(onExpired).toHaveBeenCalledTimes(1)
  expect(tokens.access()).toBeNull()
  expect(tokens.refresh()).toBeNull()
})

test('параллельные запросы используют один успешный refresh', async () => {
  tokens.save({ access: 'expired', refresh: 'refresh-token' })
  const bothRequestsStarted = latch()
  let expiredRequests = 0
  const refresh = vi.fn(async () => {
    await bothRequestsStarted.promise
    return HttpResponse.json({ access: 'new' })
  })
  server.use(
    http.post('*/api/auth/token/refresh/', refresh),
    http.get('*/api/auth/me/', ({ request }) => {
      if (request.headers.get('Authorization') === 'Bearer new') {
        return HttpResponse.json({ username: 'buyer' })
      }
      expiredRequests += 1
      if (expiredRequests === 2) bothRequestsStarted.release()
      return invalidToken()
    }),
  )

  const requests = await Promise.all([api.GET('/api/auth/me/'), api.GET('/api/auth/me/')])
  expect(requests.map(({ data }) => data?.username)).toEqual(['buyer', 'buyer'])
  expect(refresh).toHaveBeenCalledOnce()
  expect(tokens.access()).toBe('new')
})

test('не обновляет токен при неверном пароле или запросе гостя', async () => {
  tokens.save({ access: 'old', refresh: 'refresh-token' })
  const refresh = vi.fn(invalidToken)
  server.use(
    http.post('*/api/auth/token/refresh/', refresh),
    http.post('*/api/auth/token/', ({ request }) => {
      expect(request.headers.get('Authorization')).toBeNull()
      return invalidToken()
    }),
    http.get('*/api/auth/me/', invalidToken),
  )

  const login = await api.POST('/api/auth/token/', {
    body: { username: 'buyer', password: 'wrong' },
  })
  expect(login.response.status).toBe(401)
  expect(tokens.access()).toBe('old')
  tokens.clear()
  expect((await api.GET('/api/auth/me/')).response.status).toBe(401)
  expect(refresh).not.toHaveBeenCalled()
})

test('приводит общие и полевые ошибки DRF к единому формату', () => {
  const response = new Response(null, { status: 400 })
  expect(toApiError(response, { detail: 'Корзина пуста.' }).message).toBe('Корзина пуста.')
  expect(toApiError(response, ['Ошибка 1.', 'Ошибка 2.']).message).toBe('Ошибка 1. Ошибка 2.')
  const error = toApiError(response, { phone: ['Неверный номер.'], email: ['Обязательное поле.'] })
  expect(error.status).toBe(400)
  expect(error.message).toBe('Неверный номер.')
  expect(error.fields).toEqual({ phone: ['Неверный номер.'], email: ['Обязательное поле.'] })
})
