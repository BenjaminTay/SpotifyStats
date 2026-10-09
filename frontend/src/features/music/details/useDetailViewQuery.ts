import { useEffect } from 'react'
import { useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ApiQueryParam } from '@/api/client'
import { SnapshotUnavailableError } from '@/api/errors'

/** Disabled tab observers stay mounted, so explicitly cancel their in-flight request. */
export function useDetailViewQuery<T>(queryKey: QueryKey, path: string, params: Record<string, ApiQueryParam>, enabled: boolean) {
  const client = useQueryClient()
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => api.get<T>(path, params, undefined, signal),
    enabled,
    retry: (count, error) => !(error instanceof SnapshotUnavailableError) && count < 2,
  })
  useEffect(() => {
    if (!enabled) void client.cancelQueries({ queryKey, exact: true })
  }, [client, enabled, queryKey])
  return query
}
