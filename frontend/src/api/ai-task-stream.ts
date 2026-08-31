import type { AiTaskEvent, AiTaskRun, AiToolCall } from '@/types/ai-tasks'

export type AiTaskStreamEvent =
  | { type: 'stream.connected'; data: { task_id: string } }
  | { type: 'task.snapshot'; data: AiTaskRun }
  | { type: 'task.progress'; data: AiTaskEvent }
  | { type: 'task.tool'; data: AiToolCall }
  | { type: 'task.answer_delta'; data: { task_id: string; delta: string } }
  | { type: 'task.completed'; data: AiTaskRun }
  | { type: 'stream.error'; data: { code: string; message: string } }

export type AiTaskStreamEnvelope = AiTaskStreamEvent & { id?: string }

interface AiTaskStreamHandlers {
  onEvent: (event: AiTaskStreamEnvelope) => void
  onCursor?: (cursor: string) => void
}

function streamHeaders(cursor?: string): HeadersInit {
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  const token = import.meta.env.VITE_API_TOKEN
  if (token) headers.Authorization = `Bearer ${token}`
  if (cursor) headers['Last-Event-ID'] = cursor
  return headers
}

function parseBlock(block: string): AiTaskStreamEnvelope | null {
  let eventType = ''
  let eventId = ''
  const dataLines: string[] = []
  for (const rawLine of block.split(/\r?\n/)) {
    if (rawLine.startsWith('event:')) eventType = rawLine.slice(6).trim()
    if (rawLine.startsWith('id:')) eventId = rawLine.slice(3).trim()
    if (rawLine.startsWith('data:')) dataLines.push(rawLine.slice(5).trimStart())
  }
  if (!eventType || dataLines.length === 0) return null
  try {
    return {
      type: eventType,
      data: JSON.parse(dataLines.join('\n')),
      ...(eventId ? { id: eventId } : {}),
    } as AiTaskStreamEnvelope
  } catch {
    return null
  }
}

/** Consume the AI task SSE endpoint with auth-capable fetch streaming. */
export async function streamAiTask(
  taskId: string,
  handlers: AiTaskStreamHandlers,
  signal: AbortSignal,
  cursor?: string,
): Promise<void> {
  if (typeof fetch !== 'function') throw new Error('当前环境不支持 SSE')
  const response = await fetch(`/api/ai/tasks/${encodeURIComponent(taskId)}/stream`, {
    headers: streamHeaders(cursor),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`AI 任务流连接失败 (${response.status})`)
  }
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('text/event-stream')) {
    throw new Error('AI 任务流响应格式无效')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (!signal.aborted) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const event = parseBlock(block)
      if (event) {
        if (event.id) handlers.onCursor?.(event.id)
        handlers.onEvent(event)
      }
      boundary = buffer.indexOf('\n\n')
    }
    if (done) break
  }
}
