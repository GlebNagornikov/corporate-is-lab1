import { useLayoutEffect, useRef, useState } from 'react'
import { useLocation, useNavigationType, useSearchParams } from 'react-router'
import { orderingOptions } from '../lib/catalogParams'

const SEARCH_DELAY = 300

export default function Filters() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { key } = useLocation()
  const navigationType = useNavigationType()
  const query = searchParams.get('q') ?? ''
  const [draft, setDraft] = useState({ key, query, value: query })
  const searchTimer = useRef<number | undefined>(undefined)
  const latestParams = useRef(searchParams)

  // Restore the URL value on Back/Forward while keeping the draft during other filter changes.
  if (draft.key !== key) {
    const restoreQuery = navigationType === 'POP' || draft.query !== query
    setDraft({ key, query, value: restoreQuery ? query : draft.value })
  }

  useLayoutEffect(() => {
    if (navigationType === 'POP' || latestParams.current.get('q') !== searchParams.get('q')) {
      window.clearTimeout(searchTimer.current)
    }
    latestParams.current = searchParams
  }, [key, navigationType, searchParams])

  useLayoutEffect(() => () => window.clearTimeout(searchTimer.current), [])

  function update(name: string, value: string) {
    const current = latestParams.current
    if ((current.get(name) ?? '') === value) return

    const next = new URLSearchParams(current)
    if (value) next.set(name, value)
    else next.delete(name)
    next.delete('page')
    latestParams.current = next
    setSearchParams(next, { replace: name === 'q' })
  }

  function handleSearch(value: string) {
    setDraft({ key, query, value })
    window.clearTimeout(searchTimer.current)
    searchTimer.current = window.setTimeout(() => update('q', value.trim()), SEARCH_DELAY)
  }

  const priceMin = searchParams.get('price_min') ?? ''
  const priceMax = searchParams.get('price_max') ?? ''

  return (
    <form className="filters" role="search" onSubmit={(event) => event.preventDefault()}>
      <label>
        Поиск
        <input type="search" value={draft.value} onChange={(event) => handleSearch(event.target.value)} />
      </label>
      <label>
        Цена от
        <input
          key={priceMin}
          type="number"
          min={0}
          step="0.01"
          defaultValue={priceMin}
          onBlur={(event) => {
            if (event.target.validity.valid) update('price_min', event.target.value)
          }}
        />
      </label>
      <label>
        Цена до
        <input
          key={priceMax}
          type="number"
          min={0}
          step="0.01"
          defaultValue={priceMax}
          onBlur={(event) => {
            if (event.target.validity.valid) update('price_max', event.target.value)
          }}
        />
      </label>
      <label className="inline">
        <input
          type="checkbox"
          checked={searchParams.get('in_stock') === 'true'}
          onChange={(event) => update('in_stock', event.target.checked ? 'true' : '')}
        />
        В наличии
      </label>
      <label className="inline">
        <input
          type="checkbox"
          checked={searchParams.get('on_sale') === 'true'}
          onChange={(event) => update('on_sale', event.target.checked ? 'true' : '')}
        />
        Со скидкой
      </label>
      <label>
        Сортировка
        <select
          value={searchParams.get('ordering') ?? ''}
          onChange={(event) => update('ordering', event.target.value)}
        >
          {orderingOptions.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
    </form>
  )
}
