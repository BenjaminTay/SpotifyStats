import { useEffect, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type { AiTaskCreatePayload, AiTaskEventsPayload, AiTaskRun } from '@/types/ai-tasks'
import type { ReportType } from '@/types/ai-insights'

const POLL_INTERVAL_MS = 1_000

function isActiveStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'queued' || status === 'running'
}

function isTerminalStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'done' || status === 'error' || status === 'cancelled'
}

function isActiveTask(task: AiTaskRun | null | undefined): boolean {
  return isActiveStatus(task?.status)
}

function queryErrorMessage(error: unknown): string | null {
  if (!error) return null
  return error instanceof Error ? error.message : String(error)
}

export interface ReportTaskRequest {
  report_type: ReportType
  action: 'cache_only' | 'generate'
  report_mode?: 'visual_yearly_artifact' | 'agentic_longform' | 'basic_summary'
  force?: boolean
  week_start?: string
  week_end?: string
  month?: string
  year?: number
  min_ms?: number
  music_only?: boolean
  merge_enabled?: boolean
  dynamic_threshold?: boolean
  max_merge_gap_minutes?: number | null
}

export interface ChatAgentTaskRequest {
  question: string
  conversation_history?: Array<{ role: string; content: string }>
  question_time?: string
  timezone?: string
  thinking_mode?: boolean
  min_ms?: number
  music_only?: boolean
  merge_enabled?: boolean
  dynamic_threshold?: boolean
  max_merge_gap_minutes?: number | null
  merge_level?: number
}

export interface ArtistEnrichmentTaskRequest {
  artist_name: string
}

export interface AlbumEnrichmentTaskRequest {
  album_name: string
  artist_name: string
}

export function useStartReportTask() {
  return useMutation({
    mutationFn: (payload: ReportTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/report', payload),
  })
}

export function useStartChatAgentTask() {
  return useMutation({
    mutationFn: (payload: ChatAgentTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/chat', payload),
  })
}

export function useStartArtistEnrichmentTask() {
  return useMutation({
    mutationFn: (payload: ArtistEnrichmentTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/enrichment/artist', payload),
  })
}

export function useStartAlbumEnrichmentTask() {
  return useMutation({
    mutationFn: (payload: AlbumEnrichmentTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/enrichment/album', payload),
  })
}

export function useCancelAiTask() {
  return useMutation({
    mutationFn: (taskId: string) =>
      api.post<AiTaskRun>(`/ai/tasks/${taskId}/cancel`),
  })
}

export function useAiTask(taskId: string | null) {
  const enabled = Boolean(taskId)
  const previousTaskStateRef = useRef<{ taskId: string | null; status: AiTaskRun['status'] | null }>({
    taskId: null,
    status: null,
  })
  const taskKey = taskId ? queryKeys.aiTasks.task(taskId) : [...queryKeys.aiTasks.all, 'task', 'none'] as const
  const eventsKey = taskId ? queryKeys.aiTasks.events(taskId) : [...queryKeys.aiTasks.all, 'events', 'none'] as const

  const taskQuery = useQuery({
    queryKey: taskKey,
    queryFn: () => api.get<AiTaskRun>(`/ai/tasks/${taskId}`),
    enabled,
    refetchInterval: (query) =>
      isActiveTask(query.state.data as AiTaskRun | null | undefined) ? POLL_INTERVAL_MS : false,
  })

  const eventsQuery = useQuery({
    queryKey: eventsKey,
    queryFn: () => api.get<AiTaskEventsPayload>(`/ai/tasks/${taskId}/events`),
    enabled,
    refetchInterval: () => (isActiveTask(taskQuery.data) ? POLL_INTERVAL_MS : false),
  })
  const refetchEvents = eventsQuery.refetch

  useEffect(() => {
    const status = taskQuery.data?.status ?? null
    const previousState = previousTaskStateRef.current
    const previousStatus = previousState.taskId === taskId ? previousState.status : null

    previousTaskStateRef.current = { taskId, status }

    if (taskId && isActiveStatus(previousStatus) && isTerminalStatus(status)) {
      void refetchEvents()
    }
  }, [refetchEvents, taskId, taskQuery.data?.status])

  return {
    task: taskQuery.data ?? null,
    events: eventsQuery.data?.events ?? [],
    toolCalls: eventsQuery.data?.tool_calls ?? [],
    loading: taskQuery.isLoading || eventsQuery.isLoading,
    fetching: taskQuery.isFetching || eventsQuery.isFetching,
    error: queryErrorMessage(taskQuery.error ?? eventsQuery.error),
    refetch: () => {
      if (!taskId) return
      void taskQuery.refetch()
      void eventsQuery.refetch()
    },
  }
}
