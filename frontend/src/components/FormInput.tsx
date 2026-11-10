import { useId, type ComponentPropsWithRef } from 'react'

type FormInputProps = ComponentPropsWithRef<'input'> & {
  label: string
  error?: string
}

export default function FormInput({ label, error, 'aria-describedby': hintId, ...input }: FormInputProps) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <input
        {...input}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={[hintId, error ? errorId : undefined].filter(Boolean).join(' ') || undefined}
      />
      {error && <p className="error" id={errorId}>{error}</p>}
    </div>
  )
}
