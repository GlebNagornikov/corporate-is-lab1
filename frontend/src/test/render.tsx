import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { createMemoryRouter, useLocation } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { SessionProvider } from '../auth/SessionProvider'
import { CartProvider } from '../cart/CartProvider'

function LocationProbe() {
  const { pathname, search } = useLocation()
  return <output data-testid="location">{pathname + search}</output>
}

export function renderRoute(element: ReactNode, initialEntry = '/', action?: (request: Request, client: QueryClient) => unknown) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  const router = createMemoryRouter(
    [
      {
        path: '/',
        action: action ? ({ request }) => action(request, queryClient) : undefined,
        element: (
          <>
            <SessionProvider><CartProvider>{element}</CartProvider></SessionProvider>
            <LocationProbe />
          </>
        ),
      },
    ],
    { initialEntries: [initialEntry] },
  )

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}
