import type { QueryClient } from '@tanstack/react-query'
import { data, redirect, replace, type RouteObject } from 'react-router'
import { requireManager } from '../auth/session'
import { readOrderPage } from '../api/orders'
import NotFoundPage from '../routes/NotFoundPage'
import RouteError from '../routes/RouteError'
import { orderFilters } from './orderFilters'
import { defaultReportPeriod, readReportPeriod, reportPeriodError } from './reportPeriod'
import {
  catalogFilters, managerBookQuery, managerBooksQuery, managerCategoriesQuery,
  managerOrderQuery, managerOrdersQuery, managerPromosQuery, managerReviewsQuery,
  managerReportQuery,
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
      {
        path: 'reviews',
        lazy: async () => ({ Component: (await import('./ManagerReviewsPage')).default }),
        loader: async ({ request }) => {
          await requireManager(request, client)
          void client.prefetchQuery(managerReviewsQuery())
          return null
        },
      },
      {
        path: 'promos',
        lazy: async () => ({ Component: (await import('./ManagerPromosPage')).default }),
        loader: async ({ request }) => {
          await requireManager(request, client)
          void client.prefetchQuery(managerPromosQuery(readOrderPage(new URL(request.url).searchParams)))
          return null
        },
      },
      {
        path: 'reports',
        lazy: async () => ({ Component: (await import('./ManagerReportPage')).default }),
        loader: async ({ request }) => {
          await requireManager(request, client)
          const url = new URL(request.url)
          if (!url.searchParams.has('start') && !url.searchParams.has('end')) {
            url.search = new URLSearchParams(defaultReportPeriod()).toString()
            return replace(url.pathname + url.search)
          }
          const period = readReportPeriod(url.searchParams)
          if (!reportPeriodError(period)) void client.prefetchQuery(managerReportQuery(period))
          return null
        },
      },
      { path: '*', Component: NotFoundPage },
    ],
  }
}
