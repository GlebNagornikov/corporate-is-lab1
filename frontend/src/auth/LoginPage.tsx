import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router'
import FormInput from '../components/FormInput'
import { useRouteForm } from '../lib/routeForm'
import { usePageTitle } from '../lib/usePageTitle'
import { loginFields, loginSchema } from './authActions'
import { nextPath } from './nextPath'

export default function LoginPage() {
  usePageTitle('Вход')
  const [searchParams] = useSearchParams()
  const next = nextPath(searchParams.get('next'))
  const form = useForm({ resolver: zodResolver(loginSchema) })
  const { register, formState: { errors, isSubmitting } } = form
  const { onSubmit, isPending } = useRouteForm(form, loginFields)
  const busy = isSubmitting || isPending

  return (
    <form className="details narrow form auth-form" onSubmit={onSubmit} aria-busy={busy} noValidate>
      <p className="eyebrow">Личный кабинет</p>
      <h1>Вход</h1>
      <p className="muted">Войдите, чтобы сохранить корзину и вернуться к своим заказам.</p>
      <FormInput label="Имя пользователя" autoComplete="username"
        error={errors.username?.message} {...register('username')} />
      <FormInput label="Пароль" type="password" autoComplete="current-password"
        error={errors.password?.message} {...register('password')} />
      {errors.root?.message && <p className="error" role="alert">{errors.root.message}</p>}
      <button type="submit" disabled={busy}>{busy ? 'Входим…' : 'Войти'}</button>
      <p>Нет учётной записи? <Link to={`/register?next=${encodeURIComponent(next)}`}>Регистрация</Link></p>
    </form>
  )
}
