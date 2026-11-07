import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import { ApiError } from '../api/client'

export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fieldNames: readonly Path<T>[],
) {
  if (!(error instanceof ApiError)) {
    setError('root', { message: 'Сервер недоступен. Попробуйте позже.' })
    return
  }

  const root = new Set<string>()
  let hasFieldError = false
  for (const [name, messages] of Object.entries(error.fields)) {
    if (messages.length === 0) continue
    const field = fieldNames.find((field) => field === name)
    if (field) {
      setError(field, { message: messages.join(' ') }, { shouldFocus: !hasFieldError })
      hasFieldError = true
    } else {
      messages.forEach((message) => root.add(message))
    }
  }
  const repeatsField = Object.values(error.fields).flat().includes(error.message)
  if (!repeatsField || (!hasFieldError && root.size === 0)) root.add(error.message)
  if (root.size > 0) setError('root', { message: [...root].join(' ') })
}
