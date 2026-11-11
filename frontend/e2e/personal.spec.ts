import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { createBuyer, loginAs } from './helpers.ts'

test('М3: избранное, отказ, пополнение из кабинета и личные уведомления', async ({
  browser, page, request, baseURL,
}, testInfo) => {
  test.setTimeout(75_000)
  const manager = {
    username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
    password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
  }
  const token = await request.post('/api/auth/token/', { data: manager })
  await expect(token).toBeOK()
  const { access } = await token.json() as { access: string }
  const headers = { Authorization: `Bearer ${access}` }
  const categories = await request.get('/api/manager/categories/', { headers })
  await expect(categories).toBeOK()
  const genres = await categories.json() as { id: number; slug: string }[]
  const category = genres.find((genre) => genre.slug === 'fairy-tales')
  expect(category).toBeDefined()
  const slug = `restock-${randomUUID().slice(0, 8)}`
  const title = `Тестовое издание ${slug}`
  const created = await request.post('/api/manager/catalog/', {
    headers,
    data: {
      category: category?.id, name: title, slug, sku: slug, price: '399.00',
      author: 'Анна Иванова', publisher: 'Полка', year: 2025, language: 'Русский',
      binding: 'hardcover', pages: 224, stock: 0, is_active: true,
    },
  })
  expect(created.status(), await created.text()).toBe(201)
  const { id } = await created.json() as { id: number }
  const detail = `/api/manager/catalog/${id}/`
  const staffProfile = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  try {
    const buyer = await createBuyer(request)
    const other = await createBuyer(request)
    await loginAs(page, buyer, `/catalog?q=${slug}`)
    const card = page.locator('.card').filter({ hasText: title })
    const favorite = card.getByRole('button', { name: `Избранное: ${title}` })
    await favorite.click()
    await expect(favorite).toHaveAttribute('aria-pressed', 'true')
    await expect(favorite).toBeEnabled()
    await page.screenshot({ path: testInfo.outputPath('catalog-desktop.png'), fullPage: true })
    await card.getByRole('link', { name: title }).click()
    const detailFavorite = page.getByRole('button', { name: `Избранное: ${title}` })
    await expect(detailFavorite).toHaveAttribute('aria-pressed', 'true')
    await page.route(`**/api/wishlist/${id}/`, (route) =>
      route.fulfill({ status: 503, json: { detail: 'Тестовый отказ' } }),
    )
    await detailFavorite.click()
    await expect(page.getByRole('alert').filter({ hasText: 'Тестовый отказ' })).toBeVisible()
    await expect(detailFavorite).toHaveAttribute('aria-pressed', 'true')
    await page.unroute(`**/api/wishlist/${id}/`)
    await page.getByRole('link', { name: 'Избранное', exact: true }).click()
    await expect(page.getByRole('link', { name: title })).toBeVisible()
    await page.setViewportSize({ width: 360, height: 900 })
    await page.screenshot({ path: testInfo.outputPath('wishlist-mobile.png'), fullPage: true })
    await page.getByRole('link', { name: title }).click()
    await page.getByRole('button', { name: 'Сообщить о поступлении' }).click()
    await expect(page.getByText('Сообщим, когда книга появится в наличии.')).toBeVisible()
    await page.reload()
    await expect(page.getByText('Сообщим, когда книга появится в наличии.')).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('book-mobile.png'), fullPage: true })

    const staff = await staffProfile.newPage()
    await loginAs(staff, manager, `/manager/catalog/${id}/edit`)
    await staff.getByLabel('Остаток', { exact: true }).fill('1')
    const saved = staff.waitForResponse((response) =>
      response.url().endsWith(detail) && response.request().method() === 'PATCH',
    )
    await staff.getByRole('button', { name: 'Сохранить книгу' }).click()
    const update = await saved
    expect(update.status(), await update.text()).toBe(200)
    await expect(await request.patch(detail, { headers, data: { stock: 2 } })).toBeOK()

    await page.bringToFront()
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
    const badge = page.getByRole('link', { name: 'Уведомления, непрочитанных: 1' })
    await expect(badge).toBeVisible()
    await badge.click()
    await expect(page.getByRole('link', { name: title })).toBeVisible()
    await expect(page.getByText('Книга снова в наличии')).toHaveCount(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(360)
    await page.screenshot({ path: testInfo.outputPath('notifications-mobile.png'), fullPage: true })
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.screenshot({ path: testInfo.outputPath('notifications-desktop.png'), fullPage: true })
    await page.getByRole('button', { name: 'Прочитать всё' }).click()
    await expect(badge).toHaveCount(0)
    await expect(page.getByText('Новое', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Выйти' }).click()
    await expect(page.getByRole('link', { name: /Уведомления/ })).toHaveCount(0)
    await loginAs(page, other, '/notifications')
    await expect(page.getByText('Здесь появятся сообщения', { exact: false })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Уведомления', exact: true })).toBeVisible()
  } finally {
    await staffProfile.close()
    await expect(await request.delete(detail, { headers })).toBeOK()
  }
})
