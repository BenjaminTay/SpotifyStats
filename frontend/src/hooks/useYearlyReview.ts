import { useQuery } from '@tanstack/react-query'

import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type { WrappedFullResponse } from '@/types/yearly-review'

export function prefetchYearlyReview(year: number): Promise<void> {
  if (year <= 0) return Promise.resolve()
  return queryClient
    .prefetchQuery({
      queryKey: queryKeys.yearlyReview.full(year),
      queryFn: () => api.get<WrappedFullResponse>(`/wrapped/${year}/full`),
    })
    .then(() => undefined)
}

export function useYearlyReview(year: number, enabled = true) {
  const query = useQuery({
    queryKey: queryKeys.yearlyReview.full(year),
    queryFn: () => api.get<WrappedFullResponse>(`/wrapped/${year}/full`),
    enabled: enabled && year > 0,
  })

  return {
    data: query.data ?? null,
    loading: enabled && year > 0 ? query.isLoading : false,
    error: query.error instanceof Error ? query.error.message : null,
    refetch: () => void query.refetch(),
  }
}
