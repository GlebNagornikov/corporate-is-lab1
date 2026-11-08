import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { useSession } from '../auth/useSession'
import { useCartSnapshot } from '../cart/useCartSnapshot'
import FormInput from '../components/FormInput'
import { formatPrice } from '../lib/format'
import { useRouteForm } from '../lib/routeForm'
import { usePageTitle } from '../lib/usePageTitle'
import { checkoutFields, checkoutSchema, type CheckoutForm } from './checkoutSchema'

export default function CheckoutPage() {
  usePageTitle('Оформление заказа')
  const navigate = useNavigate()
  const { data: me } = useSession()
  const { cart, isLoading, error, retry } = useCartSnapshot()
  const form = useForm<CheckoutForm>({
    resolver: zodResolver(checkoutSchema),
    defaultValues: {
      full_name: [me?.first_name, me?.last_name].filter(Boolean).join(' '),
      phone: '',
      email: me?.email ?? '',
      delivery_method: 'pickup',
      address: '',
      comment: '',
      promo_code: '',
    },
  })
  const { register, control, clearErrors, formState: { errors, isSubmitting } } = form
  const { onSubmit, isPending } = useRouteForm(form, checkoutFields, (id) => {
    void navigate(`/orders/${id}`, { replace: true, state: { justPlaced: true } })
  })
  const busy = isSubmitting || isPending
  const delivery = useWatch({ control, name: 'delivery_method' })

  if (!cart.items.length && !busy) {
    return (
      <section className="details narrow">
        <h1>Оформление заказа</h1>
        {isLoading && <p role="status">Загрузка корзины…</p>}
        {error && (
          <>
            <p className="error" role="alert">{error.message}</p>
            <button type="button" onClick={retry}>Повторить</button>
          </>
        )}
        {!isLoading && !error && <p className="muted">Корзина пуста. <Link to="/catalog">В каталог</Link></p>}
      </section>
    )
  }

  return (
    <section>
      <p className="eyebrow">Последний шаг</p>
      <h1>Оформление заказа</h1>
      <div className="order-layout">
        <form className="details form" onSubmit={onSubmit} aria-busy={busy} noValidate>
          <h2>Получатель и доставка</h2>
          <FormInput label="Получатель" autoComplete="name"
            error={errors.full_name?.message} {...register('full_name')} />
          <FormInput label="Телефон" type="tel" autoComplete="tel" placeholder="+7 913 123-45-67"
            error={errors.phone?.message} {...register('phone')} />
          <FormInput label="Электронная почта" type="email" autoComplete="email"
            error={errors.email?.message} {...register('email')} />
          <fieldset aria-describedby={errors.delivery_method ? 'delivery-error' : undefined}>
            <legend>Способ получения</legend>
            <label className="form-radio">
              <input
                type="radio" value="pickup"
                {...register('delivery_method', { onChange: () => clearErrors('address') })}
              /> Самовывоз
            </label>
            <label className="form-radio">
              <input type="radio" value="courier" {...register('delivery_method')} /> Курьер
            </label>
            {errors.delivery_method && <p className="error" id="delivery-error">{errors.delivery_method.message}</p>}
          </fieldset>
          {delivery === 'courier' && (
            <>
              <p className="muted">Доставка курьером стоит 500 ₽. От 5000 ₽ после скидок доставка бесплатна.</p>
              <FormInput label="Адрес доставки" autoComplete="street-address"
                error={errors.address?.message} {...register('address')} />
            </>
          )}
          <FormInput label="Промокод" error={errors.promo_code?.message} {...register('promo_code')} />
          <div className="form-field">
            <label htmlFor="checkout-comment">Комментарий</label>
            <textarea id="checkout-comment" rows={3} aria-invalid={Boolean(errors.comment)}
              aria-describedby={errors.comment ? 'comment-error' : undefined} {...register('comment')} />
            {errors.comment && <p className="error" id="comment-error">{errors.comment.message}</p>}
          </div>
          {errors.root?.message && <p className="error" role="alert">{errors.root.message}</p>}
          <button type="submit" disabled={busy}>
            {busy ? 'Отправка…' : 'Подтвердить заказ'}
          </button>
        </form>
        <aside className="details order-summary" aria-label="Сводка заказа">
          <h2>Ваш заказ</h2>
          <ul className="summary-lines">{cart.items.map((item) => (
            <li key={`${item.product_id}:${item.variant_id}`}><span>{item.name} × {item.quantity}</span><span>{formatPrice(item.total)}</span></li>
          ))}</ul>
          <p className="price">Книги · {formatPrice(cart.total)}</p>
          <p className="muted">{delivery === 'pickup' ? 'Самовывоз бесплатный.' : 'Доставка и скидка рассчитываются при оформлении.'}</p>
          <Link to="/cart">Вернуться в корзину</Link>
        </aside>
      </div>
    </section>
  )
}
