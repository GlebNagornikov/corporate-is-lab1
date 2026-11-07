import type { QueryClient } from '@tanstack/react-query'
import { data, type RouteObject } from 'react-router'
import { orderQuery, ordersQuery } from './api/orders'
import { categoriesQuery, productQuery, productsQuery } from './api/queries'
import { meQuery, requireManager, requireUser } from './auth/session'
import SessionOutlet from './auth/SessionOutlet'
import CartPage from './cart/CartPage'
import { cartQuery } from './cart/queries'
import { parseCatalogParams } from './lib/catalogParams'
import { orderFilters } from './manager/orderFilters'
import OrderPage from './orders/OrderPage'
import OrdersPage from './orders/OrdersPage'
import CatalogPage from './routes/CatalogPage'
import NotFoundPage from './routes/NotFoundPage'
import ProductPage from './routes/ProductPage'
import RootLayout from './routes/RootLayout'
import RouteError from './routes/RouteError'

export function createAppRoutes(queryClient: QueryClient): RouteObject[] {
  return [
    {
      path: '/',
      Component: RootLayout,
      ErrorBoundary: RouteError,
      HydrateFallback: () => <p role="status">Загрузка…</p>,
      loader: async () => {
        void queryClient.prefetchQuery(categoriesQuery())
        await queryClient.ensureQueryData(meQuery())
        return null
      },
      children: [
        {
          index: true,
          Component: CatalogPage,
          loader: ({ request }) => {
            const query = parseCatalogParams(new URL(request.url).searchParams)
            void queryClient.prefetchQuery(productsQuery(query))
            return null
          },
        },
        {
          path: 'products/:slug',
          Component: ProductPage,
          ErrorBoundary: RouteError,
          loader: async ({ params }) => {
            await queryClient.ensureQueryData(productQuery(params.slug!))
            return null
          },
        },
        { path: 'cart', Component: CartPage },
        {
          path: 'login',
          lazy: async () => ({ Component: (await import('./auth/LoginPage')).default }),
        },
        {
          path: 'register',
          lazy: async () => ({ Component: (await import('./auth/RegisterPage')).default }),
        },
        {
          Component: SessionOutlet,
          children: [
            {
              path: 'checkout',
              lazy: async () => ({ Component: (await import('./orders/CheckoutPage')).default }),
              loader: async ({ request }) => {
                await requireUser(request, queryClient)
                void queryClient.prefetchQuery(cartQuery())
                return null
              },
            },
            {
              path: 'orders',
              Component: OrdersPage,
              loader: async ({ request }) => {
                await requireUser(request, queryClient)
                void queryClient.prefetchQuery(ordersQuery())
                return null
              },
            },
            {
              path: 'orders/:orderId',
              Component: OrderPage,
              ErrorBoundary: RouteError,
              loader: async ({ request, params }) => {
                await requireUser(request, queryClient)
                const id = Number(params.orderId)
                if (!Number.isSafeInteger(id) || id <= 0) {
                  throw data('Заказ не найден.', { status: 404 })
                }
                await queryClient.ensureQueryData(orderQuery(id))
                return null
              },
            },
            {
              path: 'manager',
              ErrorBoundary: RouteError,
              loader: async ({ request }) => {
                await requireManager(request, queryClient)
                void queryClient.prefetchQuery(ordersQuery(orderFilters(new URL(request.url).searchParams)))
                return null
              },
              children: [{
                path: 'orders',
                lazy: async () => ({
                  Component: (await import('./manager/ManagerOrdersPage')).default,
                }),
              }],
            },
          ],
        },
        { path: '*', Component: NotFoundPage },
      ],
    },
  ]
}
