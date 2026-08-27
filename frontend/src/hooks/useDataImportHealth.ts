import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type { ImportCleanupPreviewResponse, ImportHealthResponse, ImportPreflightResponse } from '@/types/data-import'

export function useDataImportHealth() {
  const queryClient = useQueryClient()
  const healthQuery = useQuery({
    queryKey: queryKeys.dataImport.health(),
    queryFn: () => api.get<ImportHealthResponse>('/import/health'),
    staleTime: 30_000,
    retry: 1,
  })
  const preflightQuery = useQuery({
    queryKey: queryKeys.dataImport.preflight(),
    queryFn: () => api.get<ImportPreflightResponse>('/import/preflight'),
    enabled: false,
    staleTime: 30_000,
    retry: 0,
  })
  const cleanupPreviewMutation = useMutation({
    mutationKey: queryKeys.dataImport.cleanupPreview(),
    mutationFn: () => api.post<ImportCleanupPreviewResponse>('/import/governance/cleanup-preview'),
  })

  return {
    health: healthQuery.data ?? null,
    healthLoading: healthQuery.isLoading,
    healthError: healthQuery.error instanceof Error ? healthQuery.error.message : null,
    refetchHealth: healthQuery.refetch,
    preflight: preflightQuery.data ?? null,
    preflightLoading: preflightQuery.isFetching,
    preflightError: preflightQuery.error instanceof Error ? preflightQuery.error.message : null,
    runPreflight: () => preflightQuery.refetch(),
    cleanupPreview: cleanupPreviewMutation.data ?? null,
    cleanupPreviewLoading: cleanupPreviewMutation.isPending,
    cleanupPreviewError: cleanupPreviewMutation.error instanceof Error ? cleanupPreviewMutation.error.message : null,
    runCleanupPreview: () => cleanupPreviewMutation.mutateAsync(),
    invalidate: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dataImport.all })
    },
  }
}
