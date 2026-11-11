import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, ApiError, requireData, type Cart } from '../api/client'
import { tokens } from '../auth/tokens'
import { formatPrice } from '../lib/format'
import { guestCart } from './guestCart'
import { cartQuery } from './queries'

async function checkPromo(code: string, subtotal: string, signal?: AbortSignal) {
  return requireData(await api.POST('/api/promo/check/', { body: { code, subtotal }, signal }))
}

export default function CartPromo({ cart, isGuest }: { cart: Cart; isGuest: boolean }) {
  const [draft, setDraft] = useState('')
  const client = useQueryClient()
  const version = tokens.version()
  const preview = useQuery({
    queryKey: ['guest-promo', version, cart.promo_code, cart.total],
    queryFn: ({ signal }) => checkPromo(cart.promo_code, cart.total, signal),
    enabled: isGuest && Boolean(cart.promo_code),
    staleTime: 0,
  })
  const selection = useMutation({
    scope: { id: `cart:${version}` },
    mutationFn: async ({ code, version: started }: { code: string; version: number }) => {
      if (started !== tokens.version()) throw new ApiError(401, 'Сессия завершена.')
      if (isGuest) {
        if (code) {
          const quote = await checkPromo(code, cart.total)
          if (quote.reason) throw new ApiError(400, quote.reason)
        }
        if (started === tokens.version()) guestCart.setPromoCode(code)
        return
      }
      const result = requireData(await api.PATCH('/api/cart/promo/', { body: { promo_code: code } }))
      if (started !== tokens.version()) return
      const { queryKey } = cartQuery()
      await client.cancelQueries({ queryKey })
      if (started === tokens.version()) client.setQueryData(queryKey, result)
    },
    onSuccess: () => setDraft(''),
  })
  const quote = isGuest ? preview.data : cart.promo_quote
  const error = selection.variables?.version === version ? selection.error : null
  const busy = selection.isPending

  return (
    <>
      <form className="form" onSubmit={(event) => {
        event.preventDefault()
        if (draft.trim() && !busy) selection.mutate({ code: draft.trim().toUpperCase(), version })
      }}>
        <label htmlFor="cart-promo">Промокод</label>
        <input id="cart-promo" value={draft} maxLength={30} onChange={(event) => setDraft(event.target.value)} />
        <button type="submit" disabled={busy || !draft.trim() || !cart.count}>Применить</button>
      </form>
      {cart.promo_code && (
        <p>
          Код {cart.promo_code}{' '}
          <button type="button" className="secondary" disabled={busy}
            onClick={() => selection.mutate({ code: '', version })}>Снять промокод</button>
        </p>
      )}
      {error && <p className="error" role="alert">{error.message}</p>}
      <div aria-live="polite">
        {preview.error && isGuest && <p className="error">{preview.error.message}</p>}
        {quote?.reason && <p className="error">{quote.reason}</p>}
        {quote && !quote.reason && <p>Скидка {formatPrice(quote.discount)}</p>}
        {cart.promo_code && !quote && !preview.error && <p>Пересчитываем скидку…</p>}
        <p className="price">Итого: {formatPrice(quote?.total ?? cart.total)}</p>
      </div>
    </>
  )
}
