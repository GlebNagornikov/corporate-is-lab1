import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import { editionLimitErrors, editionLimitRule } from './editionLimit'
import { useCart } from './useCart'
import CartPromo from './CartPromo'
import { priceChangesQuery } from './priceChanges'

export default function CartPage() {
  usePageTitle('Корзина')
  const cart = useCart()
  const { data: changes } = useQuery(priceChangesQuery())
  const limitErrors = editionLimitErrors(cart.items)

  return (
    <section>
      <p className="eyebrow">Ваш выбор</p>
      <h1>Корзина</h1>
      {cart.error && <p className="error" role="alert">{cart.error.message}</p>}
      {changes.filter(({ item }) => cart.items.some((line) =>
        item.product_id === line.product_id && item.variant_id === line.variant_id,
      )).map(({ item, before }) => (
        <p className="price-change" key={`${item.product_id}:${item.variant_id}`} role="status">
          {item.name}{!item.is_default_variant && ` · ${item.variant_name}`}. Цена изменилась:
          было {formatPrice(before)}, стало {formatPrice(item.price)}.
        </p>
      ))}
      {cart.isLoading ? (
        <p role="status">Загрузка корзины…</p>
      ) : cart.items.length > 0 ? (
        <div className="order-layout">
          <div className="details table-scroll">
            <table className="table cart-table">
              <thead>
                <tr><th scope="col">Товар</th><th scope="col" className="order-quantity">Количество</th>
                  <th scope="col" className="order-amount">Сумма</th></tr>
              </thead>
              <tbody>
                {cart.items.map((item) => {
                  const label = [item.name, item.variant_name].filter(Boolean).join(', ')
                  return (
                    <tr key={`${item.product_id}:${item.variant_id ?? ''}`}>
                      <td>
                        <div className="cart-line">
                          {item.image && <img src={item.image} alt="" width="48" height="72" />}
                          <div><Link to={`/products/${encodeURIComponent(item.slug)}`}>{item.name}</Link>
                            {item.variant_name && <small className="line-variant muted">{item.variant_name}</small>}
                          </div>
                        </div>
                      </td>
                      <td data-label="Количество">
                        <div className="actions">
                          <div className="qty">
                            <button type="button" aria-label={`Убрать одну штуку: ${label}`}
                              onClick={() => cart.setQuantity(item.product_id, item.quantity - 1, item.variant_id)}>
                              −
                            </button>
                            <span>{item.quantity}</span>
                            <button type="button" aria-label={`Добавить одну штуку: ${label}`}
                              disabled={item.quantity >= item.stock}
                              onClick={() => cart.setQuantity(item.product_id, item.quantity + 1, item.variant_id)}>
                              +
                            </button>
                          </div>
                        </div>
                      </td>
                      <td className="order-amount" data-label="Сумма">{formatPrice(item.total)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <aside className="details order-summary" aria-label="Сводка корзины">
            <h2>Ваш заказ</h2>
            <CartPromo cart={cart} isGuest={cart.isGuest} />
            {cart.isGuest && <p className="muted">Цены предварительные. После входа сервер пересчитает сумму.</p>}
            <p className="muted">{editionLimitRule}</p>
            {limitErrors.length > 0 ? (
              <ul className="error" aria-live="polite">
                {limitErrors.map(({ id, message }) => <li key={id}>{message}</li>)}
              </ul>
            ) : (
              <Link className="button" to="/checkout" onMouseEnter={() => void import('../orders/CheckoutPage')}
                onFocus={() => void import('../orders/CheckoutPage')}>
                Оформить заказ
              </Link>
            )}
          </aside>
        </div>
      ) : !cart.error && (
        <div className="details state-panel">
          <p>Корзина пуста. <Link to="/catalog">В каталог</Link></p>
        </div>
      )}
    </section>
  )
}
