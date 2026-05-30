import { useQuery } from '@tanstack/react-query'
import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import { api, type DashboardFullResponse } from '@/lib/api'

/** Prefetch dashboard data into the query cache. Safe to call multiple times. */
export function preloadDashboardData(): void {
  queryClient.prefetchQuery({
    queryKey: queryKeys.dashboard.full(),
    queryFn: () => api.get<DashboardFullResponse>('/dashboard/full'),
    staleTime: 5 * 60 * 1000,
  })
}

interface UseDashboardResult {
  data: DashboardFullResponse | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useDashboard(): UseDashboardResult {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.dashboard.full(),
    queryFn: () => api.get<DashboardFullResponse>('/dashboard/full'),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  return {
    data: data ?? null,
    loading: isLoading,
    error: error instanceof Error ? error.message : null,
    refetch: () => refetch(),
  }
}
