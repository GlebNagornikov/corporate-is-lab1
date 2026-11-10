import type { QueryClient } from '@tanstack/react-query'
import { data, type LoaderFunctionArgs, type RouteObject } from 'react-router'
import { orderQuery, ordersQuery, readOrderPage } from './api/orders'
import { categoriesQuery, productQuery, productsQuery } from './api/queries'
import { meQuery, requireUser } from './auth/session'
import SessionOutlet from './auth/SessionOutlet'
import CartPage from './cart/CartPage'
import { cartQuery } from './cart/queries'
import { parseCatalogParams } from './lib/catalogParams'
import { managerRoutes } from './manager/routes'
import CatalogPage from './routes/CatalogPage'
import NotFoundPage from './routes/NotFoundPage'
import ProductPage from './routes/ProductPage'
import RootLayout from './routes/RootLayout'
import RouteError from './routes/RouteError'
import RootError from './routes/RootError'

export function createAppRoutes(queryClient: QueryClient): RouteObject[] {
  const catalog = {
    Component: CatalogPage,
    loader: ({ request }: LoaderFunctionArgs) => {
      void queryClient.prefetchQuery(categoriesQuery())
      void queryClient.prefetchQuery(productsQuery(parseCatalogParams(new URL(request.url).searchParams)))
      return null
    },
  }
  return [
    {
      path: '/',
      Component: RootLayout,
      ErrorBoundary: RootError,
      HydrateFallback: () => <p className="shell layout" role="status">Загрузка книжной полки…</p>,
      loader: async () => {
        await queryClient.ensureQueryData(meQuery())
        return null
      },
      children: [
        { index: true, ...catalog },
        { path: 'catalog', ...catalog },
        {
          path: 'products/:slug',
          Component: ProductPage,
          ErrorBoundary: RouteError,
          loader: async ({ params }) => {
            void queryClient.prefetchQuery(categoriesQuery())
            await queryClient.ensureQueryData(productQuery(params.slug!))
            return null
          },
        },
        { path: 'cart', Component: CartPage },
        {
          path: 'login',
          lazy: async () => {
            const [{ default: Component }, { loginAction }] = await Promise.all([
              import('./auth/LoginPage'), import('./auth/authActions'),
            ])
            return { Component, action: ({ request }) => loginAction(request, queryClient) }
          },
        },
        {
          path: 'register',
          lazy: async () => {
            const [{ default: Component }, { registerAction }] = await Promise.all([
              import('./auth/RegisterPage'), import('./auth/authActions'),
            ])
            return { Component, action: ({ request }) => registerAction(request, queryClient) }
          },
        },
        {
          Component: SessionOutlet,
          children: [
            {
              path: 'checkout',
              shouldRevalidate: ({ actionResult, defaultShouldRevalidate }) =>
                actionResult?.orderId ? false : defaultShouldRevalidate,
              lazy: async () => {
                const [{ default: Component }, { checkoutAction }] = await Promise.all([
                  import('./orders/CheckoutPage'), import('./orders/checkoutAction'),
                ])
                return { Component, action: ({ request }) => checkoutAction(request, queryClient) }
              },
              loader: async ({ request }) => {
                await requireUser(request, queryClient)
                void queryClient.prefetchQuery(cartQuery())
                return null
              },
            },
            {
              path: 'orders',
              lazy: async () => ({ Component: (await import('./orders/OrdersPage')).default }),
              loader: async ({ request }) => {
                await requireUser(request, queryClient)
                const page = readOrderPage(new URL(request.url).searchParams)
                void queryClient.prefetchQuery(ordersQuery({ page }))
                return null
              },
            },
            {
              path: 'orders/:orderId',
              lazy: async () => ({ Component: (await import('./orders/OrderPage')).default }),
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
          ],
        },
        { path: '*', Component: NotFoundPage },
      ],
    },
    managerRoutes(queryClient),
  ]
}
