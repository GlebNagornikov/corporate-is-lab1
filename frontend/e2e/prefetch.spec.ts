import { expect, test } from '@playwright/test'

test('наведение загружает ленивые страницы до перехода', async ({ page, context }) => {
  const cdp = await context.newCDPSession(page)
  await cdp.send('Network.enable')
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false, latency: 100, downloadThroughput: 300_000, uploadThroughput: 100_000,
  })
  await page.goto('/')
  const loginChunk = page.waitForRequest((request) => /\/assets\/LoginPage-.*\.js/.test(request.url()))
  await page.getByRole('link', { name: 'Войти', exact: true }).hover()
  await loginChunk
  await expect(page).toHaveURL('/')

  const add = page.getByRole('button', { name: 'В корзину', exact: true }).and(page.locator(':enabled')).first()
  await add.click()
  await page.getByRole('link', { name: /Корзина: 1 шт\./ }).click()
  const checkoutChunk = page.waitForRequest((request) => /\/assets\/CheckoutPage-.*\.js/.test(request.url()))
  await page.getByRole('link', { name: 'Оформить заказ' }).hover()
  await checkoutChunk
  await expect(page).toHaveURL('/cart')
})
