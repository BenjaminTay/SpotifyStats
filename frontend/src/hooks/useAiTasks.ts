import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { streamAiTask } from '@/api/ai-task-stream'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  AiAgentInboxPayload,
  AiTaskCreatePayload,
  AiTaskEventsPayload,
  AiTaskRun,
} from '@/types/ai-tasks'
import type { ReportType } from '@/types/ai-insights'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

const POLL_INTERVAL_MS = 1_000

function isActiveStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'queued' || status === 'running' || status === 'cancelling'
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
  writer_pipeline?: 'agent_synthesis_v2' | 'editorial_agent_v1' | 'deterministic_visual_v1'
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
  session_id?: number
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
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (payload: ReportTaskRequest) => {
      if (!capabilities.ai) return Promise.reject(new Error('当前部署未开放 AI 功能'))
      return api.post<AiTaskCreatePayload>('/ai/tasks/report', payload)
    },
  })
}

export function useStartChatAgentTask() {
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (payload: ChatAgentTaskRequest) => {
      if (!capabilities.ai) return Promise.reject(new Error('当前部署未开放 AI 功能'))
      return api.post<AiTaskCreatePayload>('/ai/tasks/chat', payload)
    },
  })
}

export function useStartArtistEnrichmentTask() {
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (payload: ArtistEnrichmentTaskRequest) => {
      if (!capabilities.ai || !capabilities.cover_enrichment) {
        return Promise.reject(new Error('当前部署未开放艺人增强'))
      }
      return api.post<AiTaskCreatePayload>('/ai/tasks/enrichment/artist', payload)
    },
  })
}

export function useStartAlbumEnrichmentTask() {
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (payload: AlbumEnrichmentTaskRequest) => {
      if (!capabilities.ai || !capabilities.cover_enrichment) {
        return Promise.reject(new Error('当前部署未开放专辑增强'))
      }
      return api.post<AiTaskCreatePayload>('/ai/tasks/enrichment/album', payload)
    },
  })
}

export function useCancelAiTask() {
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (taskId: string) => {
      if (!capabilities.ai) return Promise.reject(new Error('当前部署未开放 AI 功能'))
      return api.post<AiTaskRun>(`/ai/tasks/${taskId}/cancel`)
    },
  })
}

export function useSendAiAgentInput() {
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (payload: {
      taskId: string
      action: 'steer' | 'followup'
      content: string
    }) => {
      if (!capabilities.ai) return Promise.reject(new Error('当前部署未开放 AI 功能'))
      return api.post<AiAgentInboxPayload>(`/ai/tasks/${payload.taskId}/inbox`, {
        action: payload.action,
        content: payload.content,
      })
    },
  })
}

export function useAiTask(taskId: string | null) {
  const enabled = Boolean(taskId)
  const [streamState, setStreamState] = useState<'idle' | 'connecting' | 'open' | 'failed'>('idle')
  const [streamTask, setStreamTask] = useState<AiTaskRun | null>(null)
  const [streamEvents, setStreamEvents] = useState<AiTaskEventsPayload['events']>([])
  const [streamToolCalls, setStreamToolCalls] = useState<AiTaskEventsPayload['tool_calls']>([])
  const [streamedAnswer, setStreamedAnswer] = useState('')
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
      streamState !== 'open' && isActiveTask(query.state.data as AiTaskRun | null | undefined)
        ? POLL_INTERVAL_MS
        : false,
  })

  const eventsQuery = useQuery({
    queryKey: eventsKey,
    queryFn: () => api.get<AiTaskEventsPayload>(`/ai/tasks/${taskId}/events`),
    enabled,
    refetchInterval: () => (
      streamState !== 'open' && isActiveTask(taskQuery.data) ? POLL_INTERVAL_MS : false
    ),
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

  useEffect(() => {
    // A task id change is an external stream identity change; stale data must
    // be cleared before opening the next connection.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamTask(null)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamEvents([])
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamToolCalls([])
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamedAnswer('')
    if (!taskId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStreamState('idle')
      return
    }

    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamState('connecting')
    void streamAiTask(taskId, {
      onEvent: (event) => {
        setStreamState('open')
        if (event.type === 'stream.error') {
          setStreamState('failed')
          return
        }
        if (event.type === 'task.snapshot' || event.type === 'task.completed') {
          setStreamTask(event.data)
          return
        }
        if (event.type === 'task.progress') {
          setStreamEvents((current) => current.some((item) => item.event_id === event.data.event_id)
            ? current
            : [...current, event.data])
          return
        }
        if (event.type === 'task.tool') {
          setStreamToolCalls((current) => current.some((item) => item.tool_call_id === event.data.tool_call_id)
            ? current
            : [...current, event.data])
          return
        }
        if (event.type === 'task.answer_delta') {
          setStreamedAnswer((current) => current + event.data.delta)
        }
      },
    }, controller.signal).catch(() => {
      if (!controller.signal.aborted) setStreamState('failed')
    })
    return () => controller.abort()
  }, [taskId])

  const task = streamTask ?? taskQuery.data ?? null
  const events = streamEvents.length > 0 ? streamEvents : (eventsQuery.data?.events ?? [])
  const toolCalls = streamToolCalls.length > 0
    ? streamToolCalls
    : (eventsQuery.data?.tool_calls ?? [])

  return {
    task,
    events,
    toolCalls,
    streamedAnswer,
    transport: streamState === 'open' ? 'sse' as const : 'polling' as const,
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
