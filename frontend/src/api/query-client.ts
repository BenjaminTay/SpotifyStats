import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 min — data is fresh enough to skip background refetch
      gcTime: 30 * 60 * 1000, // 30 min cache retention
      retry: 2,
      refetchOnWindowFocus: false, // local app, no need to refetch on focus
    },
  },
})
