import { useSyncExternalStore } from 'react'
import type { CartItem, Product, Variant } from '../api/client'

const KEY = 'shop-guest-cart'
const listeners = new Set<() => void>()
let cache: CartItem[] | undefined
let promoCode = ''

function storedItem(value: unknown): CartItem[] {
  if (!value || typeof value !== 'object') return []
  const item = value as Partial<CartItem>
  if (
    typeof item.product_id !== 'number' || !Number.isSafeInteger(item.product_id) ||
    typeof item.quantity !== 'number' || !Number.isSafeInteger(item.quantity) || item.quantity <= 0 ||
    typeof item.stock !== 'number' || !Number.isSafeInteger(item.stock) || item.stock < 0 ||
    typeof item.name !== 'string' || typeof item.slug !== 'string' ||
    typeof item.price !== 'string' || !Number.isFinite(Number(item.price))
  ) return []

  return [withQuantity({
    product_id: item.product_id,
    name: item.name,
    slug: item.slug,
    stock: item.stock,
    price: item.price,
    image: typeof item.image === 'string' ? item.image : null,
    variant_id: typeof item.variant_id === 'number' ? item.variant_id : null,
    variant_name: typeof item.variant_name === 'string' ? item.variant_name : '',
    is_default_variant: item.is_default_variant ?? item.variant_id == null,
  }, item.quantity)]
}

function read(): CartItem[] {
  if (!cache) {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
      const cart = Array.isArray(stored) ? { items: stored } : stored as {
        items?: unknown; promo_code?: unknown
      } | null
      cache = Array.isArray(cart?.items) ? cart.items.flatMap(storedItem) : []
      promoCode = cache.length && typeof cart?.promo_code === 'string' ? cart.promo_code : ''
    } catch {
      cache = []
    }
  }
  return cache
}

function write(items: CartItem[], code = promoCode) {
  if (items.length === 0) code = ''
  localStorage.setItem(KEY, JSON.stringify({ items, promo_code: code }))
  cache = items
  promoCode = code
  listeners.forEach((listener) => listener())
}

export function withQuantity(item: Omit<CartItem, 'quantity' | 'total'>, quantity: number): CartItem {
  return { ...item, quantity, total: (Number(item.price) * quantity).toFixed(2) }
}

export function summarizeCart(items: CartItem[], code = '') {
  return {
    items,
    count: items.reduce((sum, item) => sum + item.quantity, 0),
    total: items.reduce((sum, item) => sum + Number(item.total), 0).toFixed(2),
    promo_code: items.length ? code : '',
    promo_quote: null,
  }
}

export function limitQuantity(quantity: number, stock: number): number {
  return Math.max(0, Math.min(Math.trunc(quantity) || 0, stock))
}

export function matchesLine(item: CartItem, productId: number, variantId: number | null) {
  return item.product_id === productId && (item.variant_id ?? null) === variantId
}

export const guestCart = {
  items: read,
  promoCode() {
    read()
    return promoCode
  },
  setPromoCode(code: string) {
    write(read(), code)
  },
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
  },
  add(product: Product, quantity = 1, variant?: Variant) {
    const items = read()
    const variantId = variant?.id ?? null
    const index = items.findIndex((item) => matchesLine(item, product.id, variantId))
    const current = items[index]
    const stock = (variant && !variant.is_default ? variant.stock : product.stock) ?? 0
    const next = limitQuantity((current?.quantity ?? 0) + quantity, stock)
    if (next === 0 && !current) return

    const details = current ?? {
      product_id: product.id,
      name: product.name,
      slug: product.slug,
      image: product.image ?? null,
      variant_id: variantId,
      variant_name: variant?.name ?? '',
      is_default_variant: variant?.is_default ?? true,
      price: variant && !variant.is_default ? variant.price : product.price,
    }
    const item = withQuantity({ ...details, stock }, next)
    const updated = [...items]
    if (index === -1) updated.push(item)
    else updated[index] = item
    write(updated.filter((line) => line.quantity > 0))
  },
  setQuantity(productId: number, quantity: number, variantId: number | null = null) {
    write(read()
      .map((item) => matchesLine(item, productId, variantId)
        ? withQuantity(item, limitQuantity(quantity, item.stock))
        : item)
      .filter((item) => item.quantity > 0))
  },
  removeTransferred(transferred: CartItem[], transferredCode: string) {
    write(read().map((item) => {
      const sent = transferred.find((line) => matchesLine(line, item.product_id, item.variant_id))
      return sent ? withQuantity(item, item.quantity - sent.quantity) : item
    }).filter((item) => item.quantity > 0), transferredCode === promoCode ? '' : promoCode)
  },
  clear() {
    write([], '')
  },
}

export function useGuestCart() {
  const items = useSyncExternalStore(guestCart.subscribe, guestCart.items)
  const code = useSyncExternalStore(guestCart.subscribe, guestCart.promoCode)
  return summarizeCart(items, code)
}
