import type { CartItem } from '../api/client'

const MAX_COPIES_PER_EDITION = 5

export const editionLimitRule = `На один заказ — до ${MAX_COPIES_PER_EDITION} экземпляров каждого издания, суммарно по всем вариантам.`

export function editionLimitErrors(items: readonly CartItem[]) {
  const editions = new Map<number, { name: string; quantity: number }>()
  for (const item of items) {
    const edition = editions.get(item.product_id)
    if (edition) edition.quantity += item.quantity
    else editions.set(item.product_id, { name: item.name, quantity: item.quantity })
  }
  return Array.from(editions, ([id, { name, quantity }]) => ({ id, name, quantity }))
    .filter(({ quantity }) => quantity > MAX_COPIES_PER_EDITION)
    .map(({ id, name, quantity }) => ({
      id,
      message: `«${name}»: в корзине ${quantity}. Уберите ${quantity - MAX_COPIES_PER_EDITION} экз.`,
    }))
}
