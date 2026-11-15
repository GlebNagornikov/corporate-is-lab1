import { useLayoutEffect, useRef, type RefObject } from 'react'
import { useLocation, useNavigationType } from 'react-router'

const positions = new Map<string, number>()

export function useCatalogScroll(
  catalog: RefObject<HTMLElement | null>,
  { page, start, isHome, ready }: { page: number; start: number; isHome: boolean; ready: boolean },
) {
  const { key, pathname } = useLocation()
  const navigationType = useNavigationType()
  const previous = useRef({ pathname, isHome, page, start })
  const restored = useRef<string>(undefined)

  useLayoutEffect(() => {
    const before = previous.current
    previous.current = { pathname, isHome, page, start }
    const selectedPage = start === page && (before.page !== page || before.start !== start)
    if (navigationType !== 'POP' && before.pathname === pathname &&
        (selectedPage || (isHome && !before.isHome))) {
      catalog.current?.scrollIntoView?.()
    }
  }, [catalog, isHome, navigationType, page, pathname, start])

  useLayoutEffect(() => {
    if (!ready) return
    const position = positions.get(key)
    if (navigationType === 'POP' && restored.current !== key &&
        position !== undefined && window.scrollY !== position) {
      window.scrollTo(0, position)
    }
    restored.current = key
    return () => { positions.set(key, window.scrollY) }
  }, [key, navigationType, ready])
}
