import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { formatPrice } from '../lib/format'
import { useCart } from './useCart'
import { priceChangesQuery } from './priceChanges'

export default function CartPage() {
  const cart = useCart()
  const { data: changes } = useQuery(priceChangesQuery())

  return (
    <section className="details narrow">
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
        <>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr><th scope="col">Товар</th><th scope="col">Количество</th><th scope="col">Сумма</th></tr>
              </thead>
              <tbody>
                {cart.items.map((item) => {
                  const label = [item.name, item.variant_name].filter(Boolean).join(', ')
                  return (
                    <tr key={`${item.product_id}:${item.variant_id ?? ''}`}>
                      <td>
                        <Link to={`/products/${encodeURIComponent(item.slug)}`}>{item.name}</Link>
                        {item.variant_name && <small className="line-variant muted">{item.variant_name}</small>}
                      </td>
                      <td>
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
                      </td>
                      <td>{formatPrice(item.total)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="price">Итого: {formatPrice(cart.total)}</p>
          {cart.isGuest && (
            <p className="muted">Цены предварительные. После входа сервер пересчитает сумму.</p>
          )}
          <Link className="button" to="/checkout" onMouseEnter={() => void import('../orders/CheckoutPage')}>
            Оформить заказ
          </Link>
        </>
      ) : !cart.error && (
        <p className="muted">Корзина пуста. <Link to="/">В каталог</Link></p>
      )}
    </section>
  )
}
