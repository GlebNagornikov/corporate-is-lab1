import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { api, requireData } from '../api/client'
import { productQuery } from '../api/queries'
import { applyServerErrors } from '../lib/serverErrors'
import { z } from '../lib/zod'

const ratings = [1, 2, 3, 4, 5]
const schema = z.object({
  rating: z.string().regex(/^[1-5]$/, 'Выберите оценку').transform(Number),
  text: z.string().trim().min(1, 'Введите текст отзыва'),
})

export default function ReviewForm({ slug }: { slug: string }) {
  const client = useQueryClient()
  const { register, control, handleSubmit, reset, setError, formState: { errors, isSubmitting } } =
    useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
      resolver: zodResolver(schema), defaultValues: { rating: '', text: '' },
    })
  const rating = Number(useWatch({ control, name: 'rating' }))

  async function submit(body: z.output<typeof schema>) {
    try {
      requireData(await api.POST('/api/catalog/products/{slug}/reviews/', {
        params: { path: { slug } }, body,
      }))
      reset()
      // Ключ карточки является префиксом ключа отзывов.
      await client.invalidateQueries({ queryKey: productQuery(slug).queryKey })
    } catch (error) {
      applyServerErrors(error, setError, ['rating', 'text'])
    }
  }

  return (
    <>
      {errors.root?.message && <p className="error" role="alert">{errors.root.message}</p>}
      <form className="form" onSubmit={handleSubmit(submit)}>
        <fieldset className="rating" aria-describedby={errors.rating ? 'rating-error' : undefined}>
          <legend>Оценка</legend>
          {ratings.map((value) => (
            <label key={value}>
              <input type="radio" value={value} aria-label={`Оценка ${value} из 5`}
                {...register('rating')} />
              <span aria-hidden="true">{value <= rating ? '★' : '☆'}</span>
            </label>
          ))}
          {errors.rating && <p className="error" id="rating-error">{errors.rating.message}</p>}
        </fieldset>
        <label className="form-field">
          Текст отзыва
          <textarea rows={3} aria-invalid={Boolean(errors.text)}
            aria-describedby={errors.text ? 'review-error' : undefined} {...register('text')} />
        </label>
        {errors.text && <p className="error" id="review-error">{errors.text.message}</p>}
        <button type="submit" disabled={isSubmitting}>Оставить отзыв</button>
      </form>
    </>
  )
}
