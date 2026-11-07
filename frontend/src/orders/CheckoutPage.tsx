import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { api, requireData } from '../api/client'
import { orderQuery } from '../api/orders'
import { meQuery } from '../auth/session'
import { tokens } from '../auth/tokens'
import { cartQuery } from '../cart/queries'
import { priceChangesQuery } from '../cart/priceChanges'
import FormInput from '../components/FormInput'
import { formatPrice } from '../lib/format'
import { applyServerErrors } from '../lib/serverErrors'
import { checkoutFields, checkoutSchema, type CheckoutForm } from './checkoutSchema'

export default function CheckoutPage() {
  const navigate = useNavigate()
  const client = useQueryClient()
  const { data: me } = useQuery(meQuery())
  const cart = useQuery({ ...cartQuery(), enabled: Boolean(me) })
  const { register, handleSubmit, control, setError, clearErrors, formState: { errors, isSubmitting } } =
    useForm<CheckoutForm>({
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
  const delivery = useWatch({ control, name: 'delivery_method' })

  async function onSubmit(values: CheckoutForm) {
    const version = tokens.version()
    try {
      const order = requireData(await api.POST('/api/orders/', {
        body: { ...values, address: values.delivery_method === 'courier' ? values.address : '' },
      }))
      const cartKey = cartQuery().queryKey
      await client.cancelQueries({ queryKey: cartKey })
      if (version !== tokens.version()) return
      client.setQueryData(cartKey, { items: [], count: 0, total: '0.00' })
      client.removeQueries({ queryKey: priceChangesQuery().queryKey })
      client.setQueryData(orderQuery(order.id).queryKey, order)
      void client.invalidateQueries({ queryKey: ['orders', 'list'] })
      void navigate(`/orders/${order.id}`, { replace: true, state: { justPlaced: true } })
    } catch (error) {
      applyServerErrors(error, setError, checkoutFields)
    }
  }

  if (!cart.data?.items.length) {
    return (
      <section className="details narrow">
        <h1>Оформление заказа</h1>
        {cart.isPending && <p role="status">Загрузка корзины…</p>}
        {cart.isError && (
          <>
            <p className="error" role="alert">{cart.error.message}</p>
            <button type="button" onClick={() => void cart.refetch()}>Повторить</button>
          </>
        )}
        {cart.isSuccess && <p className="muted">Корзина пуста. <Link to="/">В каталог</Link></p>}
      </section>
    )
  }

  return (
    <form className="details narrow form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <h1>Оформление заказа</h1>
      <p>Товаров: {cart.data.count} на {formatPrice(cart.data.total)}.</p>
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
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Отправка…' : 'Подтвердить заказ'}
      </button>
    </form>
  )
}
