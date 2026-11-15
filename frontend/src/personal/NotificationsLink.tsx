import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { NavLink } from 'react-router'
import StoreIcon from '../components/StoreIcon'
import { notificationsQuery } from './queries'
import RestockNotice from './RestockNotice'

export default function NotificationsLink({ userId }: { userId: number }) {
  const client = useQueryClient()
  const { data } = useQuery(notificationsQuery(userId))
  const count = data?.filter((item) => item.read_at === null).length ?? 0

  useEffect(() => {
    const refresh = () => {
      void client.invalidateQueries({ queryKey: notificationsQuery(userId).queryKey })
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    const timer = window.setInterval(refresh, 30_000)
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [client, userId])

  return (
    <>
      <NavLink className="nav-icon" to="/notifications" aria-label={count ? `Уведомления, непрочитанных: ${count}` : undefined}>
        <StoreIcon name="bell" />Уведомления
        {count > 0 && <span className="badge" aria-hidden="true">{count}</span>}
      </NavLink>
      <RestockNotice notifications={data} />
    </>
  )
}
