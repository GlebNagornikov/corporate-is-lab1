import { randomUUID } from 'node:crypto'
import { expect, test, type APIRequestContext } from '@playwright/test'
import { createBuyer, loginAs, submitLogin } from './helpers.ts'

const bookPath = '/products/war-of-worlds-1898'
const detailPath = '/api/catalog' + bookPath + '/'
const reviewsPath = detailPath + 'reviews/'
const queuePath = '/manager/reviews'
const manager = {
  username: process.env.E2E_MANAGER_USERNAME ?? 'manager_demo',
  password: process.env.E2E_MANAGER_PASSWORD ?? 'DemoShop2026!',
}

async function authorize(request: APIRequestContext, credentials: typeof manager) {
  const token = await request.post('/api/auth/token/', { data: credentials })
  await expect(token).toBeOK()
  const { access } = await token.json() as { access: string }
  return { Authorization: `Bearer ${access}` }
}

async function deliver(
  request: APIRequestContext, product: number,
  buyer: Record<string, string>, staff: Record<string, string>,
) {
  await expect(await request.post('/api/cart/items/', {
    headers: buyer, data: { product, quantity: 1 },
  })).toBeOK()
  const order = await request.post('/api/orders/', {
    headers: buyer,
    data: {
      full_name: 'Демонстрационный читатель', phone: '+79131234567',
      email: 'e2e-review@example.test', delivery_method: 'pickup',
    },
  })
  expect(order.status()).toBe(201)
  const { id } = await order.json() as { id: number }
  await expect(await request.post(`/api/orders/${id}/simulate-payment/`, {
    headers: buyer, data: { outcome: 'success' },
  })).toBeOK()
  for (const status of ['confirmed', 'shipped', 'delivered']) {
    await expect(await request.post(`/api/manager/orders/${id}/status/`, {
      headers: staff, data: { status },
    })).toBeOK()
  }
}

test('М1: право после доставки, очередь, рейтинг и смена аккаунта', async ({
  browser, page, request, baseURL,
}) => {
  const buyer = await createBuyer(request)
  const other = await createBuyer(request)
  const buyerHeaders = await authorize(request, buyer)
  const otherHeaders = await authorize(request, other)
  const managerHeaders = await authorize(request, manager)
  const approvedText = `Публичный отзыв ${randomUUID()}`
  const rejectedText = `Скрытый отзыв ${randomUUID()}`
  const bookResponse = await request.get(detailPath)
  await expect(bookResponse).toBeOK()
  const book = await bookResponse.json() as { id: number; reviews_count: number }
  const initialHeading = `Отзывы (${book.reviews_count})`

  await page.goto(bookPath)
  await expect(page.getByRole('heading', { name: initialHeading })).toBeVisible()
  const formButton = page.getByRole('button', { name: 'Оставить отзыв' })
  await expect(formButton).toHaveCount(0)
  if (book.reviews_count > 5) {
    const reviews = page.locator('.reviews li')
    await expect(reviews).toHaveCount(5)
    await page.getByRole('button', { name: 'Показать ещё' }).click()
    await expect(reviews).toHaveCount(Math.min(10, book.reviews_count))
  }

  await loginAs(page, buyer, bookPath)
  await expect(page.getByText(/Отзыв доступен после доставки/)).toBeVisible()
  expect((await request.post(reviewsPath, {
    headers: buyerHeaders, data: { rating: 5, text: approvedText },
  })).status()).toBe(400)
  await deliver(request, book.id, buyerHeaders, managerHeaders)
  await page.reload()
  await expect(formButton).toBeVisible()
  await page.getByRole('radio', { name: 'Оценка 1 из 5' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('radio', { name: 'Оценка 2 из 5' })).toBeChecked()
  await page.keyboard.press('Tab')
  const reviewInput = page.getByLabel('Текст отзыва')
  await expect(reviewInput).toBeFocused()
  await reviewInput.fill(approvedText)
  await formButton.click()
  await expect(page.getByText('Ваш отзыв ожидает модерации.')).toBeVisible()
  await expect(page.getByText(approvedText)).toHaveCount(0)
  await expect(page.getByRole('heading', { name: initialHeading })).toBeVisible()
  expect((await request.post(reviewsPath, {
    headers: buyerHeaders, data: { rating: 1, text: 'Дубль' },
  })).status()).toBe(400)

  await deliver(request, book.id, otherHeaders, managerHeaders)
  expect((await request.post(reviewsPath, {
    headers: otherHeaders, data: { rating: 1, text: rejectedText },
  })).status()).toBe(201)
  const staffProfile = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  try {
    const staff = await staffProfile.newPage()
    await loginAs(staff, manager, queuePath)
    const approval = staff.getByRole('listitem').filter({ hasText: approvedText })
    const rejection = staff.getByRole('listitem').filter({ hasText: rejectedText })
    await approval.getByRole('button', { name: 'Одобрить' }).click()
    await expect(approval).toHaveCount(0)
    await rejection.getByRole('button', { name: 'Отклонить' }).click()
    await expect(rejection).toHaveCount(0)
  } finally {
    await staffProfile.close()
  }
  await page.reload()
  await expect(page.getByRole('heading', { name: `Отзывы (${book.reviews_count + 1})` })).toBeVisible()
  await expect(page.getByText(approvedText)).toBeVisible()
  await expect(page.getByText(rejectedText)).toHaveCount(0)
  await expect(page.getByText('Вы уже оставили отзыв на это издание.')).toBeVisible()

  // Переходы внутри SPA сохраняют общий Query-кэш.
  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.getByRole('link', { name: 'Войти', exact: true }).click()
  await submitLogin(page, other)
  await page.locator(`a[href="${bookPath}"]`).first().click()
  await expect(page.getByText('Ваш отзыв отклонён модератором.')).toBeVisible()
  await expect(formButton).toHaveCount(0)
  await page.goto(queuePath)
  await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible()
})
