import { describe, expect, test } from 'vitest'
import { parseCatalogParams } from './catalogParams'

describe('parseCatalogParams', () => {
  test('берёт только корректные значения', () => {
    const params = new URLSearchParams(
      'q=канбан&category=books&price_min=abc&price_max=0&in_stock=true&ordering=-price&page=2',
    )

    expect(parseCatalogParams(params)).toEqual({
      q: 'канбан',
      category: 'books',
      price_max: 0,
      in_stock: true,
      ordering: ['-price'],
      page: 2,
    })
  })

  test('отбрасывает неизвестную сортировку и первую страницу', () => {
    expect(parseCatalogParams(new URLSearchParams('ordering=password&page=1'))).toEqual({})
  })
})
