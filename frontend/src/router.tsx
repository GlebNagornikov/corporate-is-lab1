import { createBrowserRouter } from 'react-router'
import { createAppRoutes } from './appRoutes'
import { queryClient } from './queryClient'

export const router = createBrowserRouter(createAppRoutes(queryClient))
