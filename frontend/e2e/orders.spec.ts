import { expect, test } from '@playwright/test'
import { checkoutAsGuest, createBuyer, loginAs } from './helpers.ts'

test('гость собирает корзину, входит и оформляет заказ', async ({ page, request }) => {
  const buyer = await createBuyer(request)
  const id = await checkoutAsGuest(page, buyer)
  await expect(page.getByRole('heading', { name: `Заказ №${id}` })).toBeVisible()
})

test('менеджер подтверждает заказ после учебной оплаты', async ({ page, request }) => {
  const buyer = await createBuyer(request)
  const id = await checkoutAsGuest(page, buyer)
  await page.locator('summary').filter({ hasText: 'Оплатить' }).click()
  await page.getByRole('button', { name: 'Успех', exact: true }).click()
  await expect(page.locator('strong').getByText('Оплачен', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Выйти' }).click()
  await expect(page.getByRole('link', { name: 'Войти', exact: true })).toBeVisible()
  await loginAs(page, {
    username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
    password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
  }, '/manager/orders?status=paid')
  const row = page.getByRole('row').filter({
    has: page.getByRole('link', { name: `№${id}`, exact: true }),
  })
  await expect(row.locator('.actions button')).toHaveText(['Подтвердить', 'Отменить'])
  await row.getByRole('button', { name: 'Подтвердить', exact: true }).click()
  await expect(row).toHaveCount(0)

  await page.getByRole('combobox', { name: 'Статус', exact: true }).selectOption('confirmed')
  await expect(page).toHaveURL('/manager/orders?status=confirmed')
  await expect(row.getByRole('cell', { name: 'Подтверждён', exact: true })).toBeVisible()
  await expect(row.getByRole('button', { name: 'Передать в доставку' })).toBeEnabled()
})

test('покупатель не попадает в раздел менеджера', async ({ page, request }) => {
  await loginAs(page, await createBuyer(request), '/manager/orders')
  await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible()
})
