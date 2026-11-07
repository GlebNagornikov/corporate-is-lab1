import { z } from '../lib/zod'

function isRussianPhone(value: string): boolean {
  return /^(?:[78]\d{10}|9\d{9})$/.test(value.replace(/\D/g, ''))
}

export const checkoutSchema = z.object({
  full_name: z.string().trim().min(2, 'Укажите имя получателя').max(200, 'Не длиннее 200 символов'),
  phone: z.string().trim().max(20, 'Не длиннее 20 символов')
    .refine(isRussianPhone, 'Введите российский номер, например +7 913 123-45-67'),
  email: z.email('Введите адрес почты'),
  delivery_method: z.enum(['pickup', 'courier']),
  address: z.string().trim().max(300, 'Не длиннее 300 символов'),
  comment: z.string().max(500, 'Не длиннее 500 символов'),
  promo_code: z.string().trim().max(30, 'Не длиннее 30 символов'),
}).refine(({ delivery_method, address }) => delivery_method !== 'courier' || address !== '', {
  path: ['address'],
  message: 'Для доставки курьером укажите адрес',
})

export type CheckoutForm = z.infer<typeof checkoutSchema>

export const checkoutFields = [
  'full_name', 'phone', 'email', 'delivery_method', 'address', 'comment', 'promo_code',
] as const satisfies readonly (keyof CheckoutForm)[]
