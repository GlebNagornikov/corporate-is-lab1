import { describe, expect, test } from 'vitest'
import { checkoutSchema } from './checkoutSchema'

const valid = {
  full_name: 'Анна Смирнова',
  phone: '8 (913) 123-45-67',
  email: 'anna@example.test',
  delivery_method: 'pickup',
  address: '',
  comment: '',
  promo_code: '',
}

describe('checkoutSchema', () => {
  test('самовывоз допускает пустой адрес', () => {
    expect(checkoutSchema.safeParse(valid).success).toBe(true)
  })

  test('пустой адрес курьера даёт ошибку поля address', () => {
    const result = checkoutSchema.safeParse({ ...valid, delivery_method: 'courier', address: '  ' })
    expect(result.success).toBe(false)
    expect(result.error?.issues.map(({ path }) => path)).toEqual([['address']])
  })

  test.each(['+7 913 123-45-67', '9131234567', '89131234567'])('принимает телефон %s', (phone) => {
    expect(checkoutSchema.safeParse({ ...valid, phone }).success).toBe(true)
  })

  test.each(['12345', '+1 202 555 0100'])('отклоняет телефон %s', (phone) => {
    const result = checkoutSchema.safeParse({ ...valid, phone })
    expect(result.success).toBe(false)
    expect(result.error?.issues.map(({ path }) => path)).toEqual([['phone']])
  })
})
