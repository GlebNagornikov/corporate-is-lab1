const shopDate = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Novosibirsk', year: 'numeric', month: '2-digit', day: '2-digit',
})

export function defaultReportPeriod() {
  const end = shopDate.format(new Date())
  const firstDay = new Date(`${end}T00:00:00Z`)
  firstDay.setUTCDate(firstDay.getUTCDate() - 29)
  return { start: firstDay.toISOString().slice(0, 10), end }
}

export function readReportPeriod(search: URLSearchParams) {
  return { start: search.get('start') ?? '', end: search.get('end') ?? '' }
}

export type ReportPeriod = ReturnType<typeof readReportPeriod>

function isCalendarDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
}

export function reportPeriodError({ start, end }: ReportPeriod) {
  if (!isCalendarDate(start) || !isCalendarDate(end)) {
    return 'Укажите обе даты в формате ГГГГ-ММ-ДД.'
  }
  if (start > end) return 'Начало периода позже окончания.'
}
