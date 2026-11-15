import { randomBytes, randomUUID } from 'node:crypto'
import { expect, type APIRequestContext, type Page } from '@playwright/test'

type Credentials = { username: string; password: string }

export async function createBuyer(request: APIRequestContext): Promise<Credentials> {
  const username = `e2e-${randomUUID()}`
  const password = `Shop!${randomBytes(48).toString('base64url')}`
  const response = await request.post('/api/auth/register/', {
    data: { username, email: `${username}@example.test`, password },
  })
  const error = response.ok() ? '' : ` (${await response.text()})`
  expect(response.status(), `Регистрация тестового покупателя${error}`).toBe(201)
  return { username, password }
}

export async function submitLogin(page: Page, { username, password }: Credentials) {
  await page.getByLabel('Имя пользователя').fill(username)
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  const [response] = await Promise.all([
    page.waitForResponse((result) => result.url().endsWith('/api/auth/session/login/')),
    page.getByRole('button', { name: 'Войти', exact: true }).click(),
  ])
  expect(response.status()).toBe(200)
}

export async function loginAs(page: Page, credentials: Credentials, next: string) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`)
  await submitLogin(page, credentials)
  await expect(page).toHaveURL(next)
}

export async function payWithDemoCard(page: Page) {
  await page.locator('summary').filter({ hasText: 'Оплатить' }).click()
  await page.getByLabel('Номер карты').fill('4242424242424242')
  await page.getByLabel('Срок действия').fill(`12/${String(new Date().getFullYear() + 1).slice(-2)}`)
  await page.getByLabel('CVV').fill('123')
  await page.getByRole('button', { name: /^Оплатить / }).click()
}

export async function checkoutAsGuest(page: Page, buyer: Credentials): Promise<string> {
  await page.goto('/?category=books&in_stock=true')
  const addButton = page.getByRole('button', { name: 'В корзину', exact: true }).and(page.locator(':enabled'))
  const card = page.locator('.card').filter({ has: addButton }).first()
  const name = await card.getByRole('heading', { level: 2 }).innerText()
  await card.getByRole('button', { name: 'В корзину', exact: true }).click()
  await page.getByRole('link', { name: /Корзина: 1 шт\./ }).click()
  await page.getByRole('link', { name: 'Оформить заказ' }).click()
  await expect(page).toHaveURL('/login?next=%2Fcheckout')

  const [merged] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().endsWith('/api/cart/merge/') && response.request().method() === 'POST',
    ),
    submitLogin(page, buyer),
  ])
  expect(merged.status()).toBe(200)
  await expect(page).toHaveURL('/checkout')
  await page.getByLabel('Получатель').fill('Анна Смирнова')
  await page.getByLabel('Телефон').fill('+7 913 123-45-67')
  await page.getByRole('button', { name: 'Подтвердить заказ' }).click()
  await expect(page.getByText('Заказ оформлен. Спасибо!')).toBeVisible()
  await expect(page.getByRole('cell').filter({ hasText: name })).toBeVisible()
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  return new URL(page.url()).pathname.slice('/orders/'.length)
}
