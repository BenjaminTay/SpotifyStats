import { useQuery } from '@tanstack/react-query'
import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import { api, type AccountSummary, type ProfileData } from '@/lib/api'

interface UseAccountResult {
  data: AccountSummary | null
  loading: boolean
  error: string | null
  refetch: () => void
}

interface UseProfileResult {
  data: ProfileData | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useAccount(): UseAccountResult {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.account.summary(),
    queryFn: () => api.get<AccountSummary>('/account'),
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

export function useProfile(): UseProfileResult {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.account.profile(),
    queryFn: () => api.get<ProfileData>('/profile'),
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

/** Prefetch account data into the query cache. Safe to call multiple times. */
export function prefetchAccount(): void {
  queryClient.prefetchQuery({
    queryKey: queryKeys.account.summary(),
    queryFn: () => api.get<AccountSummary>('/account'),
    staleTime: 5 * 60 * 1000,
  })
}
