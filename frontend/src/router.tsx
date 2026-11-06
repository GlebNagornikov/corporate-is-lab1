import { createBrowserRouter } from 'react-router'
import { categoriesQuery, productQuery, productsQuery } from './api/queries'
import { parseCatalogParams } from './lib/catalogParams'
import { queryClient } from './queryClient'
import CatalogPage from './routes/CatalogPage'
import NotFoundPage from './routes/NotFoundPage'
import ProductPage from './routes/ProductPage'
import RootLayout from './routes/RootLayout'
import RouteError from './routes/RouteError'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: RootLayout,
    ErrorBoundary: RouteError,
    HydrateFallback: () => <p role="status">Загрузка…</p>,
    loader: () => {
      void queryClient.prefetchQuery(categoriesQuery())
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
      { path: '*', Component: NotFoundPage },
    ],
  },
])
