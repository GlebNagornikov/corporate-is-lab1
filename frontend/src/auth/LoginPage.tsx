import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import FormInput from '../components/FormInput'
import { applyServerErrors } from '../lib/serverErrors'
import { z } from '../lib/zod'
import { nextPath } from './nextPath'
import { login } from './session'

const schema = z.object({
  username: z.string().trim().min(1, 'Введите имя пользователя'),
  password: z.string().min(1, 'Введите пароль'),
})
type LoginForm = z.infer<typeof schema>

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = nextPath(searchParams.get('next'))
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } =
    useForm<LoginForm>({ resolver: zodResolver(schema) })

  async function onSubmit({ username, password }: LoginForm) {
    try {
      await login(username, password)
      void navigate(next, { replace: true })
    } catch (error) {
      applyServerErrors(error, setError, ['username', 'password'])
    }
  }

  return (
    <form className="details narrow form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <h1>Вход</h1>
      <FormInput label="Имя пользователя" autoComplete="username"
        error={errors.username?.message} {...register('username')} />
      <FormInput label="Пароль" type="password" autoComplete="current-password"
        error={errors.password?.message} {...register('password')} />
      {errors.root?.message && <p className="error" role="alert">{errors.root.message}</p>}
      <button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Входим…' : 'Войти'}</button>
      <p>Нет учётной записи? <Link to={`/register?next=${encodeURIComponent(next)}`}>Регистрация</Link></p>
    </form>
  )
}
