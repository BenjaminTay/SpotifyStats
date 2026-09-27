import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiTaskStreamEnvelope } from '@/api/ai-task-stream'
import { queryKeys } from '@/api/query-keys'
import { useAiTask } from '@/hooks/useAiTasks'
import { api } from '@/lib/api'

const streamControl = vi.hoisted(() => ({
  handlers: new Map<string, { onEvent: (event: AiTaskStreamEnvelope) => void }>(),
}))

vi.mock('@/api/ai-task-stream', () => ({
  streamAiTask: async (
    taskId: string,
    handlers: { onEvent: (event: AiTaskStreamEnvelope) => void },
  ) => {
    streamControl.handlers.set(taskId, handlers)
    await new Promise(() => {})
  },
}))

function setup(taskId = 'probe') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path.endsWith('/sections')) {
      return { found: true, generation: 1, sequence: 0, sections: [] }
    }
    if (path.endsWith('/events')) return { found: true, events: [], tool_calls: [] }
    const requestedTaskId = path.split('/').filter(Boolean).at(-1) ?? taskId
    return {
      found: true,
      task_id: requestedTaskId,
      status: 'running',
      generation: 1,
      state_version: 1,
      updated_at: '2026-09-24 01:00:00',
    }
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, ...renderHook(({ id }) => useAiTask(id), { initialProps: { id: taskId }, wrapper }) }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  streamControl.handlers.clear()
})

describe('useAiTask authoritative HTTP/SSE reconciliation', () => {
  it.each(['done', 'error', 'cancelled'] as const)(
    'uses a newer %s polling snapshot after an SSE outage',
    async (terminalStatus) => {
    const { client, result } = setup()
    await waitFor(() => expect(streamControl.handlers.get('probe')).toBeDefined())
    act(() => {
      streamControl.handlers.get('probe')?.onEvent({
        type: 'task.snapshot',
        data: {
          found: true,
          task_id: 'probe',
          status: 'running',
          generation: 1,
          state_version: 2,
          updated_at: '2026-09-24 01:00:01',
        },
      })
      streamControl.handlers.get('probe')?.onEvent({
        type: 'stream.error',
        data: { code: 'disconnected', message: 'disconnected' },
      })
      client.setQueryData(queryKeys.aiTasks.task('probe'), {
        found: true,
        task_id: 'probe',
        status: terminalStatus,
        generation: 1,
        state_version: 3,
        updated_at: '2026-09-24 01:01:00',
      })
    })

    await waitFor(() => expect(result.current.transport).toBe('polling'))
    expect(result.current.task?.status).toBe(terminalStatus)
    },
  )

  it('falls back to authoritative polling after a stream resync request', async () => {
    const { client, result } = setup()
    await waitFor(() => expect(streamControl.handlers.get('probe')).toBeDefined())
    act(() => {
      streamControl.handlers.get('probe')?.onEvent({
        type: 'stream.resync',
        data: { task_id: 'probe', reason: 'cursor_expired', action: 'reload_snapshot' },
      })
      client.setQueryData(queryKeys.aiTasks.task('probe'), {
        found: true,
        task_id: 'probe',
        status: 'done',
        generation: 2,
        state_version: 1,
        updated_at: '2026-09-24 01:01:00',
      })
    })

    await waitFor(() => expect(result.current.transport).toBe('polling'))
    expect(result.current.task?.generation).toBe(2)
    expect(result.current.task?.status).toBe('done')
  })

  it('treats a newer polled section snapshot as authoritative after review withdrawal', async () => {
    const { client, result } = setup()
    await waitFor(() => expect(streamControl.handlers.get('probe')).toBeDefined())
    const section = {
      task_id: 'probe',
      generation: 1,
      section_id: 'opening',
      section_order: 0,
      section_version: 1,
      status: 'validated' as const,
      source_kind: 'model' as const,
      section: { prose: 'reviewed' },
      attempt_count: 1,
      updated_at: '2026-09-24 01:00:00',
      sequence: 20,
    }
    act(() => {
      streamControl.handlers.get('probe')?.onEvent({ type: 'task.section', data: section })
      streamControl.handlers.get('probe')?.onEvent({
        type: 'stream.error',
        data: { code: 'disconnected', message: 'disconnected' },
      })
      client.setQueryData(queryKeys.aiTasks.sections('probe'), {
        found: true,
        generation: 1,
        sequence: 21,
        sections: [],
      })
    })

    await waitFor(() => expect(result.current.sections).toHaveLength(0))
  })

  it('does not let a delayed older HTTP snapshot replace a newer stream section', async () => {
    const { client, result } = setup()
    await waitFor(() => expect(streamControl.handlers.get('probe')).toBeDefined())
    act(() => {
      client.setQueryData(queryKeys.aiTasks.sections('probe'), {
        found: true,
        generation: 1,
        sequence: 10,
        sections: [],
      })
      streamControl.handlers.get('probe')?.onEvent({
        type: 'task.section',
        data: {
          task_id: 'probe',
          generation: 1,
          section_id: 'opening',
          section_order: 0,
          section_version: 2,
          status: 'validated',
          source_kind: 'model',
          section: { prose: 'newer' },
          attempt_count: 2,
          updated_at: '2026-09-24 01:00:02',
          sequence: 22,
        },
      })
    })

    await waitFor(() => expect(result.current.sections).toHaveLength(1))
    expect(result.current.sections[0]?.section?.prose).toBe('newer')
  })

  it('removes a reviewed section when a newer invalidated stream version arrives', async () => {
    const { result } = setup()
    await waitFor(() => expect(streamControl.handlers.get('probe')).toBeDefined())
    act(() => {
      streamControl.handlers.get('probe')?.onEvent({
        type: 'task.section',
        data: {
          task_id: 'probe',
          generation: 1,
          section_id: 'opening',
          section_order: 0,
          section_version: 1,
          status: 'validated',
          source_kind: 'model',
          section: { prose: 'reviewed' },
          attempt_count: 1,
          updated_at: '2026-09-24 01:00:01',
          sequence: 20,
        },
      })
      streamControl.handlers.get('probe')?.onEvent({
        type: 'task.section',
        data: {
          task_id: 'probe',
          generation: 1,
          section_id: 'opening',
          section_order: 0,
          section_version: 2,
          status: 'invalidated',
          source_kind: 'model',
          section: { prose: 'reviewed' },
          attempt_count: 1,
          updated_at: '2026-09-24 01:00:02',
          sequence: 21,
        },
      })
    })

    await waitFor(() => expect(result.current.sections).toHaveLength(0))
  })

  it('clears stream state when switching task identity', async () => {
    const { result, rerender } = setup('first')
    await waitFor(() => expect(streamControl.handlers.get('first')).toBeDefined())
    act(() => {
      streamControl.handlers.get('first')?.onEvent({
        type: 'task.snapshot',
        data: {
          found: true,
          task_id: 'first',
          status: 'done',
          generation: 1,
          state_version: 2,
        },
      })
    })
    expect(result.current.task?.task_id).toBe('first')

    rerender({ id: 'second' })
    await waitFor(() => expect(streamControl.handlers.get('second')).toBeDefined())
    await waitFor(() => expect(result.current.task?.task_id).not.toBe('first'))
  })
})
