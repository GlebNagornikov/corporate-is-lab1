import { useQuery } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router'
import { loginPath, meQuery } from './session'

export default function SessionOutlet() {
  const { data: me } = useQuery(meQuery())
  const location = useLocation()
  return me ? <Outlet /> : <Navigate to={loginPath(location)} replace />
}
