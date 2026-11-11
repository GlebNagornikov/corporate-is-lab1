import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../api/client'
import { orderQuery } from '../api/orders'
import { tokens } from '../auth/tokens'
import { useSession } from '../auth/useSession'

// The endpoint sends LF-delimited SSE frames. Network chunks may split any frame.
async function readOrderEvents(stream: ReadableStream<Uint8Array>, onChange: () => void) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) return
      pending += decoder.decode(new Uint8Array(value), { stream: true })
      let end = pending.indexOf('\n\n')
      while (end !== -1) {
        const event = pending.slice(0, end)
        pending = pending.slice(end + 2)
        if (event.startsWith('event: order-changed\n')) onChange()
        end = pending.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export function useOrderEvents(id: number, enabled: boolean) {
  const client = useQueryClient()
  const userId = useSession().data?.id

  useEffect(() => {
    if (!enabled || !userId || !tokens.access()) return
    const version = tokens.version()
    const connection = new AbortController()
    const { signal } = connection
    const isCurrent = () => !signal.aborted && tokens.version() === version
    let retry: ReturnType<typeof setTimeout> | undefined
    let delay = 1_000

    async function connect() {
      if (!isCurrent()) return
      try {
        const { data, response } = await api.GET('/api/orders/{id}/events/', {
          params: { path: { id } },
          headers: { Accept: 'text/event-stream' },
          parseAs: 'stream',
          signal,
        })
        if ([401, 403, 404].includes(response.status)) return
        if (data && response.headers.get('content-type')?.startsWith('text/event-stream')) {
          await readOrderEvents(data, () => {
            if (!isCurrent()) return
            delay = 1_000
            void client.invalidateQueries({ queryKey: orderQuery(id).queryKey })
            void client.invalidateQueries({ queryKey: ['orders', 'list'] })
          })
        } else {
          await data?.cancel()
        }
      } catch {
        // A dropped stream is reopened. Session changes and navigation abort it.
      }
      if (isCurrent()) {
        retry = setTimeout(() => { void connect() }, delay)
        delay = Math.min(delay * 2, 30_000)
      }
    }

    void connect()
    return () => {
      connection.abort()
      clearTimeout(retry)
    }
  }, [client, enabled, id, userId])
}
