import { expect, test } from '@playwright/test'
import type { components } from '../src/api/schema.d.ts'
import { createBuyer, loginAs } from './helpers.ts'

test('лимит после объединения корзин, проверка остатка и повтор оформления', async ({
  browser, page, request, baseURL,
}) => {
  test.setTimeout(60_000)
  const buyer = await createBuyer(request)
  const other = await createBuyer(request)
  const token = await request.post('/api/auth/token/', { data: other })
  await expect(token).toBeOK()
  const { access } = await token.json()
  const otherHeaders = { Authorization: `Bearer ${access}` }
  const catalog = await request.get('/api/catalog/products/?in_stock=true')
  await expect(catalog).toBeOK()
  const { results } = (await catalog.json()) as components['schemas']['PaginatedProductList']
  const book = results.find(({ stock = 0, variants }) =>
    stock >= 6 && stock <= 9 && variants.every((variant) => variant.is_default),
  )
  if (!book?.stock) throw new Error('Для проверки нужна книга с остатком 6–9 экземпляров без отдельных вариантов.')

  const add = (quantity: number, headers: Record<string, string>) => request.post('/api/cart/items/', {
    headers, data: { product: book.id, quantity },
  })
  const secondProfile = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  try {
    const second = await secondProfile.newPage()
    const [login] = await Promise.all([
      second.waitForResponse((response) => response.url().endsWith('/api/auth/session/login/')),
      loginAs(second, buyer, '/cart'),
    ])
    const { access: buyerAccess } = await login.json()
    await expect(await add(5, { Authorization: `Bearer ${buyerAccess}` })).toBeOK()

    await page.goto(`/products/${book.slug}`)
    await page.getByRole('button', { name: 'В корзину', exact: true }).click()
    await expect(page.getByRole('button', { name: 'В корзине: 1', exact: true })).toBeVisible()
    await loginAs(page, buyer, '/cart')
    await expect(page.getByText(/в корзине 6\. Уберите 1 экз\./)).toBeVisible()
    await expect(page.getByRole('link', { name: 'Оформить заказ' })).toHaveCount(0)

    await second.reload()
    await expect(second.getByText(/в корзине 6\. Уберите 1 экз\./)).toBeVisible()
    const [updated] = await Promise.all([
      second.waitForResponse((response) => response.request().method() === 'PATCH' &&
        response.url().includes('/api/cart/items/')),
      second.getByRole('button', { name: /Убрать одну штуку/ }).click(),
    ])
    expect(updated.status()).toBe(200)
  } finally {
    await secondProfile.close()
  }
  await page.reload()
  await page.getByRole('link', { name: 'Оформить заказ' }).click()
  const data = { full_name: 'Анна Смирнова', phone: '+7 913 123-45-67', email: 'checkout@example.test' }
  await page.getByLabel('Получатель').fill(data.full_name)
  await page.getByLabel('Телефон').fill(data.phone)
  await page.getByLabel('Электронная почта').fill(data.email)
  await page.getByLabel('Комментарий').fill('Позвонить заранее')

  // После загрузки формы второй покупатель забирает часть остатка.
  await expect(await add(book.stock - 4, otherHeaders)).toBeOK()
  const competingOrder = await request.post('/api/orders/', {
    headers: otherHeaders, data: { ...data, delivery_method: 'pickup' },
  })
  expect(competingOrder.status()).toBe(201)
  const { id } = await competingOrder.json()
  const submit = page.getByRole('button', { name: 'Подтвердить заказ' })
  await submit.click()
  await expect(page.getByRole('alert')).toContainText('осталось только 4 шт.')
  await expect(page.getByLabel('Телефон')).toHaveValue(data.phone)
  await expect(page.getByLabel('Комментарий')).toHaveValue('Позвонить заранее')

  await expect(await request.post(`/api/orders/${id}/cancel/`, { headers: otherHeaders })).toBeOK()
  await submit.click()
  await expect(page.getByText('Заказ оформлен. Спасибо!')).toBeVisible()
  const orderUrl = new URL(page.url()).pathname
  await expect(page.getByRole('row').filter({ hasText: book.name })).toBeVisible()
  await expect(page.getByRole('cell', { name: '5 шт.', exact: true })).toBeVisible()
  expect((await request.get(`/api${orderUrl}/`, { headers: otherHeaders })).status()).toBe(404)
  await page.getByRole('button', { name: 'Отменить заказ' }).click()
  await expect(page.locator('strong').getByText('Отменён', { exact: true })).toBeVisible()
})
