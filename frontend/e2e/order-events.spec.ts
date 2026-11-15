import { expect, test } from '@playwright/test'
import { checkoutAsGuest, createBuyer, loginAs, payWithDemoCard } from './helpers.ts'

test('покупатель получает статусы из другого профиля и восстанавливает поток', async ({
  browser, page, request, baseURL,
}) => {
  test.setTimeout(60_000)
  await page.addInitScript(() => {
    const fetchRequest = window.fetch.bind(window)
    window.fetch = (input, init) => {
      if (!(input instanceof Request) || !new URL(input.url).pathname.endsWith('/events/')) {
        return fetchRequest(input, init)
      }
      const disconnect = new AbortController()
      const signal = AbortSignal.any([input.signal, disconnect.signal])
      window.addEventListener('disconnect-order-stream', () => disconnect.abort(), { once: true, signal })
      return fetchRequest(input, { ...init, signal })
    }
  })

  const managerProfile = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  try {
    const buyer = await createBuyer(request)
    const opened = page.waitForResponse((response) => response.url().endsWith('/events/'))
    const id = await checkoutAsGuest(page, buyer)
    const stream = await opened
    const path = `/api/orders/${id}/events/`
    expect(stream.status()).toBe(200)
    expect(stream.headers()['content-type']).toBe('text/event-stream')
    expect(new URL(stream.url()).search).toBe('')
    expect((await stream.request().headerValue('authorization'))?.startsWith('Bearer ')).toBe(true)

    const other = await createBuyer(request)
    const token = await request.post('/api/auth/token/', { data: other })
    await expect(token).toBeOK()
    const { access } = await token.json()
    expect((await request.get(path)).status()).toBe(401)
    expect((await request.get(path, { headers: { Authorization: `Bearer ${access}` } })).status()).toBe(404)

    const status = page.locator('.order-detail strong')
    const manager = await managerProfile.newPage()
    await loginAs(manager, {
      username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
      password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
    }, '/manager/orders?status=paid')
    const row = manager.getByRole('row').filter({
      has: manager.getByRole('link', { name: `№${id}`, exact: true }),
    })
    await expect(row).toHaveCount(0)
    await payWithDemoCard(page)
    await expect(status).toHaveText('Оплачен')
    await expect(row).toBeVisible({ timeout: 20_000 })
    const dialog = manager.getByRole('dialog')
    await row.getByRole('button', { name: 'Подтвердить', exact: true }).click()
    await dialog.getByRole('button', { name: 'Подтвердить действие' }).click()
    await expect(status).toHaveText('Подтверждён')
    await expect(page.locator('.order-detail li').filter({ hasText: 'Подтверждён' })).toBeVisible()

    let resume = () => {}
    const gate = new Promise<void>((resolve) => { resume = resolve })
    await page.route(`**${path}`, async (route) => {
      await gate
      await route.fulfill({ status: 401, json: { detail: 'Access token expired' } })
    }, { times: 1 })
    const retryStarted = page.waitForRequest((req) => req.url().endsWith(path))
    const refreshed = page.waitForResponse((response) =>
      response.url().endsWith('/api/auth/session/refresh/'),
    )
    await page.evaluate(() => window.dispatchEvent(new Event('disconnect-order-stream')))
    try {
      await retryStarted
      await manager.getByRole('combobox', { name: 'Статус', exact: true }).selectOption('confirmed')
      await row.getByRole('button', { name: 'Передать в доставку' }).click()
      const shipped = manager.waitForResponse((response) =>
        response.url().endsWith(`/api/manager/orders/${id}/status/`),
      )
      await dialog.getByRole('button', { name: 'Подтвердить действие' }).click()
      expect((await shipped).status()).toBe(200)
      await expect(status).toHaveText('Подтверждён')
    } finally {
      resume()
    }
    expect((await refreshed).status()).toBe(200)
    await expect(status).toHaveText('Передан в доставку')
    const closed = page.waitForEvent('requestfailed', { predicate: (req) => req.url().endsWith(path) })
    await page.getByRole('button', { name: 'Выйти' }).click()
    await closed
    await expect(page.getByRole('link', { name: 'Войти', exact: true })).toBeVisible()
  } finally {
    await managerProfile.close()
  }
})
