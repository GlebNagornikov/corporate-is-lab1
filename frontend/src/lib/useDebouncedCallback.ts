import { useCallback, useLayoutEffect, useRef } from 'react'

export function useDebouncedCallback(callback: () => void, delay: number) {
  const timer = useRef<number | undefined>(undefined)
  const latest = useRef(callback)
  useLayoutEffect(() => { latest.current = callback }, [callback])

  const cancel = useCallback(() => window.clearTimeout(timer.current), [])
  useLayoutEffect(() => cancel, [cancel, delay])

  function schedule() {
    cancel()
    timer.current = window.setTimeout(() => latest.current(), delay)
  }

  return { schedule, cancel }
}
