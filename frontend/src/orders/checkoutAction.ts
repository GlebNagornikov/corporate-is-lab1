import type { QueryClient } from '@tanstack/react-query'
import { api, ApiError, requireData } from '../api/client'
import { orderQuery } from '../api/orders'
import { requireUser } from '../auth/session'
import { tokens } from '../auth/tokens'
import { priceChangesQuery } from '../cart/priceChanges'
import { cartQuery } from '../cart/queries'
import { submitRouteForm } from '../lib/routeForm'
import { checkoutSchema } from './checkoutSchema'

export async function checkoutAction(request: Request, client: QueryClient) {
  await requireUser(request, client)
  const version = tokens.version()
  return submitRouteForm(request, checkoutSchema, client, ['orders', 'checkout'], async (values) => {
    const order = requireData(await api.POST('/api/orders/', {
      body: { ...values, address: values.delivery_method === 'courier' ? values.address : '' },
    }))
    const cartKey = cartQuery().queryKey
    await client.cancelQueries({ queryKey: cartKey })
    if (version !== tokens.version()) throw new ApiError(401, 'Сессия изменилась. Войдите снова.')
    client.setQueryData(cartKey, { items: [], count: 0, total: '0.00' })
    client.removeQueries({ queryKey: priceChangesQuery().queryKey })
    client.setQueryData(orderQuery(order.id).queryKey, order)
    void client.invalidateQueries({ queryKey: ['orders', 'list'] })
    return { orderId: order.id }
  })
}
