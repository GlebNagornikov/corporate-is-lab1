import type { QueryClient } from '@tanstack/react-query'
import { useEffect, useRef, type FormEvent } from 'react'
import type { FieldValues, Path, UseFormReturn } from 'react-hook-form'
import { useFetcher, useLocation } from 'react-router'
import { ApiError } from '../api/client'
import { applyServerErrors } from './serverErrors'
import type { z } from './zod'

type FormFailure = { status: number; message: string; fields: Record<string, string[]> }
type OrderPlaced = { orderId: number }
type FormResult = FormFailure | OrderPlaced

export async function submitRouteForm<T>(
  request: Request, schema: z.ZodType<T>, client: QueryClient, mutationKey: readonly string[],
  mutationFn: (values: T) => Promise<Response | OrderPlaced>,
): Promise<FormResult | Response> {
  const parsed = schema.safeParse(await request.json().catch(() => null))
  if (!parsed.success) {
    const fields: Record<string, string[]> = {}
    for (const { path: [field], message } of parsed.error.issues) {
      if (typeof field === 'string') (fields[field] ??= []).push(message)
    }
    return { status: 400, message: 'Проверьте данные формы.', fields }
  }
  if (client.isMutating({ mutationKey, exact: true })) {
    return { status: 409, message: 'Форма уже отправляется.', fields: {} }
  }
  try {
    return await client.getMutationCache().build(client, {
      mutationKey, mutationFn, retry: false,
    }).execute(parsed.data)
  } catch (error) {
    return error instanceof ApiError
      ? { status: error.status, message: error.message, fields: error.fields }
      : { status: 503, message: 'Сервер недоступен. Попробуйте позже.', fields: {} }
  }
}

export function useRouteForm<T extends FieldValues>(
  { handleSubmit, setError }: Pick<UseFormReturn<T>, 'handleSubmit' | 'setError'>,
  fields: readonly Path<T>[],
  onPlaced?: (orderId: number) => void,
) {
  const fetcher = useFetcher<FormResult>()
  const { pathname, search } = useLocation()
  const locked = useRef(false)
  const result = fetcher.data
  const handled = useRef<FormResult>(undefined)

  useEffect(() => {
    if (fetcher.state !== 'idle' || !result || result === handled.current) return
    handled.current = result
    if ('orderId' in result) onPlaced?.(result.orderId)
    else applyServerErrors(new ApiError(result.status, result.message, result.fields), setError, fields)
  }, [result, fetcher.state, fields, onPlaced, setError])

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (locked.current || fetcher.state !== 'idle') return
    locked.current = true
    void handleSubmit((values) => fetcher.submit(values, {
      method: 'post', encType: 'application/json', action: pathname + search,
    }))(event).finally(() => { locked.current = false })
  }

  return { onSubmit, isPending: fetcher.state !== 'idle' || Boolean(result && 'orderId' in result) }
}
