import { useState } from 'react'
import type { components } from '../api/schema'
import { formatPrice } from '../lib/format'

type SalesReport = components['schemas']['SalesReport']
type Bar = { key: string; label: string; value: number; formatted: string }
type SortColumn = 'name' | 'quantity' | 'revenue'

const shortDate = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeZone: 'UTC' })
const bookNames = new Intl.Collator('ru')
const columns: { key: SortColumn; title: string }[] = [
  { key: 'name', title: 'Книга' },
  { key: 'quantity', title: 'Экз.' },
  { key: 'revenue', title: 'Стоимость позиций' },
]

function Bars({ rows, label }: { rows: Bar[]; label: string }) {
  const maximum = rows.reduce((max, row) => Math.max(max, row.value), 0) || 1
  return (
    <div className="report-bars-scroll" role="region" aria-label={label} tabIndex={0}>
      <ul className="report-bars" role="list">
        {rows.map((row) => (
          <li key={row.key}>
            <span>{row.label}</span>
            <strong>{row.formatted}</strong>
            <span className="report-bar-track" aria-hidden="true">
              <span style={{ width: `${row.value / maximum * 100}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function TopBooks({ books }: { books: SalesReport['top_quantity'] }) {
  const [sort, setSort] = useState<{ key: SortColumn; ascending: boolean }>({
    key: 'quantity', ascending: false,
  })
  const sorted = books.toSorted((left, right) => {
    const difference = sort.key === 'name'
      ? bookNames.compare(left.name, right.name)
      : Number(left[sort.key]) - Number(right[sort.key])
    return (sort.ascending ? difference : -difference) || left.product_id - right.product_id
  })

  return (
    <section className="details report-top">
      <h2 id="report-top-title">Топ-10 книг</h2>
      <p className="muted">В топ входят книги с наибольшим числом экземпляров в заказах без отменённых.
        Стоимость позиций считается по ценам из заказов до скидки на заказ и без доставки.</p>
      {sorted.length === 0 ? <p>Нет книг за этот период.</p> : (
        <table className="table report-top-table" aria-labelledby="report-top-title">
          <thead><tr>{columns.map(({ key, title }) => (
            <th key={key} scope="col" aria-sort={sort.key === key
              ? (sort.ascending ? 'ascending' : 'descending')
              : undefined}>
              <button type="button" onClick={() => setSort({
                key, ascending: sort.key === key ? !sort.ascending : key === 'name',
              })}>
                {title} <span aria-hidden="true">{sort.key === key ? (sort.ascending ? '↑' : '↓') : '↕'}</span>
              </button>
            </th>
          ))}</tr></thead>
          <tbody>{sorted.map((book) => (
            <tr key={book.product_id}>
              <th scope="row">{book.name}</th>
              <td>{book.quantity}</td>
              <td>{formatPrice(book.revenue)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </section>
  )
}

export default function ReportCharts({ report }: { report: SalesReport }) {
  return (
    <>
      <div className="report-charts">
        <section className="details">
          <h2>Выручка по дням</h2>
          {report.daily.length === 0 ? <p>За выбранный период выручки нет.</p> : (
            <Bars label="Дневная выручка" rows={report.daily.map(({ day, revenue }) => ({
              key: day, label: shortDate.format(new Date(day)),
              value: Number(revenue), formatted: formatPrice(revenue),
            }))} />
          )}
        </section>
        <section className="details">
          <h2>Заказы по статусам</h2>
          <Bars label="Распределение заказов" rows={report.statuses.map(({ status, label, count }) => ({
            key: status, label, value: count, formatted: String(count),
          }))} />
        </section>
      </div>
      <TopBooks books={report.top_quantity} />
    </>
  )
}
