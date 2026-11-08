import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { meQuery } from './session'
import { SessionContext } from './useSession'

export function SessionProvider({ children }: { children: ReactNode }) {
  const session = useQuery(meQuery())
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}
