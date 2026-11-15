import { Navigate, Outlet, useLocation } from 'react-router'
import { useSession } from './useSession'
import { loginPath } from './session'

export default function SessionOutlet() {
  const { data: me } = useSession()
  const location = useLocation()
  return me ? <Outlet /> : <Navigate to={loginPath(location)} replace />
}
