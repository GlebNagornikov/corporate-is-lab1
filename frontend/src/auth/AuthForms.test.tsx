import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, expect, test, vi } from 'vitest'
import { queryClient } from '../queryClient'
import { renderRoute } from '../test/render'
import { server } from '../test/server'
import LoginPage from './LoginPage'
import { nextPath } from './nextPath'
import RegisterPage from './RegisterPage'
import { loginAction, registerAction } from './authActions'
import { tokens } from './tokens'

afterEach(() => {
  tokens.clear()
  queryClient.clear()
})

test('форма входа показывает ошибку пароля и после успешного входа возвращает на исходный адрес', async () => {
  const token = vi.fn()
    .mockReturnValueOnce(HttpResponse.json({ detail: 'Неверные данные' }, { status: 401 }))
    .mockReturnValueOnce(HttpResponse.json({ access: 'a' }))
  server.use(
    http.post('*/api/auth/session/login/', token),
    http.get('*/api/auth/me/', () => HttpResponse.json({ id: 1, username: 'buyer' })),
    http.get('*/api/cart/', () => HttpResponse.json({ items: [], count: 0, total: '0.00' })),
  )
  const user = userEvent.setup()
  renderRoute(<LoginPage />, '/?next=%2F%3Ffrom%3Dcheckout', loginAction)

  await user.type(screen.getByLabelText('Имя пользователя'), 'buyer')
  await user.type(screen.getByLabelText('Пароль'), 'secret')
  await user.click(screen.getByRole('button', { name: 'Войти' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Неверное имя пользователя или пароль')
  await user.click(screen.getByRole('button', { name: 'Войти' }))
  expect(await screen.findByText('/?from=checkout')).toBeInTheDocument()
  expect(token).toHaveBeenCalledTimes(2)
})

test('форма регистрации проверяет совпадение паролей и показывает полевые и общие ошибки DRF', async () => {
  const registration = vi.fn(() => HttpResponse.json({
    username: ['Имя уже занято.'],
    non_field_errors: ['Регистрация недоступна.'],
  }, { status: 400 }))
  server.use(http.post('*/api/auth/register/', registration))
  const user = userEvent.setup()
  renderRoute(<RegisterPage />, '/', registerAction)

  await user.type(screen.getByLabelText('Имя пользователя'), 'buyer')
  await user.type(screen.getByLabelText('Электронная почта'), 'buyer@example.test')
  await user.type(screen.getByLabelText('Пароль', { exact: true }), 'password1')
  const confirmation = screen.getByLabelText('Пароль ещё раз')
  await user.type(confirmation, 'password2')
  const submit = screen.getByRole('button', { name: 'Зарегистрироваться' })
  await user.click(submit)
  expect(await screen.findByText('Пароли не совпадают')).toBeInTheDocument()
  expect(registration).not.toHaveBeenCalled()

  await user.clear(confirmation)
  await user.type(confirmation, 'password1')
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent('Регистрация недоступна.')
  expect(screen.getByLabelText('Имя пользователя')).toHaveAccessibleDescription('Имя уже занято.')
})

test('возврат после входа допускает только внутренний путь', () => {
  for (const path of ['https://example.test', '//example.test', '/\\example.test', '/a/..//example.test']) {
    expect(nextPath(path)).toBe('/')
  }
  expect(nextPath('/checkout?from=cart#delivery')).toBe('/checkout?from=cart#delivery')
})
