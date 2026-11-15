import { act, renderHook } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { useDebouncedCallback } from './useDebouncedCallback'
import { usePageTitle } from './usePageTitle'

test('задержка объединяет изменения, вызывает свежую функцию и очищает таймер', () => {
  vi.useFakeTimers()
  try {
    const first = vi.fn()
    const latest = vi.fn()
    const { result, rerender, unmount } = renderHook(({ callback }) => useDebouncedCallback(callback, 300), {
      initialProps: { callback: first },
    })
    act(() => {
      result.current.schedule()
      vi.advanceTimersByTime(150)
      result.current.schedule()
    })
    rerender({ callback: latest })
    act(() => vi.advanceTimersByTime(299))
    expect(latest).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(first).not.toHaveBeenCalled()
    expect(latest).toHaveBeenCalledOnce()
    act(() => result.current.schedule())
    unmount()
    act(() => vi.advanceTimersByTime(300))
    expect(latest).toHaveBeenCalledOnce()
  } finally {
    vi.useRealTimers()
  }
})

test('название вкладки меняется вместе со страницей', () => {
  const { rerender } = renderHook<void, { title?: string }>(({ title }) => usePageTitle(title), {
    initialProps: { title: 'Корзина' },
  })
  expect(document.title).toBe('Корзина · Книжная полка')
  rerender({ title: undefined })
  expect(document.title).toBe('Книжная полка')
})
