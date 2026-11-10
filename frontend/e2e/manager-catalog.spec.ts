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
  const storefront = await page.getByRole('link', { name: 'На витрину' }).boundingBox()
  const logout = await page.getByRole('button', { name: 'Выйти' }).boundingBox()
  expect(logout!.x - storefront!.x - storefront!.width).toBeGreaterThanOrEqual(18)
  const find = await page.getByRole('button', { name: 'Найти' }).boundingBox()
  const add = await page.getByRole('link', { name: 'Добавить книгу' }).boundingBox()
  expect(find!.width).toBeCloseTo(add!.width)
  expect(find!.height).toBeCloseTo(add!.height)
  await page.getByRole('link', { name: 'Добавить книгу' }).click()
  await expect(page).toHaveURL('/manager/catalog/new')
  await expect(page.getByRole('heading', { name: 'Новая книга' })).toBeVisible()
  await page.getByLabel('Название', { exact: true }).fill(name)
  await page.getByLabel('Автор', { exact: true }).fill('Тестовый Автор')
  await page.getByLabel('Адрес в URL').fill(slug)
  await page.getByLabel('Артикул (SKU)').fill(slug)
  const genre = page.getByLabel('Жанр', { exact: true })
  await expect(genre.locator('option').filter({ hasText: /^Книги$/ })).toHaveCount(0)
  await page.getByRole('button', { name: 'Добавить жанр' }).click()
  const dialog = page.getByRole('dialog', { name: 'Новый жанр' })
  const genreName = `Тестовый жанр ${suffix}`
  await dialog.getByLabel('Название жанра').fill(genreName)
  await dialog.getByRole('button', { name: 'Сохранить жанр' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(genre.locator('option:checked')).toHaveText(genreName)
  await expect(page.getByLabel('Название', { exact: true })).toHaveValue(name)
  for (const label of ['Артикул (SKU)', 'Жанр', 'Аннотация']) {
    const labelBox = await page.locator('label').filter({ hasText: label })
      .filter({ hasNot: page.locator('input, select, textarea') }).first().boundingBox()
    const inputBox = await page.getByLabel(label, { exact: true }).boundingBox()
    expect(inputBox!.y - labelBox!.y - labelBox!.height).toBeLessThanOrEqual(6)
  }
  const annotation = page.getByLabel('Аннотация', { exact: true })
  const textarea = await annotation.boundingBox()
  const fieldset = await annotation.locator('xpath=ancestor::fieldset').boundingBox()
  expect(textarea!.width / fieldset!.width).toBeGreaterThan(0.9)
  await page.getByLabel('Издательство').fill('Полка')
  await page.getByLabel('Год издания').fill('2025')
  await page.getByLabel('Число страниц').fill('224')
  await page.getByLabel('Переплёт').selectOption('hardcover')
  await page.getByLabel('Цена, ₽', { exact: true }).fill('325,50')
  await page.getByLabel('Остаток', { exact: true }).fill('4')

  const upload = page.getByLabel('Обложка (JPEG или PNG)')
  const save = page.getByRole('button', { name: 'Сохранить книгу' })
  const isbn = page.getByLabel('ISBN-13', { exact: true })
  await isbn.fill('978-5-17-1542')
  await save.click()
  await expect(isbn).toHaveAttribute('aria-invalid', 'true')
  await isbn.fill('978-0-14-044913-6')
  await expect(isbn).toHaveValue('978-0-14-044913-6')
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
  await expect(isbn).toHaveValue('9780140449136')
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
  for (const path of ['/manager', '/manager/catalog', '/manager/catalog/new', '/manager/catalog/import',
    '/manager/catalog/1/edit', '/manager/orders/1']) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible()
  }
})

test('сотрудник проверяет JSON, импортирует две книги и удаляет карточку', async ({ page }) => {
  const suffix = randomUUID().slice(0, 8)
  const slug = `import-${suffix}`
  const title = `Импорт ${suffix}`
  await loginAs(page, manager, '/manager/catalog')
  const current = page.getByRole('navigation', { name: 'Страницы каталога сотрудника' })
    .locator('[aria-current="page"]')
  await expect(current).toHaveText('Страница 1')
  expect(await current.evaluate((element) => parseFloat(getComputedStyle(element).paddingLeft))).toBeGreaterThan(8)
  expect(await current.evaluate((element) => parseFloat(getComputedStyle(element).borderRadius))).toBeGreaterThan(0)
  await page.getByRole('link', { name: 'Импорт JSON' }).click()
  await expect(page).toHaveURL('/manager/catalog/import')
  const template = await page.request.get('/manager-books.json')
  expect(template.ok()).toBe(true)
  expect(await template.json()).toEqual([expect.objectContaining({ sku: expect.any(String) })])
  const help = page.getByText(/Для новой книги используйте поля из шаблона/)
  const fieldFont = await help.locator('code').first().evaluate((field) => getComputedStyle(field).fontFamily)
  expect(fieldFont).toBe(await help.evaluate((paragraph) => getComputedStyle(paragraph).fontFamily))
  const input = page.getByLabel('Файл JSON')
  const check = page.getByRole('button', { name: 'Проверить JSON' })
  const apply = page.getByRole('button', { name: 'Импортировать книги' })
  const book = (number: number, year: number | string) => ({
    sku: `${slug}-${number}`, name: `${title} ${number}`, slug: `${slug}-${number}`,
    category: 'fairy-tales', price: '405.00', stock: 5, author: 'Автор', publisher: 'Полка',
    year, language: 'Русский', binding: 'hardcover', pages: 240, is_active: true,
  })
  async function select(secondYear: number | string) {
    const json = JSON.stringify([book(1, 2025), book(2, secondYear)])
    await input.setInputFiles({ name: 'books.json', mimeType: 'application/json', buffer: Buffer.from(json) })
  }
  await select('invalid')
  await check.click()
  await expect(page.getByRole('alert')).toContainText('Запись 2, year')
  await expect(apply).toBeDisabled()
  await select(2026)
  await check.click()
  await expect(page.getByText('Книг проверено — 2.')).toBeVisible()
  expect((await page.request.get(`/api/catalog/products/${slug}-1/`)).status()).toBe(404)
  await apply.click()
  await expect(page.getByText('Книг импортировано — 2.')).toBeVisible()

  await page.goto('/')
  const editorial = page.getByRole('region', { name: 'Выбор редакции' })
  await expect(editorial.locator('a[href="/products/wonderful-wizard-oz-1900"]')).toBeVisible()
  await page.goto(`/manager/catalog?q=${slug}`)
  await expect(page.getByRole('link', { name: `${title} 2`, exact: true })).toBeVisible()
  await page.getByRole('link', { name: `${title} 1`, exact: true }).click()
  await page.getByRole('button', { name: 'Удалить книгу', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: 'Удалить книгу?' })
  await expect(confirmation.getByRole('button', { name: 'Отмена' })).toBeFocused()
  await confirmation.getByRole('button', { name: 'Удалить книгу', exact: true }).click()
  await expect(page.getByText('Книга удалена.')).toBeVisible()
  expect((await page.request.get(`/api/catalog/products/${slug}-1/`)).status()).toBe(404)
  expect((await page.request.get(`/api/catalog/products/${slug}-2/`)).status()).toBe(200)
})
