/// <reference lib="dom" />

import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { loginAs, payWithDemoCard } from './helpers.ts'

test('главная, темы и основные страницы работают на ширине 360 px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Книги, к которым возвращаются' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Выбор редакции' })).toBeVisible()

  const theme = page.getByLabel('Тема', { exact: true })
  await theme.selectOption('dark')
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(25, 21, 23)')
  await page.reload()
  await expect(theme).toHaveValue('dark')
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(25, 21, 23)')
  await theme.selectOption('light')
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(248, 244, 235)')
  await theme.selectOption('system')
  await page.emulateMedia({ colorScheme: 'dark' })
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(25, 21, 23)')
  await page.emulateMedia({ colorScheme: 'light' })

  async function checkLayout(title: string) {
    await expect(page).toHaveTitle(new RegExp(title))
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
  }
  await page.getByRole('link', { name: 'Открыть каталог' }).click()
  await checkLayout('Каталог')
  await page.getByRole('searchbox').fill('Война миров')
  await page.getByRole('link', { name: /^Война миров/ }).click()
  await checkLayout('Война миров')
  await page.getByRole('link', { name: 'Корзина', exact: true }).click()
  await checkLayout('Корзина')
  await page.getByRole('link', { name: 'Войти', exact: true }).click()
  await checkLayout('Вход')
  await page.getByRole('link', { name: 'Регистрация', exact: true }).click()
  await checkLayout('Регистрация')
  await page.goto('/missing-page')
  await checkLayout('Страница не найдена')
})

test('регистрация, поиск с фильтром, один заказ и смена статуса сотрудником', async ({
  page, browser, baseURL,
}) => {
  const username = `book-${randomUUID().slice(0, 12)}`
  const password = `Book!${randomUUID()}`
  await page.goto('/orders?page=1')
  await expect(page).toHaveURL('/login?next=%2Forders%3Fpage%3D1')
  await page.getByRole('link', { name: 'Регистрация', exact: true }).click()
  const register = page.getByRole('button', { name: 'Зарегистрироваться' })
  await register.click()
  await expect(page.getByText('Не короче 3 символов')).toBeVisible()
  await page.getByLabel('Имя пользователя').fill(username)
  await page.getByLabel('Электронная почта').fill(`${username}@example.test`)
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByLabel('Пароль ещё раз').fill(password)
  await register.click()
  await expect(page).toHaveURL('/orders?page=1')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Мои заказы' })).toBeVisible()

  await page.getByRole('link', { name: 'Каталог', exact: true }).click()
  await page.getByRole('searchbox').fill('Война миров')
  await expect(page).toHaveURL(/[?&]q=/)
  await page.getByRole('checkbox', { name: 'В наличии', exact: true }).click()
  await expect(page).toHaveURL(/[?&]in_stock=true/)
  const shared = await page.context().newPage()
  await shared.goto(page.url())
  await expect(shared.getByRole('searchbox')).toHaveValue('Война миров')
  await expect(shared.getByRole('checkbox', { name: 'В наличии', exact: true })).toBeChecked()
  await expect(shared.getByRole('link', { name: /^Война миров/ })).toBeVisible()
  await shared.close()
  await page.getByRole('link', { name: /^Война миров/ }).click()
  await expect(page).toHaveURL('/products/war-of-worlds-1898')
  await page.reload()
  await page.getByRole('button', { name: 'В корзину', exact: true }).click()
  await expect(page.getByRole('link', { name: /Корзина: 1 шт/ })).toBeVisible()
  await page.setViewportSize({ width: 360, height: 800 })
  await page.getByRole('link', { name: /Корзина: 1 шт/ }).click()
  await page.getByRole('link', { name: 'Оформить заказ' }).click()
  await expect(page).toHaveURL('/checkout')
  await page.reload()
  const submit = page.getByRole('button', { name: 'Подтвердить заказ' })
  await submit.click()
  await expect(page.getByText('Укажите имя получателя')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
  await page.getByLabel('Получатель').fill('Читатель Книжный')
  await page.getByLabel('Телефон').fill('+7 913 123-45-67')

  let writes = 0
  let release = () => {}
  const gate = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/orders/', async (route) => {
    if (route.request().method() === 'POST') {
      writes++
      await gate
    }
    await route.continue()
  })
  try {
    await page.locator('form').evaluate((form: HTMLFormElement) => {
      form.requestSubmit()
      form.requestSubmit()
    })
    await expect(page.getByRole('button', { name: 'Отправка…' })).toBeDisabled()
    await expect.poll(() => writes).toBe(1)
  } finally {
    release()
  }
  await expect(page.getByText('Заказ оформлен. Спасибо!')).toBeVisible()
  expect(writes).toBe(1)
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  const orderPath = new URL(page.url()).pathname
  const orderNumber = orderPath.split('/').at(-1)
  await page.reload()
  await expect(page.getByRole('cell', { name: /Война миров/ })).toBeVisible()
  await payWithDemoCard(page)
  const status = page.locator('.order-detail strong')
  await expect(status).toHaveText('Оплачен')
  await page.getByRole('link', { name: 'Мои заказы', exact: true }).click()
  await page.locator(`a[href="${orderPath}"]`).click()

  const staff = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  try {
    const manager = await staff.newPage()
    await loginAs(manager, {
      username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
      password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
    }, '/manager/orders?status=paid')
    await manager.reload()
    const row = manager.getByRole('row').filter({
      has: manager.getByRole('link', { name: `№${orderNumber}`, exact: true }),
    })
    const confirm = row.getByRole('button', { name: 'Подтвердить', exact: true })
    await confirm.focus()
    await manager.keyboard.press('Enter')
    const dialog = manager.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await manager.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(confirm).toBeFocused()
    await manager.keyboard.press('Enter')
    await dialog.getByRole('button', { name: 'Подтвердить действие' }).click()
    await expect(status).toHaveText('Подтверждён')
  } finally {
    await staff.close()
  }
})
