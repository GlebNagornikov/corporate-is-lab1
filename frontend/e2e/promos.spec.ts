import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import type { components } from '../src/api/schema.d.ts'
import { createBuyer, loginAs } from './helpers.ts'

test('промокод переживает перезагрузку и вход, а заказ расходует его один раз', async ({
  browser, page, request, baseURL,
}) => {
  test.setTimeout(60_000)
  const buyer = await createBuyer(request)
  const catalog = await request.get('/api/catalog/products/?in_stock=true')
  await expect(catalog).toBeOK()
  const { results } = (await catalog.json()) as components['schemas']['PaginatedProductList']
  const book = results.find(({ price, stock = 0, variants }) =>
    stock >= 2 && Number(price) >= 500 && Number(price) < 1000 &&
    variants.every((variant) => variant.is_default),
  )
  if (!book) throw new Error('Нужно издание по цене от 500 до 999,99 ₽ с двумя экземплярами.')

  const managerProfile = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  const staff = await managerProfile.newPage()
  const code = `LAB8-${randomUUID().slice(0, 8).toUpperCase()}`
  const row = staff.getByRole('row').filter({ has: staff.getByRole('rowheader', { name: code }) })

  try {
    await loginAs(staff, {
      username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
      password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
    }, '/manager/promos')
    await staff.getByLabel('Код', { exact: true }).fill(code)
    await staff.getByLabel('Скидка, %').fill('10')
    await staff.getByLabel('Минимальная сумма, ₽').fill('1000')
    await staff.getByLabel('Действует с', { exact: true }).fill('2020-01-01T00:00')
    await staff.getByLabel('Действует по', { exact: true }).fill('2099-01-01T00:00')
    await staff.getByLabel('Лимит использований').fill('1')
    await staff.getByRole('button', { name: 'Создать промокод' }).click()
    await expect(row.getByRole('cell', { name: '0 / 1' })).toBeVisible()

    await page.goto(`/products/${book.slug}`)
    await page.getByRole('button', { name: 'В корзину', exact: true }).click()
    await page.getByRole('link', { name: /Корзина: 1 шт\./ }).click()
    const add = page.getByRole('button', { name: /Добавить одну штуку/ })
    const remove = page.getByRole('button', { name: /Убрать одну штуку/ })
    const apply = async () => {
      await page.getByLabel('Промокод', { exact: true }).fill(code.toLowerCase())
      await page.getByRole('button', { name: 'Применить', exact: true }).click()
    }
    await add.click()
    await apply()
    await expect(page.getByText('Код ' + code, { exact: false })).toBeVisible()
    await expect(page.getByText(/^Скидка /)).toBeVisible()
    await page.reload()
    await expect(page.getByText(/^Скидка /)).toBeVisible()

    await loginAs(page, buyer, '/cart')
    await page.reload()
    await expect(page.getByText(/^Скидка /)).toBeVisible()
    await remove.click()
    await expect(page.getByText(/сумме книг от 1000\.00/)).toBeVisible()
    await add.click()
    await expect(page.getByText(/^Скидка /)).toBeVisible()
    await staff.reload()
    await expect(row.getByRole('cell', { name: '0 / 1' })).toBeVisible()

    await page.getByRole('link', { name: 'Оформить заказ' }).click()
    await expect(page.getByLabel('Промокод', { exact: true })).toHaveValue(code)
    await page.getByLabel('Получатель').fill('Анна Смирнова')
    await page.getByLabel('Телефон').fill('+7 913 123-45-67')
    await page.getByRole('button', { name: 'Подтвердить заказ' }).click()
    await expect(page.getByText('Заказ оформлен. Спасибо!')).toBeVisible()
    await expect(page.locator('dt').filter({ hasText: 'Скидка (' + code })).toBeVisible()
    await staff.reload()
    await expect(row.getByRole('cell', { name: '1 / 1' })).toBeVisible()

    await page.getByRole('button', { name: 'Отменить заказ' }).click()
    await expect(page.locator('strong').getByText('Отменён', { exact: true })).toBeVisible()
    await page.goto(`/products/${book.slug}`)
    await page.getByRole('button', { name: 'В корзину', exact: true }).click()
    await page.getByRole('link', { name: /Корзина: 1 шт\./ }).click()
    await add.click()
    await apply()
    await expect(page.getByRole('alert')).toContainText('исчерпан')

    await row.getByRole('button', { name: 'Деактивировать ' + code }).click()
    await expect(row.getByRole('cell', { name: 'Деактивирован' })).toBeVisible()
    await apply()
    await expect(page.getByRole('alert')).toContainText('деактивирован')
    await expect(row.getByRole('cell', { name: '1 / 1' })).toBeVisible()
  } finally {
    await managerProfile.close()
  }
})
