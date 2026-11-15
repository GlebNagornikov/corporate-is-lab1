import { useQuery } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import { reviewEligibilityQuery } from '../api/queries'
import { renderRoute } from '../test/render'
import { server } from '../test/server'
import ReviewForm from './ReviewForm'
import Reviews from './Reviews'

const slug = 'bk-001'
const endpoint = '*/api/catalog/products/bk-001/reviews/'

function EligibleReviewForm() {
  const { data } = useQuery(reviewEligibilityQuery(slug, 1))
  return data?.can_review ? <ReviewForm slug={slug} buyerId={1} /> : <p>{data?.message}</p>
}

test('звёзды управляются клавиатурой, новый отзыв ожидает модерации', async () => {
  let submitted = false
  const review = {
    id: 1, rating: 4, text: 'Хорошая книга', author: 'buyer', created_at: '2026-11-07T12:00:00Z',
  }
  const post = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.json()).toEqual({ rating: 4, text: review.text })
    submitted = true
    return HttpResponse.json(review, { status: 201 })
  })
  server.use(
    http.get('*/api/catalog/products/bk-001/review-eligibility/', () =>
      HttpResponse.json({ can_review: !submitted, message: submitted ? 'Ваш отзыв ожидает модерации.' : '' })),
    http.get(endpoint, () => HttpResponse.json({ count: 0, next: null, previous: null, results: [] })),
    http.post(endpoint, post),
  )

  renderRoute(<><EligibleReviewForm /><Reviews slug={slug} /></>)
  const user = userEvent.setup()
  await screen.findByText('Отзывов пока нет.')
  await screen.findByRole('radio', { name: 'Оценка 1 из 5' })
  await user.tab()
  expect(screen.getByRole('radio', { name: 'Оценка 1 из 5' })).toHaveFocus()
  await user.keyboard('[ArrowRight][ArrowRight][ArrowRight]')
  expect(screen.getByRole('radio', { name: 'Оценка 4 из 5' })).toBeChecked()
  await user.type(screen.getByLabelText('Текст отзыва'), review.text)
  await user.click(screen.getByRole('button', { name: 'Оставить отзыв' }))
  expect(await screen.findByText('Ваш отзыв ожидает модерации.')).toBeInTheDocument()
  expect(screen.queryByText(review.text)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Оставить отзыв' })).not.toBeInTheDocument()
  expect(post).toHaveBeenCalledOnce()
})

test('ошибка DRF в виде массива показана над формой, введённый текст сохранён', async () => {
  server.use(http.post(endpoint, () =>
    HttpResponse.json(['Вы уже оставили отзыв на этот товар.'], { status: 400 })))
  renderRoute(<ReviewForm slug={slug} buyerId={1} />)
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

test('Показать ещё добавляет вторую страницу к первой', async () => {
  const review = { rating: 5, author: 'buyer', created_at: '2026-11-07T12:00:00Z' }
  const get = vi.fn(({ request }: { request: Request }) => {
    const first = new URL(request.url).searchParams.get('page') === '1'
    return HttpResponse.json({
      count: 2,
      next: first ? '?page=2' : null,
      previous: first ? null : '?page=1',
      results: first
        ? [{ ...review, id: 2, text: 'Свежий отзыв' }]
        : [{ ...review, id: 1, text: 'Ранний отзыв' }],
    })
  })
  server.use(http.get(endpoint, get))
  renderRoute(<Reviews slug={slug} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Показать ещё' }))
  expect(await screen.findByText('Ранний отзыв')).toBeInTheDocument()
  expect(screen.getAllByText('Свежий отзыв')).toHaveLength(1)
  expect(get).toHaveBeenCalledTimes(2)
  expect(screen.queryByRole('button', { name: 'Показать ещё' })).not.toBeInTheDocument()
})
