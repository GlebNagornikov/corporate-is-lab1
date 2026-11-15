import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router'
import FormInput from '../components/FormInput'
import { useRouteForm } from '../lib/routeForm'
import { usePageTitle } from '../lib/usePageTitle'
import { registerFields, registerSchema } from './authActions'
import { nextPath } from './nextPath'

export default function RegisterPage() {
  usePageTitle('Регистрация')
  const [searchParams] = useSearchParams()
  const next = nextPath(searchParams.get('next'))
  const form = useForm({ resolver: zodResolver(registerSchema) })
  const { register, formState: { errors, isSubmitting } } = form
  const { onSubmit, isPending } = useRouteForm(form, registerFields)
  const busy = isSubmitting || isPending

  return (
    <form className="details narrow form auth-form" onSubmit={onSubmit} aria-busy={busy} noValidate>
      <p className="eyebrow">Личный кабинет</p>
      <h1>Регистрация</h1>
      <p className="muted">Создайте учётную запись для покупок и истории заказов.</p>
      <FormInput label="Имя пользователя" autoComplete="username"
        error={errors.username?.message} {...register('username')} />
      <FormInput label="Электронная почта" type="email" autoComplete="email"
        error={errors.email?.message} {...register('email')} />
      <FormInput label="Пароль" type="password" autoComplete="new-password"
        error={errors.password?.message} {...register('password')} />
      <FormInput label="Пароль ещё раз" type="password" autoComplete="new-password"
        error={errors.password2?.message} {...register('password2')} />
      {errors.root?.message && <p className="error" role="alert">{errors.root.message}</p>}
      <button type="submit" disabled={busy}>
        {busy ? 'Регистрируем…' : 'Зарегистрироваться'}
      </button>
      <p>Есть учётная запись? <Link to={`/login?next=${encodeURIComponent(next)}`}>Войти</Link></p>
    </form>
  )
}
