import { useQuery } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import { productQuery } from '../api/queries'
import { makeProduct } from '../test/fixtures'
import { renderRoute } from '../test/render'
import { server } from '../test/server'
import ReviewForm from './ReviewForm'
import Reviews from './Reviews'

const slug = 'bk-001'
const endpoint = '*/api/catalog/products/bk-001/reviews/'

function ProductRating() {
  const { data } = useQuery(productQuery(slug))
  return <p>Рейтинг товара: {data?.rating ?? '—'}</p>
}

test('звёзды управляются клавиатурой, отзыв и рейтинг обновляются после отправки', async () => {
  let published = false
  const review = {
    id: 1, rating: 4, text: 'Хорошая книга', author: 'buyer', created_at: '2026-11-07T12:00:00Z',
  }
  const post = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.json()).toEqual({ rating: 4, text: review.text })
    published = true
    return HttpResponse.json(review, { status: 201 })
  })
  server.use(
    http.get('*/api/catalog/products/bk-001/', () =>
      HttpResponse.json(makeProduct({ rating: published ? 4 : null }))),
    http.get(endpoint, () => HttpResponse.json(published ? [review] : [])),
    http.post(endpoint, post),
  )

  renderRoute(<><ReviewForm slug={slug} /><ProductRating /><Reviews slug={slug} /></>)
  const user = userEvent.setup()
  await screen.findByText('Отзывов пока нет.')
  await user.tab()
  expect(screen.getByRole('radio', { name: 'Оценка 1 из 5' })).toHaveFocus()
  await user.keyboard('[ArrowRight][ArrowRight][ArrowRight]')
  expect(screen.getByRole('radio', { name: 'Оценка 4 из 5' })).toBeChecked()
  await user.type(screen.getByLabelText('Текст отзыва'), review.text)
  await user.click(screen.getByRole('button', { name: 'Оставить отзыв' }))
  expect(await screen.findByText(review.text)).toBeInTheDocument()
  expect(await screen.findByText('Рейтинг товара: 4')).toBeInTheDocument()
  expect(post).toHaveBeenCalledOnce()
})

test('ошибка DRF в виде массива показана над формой, введённый текст сохранён', async () => {
  server.use(http.post(endpoint, () =>
    HttpResponse.json(['Вы уже оставили отзыв на этот товар.'], { status: 400 })))
  renderRoute(<ReviewForm slug={slug} />)
  const user = userEvent.setup()
  const input = screen.getByLabelText('Текст отзыва')
  await user.click(screen.getByRole('radio', { name: 'Оценка 5 из 5' }))
  await user.type(input, 'Повторный отзыв')
  await user.click(screen.getByRole('button', { name: 'Оставить отзыв' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('Вы уже оставили отзыв на этот товар.')
  expect(alert.nextElementSibling?.tagName).toBe('FORM')
  expect(input).toHaveValue('Повторный отзыв')
})
