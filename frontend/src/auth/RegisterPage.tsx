import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import FormInput from '../components/FormInput'
import { applyServerErrors } from '../lib/serverErrors'
import { z } from '../lib/zod'
import { nextPath } from './nextPath'
import { register as registerUser } from './session'

const schema = z.object({
  username: z.string().trim().min(3, 'Не короче 3 символов'),
  email: z.email('Введите адрес почты'),
  password: z.string().min(8, 'Не короче 8 символов'),
  password2: z.string(),
}).refine(({ password, password2 }) => password === password2, {
  path: ['password2'],
  message: 'Пароли не совпадают',
})
type RegisterForm = z.infer<typeof schema>

export default function RegisterPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = nextPath(searchParams.get('next'))
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } =
    useForm<RegisterForm>({ resolver: zodResolver(schema) })

  async function onSubmit({ username, email, password }: RegisterForm) {
    try {
      await registerUser({ username, email, password })
      void navigate(next, { replace: true })
    } catch (error) {
      applyServerErrors(error, setError, ['username', 'email', 'password'])
    }
  }

  return (
    <form className="details narrow form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <h1>Регистрация</h1>
      <FormInput label="Имя пользователя" autoComplete="username"
        error={errors.username?.message} {...register('username')} />
      <FormInput label="Электронная почта" type="email" autoComplete="email"
        error={errors.email?.message} {...register('email')} />
      <FormInput label="Пароль" type="password" autoComplete="new-password"
        error={errors.password?.message} {...register('password')} />
      <FormInput label="Пароль ещё раз" type="password" autoComplete="new-password"
        error={errors.password2?.message} {...register('password2')} />
      {errors.root?.message && <p className="error" role="alert">{errors.root.message}</p>}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Регистрируем…' : 'Зарегистрироваться'}
      </button>
      <p>Есть учётная запись? <Link to={`/login?next=${encodeURIComponent(next)}`}>Войти</Link></p>
    </form>
  )
}
