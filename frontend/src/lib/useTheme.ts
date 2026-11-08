import { useEffect, useState } from 'react'

const storageKey = 'bookshop-theme'
export type Theme = 'system' | 'light' | 'dark'

export function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(storageKey)
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    return 'system'
  }
}

export function applyTheme(theme: Theme) {
  if (theme === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
}

export function useTheme() {
  const [theme, setTheme] = useState(readTheme)
  useEffect(() => { applyTheme(theme) }, [theme])

  function selectTheme(choice: Theme) {
    setTheme(choice)
    try {
      if (choice === 'system') localStorage.removeItem(storageKey)
      else localStorage.setItem(storageKey, choice)
    } catch {
      // Тема по-прежнему действует до перезагрузки.
    }
  }

  return { theme, selectTheme }
}
