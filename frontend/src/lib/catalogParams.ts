import type { paths } from '../api/schema'

export type ProductQuery = NonNullable<
  paths['/api/catalog/products/']['get']['parameters']['query']
>

export type Ordering = NonNullable<ProductQuery['ordering']>[number]

export const orderingOptions: { value: Ordering | ''; label: string }[] = [
  { value: '', label: 'Сначала новые' },
  { value: 'price', label: 'Сначала дешёвые' },
  { value: '-price', label: 'Сначала дорогие' },
  { value: '-rating', label: 'По рейтингу' },
  { value: 'name', label: 'По названию' },
]

export function parseCatalogParams(searchParams: URLSearchParams): ProductQuery {
  const query: ProductQuery = {}
  const q = searchParams.get('q')?.trim()
  const category = searchParams.get('category')
  const binding = searchParams.get('binding')
  const priceMin = Number(searchParams.get('price_min')?.trim() || NaN)
  const priceMax = Number(searchParams.get('price_max')?.trim() || NaN)
  const requestedOrdering = searchParams.get('ordering')
  const ordering = orderingOptions.find(({ value }) => value === requestedOrdering)?.value
  const page = Number(searchParams.get('page'))

  if (q) query.q = q
  if (category) query.category = category
  if (binding === 'hardcover' || binding === 'paperback') query.binding = binding
  if (Number.isFinite(priceMin) && priceMin >= 0) query.price_min = priceMin
  if (Number.isFinite(priceMax) && priceMax >= 0) query.price_max = priceMax
  if (searchParams.get('in_stock') === 'true') query.in_stock = true
  if (searchParams.get('on_sale') === 'true') query.on_sale = true
  if (ordering) query.ordering = [ordering]
  if (Number.isSafeInteger(page) && page > 1) query.page = page

  return query
}
