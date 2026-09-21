import { useEffect, useRef } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  ImportBatch,
  ImportBatchCreatePayload,
  ImportBatchUploadResult,
  ImportPreflightResponse,
  ImportRequestedMode,
  ImportRunCreatePayload,
  ImportRunCreateResult,
  ImportRunDetail,
  ImportRunHistoryPage,
} from '@/types/data-import'
import type { ImportJob } from '@/types/settings'

const HISTORY_PAGE_SIZE = 10
const ACTIVE_RUN_STATUSES = new Set(['pending', 'queued', 'running', 'retrying', 'warming'])

export function importRunNeedsPolling(run: ImportRunDetail | null | undefined): boolean {
  return Boolean(run && ACTIVE_RUN_STATUSES.has(run.status))
}

function pollingInterval(query: { state: { data?: ImportRunDetail | null } }) {
  return importRunNeedsPolling(query.state.data) ? 1_000 : false
}

function legacyPollingInterval(query: { state: { data?: ImportJob } }) {
  return query.state.data?.status === 'running' ? 1_000 : false
}

interface UseDataImportOptions {
  enabled?: boolean
  batchId?: string | null
  runId?: string | null
  mode?: ImportRequestedMode
}

interface UploadInput {
  batchId: string
  file: File
  sourceType: 'audio' | 'video'
}

interface RetryInput {
  runId: string
  stage: string
}

