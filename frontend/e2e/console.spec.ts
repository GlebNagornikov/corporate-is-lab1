import { expect, test } from '@playwright/test'

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
