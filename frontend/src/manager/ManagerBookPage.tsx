import { useSuspenseQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useFetcher, useParams, useSearchParams } from 'react-router'
import type { Category, Variant } from '../api/client'
import FormInput from '../components/FormInput'
import { formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import type { bookAction } from './bookAction'
import BookDeleteDialog from './BookDeleteDialog'
import GenreDialog from './GenreDialog'
import { managerBookQuery, managerCategoriesQuery, type ManagerBook } from './queries'

type BookAction = typeof bookAction

function Availability({ checked, label }: { checked?: boolean; label: string }) {
  return <label className="manager-check">
    <input type="hidden" name="is_active" value="false" />
    <input type="checkbox" name="is_active" value="true" defaultChecked={checked} />
    {label}
  </label>
}

function CoverInput({ current, error }: { current?: string | null; error?: string }) {
  const objectUrl = useRef<string>(undefined)
  const [preview, setPreview] = useState<string>()
  useEffect(() => () => {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
  }, [])
  const source = preview ?? current
  return (
    <div className="form-field">
      <FormInput name="image" type="file" label="Обложка (JPEG или PNG)" accept="image/jpeg,image/png"
        error={error} onChange={({ target }) => {
          if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
          const file = target.files?.[0]
          objectUrl.current = file ? URL.createObjectURL(file) : undefined
          setPreview(objectUrl.current)
        }} />
      <small className="muted">Файл до 5 МБ. Для обложки подойдёт, например, 1200 × 1800 px.</small>
      {source && <img className="manager-cover" src={source} alt={preview ? 'Предпросмотр обложки' : 'Текущая обложка'} />}
    </div>
  )
}

function VariantForm({ bookId, variant }: { bookId: number; variant: Variant }) {
  const fetcher = useFetcher<BookAction>()
  const pending = fetcher.state !== 'idle'
  const fields = fetcher.data?.fields
  return (
    <fetcher.Form className="form manager-variant" method="post" encType="multipart/form-data"
      action={`/manager/catalog/${bookId}/edit?variant=${variant.id}`} aria-busy={pending}>
      <h3>{variant.name} · {variant.sku}</h3>
      <fieldset disabled={pending} className="manager-fields">
        <FormInput name="price" label="Цена варианта, ₽" inputMode="decimal"
          required defaultValue={variant.price} error={fields?.price?.join(' ')} />
        <FormInput name="stock" label="Остаток варианта" type="number" min={0} required
          defaultValue={variant.stock} error={fields?.stock?.join(' ')} />
        <Availability checked={variant.is_active} label="Вариант доступен" />
      </fieldset>
      {fetcher.data && <p className="error" role="alert">{fetcher.data.message}</p>}
      <button type="submit" disabled={pending}>{pending ? 'Сохраняем…' : 'Сохранить вариант'}</button>
    </fetcher.Form>
  )
}

function BookEditor({ book, categories }: { book?: ManagerBook; categories: Category[] }) {
  const fetcher = useFetcher<BookAction>()
  const [category, setCategory] = useState(book?.category.id)
  const [addingGenre, setAddingGenre] = useState(false)
  const [deletingBook, setDeletingBook] = useState(false)
  const [search] = useSearchParams()
  const edition = book?.book
  const variants = book?.variants.filter((variant) => !variant.is_default) ?? []
  const hasVariants = variants.length > 0
  const pending = fetcher.state !== 'idle'
  const title = book ? 'Редактирование книги' : 'Новая книга'
  usePageTitle(title)

  function error(field: string) { return fetcher.data?.fields[field]?.join(' ') }

  return (
    <section className="details manager-editor">
      <div className="manager-toolbar">
        <h1>{title}</h1>
        <Link to="/manager/catalog">К каталогу сотрудника</Link>
        {book?.is_active && <Link to={`/products/${book.slug}`}>Открыть на витрине</Link>}
      </div>
      {!fetcher.data && search.has('saved') && (
        <p className="success" role="status">{search.get('saved') === 'variant' ? 'Вариант сохранён.' : 'Книга сохранена.'}</p>
      )}
      <fetcher.Form className="form" method="post" encType="multipart/form-data" aria-busy={pending}
        action={book ? `/manager/catalog/${book.id}/edit` : '/manager/catalog/new'}>
        <fieldset className="manager-fields" disabled={pending}>
          <legend>Карточка книги</legend>
          <FormInput label="Название" name="name" required maxLength={200} defaultValue={book?.name} error={error('name')} />
          <FormInput label="Автор" name="author" required maxLength={200} defaultValue={edition?.author} error={error('author')} />
          <FormInput label="Адрес в URL" name="slug" required maxLength={200} readOnly={Boolean(book)}
            defaultValue={book?.slug} placeholder="nazvanie-knigi" error={error('slug')} />
          <FormInput label="Артикул (SKU)" name="sku" required maxLength={32} readOnly={Boolean(book)}
            defaultValue={book?.sku} error={error('sku')} />
          <div className="form-field manager-genre">
            <label htmlFor="book-genre">Жанр</label>
            <select id="book-genre" name="category" required
              value={categories.some(({ id }) => id === category) ? category : ''}
              onChange={({ target }) => setCategory(Number(target.value))}
              aria-invalid={Boolean(error('category'))} aria-describedby={error('category') ? 'book-genre-error' : undefined}>
              <option value="">Выберите жанр</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
            {error('category') && <p className="error" id="book-genre-error">{error('category')}</p>}
            <div className="actions">
              <button type="button" className="secondary" onClick={() => setAddingGenre(true)}>Добавить жанр</button>
            </div>
          </div>
          <div className="form-field manager-wide">
            <label htmlFor="book-description">Аннотация</label>
            <textarea id="book-description" name="description" rows={4} defaultValue={book?.description}
              aria-invalid={Boolean(error('description'))}
              aria-describedby={error('description') ? 'book-description-error' : undefined} />
            {error('description') && <p className="error" id="book-description-error">{error('description')}</p>}
          </div>
          <CoverInput key={book?.image} current={book?.image} error={error('image')} />
        </fieldset>
        <fieldset className="manager-fields" disabled={pending}>
          <legend>Параметры издания</legend>
          <FormInput label="Издательство" name="publisher" required maxLength={200}
            defaultValue={edition?.publisher} error={error('publisher')} />
          <FormInput label="Язык" name="language" required maxLength={80}
            defaultValue={edition?.language ?? 'Русский'} error={error('language')} />
          <FormInput label="Год издания" name="year" type="number" min={1450} max={32767} required
            defaultValue={edition?.year} error={error('year')} />
          <FormInput label="Число страниц" name="pages" type="number" min={1} required
            defaultValue={edition?.pages} error={error('pages')} />
          <div className="form-field">
            <FormInput label="ISBN-13" name="isbn" maxLength={40} aria-describedby="book-isbn-hint"
              defaultValue={edition?.isbn} error={error('isbn')} />
            <small id="book-isbn-hint" className="muted">13 цифр, можно с дефисами или пробелами.</small>
          </div>
          <div className="form-field">
            <label htmlFor="book-binding">Переплёт</label>
            <select id="book-binding" name="binding" required defaultValue={edition?.binding ?? ''}
              aria-invalid={Boolean(error('binding'))} aria-describedby={error('binding') ? 'book-binding-error' : undefined}>
              <option value="">Выберите переплёт</option>
              <option value="hardcover">Твёрдый</option>
              <option value="paperback">Мягкий</option>
            </select>
            {error('binding') && <p className="error" id="book-binding-error">{error('binding')}</p>}
          </div>
        </fieldset>
        <fieldset className="manager-fields" disabled={pending}>
          <legend>Продажа и остаток</legend>
          {hasVariants && book ? (
            <p className="muted manager-wide">Цена от {formatPrice(book.price)}, всего {book.stock} шт.
              Цена и остаток редактируются у вариантов ниже.</p>
          ) : (
            <>
              <FormInput label="Цена, ₽" name="price" inputMode="decimal" required
                defaultValue={book?.price} error={error('price')} />
              <FormInput label="Остаток" name="stock" type="number" min={0} required
                defaultValue={book?.stock ?? 0} error={error('stock')} />
            </>
          )}
          <FormInput label="Старая цена, ₽" name="old_price" inputMode="decimal"
            defaultValue={book?.old_price ?? ''} error={error('old_price')} />
          <Availability checked={book?.is_active} label="Показывать на витрине" />
        </fieldset>
        {fetcher.data && <p className="error" role="alert">{fetcher.data.message}</p>}
        <button type="submit" disabled={pending}>{pending ? 'Сохраняем…' : 'Сохранить книгу'}</button>
      </fetcher.Form>
      {addingGenre && <GenreDialog close={() => setAddingGenre(false)} select={setCategory} />}
      {book && hasVariants && (
        <section aria-label="Складские варианты">
          <h2>Складские варианты</h2>
          {variants.map((variant) => <VariantForm key={variant.id} variant={variant} bookId={book.id} />)}
        </section>
      )}
      {book && (
        <div className="manager-card-actions">
          <button type="button" className="secondary manager-delete" disabled={pending}
            onClick={() => setDeletingBook(true)}>Удалить книгу</button>
          {deletingBook && <BookDeleteDialog book={book} close={() => setDeletingBook(false)} />}
        </div>
      )}
    </section>
  )
}

function EditBook({ id, categories }: { id: number; categories: Category[] }) {
  const { data: book } = useSuspenseQuery(managerBookQuery(id))
  return <BookEditor book={book} categories={categories} />
}

export default function ManagerBookPage() {
  const { bookId } = useParams<'bookId'>()
  const { data: categories } = useSuspenseQuery(managerCategoriesQuery())
  return bookId
    ? <EditBook key={bookId} id={Number(bookId)} categories={categories} />
    : <BookEditor categories={categories} />
}
