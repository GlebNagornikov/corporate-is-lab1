import type { QueryClient } from '@tanstack/react-query'
import { redirect } from 'react-router'
import { api, ApiError, requireData } from '../api/client'
import { productQuery } from '../api/queries'
import type { components } from '../api/schema'
import { requireManager } from '../auth/session'
import { tokens } from '../auth/tokens'
import { submitRouteForm } from '../lib/routeForm'
import { z } from '../lib/zod'
import { managerBookQuery, refreshCatalog, type ManagerBook } from './queries'
import { routeId } from './routes'

const integer = (min: number, max: number) => z.string().regex(/^\d+$/, 'Введите целое число.')
  .transform(Number).pipe(z.number().int().min(min).max(max))
const money = z.string().trim().transform((value) => value.replace(',', '.'))
  .pipe(z.string().regex(/^\d{1,8}(\.\d{1,2})?$/, 'Введите цену с точностью до копеек.')
    .refine((value) => Number(value) > 0, 'Цена должна быть больше нуля.'))
const text = (max: number) => z.string().trim().min(1, 'Заполните поле.').max(max)
const checked = z.enum(['true', 'false']).transform((value) => value === 'true')
const stock = integer(0, 2147483647)

const bookSchema = z.object({
  name: text(200),
  slug: text(200).regex(/^[a-zA-Z0-9_-]+$/, 'Используйте латиницу, цифры, дефис и подчёркивание.'),
  sku: text(32),
  category: integer(1, Number.MAX_SAFE_INTEGER),
  description: z.string().trim(),
  price: money.optional(),
  old_price: z.union([z.literal('').transform(() => null), money]),
  stock: stock.optional(),
  is_active: checked,
  author: text(200),
  publisher: text(200),
  year: integer(1450, 32767),
  language: text(80),
  binding: z.enum(['hardcover', 'paperback'], { error: 'Выберите переплёт.' }),
  isbn: z.string().transform((value) => value.replace(/[\s\-\u2010-\u2015]/g, ''))
    .pipe(z.string().regex(/^(\d{13})?$/, 'Укажите все 13 цифр ISBN или оставьте поле пустым.')),
  pages: integer(1, 2147483647),
  image: z.instanceof(File).optional(),
})

const variantSchema = z.object({ price: money, stock, is_active: checked })

async function readMultipart(request: Request) {
  const form = Object.fromEntries(await request.formData())
  if (form.image instanceof File && !form.image.name) delete form.image
  return form
}

function multipart(body: components['schemas']['PatchedManagerBookWriteRequest'], cover?: File) {
  const form = new FormData()
  for (const [key, value] of Object.entries(body)) {
    if (value !== undefined) form.set(key, value === null ? '' : String(value))
  }
  if (cover) form.set('image', cover)
  return form
}

export async function bookAction(request: Request, client: QueryClient, bookId?: string) {
  await requireManager(request, client)
  const id = bookId ? routeId(bookId, 'Книга не найдена.') : undefined
  const version = tokens.version()
  const variant = new URL(request.url).searchParams.get('variant')

  async function finish(book: ManagerBook) {
    if (version !== tokens.version()) throw new ApiError(401, 'Сессия изменилась. Войдите снова.')
    const key = managerBookQuery(book.id).queryKey
    await client.cancelQueries({ queryKey: key })
    if (version !== tokens.version()) throw new ApiError(401, 'Сессия изменилась. Войдите снова.')
    client.setQueryData(key, book)
    client.removeQueries({ queryKey: productQuery(book.slug).queryKey, exact: true })
    await refreshCatalog(client)
    return redirect(`/manager/catalog/${book.id}/edit?saved=${variant ? 'variant' : 'book'}`)
  }

  const mutationKey = ['manager', 'edit-book', bookId ?? 'new']
  if (variant && id) {
    const variantId = routeId(variant, 'Вариант не найден.')
    return submitRouteForm(request, variantSchema, client, mutationKey, async (body) =>
      finish(requireData(await api.PATCH('/api/manager/catalog/{id}/variants/{variant_id}/', {
        params: { path: { id, variant_id: variantId } }, body,
      }))), readMultipart)
  }

  return submitRouteForm(request, bookSchema, client, mutationKey, async ({ image, ...body }) => {
    if (id) {
      return finish(requireData(await api.PATCH('/api/manager/catalog/{id}/', {
        params: { path: { id } }, body, bodySerializer: () => multipart(body, image),
      })))
    }
    const { price, stock } = body
    if (!price) throw new ApiError(400, 'Укажите цену.', { price: ['Укажите цену.'] })
    return finish(requireData(await api.POST('/api/manager/catalog/', {
      body: { ...body, price, stock }, bodySerializer: (data) => multipart(data, image),
    })))
  }, readMultipart)
}
