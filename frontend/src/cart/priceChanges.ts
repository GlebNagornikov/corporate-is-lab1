import { queryOptions } from '@tanstack/react-query'
import type { CartItem } from '../api/client'

type PriceChange = {
  item: CartItem
  before: string
}

export const priceChangesQuery = () => queryOptions({
  queryKey: ['cart-price-changes'],
  queryFn: (): PriceChange[] => [],
  enabled: false,
  initialData: [],
})

export function findPriceChanges(before: CartItem[], after: CartItem[]): PriceChange[] {
  return before.flatMap((guest) => {
    const item = after.find((line) => line.product_id === guest.product_id &&
      (guest.variant_id === null ? line.is_default_variant : line.variant_id === guest.variant_id))
    return item && Number(item.price) !== Number(guest.price) ? [{ item, before: guest.price }] : []
  })
}
