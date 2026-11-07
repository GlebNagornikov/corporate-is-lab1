import { useState } from 'react'
import type { Product } from '../api/client'
import { useCart } from '../cart/useCart'

export default function AddToCartButton({ product }: { product: Product }) {
  const cart = useCart()
  const [selectedId, setSelectedId] = useState('')
  const hasVariants = product.variants.some((variant) => !variant.is_default)
  const variants = product.variants.filter((variant) => !variant.is_default && variant.is_active !== false)
  const selected = variants.find((variant) => String(variant.id) === selectedId)
  const quantity = cart.items.filter((item) =>
    item.product_id === product.id && (!hasVariants || item.variant_id === selected?.id),
  ).reduce((sum, item) => sum + item.quantity, 0)
  const stock = (hasVariants ? selected?.stock : product.stock) ?? 0

  return (
    <div className="cart-add">
      {variants.length > 0 && (
        <label className="form-field">
          Вариант товара
          <select value={selected ? selectedId : ''} onChange={(event) => setSelectedId(event.target.value)}>
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
        disabled={cart.isLoading || cart.isAdding || stock <= quantity}
        onClick={() => cart.add(product, selected)}
      >
        {quantity > 0 ? `В корзине: ${quantity}` : 'В корзину'}
      </button>
      {cart.error && <span className="error" role="alert">{cart.error.message}</span>}
    </div>
  )
}
