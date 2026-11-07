const priceFormat = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

export function formatPrice(value: string): string {
  return priceFormat.format(Number(value))
}

const dateFormat = new Intl.DateTimeFormat('ru-RU', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatDate(value: string): string {
  return dateFormat.format(new Date(value))
}
