import type { QueryClient } from '@tanstack/react-query'
import { replace } from 'react-router'
import { submitRouteForm } from '../lib/routeForm'
import { z } from '../lib/zod'
import { nextPath } from './nextPath'
import { login, register } from './session'

export const loginSchema = z.object({
  username: z.string().trim().min(1, 'Введите имя пользователя'),
  password: z.string().min(1, 'Введите пароль'),
})

export const registerSchema = z.object({
  username: z.string().trim().min(3, 'Не короче 3 символов'),
  email: z.email('Введите адрес почты'),
  password: z.string().min(8, 'Не короче 8 символов'),
  password2: z.string(),
}).refine(({ password, password2 }) => password === password2, {
  path: ['password2'], message: 'Пароли не совпадают',
})

export const loginFields = ['username', 'password'] as const
export const registerFields = ['username', 'email', 'password', 'password2'] as const

const sessionMutationKey = ['session', 'sign-in']
const destination = (request: Request) => nextPath(new URL(request.url).searchParams.get('next'))

export function loginAction(request: Request, client: QueryClient) {
  return submitRouteForm(request, loginSchema, client, sessionMutationKey, async ({ username, password }) => {
    await login(username, password, client)
    return replace(destination(request))
  })
}

export function registerAction(request: Request, client: QueryClient) {
  return submitRouteForm(request, registerSchema, client, sessionMutationKey, async ({ username, email, password }) => {
    await register({ username, email, password }, client)
    return replace(destination(request))
  })
}
