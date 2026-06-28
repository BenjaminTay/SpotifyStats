import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import { useAiTask } from '@/hooks/useAiTasks'

async function advanceTimers(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

async function flushMicrotasks() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  })
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('useAiTask', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('loads task status and task events together', async () => {
    const client = createClient()
    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/ai/tasks/task-1') {
        return Promise.resolve({
          found: true,
          task_id: 'task-1',
          task_type: 'ai_report_weekly',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '完成',
          result: { report: 'hello' },
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:01',
        })
      }
      if (path === '/ai/tasks/task-1/events') {
        return Promise.resolve({
          found: true,
          events: [
            {
              event_id: 1,
              task_id: 'task-1',
              event_type: 'stage_completed',
              stage: 'gathering_local_data',
              message: '已汇总播放数据',
              payload: null,
              created_at: '2026-06-28T00:00:00',
            },
          ],
          tool_calls: [
            {
              tool_call_id: 1,
              task_id: 'task-1',
              tool_name: 'analysis_charts',
              status: 'done',
              params_summary: '2026 artist plays top 10',
              result_summary: 'Artist A ranked #1',
              source_range: '2026-01-01 to 2026-12-31',
              error: null,
              started_at: '2026-06-28T00:00:00',
              completed_at: '2026-06-28T00:00:01',
            },
          ],
        })
      }
      return Promise.reject(new Error(`unexpected path: ${path}`))
    })

    const { result } = renderHook(() => useAiTask('task-1'), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.task?.status).toBe('done'))
    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0]?.message).toBe('已汇总播放数据')
    expect(result.current.toolCalls).toHaveLength(1)
    expect(result.current.toolCalls[0]?.tool_name).toBe('analysis_charts')
    expect(getSpy).toHaveBeenCalledWith('/ai/tasks/task-1')
    expect(getSpy).toHaveBeenCalledWith('/ai/tasks/task-1/events')
  })

  it('does not request anything when taskId is null', async () => {
    const client = createClient()
    vi.spyOn(api, 'get').mockResolvedValue({})

    const { result } = renderHook(() => useAiTask(null), {
      wrapper: wrapperFor(client),
    })

    expect(api.get).not.toHaveBeenCalled()
    expect(result.current.task).toBeNull()
    expect(result.current.events).toEqual([])
    expect(result.current.toolCalls).toEqual([])
  })

  it('does not request anything when manually refetching a null taskId', async () => {
    const client = createClient()
    vi.spyOn(api, 'get').mockResolvedValue({})

    const { result } = renderHook(() => useAiTask(null), {
      wrapper: wrapperFor(client),
    })

    await act(async () => {
      result.current.refetch()
      await Promise.resolve()
    })

    expect(api.get).not.toHaveBeenCalled()
    expect(result.current.task).toBeNull()
    expect(result.current.events).toEqual([])
    expect(result.current.toolCalls).toEqual([])
  })

  it('polls again while the task is running', async () => {
    vi.useFakeTimers()
    const client = createClient()
    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/ai/tasks/task-2') {
        return Promise.resolve({
          found: true,
          task_id: 'task-2',
          task_type: 'ai_report_weekly',
          status: 'running',
          stage: 'calling_llm',
          progress_pct: 0.6,
          message: 'AI 正在生成周报',
          result: null,
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:01',
        })
      }
      if (path === '/ai/tasks/task-2/events') {
        return Promise.resolve({ found: true, events: [], tool_calls: [] })
      }
      return Promise.reject(new Error(`unexpected path: ${path}`))
    })

    renderHook(() => useAiTask('task-2'), {
      wrapper: wrapperFor(client),
    })

    await advanceTimers(0)
    expect(getSpy).toHaveBeenCalledWith('/ai/tasks/task-2')
    const initialCalls = getSpy.mock.calls.length

    await advanceTimers(1_000)

    expect(getSpy.mock.calls.length).toBeGreaterThan(initialCalls)
  })

  it('keeps the terminal event trace after the task query reaches done', async () => {
    vi.useFakeTimers()
    const client = createClient()
    const taskResponses = [
      {
        found: true,
        task_id: 'task-3',
        task_type: 'ai_report_weekly',
        status: 'running',
        stage: 'calling_llm',
        progress_pct: 0.6,
        message: 'AI 正在生成周报',
        result: null,
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      },
      {
        found: true,
        task_id: 'task-3',
        task_type: 'ai_report_weekly',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '完成',
        result: { report: 'hello' },
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:02',
      },
    ]
    const eventsResponses = [
      { found: true, events: [], tool_calls: [] },
      {
        found: true,
        events: [
          {
            event_id: 2,
            task_id: 'task-3',
            event_type: 'result_ready',
            stage: 'done',
            message: '报告已生成',
            payload: { report_id: 'weekly-1' },
            created_at: '2026-06-28T00:00:02',
          },
        ],
        tool_calls: [
          {
            tool_call_id: 2,
            task_id: 'task-3',
            tool_name: 'llm_generate_report',
            status: 'done',
            params_summary: 'weekly report',
            result_summary: '生成 1 篇周报',
            source_range: '2026-06-21 to 2026-06-28',
            error: null,
            started_at: '2026-06-28T00:00:01',
            completed_at: '2026-06-28T00:00:02',
          },
        ],
      },
    ]

    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/ai/tasks/task-3') {
        return Promise.resolve(taskResponses.shift() ?? taskResponses.at(-1)!)
      }
      if (path === '/ai/tasks/task-3/events') {
        const response = eventsResponses.shift() ?? eventsResponses.at(-1)!
        return new Promise((resolve) => {
          setTimeout(() => resolve(response), 10)
        })
      }
      return Promise.reject(new Error(`unexpected path: ${path}`))
    })

    const { result } = renderHook(() => useAiTask('task-3'), {
      wrapper: wrapperFor(client),
    })

    await advanceTimers(0)
    expect(result.current.task?.status).toBe('running')
    await advanceTimers(10)
    expect(result.current.events).toEqual([])

    await act(async () => {
      await client.refetchQueries({ queryKey: queryKeys.aiTasks.task('task-3') })
    })
    await advanceTimers(0)
    expect(result.current.task?.status).toBe('done')
    await advanceTimers(10)
    await advanceTimers(1)
    await advanceTimers(0)
    await flushMicrotasks()

    expect(getSpy.mock.calls.filter(([path]) => path === '/ai/tasks/task-3/events')).toHaveLength(2)
    expect(result.current.events.some((event) => event.event_type === 'result_ready')).toBe(true)
    expect(result.current.toolCalls.some((toolCall) => toolCall.tool_name === 'llm_generate_report')).toBe(true)
  })
})
