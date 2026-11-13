/// <reference lib="dom" />

import { expect, test } from '@playwright/test'
import type { components } from '../src/api/schema.d.ts'

type ProductPage = components['schemas']['PaginatedProductList']
const catalogUrl = '/catalog?category=books&ordering=price'
const secondUrl = `${catalogUrl}&page=2`
const apiUrl = '/api/catalog/products/?category=books&ordering=price'
const cards = '.catalog-results > .grid article h2 a'

test('дозагружает страницы по одной, возвращает список и позицию, открывает прямую ссылку', async ({ page, context }) => {
  const firstResponse = await page.request.get(apiUrl)
  const secondResponse = await page.request.get(`${apiUrl}&page=2`)
  await expect(firstResponse).toBeOK()
  await expect(secondResponse).toBeOK()
  const first: ProductPage = await firstResponse.json()
  const second: ProductPage = await secondResponse.json()
  const firstLinks = first.results.map((book) => `/products/${book.slug}`)
  const secondLinks = second.results.map((book) => `/products/${book.slug}`)
  let requests = 0
  let release = () => {}
  const slow = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/catalog/products/?*', async (route) => {
    if (new URL(route.request().url()).searchParams.get('page') === '2') {
      requests++
      await slow
    }
    await route.continue()
  })
  await page.goto(catalogUrl)
  const links = page.locator(cards)
  await expect(links).toHaveCount(firstLinks.length)

  try {
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await expect.poll(() => requests).toBe(1)
    await expect(page).toHaveURL(catalogUrl)
    const loading = page.getByRole('button', { name: 'Загружаем…' })
    await expect(loading).toBeDisabled()
    await loading.evaluate((button: HTMLButtonElement) => {
      button.click()
      button.click()
      window.scrollTo(0, 0)
      window.scrollTo(0, document.documentElement.scrollHeight)
    })
    const pageTwo = page.waitForResponse((response) => {
      const url = new URL(response.url())
      return url.pathname === '/api/catalog/products/' && url.searchParams.get('page') === '2'
    })
    release()
    expect((await pageTwo).ok()).toBe(true)
  } finally {
    release()
  }

  await expect(page).toHaveURL(secondUrl)
  await expect(links).toHaveCount(firstLinks.length + secondLinks.length)
  expect(await links.evaluateAll((elements) => elements.map((link) => link.getAttribute('href'))))
    .toEqual([...firstLinks, ...secondLinks])
  expect(requests).toBe(1)

  const opened = links.nth(firstLinks.length)
  await opened.evaluate((link) => link.scrollIntoView({ block: 'center' }))
  const position = await page.evaluate(() => window.scrollY)
  await opened.click()
  await expect(page).toHaveURL(secondLinks[0])
  await page.goBack()
  await expect(page).toHaveURL(secondUrl)
  await expect(links).toHaveCount(firstLinks.length + secondLinks.length)
  await expect(opened).toBeInViewport()
  await expect.poll(async () => Math.abs(await page.evaluate(() => window.scrollY) - position))
    .toBeLessThan(5)

  const shared = await context.newPage()
  // Check the initial shared page even when its short grid fits in the viewport.
  await shared.addInitScript(() => Reflect.deleteProperty(window, 'IntersectionObserver'))
  await shared.goto(secondUrl)
  await expect(shared).toHaveURL(secondUrl)
  await expect(shared.locator(cards)).toHaveCount(secondLinks.length)
  expect(await shared.locator(cards).evaluateAll((elements) => elements.map((link) => link.getAttribute('href'))))
    .toEqual(secondLinks)
})

test('клавиатура загружает следующую страницу и позволяет повторить запрос после ошибки', async ({ page }) => {
  await page.addInitScript(() => Reflect.deleteProperty(window, 'IntersectionObserver'))
  let requests = 0
  await page.route('**/api/catalog/products/?*', async (route) => {
    if (new URL(route.request().url()).searchParams.get('page') === '2' && ++requests === 1) {
      await route.fulfill({ status: 400, json: { detail: 'Пробный сбой' } })
      return
    }
    await route.continue()
  })
  await page.goto(catalogUrl)
  await page.getByRole('link', { name: '1', exact: true }).focus()
  await page.keyboard.press('Shift+Tab')
  const more = page.getByRole('button', { name: 'Показать ещё' })
  await expect(more).toBeFocused()
  const before = await page.locator(cards).count()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('alert')).toContainText('Пробный сбой')
  await expect(page.locator(cards)).toHaveCount(before)
  await expect(page).toHaveURL(catalogUrl)

  await expect(page.getByRole('button', { name: 'Повторить загрузку' })).toBeFocused()
  const [retried] = await Promise.all([
    page.waitForResponse((response) => {
      const url = new URL(response.url())
      return url.pathname === '/api/catalog/products/' && url.searchParams.get('page') === '2'
    }),
    page.keyboard.press('Enter'),
  ])
  expect(retried.ok()).toBe(true)
  await expect(page).toHaveURL(secondUrl)
  await expect.poll(() => page.locator(cards).count()).toBeGreaterThan(before)
  expect(requests).toBe(2)
})
