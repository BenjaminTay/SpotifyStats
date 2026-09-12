import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamAiTask } from '@/api/ai-task-stream'

describe('AI task SSE transport', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses split SSE frames and forwards only typed task events', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: stream.connected\ndata: {"task_id":"task-1"}\n\n'))
        controller.enqueue(encoder.encode('id: v1:p2:t1:a1\nevent: task.answer_delta\ndata: {"task_id":"task-1","del'))
        controller.enqueue(encoder.encode('ta":"最终答案"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream; charset=utf-8' },
    })))
    const events: Array<{ type: string; data: unknown; id?: string }> = []

    await streamAiTask('task-1', { onEvent: (event) => events.push(event) }, new AbortController().signal)

    expect(events.map((event) => event.type)).toEqual([
      'stream.connected',
      'task.answer_delta',
    ])
    expect(events[1].data).toEqual({ task_id: 'task-1', delta: '最终答案' })
    expect(events[1].id).toBe('v1:p2:t1:a1')
    expect(fetch).toHaveBeenCalledWith('/api/ai/tasks/task-1/stream', expect.objectContaining({
      headers: expect.objectContaining({ Accept: 'text/event-stream' }),
    }))
  })

  it('sends the durable replay cursor when reconnecting', async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    })))

    await streamAiTask(
      'task-1',
      { onEvent: vi.fn() },
      new AbortController().signal,
      'v1:p2:t1:a1',
    )

    expect(fetch).toHaveBeenCalledWith('/api/ai/tasks/task-1/stream', expect.objectContaining({
      headers: expect.objectContaining({ 'Last-Event-ID': 'v1:p2:t1:a1' }),
    }))
  })

  it('rejects non-SSE responses so callers can fall back to polling', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })))

    await expect(streamAiTask(
      'task-1',
      { onEvent: vi.fn() },
      new AbortController().signal,
    )).rejects.toThrow('响应格式无效')
  })
})
