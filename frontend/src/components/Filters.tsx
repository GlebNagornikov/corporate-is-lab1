import { useLayoutEffect, useRef, useState } from 'react'
import { useLocation, useNavigationType, useSearchParams } from 'react-router'
import { orderingOptions } from '../lib/catalogParams'
import { useDebouncedCallback } from '../lib/useDebouncedCallback'

const FILTER_DELAY = 300
const textFields = ['q', 'price_min', 'price_max'] as const
type TextField = (typeof textFields)[number]

function readTextFields(params: URLSearchParams) {
  return {
    q: params.get('q') ?? '',
    price_min: params.get('price_min') ?? '',
    price_max: params.get('price_max') ?? '',
  }
}

export default function Filters() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { key } = useLocation()
  const navigationType = useNavigationType()
  const applied = [
    ['q', searchParams.get('q') ? `Поиск: ${searchParams.get('q')}` : ''],
    ['binding', { hardcover: 'Твёрдый переплёт', paperback: 'Мягкий переплёт' }[searchParams.get('binding') ?? ''] ?? ''],
    ['price_min', searchParams.get('price_min') ? `От ${searchParams.get('price_min')} ₽` : ''],
    ['price_max', searchParams.get('price_max') ? `До ${searchParams.get('price_max')} ₽` : ''],
    ['in_stock', searchParams.get('in_stock') === 'true' ? 'В наличии' : ''],
    ['on_sale', searchParams.get('on_sale') === 'true' ? 'Со скидкой' : ''],
    ['ordering', orderingOptions.find(({ value }) => value && value === searchParams.get('ordering'))?.label ?? ''],
  ]
  const committed = readTextFields(searchParams)
  const [draft, setDraft] = useState({ key, committed, values: committed })
  const pending = useRef(new Map<TextField, string>())
  const latestParams = useRef(searchParams)

  function update(values: Iterable<[string, string]>) {
    const current = latestParams.current
    const changes = [...values].filter(([name, value]) => (current.get(name) ?? '') !== value)
    if (changes.length === 0) return

    const next = new URLSearchParams(current)
    for (const [name, value] of changes) {
      if (value) next.set(name, value)
      else next.delete(name)
    }
    next.delete('page')
    latestParams.current = next
    setSearchParams(next, { replace: changes.every(([name]) => name === 'q') })
  }

  const { schedule, cancel } = useDebouncedCallback(() => {
    const changes = [...pending.current]
    pending.current.clear()
    update(changes)
  }, FILTER_DELAY)

  // Restore the URL values on Back/Forward and keep drafts during other filter changes.
  if (draft.key !== key) {
    const restore = navigationType === 'POP' ||
      textFields.some((field) => draft.committed[field] !== committed[field])
    setDraft({ key, committed, values: restore ? committed : draft.values })
  }

  useLayoutEffect(() => {
    const previous = latestParams.current
    const textChanged = textFields.some((field) => previous.get(field) !== searchParams.get(field))
    if (navigationType === 'POP' || textChanged) {
      cancel()
      pending.current.clear()
    }
    latestParams.current = searchParams
  }, [cancel, key, navigationType, searchParams])

  function handleText(field: TextField, value: string, valid = true) {
    setDraft((previous) => ({ ...previous, values: { ...previous.values, [field]: value } }))
    if (valid) pending.current.set(field, value.trim())
    else pending.current.delete(field)
    schedule()
  }

  return (
    <>
      <form className="filters" role="search" onSubmit={(event) => event.preventDefault()}>
        <label>
          Поиск
          <input type="search" placeholder="Название или автор" value={draft.values.q} onChange={(event) => handleText('q', event.target.value)} />
        </label>
        <label>
          Цена от
          <input
            type="number"
            min={0}
            step="0.01"
            value={draft.values.price_min}
            onChange={(event) => handleText('price_min', event.target.value, event.target.validity.valid)}
          />
        </label>
        <label>
          Цена до
          <input
            type="number"
            min={0}
            step="0.01"
            value={draft.values.price_max}
            onChange={(event) => handleText('price_max', event.target.value, event.target.validity.valid)}
          />
        </label>
        <label className="inline">
          <input
            type="checkbox"
            checked={searchParams.get('in_stock') === 'true'}
            onChange={(event) => update([['in_stock', event.target.checked ? 'true' : '']])}
          />
          В наличии
        </label>
        <label className="inline">
          <input
            type="checkbox"
            checked={searchParams.get('on_sale') === 'true'}
            onChange={(event) => update([['on_sale', event.target.checked ? 'true' : '']])}
          />
          Со скидкой
        </label>
        <label>
          Переплёт
          <select value={searchParams.get('binding') ?? ''}
            onChange={(event) => update([['binding', event.target.value]])}>
            <option value="">Любой</option>
            <option value="hardcover">Твёрдый</option>
            <option value="paperback">Мягкий</option>
          </select>
        </label>
        <label>
          Сортировка
          <select
            value={searchParams.get('ordering') ?? ''}
            onChange={(event) => update([['ordering', event.target.value]])}
          >
            {orderingOptions.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      </form>
      {applied.some(([, label]) => label) && (
        <div className="applied-filters" role="group" aria-label="Применённые фильтры">
          {applied.filter(([, label]) => label).map(([name, label]) => (
            <button className="secondary" type="button" key={name} aria-label={`Снять фильтр: ${label}`} onClick={() => update([[name, '']])}>
              {label} <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      )}
    </>
  )
}
