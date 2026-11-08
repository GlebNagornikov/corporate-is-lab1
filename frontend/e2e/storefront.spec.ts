/// <reference lib="dom" />

import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

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
  await page.getByRole('link', { name: /Война миров/ }).click()
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

test('регистрация возвращает в кабинет, а двойное нажатие оформляет один заказ', async ({ page }) => {
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
  await page.getByRole('link', { name: /Война миров/ }).click()
  await page.getByRole('button', { name: 'В корзину', exact: true }).click()
  await expect(page.getByRole('link', { name: /Корзина: 1 шт/ })).toBeVisible()
  await page.setViewportSize({ width: 360, height: 800 })
  await page.getByRole('link', { name: /Корзина: 1 шт/ }).click()
  await page.getByRole('link', { name: 'Оформить заказ' }).click()
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
})
