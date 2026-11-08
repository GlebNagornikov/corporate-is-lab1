import { useQueries } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useLocation, useNavigation, useSearchParams } from 'react-router'
import { productsQuery } from '../api/queries'
import { parseCatalogParams } from './catalogParams'

export function useCatalogPages() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { key, state } = useLocation()
  const navigating = useNavigation().state !== 'idle'
  const [requestedFrom, setRequestedFrom] = useState<string>()
  if (requestedFrom !== undefined && requestedFrom !== key) setRequestedFrom(undefined)
  const { page = 1, ...filters } = parseCatalogParams(searchParams)
  const savedStart: unknown = state?.catalogStartPage
  // A shared URL starts at its own page; only this history entry knows the loaded range.
  const start = typeof savedStart === 'number' && Number.isSafeInteger(savedStart) &&
    savedStart > 0 && savedStart < page ? savedStart : page
  const pageCount = page - start + 1
  const appending = requestedFrom === key
  const queries = useQueries({
    queries: Array.from({ length: pageCount + Number(appending) }, (_, index) => {
      const number = start + index
      return productsQuery({ ...filters, ...(number > 1 ? { page: number } : {}) })
    }),
  })
  const loaded = queries.slice(0, pageCount)
  const ready = loaded.every(({ data }) => data !== undefined)
  const failed = loaded.find(({ data, isError }) => !data && isError)
  const first = loaded[0].data
  const hasNext = ready && Boolean(loaded.at(-1)?.data?.next)
  const next = queries[pageCount]
  const appended = next?.isSuccess
  const results = new Map(loaded.flatMap(({ data }) => data?.results ?? []).map((book) => [book.id, book]))

  useEffect(() => {
    if (!appended || navigating) return
    const params = new URLSearchParams(searchParams)
    params.set('page', String(page + 1))
    setSearchParams(params, {
      replace: true,
      preventScrollReset: true,
      state: { catalogStartPage: start },
    })
  }, [appended, navigating, page, searchParams, setSearchParams, start])

  const canLoadMore = hasNext && !appending && !navigating
  function loadMore() {
    if (canLoadMore) setRequestedFrom(key)
  }

  return {
    page, start, filters, searchParams, first, results: [...results.values()],
    ready, failed, hasNext, next, canLoadMore, loadMore,
  }
}