export function useDataImport({
  enabled = true,
  batchId = null,
  runId = null,
  mode = 'auto',
}: UseDataImportOptions = {}) {
  const queryClient = useQueryClient()
  const invalidatedTerminalRun = useRef<string | null>(null)

  const latestQuery = useQuery({
    queryKey: queryKeys.dataImport.latestRun(),
    queryFn: () => api.get<ImportRunDetail | null>('/import/runs/latest'),
    enabled,
    retry: false,
    refetchInterval: pollingInterval,
  })
  const selectedRunId = runId ?? latestQuery.data?.run_id ?? null
  const runQuery = useQuery({
    queryKey: queryKeys.dataImport.run(selectedRunId),
    queryFn: () => api.get<ImportRunDetail>(`/import/runs/${selectedRunId}`),
    enabled: enabled && selectedRunId !== null,
    retry: false,
    refetchInterval: pollingInterval,
  })
  const preflightQuery = useQuery({
    queryKey: queryKeys.dataImport.batchPreflight(batchId, mode),
    queryFn: () => api.get<ImportPreflightResponse>(`/import/batches/${batchId}/preflight`, { mode }),
    enabled: enabled && batchId !== null,
    retry: false,
  })
  const historyQuery = useInfiniteQuery({
    queryKey: queryKeys.dataImport.runHistory(HISTORY_PAGE_SIZE),
    queryFn: ({ pageParam }) => api.get<ImportRunHistoryPage>('/import/runs', {
      limit: HISTORY_PAGE_SIZE,
      offset: typeof pageParam === 'number' ? pageParam : 0,
      ...(typeof pageParam === 'string' ? { cursor: pageParam } : {}),
    }),
    initialPageParam: 0 as number | string,
    getNextPageParam: (lastPage, pages) => {
      if (lastPage.next_cursor) return lastPage.next_cursor
      if (typeof lastPage.next_offset === 'number') return lastPage.next_offset
      if (lastPage.has_more === false || lastPage.runs.length < HISTORY_PAGE_SIZE) return undefined
      return pages.reduce((count, page) => count + page.runs.length, 0)
    },
    enabled,
    retry: false,
  })
  const accountImportMutation = useMutation({
    mutationFn: () => api.post<{ job_id: string }>('/import/account'),
  })
  const accountJobId = accountImportMutation.data?.job_id ?? null
  const accountJobQuery = useQuery({
    queryKey: queryKeys.dataImport.legacyJob(accountJobId),
    queryFn: () => api.get<ImportJob>(`/import/status/${accountJobId}`),
    enabled: enabled && accountJobId !== null,
    retry: false,
    refetchInterval: legacyPollingInterval,
  })

  const invalidateRuns = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.dataImport.runs() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.dataImport.latestRun() }),
    ])
  }

  const createBatchMutation = useMutation({
    mutationFn: (payload: ImportBatchCreatePayload = {}) =>
      api.post<ImportBatch>('/import/batches', { kind: payload.kind ?? 'snapshot', ...payload }),
    onSuccess: (batch) => {
      queryClient.setQueryData(queryKeys.dataImport.batch(batch.batch_id), batch)
    },
  })
  const uploadMutation = useMutation({
    mutationFn: ({ batchId: targetBatchId, file, sourceType }: UploadInput) =>
      api.putWithParams<ImportBatchUploadResult>(
        `/import/batches/${targetBatchId}/files/${encodeURIComponent(file.name)}`,
        file,
        { source_type: sourceType },
        120_000,
      ),
  })
  const finalizeMutation = useMutation({
    mutationFn: (targetBatchId: string) =>
      api.post<ImportBatch>(`/import/batches/${targetBatchId}/finalize`),
    onSuccess: (batch) => {
      queryClient.setQueryData(queryKeys.dataImport.batch(batch.batch_id), batch)
      void queryClient.invalidateQueries({
        queryKey: queryKeys.dataImport.batchPreflight(batch.batch_id, mode),
      })
    },
  })
  const executeMutation = useMutation({
    mutationFn: ({ targetBatchId, payload }: { targetBatchId: string; payload: ImportRunCreatePayload }) =>
      api.post<ImportRunCreateResult>(`/import/batches/${targetBatchId}/runs`, payload),
    onSuccess: () => invalidateRuns(),
  })
  const retryMutation = useMutation({
    mutationFn: ({ runId: targetRunId, stage }: RetryInput) =>
      api.post<ImportRunCreateResult>(`/import/runs/${targetRunId}/retry`, { stage }),
    onSuccess: (_result, input) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dataImport.run(input.runId) })
      void invalidateRuns()
    },
  })
  const recheckMutation = useMutation({
    mutationFn: (targetRunId: string) =>
      api.post<ImportRunDetail>(`/import/runs/${targetRunId}/recheck`),
    onSuccess: (run) => {
      queryClient.setQueryData(queryKeys.dataImport.run(run.run_id), run)
      queryClient.setQueryData(queryKeys.dataImport.report(run.run_id), run)
      void invalidateRuns()
    },
  })

  const run = runQuery.data ?? latestQuery.data ?? null

  useEffect(() => {
    if (!run || importRunNeedsPolling(run) || invalidatedTerminalRun.current === run.run_id) return
    invalidatedTerminalRun.current = run.run_id
    void queryClient.invalidateQueries({ queryKey: queryKeys.dataImport.runHistory(HISTORY_PAGE_SIZE) })
    void queryClient.invalidateQueries({ queryKey: queryKeys.settings.data() })
    void queryClient.invalidateQueries({ queryKey: queryKeys.dataImport.health() })
  }, [queryClient, run])

  useEffect(() => {
    if (accountJobQuery.data?.status !== 'done') return
    void queryClient.invalidateQueries({ queryKey: queryKeys.settings.data() })
  }, [accountJobQuery.data?.status, queryClient])

  return {
    latestRun: latestQuery.data ?? null,
    run,
    report: run,
    preflight: preflightQuery.data ?? null,
    historyRuns: historyQuery.data?.pages.flatMap((page) => page.runs) ?? [],
    latestLoading: latestQuery.isLoading,
    runLoading: runQuery.isLoading,
    preflightLoading: preflightQuery.isLoading,
    historyLoading: historyQuery.isLoading,
    error: latestQuery.error ?? runQuery.error ?? preflightQuery.error ?? historyQuery.error,
    refetchRun: runQuery.refetch,
    refetchPreflight: preflightQuery.refetch,
    fetchNextHistoryPage: historyQuery.fetchNextPage,
    hasNextHistoryPage: historyQuery.hasNextPage,
    isFetchingNextHistoryPage: historyQuery.isFetchingNextPage,
    createBatch: createBatchMutation.mutateAsync,
    creatingBatch: createBatchMutation.isPending,
    uploadFile: uploadMutation.mutateAsync,
    uploadingFile: uploadMutation.isPending,
    finalizeBatch: finalizeMutation.mutateAsync,
    finalizingBatch: finalizeMutation.isPending,
    executeRun: executeMutation.mutateAsync,
    executingRun: executeMutation.isPending,
    retryStage: retryMutation.mutateAsync,
    retryingStage: retryMutation.isPending,
    recheckRun: recheckMutation.mutateAsync,
    recheckingRun: recheckMutation.isPending,
    startAccountImport: accountImportMutation.mutateAsync,
    accountImporting: accountImportMutation.isPending || accountJobQuery.data?.status === 'running',
    accountJob: accountJobQuery.data ?? null,
  }
}
