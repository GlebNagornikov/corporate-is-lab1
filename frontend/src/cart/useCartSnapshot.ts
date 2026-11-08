import { createContext, useContext } from 'react'
import type { Cart } from '../api/client'

export const CartContext = createContext<{
  cart: Cart; isGuest: boolean; isLoading: boolean; error: Error | null; retry: () => void
} | null>(null)

export function useCartSnapshot() {
  const state = useContext(CartContext)
  if (!state) throw new Error('CartProvider is missing')
  return state
}
