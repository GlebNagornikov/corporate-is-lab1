import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, type Product } from '../api/client'
import { productQuery } from '../api/queries'
import { tokens } from '../auth/tokens'
import { useCart } from '../cart/useCart'

export default function AddToCartButton({ product }: { product: Product }) {
  const cart = useCart()
  const client = useQueryClient()
  const [selectedId, setSelectedId] = useState('')
  const hasVariants = product.variants.some((variant) => !variant.is_default)
  const variants = product.variants.filter((variant) => !variant.is_default && variant.is_active !== false)
  const selected = variants.find((variant) => String(variant.id) === selectedId)
  const quantity = cart.items.filter((item) =>
    item.product_id === product.id && (!hasVariants || item.variant_id === selected?.id),
  ).reduce((sum, item) => sum + item.quantity, 0)
  const stock = (hasVariants ? selected?.stock : product.stock) ?? 0
  const guestAdd = useMutation({
    mutationFn: async ({ version, variantId }: { version: number; variantId?: number }) => {
      const latest = await client.fetchQuery({ ...productQuery(product.slug), staleTime: 0 })
      if (version !== tokens.version()) return
      const variant = latest.variants.find((item) => item.id === variantId && item.is_active !== false)
      const available = variantId === undefined
        ? (latest.variants.some((item) => !item.is_default) ? 0 : (latest.stock ?? 0))
        : variant?.stock ?? 0
      if (available <= quantity) {
        throw new ApiError(400, available > 0 ? 'Доступные экземпляры уже в корзине.' : 'Книги больше нет в наличии.')
      }
      cart.add(latest, variant)
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: ['products', 'list'] })
      void client.invalidateQueries({ queryKey: ['products', 'editorial'] })
    },
  })
  const adding = cart.isAdding || guestAdd.isPending
  const error = cart.isGuest
    ? (guestAdd.variables?.version === tokens.version() ? guestAdd.error : null)
    : cart.error

  return (
    <div className="cart-add">
      {variants.length > 0 && (
        <label className="form-field">
          Вариант товара
          <select value={selected ? selectedId : ''} onChange={(event) => {
            setSelectedId(event.target.value)
            guestAdd.reset()
          }}>
            <option value="">Выберите вариант</option>
            {variants.map((variant) => (
              <option key={variant.id} value={variant.id} disabled={(variant.stock ?? 0) <= 0}>
                {variant.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="button"
        disabled={cart.isLoading || adding || stock <= quantity}
        onClick={() => {
          if (cart.isGuest) guestAdd.mutate({ version: tokens.version(), variantId: selected?.id })
          else cart.add(product, selected)
        }}
      >
        {quantity > 0 ? `В корзине: ${quantity}` : 'В корзину'}
      </button>
      {error && <span className="error" role="alert">{error.message}</span>}
    </div>
  )
}
