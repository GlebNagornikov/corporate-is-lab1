import { expect, test } from '@playwright/test'
import { createBuyer } from './helpers.ts'

test('страницы магазина не вызывают ошибок JavaScript и нарушений CSP', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  await page.goto('/?category=books&q=война%20миров')
  await page.getByRole('link', { name: /Война миров/ }).first().click()
  await expect(page).toHaveURL(/\/products\/war-of-worlds-1898/)
  await page.getByRole('link', { name: /Корзина/ }).click()
  await page.getByRole('link', { name: 'Войти', exact: true }).click()
  await page.getByRole('link', { name: 'Регистрация' }).click()
  await page.waitForLoadState('networkidle')
  expect(errors).toEqual([])
})

test('nginx обслуживает страницы сравнения и адресной книги Django', { tag: '@https' }, async ({ page, request, baseURL }) => {
  test.skip(!baseURL?.startsWith('https:'), 'Проверка маршрутизации HTTPS-стенда')
  await page.goto('/product/war-of-worlds-1898/')
  await expect(page.getByRole('heading', { name: /Война миров/ })).toBeVisible()
  await page.getByRole('button', { name: 'Сравнить' }).click()
  await page.getByRole('link', { name: 'Сравнение', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Сравнение товаров' })).toBeVisible()
  await expect(page.getByRole('table').getByRole('link', { name: /Война миров/ })).toBeVisible()

  const buyer = await createBuyer(request)
  await page.goto('/accounts/addresses/')
  await expect(page).toHaveURL(/\/accounts\/login\//)
  await page.locator('[name="username"]').fill(buyer.username)
  await page.locator('[name="password"]').fill(buyer.password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Адресная книга' })).toBeVisible()
})
