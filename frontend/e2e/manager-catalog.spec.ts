import { randomUUID } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { createBuyer, loginAs } from './helpers.ts'

const manager = {
  username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
  password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
}
const cover = fileURLToPath(new URL('../../backend/catalog/demo_books/covers/anne.png', import.meta.url))

test('сотрудник создаёт черновик с обложкой, публикует и снимает книгу с продажи', async ({ page }) => {
  const suffix = randomUUID().slice(0, 8)
  const slug = `kt3-${suffix}`
  const name = `Книга КТ3 ${suffix}`
  await loginAs(page, manager, '/manager/catalog')
  await page.getByRole('link', { name: 'Добавить книгу' }).click()
  await expect(page).toHaveURL('/manager/catalog/new')
  await expect(page.getByRole('heading', { name: 'Новая книга' })).toBeVisible()
  await page.getByLabel('Название', { exact: true }).fill(name)
  await page.getByLabel('Автор', { exact: true }).fill('Тестовый Автор')
  await page.getByLabel('Адрес в URL').fill(slug)
  await page.getByLabel('Артикул (SKU)').fill(slug)
  await page.getByLabel('Жанр', { exact: true }).selectOption({ index: 1 })
  await page.getByLabel('Издательство').fill('Полка')
  await page.getByLabel('Год издания').fill('2025')
  await page.getByLabel('Число страниц').fill('224')
  await page.getByLabel('Переплёт').selectOption('hardcover')
  await page.getByLabel('Цена, ₽', { exact: true }).fill('325,50')
  await page.getByLabel('Остаток', { exact: true }).fill('4')

  const upload = page.getByLabel('Обложка (JPEG или PNG)')
  const save = page.getByRole('button', { name: 'Сохранить книгу' })
  await upload.setInputFiles({ name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('invalid') })
  const invalid = page.waitForResponse((result) =>
    result.url().endsWith('/api/manager/catalog/') && result.request().method() === 'POST')
  await save.click()
  expect((await invalid).status()).toBe(400)
  await expect(upload).toHaveAttribute('aria-invalid', 'true')

  await upload.setInputFiles(cover)
  const preview = page.getByRole('img', { name: 'Предпросмотр обложки' })
  await expect(preview).toHaveAttribute('src', /^blob:/)
  await expect.poll(() => preview.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  await save.click()
  await expect(page).toHaveURL(/\/manager\/catalog\/\d+\/edit\?saved=book$/)
  await expect(page.getByText('Книга сохранена.')).toBeVisible()
  await expect(page.getByLabel('Показывать на витрине')).not.toBeChecked()
  await expect(page.getByRole('img', { name: 'Текущая обложка' })).toBeVisible()
  expect((await page.request.get(`/api/catalog/products/${slug}/`)).status()).toBe(404)

  await page.getByRole('link', { name: 'К каталогу сотрудника' }).click()
  await page.getByLabel('Поиск по каталогу').fill(slug)
  await page.getByRole('button', { name: 'Найти' }).click()
  await expect(page).toHaveURL(`/manager/catalog?q=${slug}`)
  const row = page.getByRole('row').filter({ hasText: name })
  await expect(row.getByText('Скрыта')).toBeVisible()
  await row.getByRole('link', { name }).click()
  await expect(page).toHaveURL(/\/manager\/catalog\/\d+\/edit$/)
  const editPath = new URL(page.url()).pathname
  await page.setViewportSize({ width: 360, height: 780 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(360)
  await page.getByLabel('Цена, ₽', { exact: true }).fill('405')
  await page.getByLabel('Остаток', { exact: true }).fill('5')
  await page.getByLabel('Показывать на витрине').check()
  await save.click()
  await expect(page.getByRole('link', { name: 'Открыть на витрине' })).toBeVisible()
  await page.getByRole('link', { name: 'Открыть на витрине' }).click()
  await expect(page).toHaveURL(`/products/${slug}`)
  await expect(page.getByRole('heading', { name })).toBeVisible()
  const visible = await page.request.get(`/api/catalog/products/${slug}/`)
  expect(visible.status()).toBe(200)
  expect(await visible.json()).toMatchObject({ price: '405.00', stock: 5 })

  await page.goto(editPath)
  await page.getByLabel('Показывать на витрине').uncheck()
  await save.click()
  await expect(page.getByText('Книга сохранена.')).toBeVisible()
  await page.goto(`/products/${slug}`)
  await expect(page.getByRole('heading', { name: 'Не найдено' })).toBeVisible()
})

test('покупатель получает отказ на прямых ссылках кабинета', async ({ page, request }) => {
  const buyer = await createBuyer(request)
  await loginAs(page, buyer, '/orders')
  for (const path of ['/manager', '/manager/catalog', '/manager/catalog/new',
    '/manager/catalog/1/edit', '/manager/orders/1']) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible()
  }
})
