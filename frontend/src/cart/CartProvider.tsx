import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { Cart } from '../api/client'
import { useSession } from '../auth/useSession'
import { summarizeCart, useGuestCart } from './guestCart'
import { cartQuery } from './queries'
import { CartContext } from './useCartSnapshot'

const emptyCart: Cart = summarizeCart([])

export function CartProvider({ children }: { children: ReactNode }) {
  const { data: me } = useSession()
  const guest = useGuestCart()
  const server = useQuery({ ...cartQuery(), enabled: Boolean(me) })
  return (
    <CartContext.Provider value={{
      cart: me ? server.data ?? emptyCart : guest,
      isGuest: !me,
      isLoading: Boolean(me) && server.isPending,
      error: me ? server.error : null,
      retry: () => { void server.refetch() },
    }}>
      {children}
    </CartContext.Provider>
  )
}
