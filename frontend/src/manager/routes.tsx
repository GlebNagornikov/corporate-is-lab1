import type { QueryClient } from '@tanstack/react-query'
import { data, redirect, type RouteObject } from 'react-router'
import { requireManager } from '../auth/session'
import NotFoundPage from '../routes/NotFoundPage'
import RouteError from '../routes/RouteError'
import { orderFilters } from './orderFilters'
import {
  catalogFilters, managerBookQuery, managerBooksQuery, managerCategoriesQuery,
  managerOrderQuery, managerOrdersQuery,
} from './queries'

export function routeId(value: string | undefined, message: string) {
  const id = Number(value)
  if (!Number.isSafeInteger(id) || id <= 0) throw data(message, { status: 404 })
  return id
}

export function managerRoutes(client: QueryClient): RouteObject {
  return {
    path: '/manager',
    lazy: async () => ({ Component: (await import('./ManagerLayout')).ManagerLayout }),
    ErrorBoundary: RouteError,
    HydrateFallback: () => <p className="shell layout" role="status">Загрузка кабинета…</p>,
    loader: async ({ request }) => {
      await requireManager(request, client)
      return null
    },
    children: [
      { index: true, loader: () => redirect('/manager/orders') },
      {
        path: 'orders',
        lazy: async () => ({ Component: (await import('./ManagerOrdersPage')).default }),
        loader: async ({ request }) => {
          await requireManager(request, client)
          void client.prefetchQuery(managerOrdersQuery(orderFilters(new URL(request.url).searchParams)))
          return null
        },
      },
      {
        path: 'orders/:orderId',
        ErrorBoundary: RouteError,
        lazy: async () => ({ Component: (await import('../orders/OrderPage')).ManagerOrderPage }),
        loader: async ({ request, params }) => {
          await requireManager(request, client)
          await client.ensureQueryData(managerOrderQuery(routeId(params.orderId, 'Заказ не найден.')))
          return null
        },
      },
      {
        path: 'catalog/import',
        ErrorBoundary: RouteError,
        lazy: async () => ({ Component: (await import('./ManagerImportPage')).default }),
        loader: async ({ request }) => {
          await requireManager(request, client)
          await client.ensureQueryData(managerCategoriesQuery())
          return null
        },
      },
      {
        path: 'catalog',
        lazy: async () => ({ Component: (await import('./ManagerCatalogPage')).default }),
        loader: async ({ request }) => {
          await requireManager(request, client)
          void client.prefetchQuery(managerBooksQuery(catalogFilters(new URL(request.url).searchParams)))
          return null
        },
      },
      ...['catalog/new', 'catalog/:bookId/edit'].map((path): RouteObject => ({
        path,
        ErrorBoundary: RouteError,
        lazy: async () => {
          const [{ default: Component }, { bookAction }] = await Promise.all([
            import('./ManagerBookPage'), import('./bookAction'),
          ])
          return { Component, action: ({ request, params }) => bookAction(request, client, params.bookId) }
        },
        loader: async ({ request, params }) => {
          await requireManager(request, client)
          await Promise.all([
            client.ensureQueryData(managerCategoriesQuery()),
            params.bookId
              ? client.ensureQueryData(managerBookQuery(routeId(params.bookId, 'Книга не найдена.')))
              : null,
          ])
          return null
        },
      })),
      ...[
        ['reviews', 'Отзывы'],
        ['promos', 'Промокоды'],
        ['reports', 'Отчёты'],
      ].map(([path, title]): RouteObject => ({
        path,
        lazy: async () => {
          const { ManagerPlaceholder } = await import('./ManagerLayout')
          return { Component: () => <ManagerPlaceholder title={title} /> }
        },
      })),
      { path: '*', Component: NotFoundPage },
    ],
  }
}
