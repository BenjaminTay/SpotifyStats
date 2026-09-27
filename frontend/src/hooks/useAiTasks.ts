import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { streamAiTask, type AiTaskStreamEnvelope } from '@/api/ai-task-stream'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  AiAgentInboxPayload,
  AiReportSection,
  AiReportSectionsPayload,
  AiTaskCreatePayload,
  AiTaskEventsPayload,
  AiTaskRun,
} from '@/types/ai-tasks'
import type { ReportType } from '@/types/ai-insights'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

const POLL_INTERVAL_MS = 1_000

function isActiveStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'queued' || status === 'running' || status === 'awaiting_input' || status === 'cancelling'
}

function isTerminalStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'done' || status === 'error' || status === 'cancelled'
}

function isActiveTask(task: AiTaskRun | null | undefined): boolean {
  return isActiveStatus(task?.status)
}

function newerTask(
  streamTask: AiTaskRun | null,
  polledTask: AiTaskRun | null | undefined,
): AiTaskRun | null {
  if (!streamTask) return polledTask ?? null
  if (!polledTask) return streamTask
  const streamGeneration = streamTask.generation ?? 0
  const polledGeneration = polledTask.generation ?? 0
  if (streamGeneration !== polledGeneration) {
    return streamGeneration > polledGeneration ? streamTask : polledTask
  }
  const streamVersion = streamTask.state_version ?? 0
  const polledVersion = polledTask.state_version ?? 0
  if (streamVersion !== polledVersion) return streamVersion > polledVersion ? streamTask : polledTask
  if (isTerminalStatus(polledTask.status) && !isTerminalStatus(streamTask.status)) return polledTask
  if (isTerminalStatus(streamTask.status) && !isTerminalStatus(polledTask.status)) return streamTask
  const streamUpdated = String(streamTask.updated_at ?? '')
  const polledUpdated = String(polledTask.updated_at ?? '')
  return polledUpdated > streamUpdated ? polledTask : streamTask
}

function mergeAppendOnly<T, K extends string | number>(
  polled: T[],
  streamed: T[],
  key: (item: T) => K,
): T[] {
  const merged = new Map<K, T>()
  for (const item of [...polled, ...streamed]) merged.set(key(item), item)
  return [...merged.values()]
}

function reconcileSections(
  snapshot: AiReportSectionsPayload | undefined,
  streamed: AiReportSection[],
): AiReportSection[] {
  const snapshotGeneration = snapshot?.generation ?? 0
  const snapshotSequence = snapshot?.sequence ?? 0
  const streamGeneration = streamed.reduce(
    (latest, item) => Math.max(latest, item.generation ?? 0),
    0,
  )
  const streamSequence = streamed.reduce(
    (latest, item) => Math.max(latest, item.sequence ?? 0),
    0,
  )
  if (snapshotGeneration > streamGeneration) {
    return [...(snapshot?.sections ?? [])].sort((a, b) => a.section_order - b.section_order)
  }
  const merged = new Map<string, AiReportSection>()
  for (const section of snapshot?.sections ?? []) merged.set(section.section_id, section)
  const snapshotIsAuthoritative = snapshotGeneration === streamGeneration
    && snapshotSequence >= streamSequence
  if (!snapshotIsAuthoritative) {
    for (const section of [...streamed].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0))) {
      if (streamGeneration > 0 && section.generation !== streamGeneration) continue
      if (
        snapshotGeneration === section.generation
        && (section.sequence ?? 0) <= snapshotSequence
      ) continue
      if (section.status === 'invalidated') merged.delete(section.section_id)
      else {
        const current = merged.get(section.section_id)
        if (!current || section.section_version >= current.section_version) {
          merged.set(section.section_id, section)
        }
      }
    }
  }
  return [...merged.values()]
    .filter((section) => section.status === 'validated')
    .sort((a, b) => a.section_order - b.section_order)
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

