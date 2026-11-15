import { useState, type FormEvent } from 'react'
import { formatPrice } from '../lib/format'

const acceptedCard = '4242424242424242'
const declinedCard = '4000000000000002'

function passesLuhn(number: string) {
  return [...number].reverse().reduce((sum, digit, index) => {
    const value = Number(digit) * (index % 2 === 0 ? 1 : 2)
    return sum + (value > 9 ? value - 9 : value)
  }, 0) % 10 === 0
}

function validExpiry(expiry: string) {
  if (!/^\d{2}\/\d{2}$/.test(expiry)) return false
  const month = Number(expiry.slice(0, 2))
  const year = 2000 + Number(expiry.slice(3))
  const now = new Date()
  return month >= 1 && month <= 12 &&
    (year > now.getFullYear() || (year === now.getFullYear() && month >= now.getMonth() + 1))
}

type Field = 'number' | 'expiry' | 'code'

export default function PaymentCardForm({ total, disabled, submit }: {
  total: string
  disabled: boolean
  submit: (outcome: 'success' | 'failed') => void
}) {
  const [number, setNumber] = useState('')
  const [expiry, setExpiry] = useState('')
  const [code, setCode] = useState('')
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({})

  function pay(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (disabled) return
    const next: typeof errors = {}
    if (number.length !== 16 || !passesLuhn(number)) {
      next.number = 'Введите действительный номер из 16 цифр.'
    } else if (number !== acceptedCard && number !== declinedCard) {
      next.number = 'Введите один из двух учебных номеров, указанных над формой.'
    }
    if (!validExpiry(expiry)) next.expiry = 'Укажите месяц ММ/ГГ. Срок не должен истечь.'
    if (code.length !== 3) next.code = 'Введите три цифры.'
    setErrors(next)
    const invalid = Object.keys(next)[0]
    if (invalid) {
      const input = event.currentTarget.elements.namedItem(invalid)
      if (input instanceof HTMLInputElement) input.focus()
      return
    }
    setCode('')
    submit(number === acceptedCard ? 'success' : 'failed')
  }

  return (
    <form className="form payment-card-form" noValidate autoComplete="off" onSubmit={pay}>
      <div className="payment-instructions">
        <p>Используйте учебные реквизиты. Реальные деньги не списываются.</p>
        <ul>
          <li><code>4242 4242 4242 4242</code> — успешный платёж</li>
          <li><code>4000 0000 0000 0002</code> — отказ банка</li>
        </ul>
        <p>Укажите текущий или будущий месяц и любые три цифры CVV.</p>
      </div>
      <div className="payment-card">
        <label className="form-field">
          Номер карты
          <input name="number" inputMode="numeric" required placeholder="0000 0000 0000 0000"
            value={number.replace(/(\d{4})(?=\d)/g, '$1 ')}
            aria-invalid={Boolean(errors.number)} aria-describedby={errors.number ? 'payment-number-error' : undefined}
            onChange={({ target }) => { setNumber(target.value.replace(/\D/g, '').slice(0, 16)); setErrors({ ...errors, number: undefined }) }} />
        </label>
        {errors.number && <p className="error" id="payment-number-error" role="alert">{errors.number}</p>}
        <div className="payment-card-fields">
          <div>
            <label className="form-field">
              Срок действия
              <input name="expiry" inputMode="numeric" required placeholder="ММ/ГГ" value={expiry}
                aria-invalid={Boolean(errors.expiry)} aria-describedby={errors.expiry ? 'payment-expiry-error' : undefined}
                onChange={({ target }) => {
                  const digits = target.value.replace(/\D/g, '').slice(0, 4)
                  setExpiry(digits.length > 2 ? digits.slice(0, 2) + '/' + digits.slice(2) : digits)
                  setErrors({ ...errors, expiry: undefined })
                }} />
            </label>
            {errors.expiry && <p className="error" id="payment-expiry-error" role="alert">{errors.expiry}</p>}
          </div>
          <div>
            <label className="form-field">
              CVV
              <input name="code" type="password" inputMode="numeric" required placeholder="•••" value={code}
                aria-invalid={Boolean(errors.code)} aria-describedby={errors.code ? 'payment-code-error' : undefined}
                onChange={({ target }) => { setCode(target.value.replace(/\D/g, '').slice(0, 3)); setErrors({ ...errors, code: undefined }) }} />
            </label>
            {errors.code && <p className="error" id="payment-code-error" role="alert">{errors.code}</p>}
          </div>
        </div>
      </div>
      <button type="submit" disabled={disabled}>Оплатить {formatPrice(total)}</button>
    </form>
  )
}
