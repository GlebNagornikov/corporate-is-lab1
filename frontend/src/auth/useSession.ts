import type { UseQueryResult } from '@tanstack/react-query'
import { createContext, useContext } from 'react'
import type { Me } from '../api/client'

export const SessionContext = createContext<UseQueryResult<Me | null> | null>(null)

export function useSession() {
  const session = useContext(SessionContext)
  if (!session) throw new Error('SessionProvider is missing')
  return session
}