export function useLookupReportTask() {
  const { capabilities } = useRuntimeCapabilities()
  return useMutation({
    mutationFn: (payload: ReportTaskRequest) => {
      if (!capabilities.ai) return Promise.reject(new Error('当前部署未开放 AI 功能'))
      return api.post<AiTaskRun>('/ai/tasks/report/lookup', {
        ...payload,
        action: 'generate',
      })
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
  const [streamSections, setStreamSections] = useState<AiReportSection[]>([])
  const [streamedAnswer, setStreamedAnswer] = useState('')
  const previousTaskStateRef = useRef<{ taskId: string | null; status: AiTaskRun['status'] | null }>({
    taskId: null,
    status: null,
  })
  const taskKey = taskId ? queryKeys.aiTasks.task(taskId) : [...queryKeys.aiTasks.all, 'task', 'none'] as const
  const eventsKey = taskId ? queryKeys.aiTasks.events(taskId) : [...queryKeys.aiTasks.all, 'events', 'none'] as const
  const sectionsKey = taskId ? queryKeys.aiTasks.sections(taskId) : [...queryKeys.aiTasks.all, 'sections', 'none'] as const

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
  const sectionsQuery = useQuery({
    queryKey: sectionsKey,
    queryFn: () => api.get<AiReportSectionsPayload>(`/ai/tasks/${taskId}/sections`),
    enabled,
    refetchInterval: () => (
      streamState !== 'open' && isActiveTask(taskQuery.data) ? POLL_INTERVAL_MS : false
    ),
  })

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
    setStreamSections([])
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamedAnswer('')
    if (!taskId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStreamState('idle')
      return
    }

    const controller = new AbortController()
    let cursor: string | undefined
    let completed = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStreamState('connecting')
    const handlers = {
      onCursor: (nextCursor: string) => {
        cursor = nextCursor
      },
      onEvent: (event: AiTaskStreamEnvelope) => {
        setStreamState('open')
        if (event.type === 'stream.error') {
          setStreamState('failed')
          return
        }
        if (event.type === 'stream.resync') {
          cursor = undefined
          setStreamState('failed')
          return
        }
        if (event.type === 'task.snapshot' || event.type === 'task.completed') {
          setStreamTask(event.data)
          if (event.type === 'task.completed') completed = true
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
        if (event.type === 'task.section') {
          setStreamSections((current) => {
            const filtered = current.filter((item) => item.section_id !== event.data.section_id)
            return [...filtered, event.data].sort((a, b) => a.section_order - b.section_order)
          })
          return
        }
        if (event.type === 'task.answer_delta') {
          setStreamedAnswer((current) => current + event.data.delta)
        }
      },
    }
    const connectWithReplay = async () => {
      for (let attempt = 0; attempt < 4 && !controller.signal.aborted; attempt += 1) {
        try {
          await streamAiTask(taskId, handlers, controller.signal, cursor)
          if (completed || controller.signal.aborted) return
        } catch {
          if (controller.signal.aborted) return
        }
        setStreamState('connecting')
        await new Promise<void>((resolve) => {
          const timeout = window.setTimeout(resolve, Math.min(4_000, 500 * (2 ** attempt)))
          controller.signal.addEventListener('abort', () => {
            window.clearTimeout(timeout)
            resolve()
          }, { once: true })
        })
      }
      if (!controller.signal.aborted && !completed) setStreamState('failed')
    }
    void connectWithReplay()
    return () => controller.abort()
  }, [taskId])

  const task = newerTask(streamTask, taskQuery.data)
  const events = mergeAppendOnly(
    eventsQuery.data?.events ?? [],
    streamEvents,
    (item) => item.event_id,
  ).sort((a, b) => a.event_id - b.event_id)
  const toolCalls = mergeAppendOnly(
    eventsQuery.data?.tool_calls ?? [],
    streamToolCalls,
    (item) => item.tool_call_id,
  ).sort((a, b) => a.tool_call_id - b.tool_call_id)
  const orderedSections = reconcileSections(sectionsQuery.data, streamSections)

  return {
    task,
    events,
    toolCalls,
    sections: orderedSections,
    streamedAnswer,
    transport: streamState === 'open' ? 'sse' as const : 'polling' as const,
    loading: taskQuery.isLoading || eventsQuery.isLoading || sectionsQuery.isLoading,
    fetching: taskQuery.isFetching || eventsQuery.isFetching || sectionsQuery.isFetching,
    // Section transport may fail independently; it must not hide a completed
    // report or the task's own terminal error. The polling/SSE merge can heal
    // sections on the next reconnect.
    error: queryErrorMessage(taskQuery.error ?? eventsQuery.error),
    refetch: () => {
      if (!taskId) return
      void taskQuery.refetch()
      void eventsQuery.refetch()
      void sectionsQuery.refetch()
    },
  }
}
