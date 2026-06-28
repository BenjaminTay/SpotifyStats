/** AI Insights feature types. */

import type { AiTaskJsonPayload, AiToolCall } from './ai-tasks'

export interface ReportEntities {
  artists: string[]
  tracks: string[]
}

export interface WeeklyDigestResponse {
  success: boolean
  report: string | null
  cached: boolean
  cached_at: string | null
  entities: ReportEntities | null
  error: string | null
}

export interface MonthlyPersonalityResponse {
  success: boolean
  report: string | null
  cached: boolean
  cached_at: string | null
  entities: ReportEntities | null
  error: string | null
}

export interface YearlyStoryResponse {
  success: boolean
  report: string | null
  cached: boolean
  cached_at: string | null
  entities: ReportEntities | null
  error: string | null
}

export interface AskResponse {
  success: boolean
  answer: string
  period_info: string | null
  start_date: string | null
  end_date: string | null
  error: string | null
}

export interface ChatMessageMeta extends Partial<AskResponse> {
  task_id?: string
  result?: AiTaskJsonPayload | null
  tool_calls?: AiToolCall[]
  tool_call_count?: number
  tools?: unknown[]
  cancelled?: boolean
}

export type ReportType = 'weekly' | 'monthly' | 'yearly'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'error'
  content: string
  /** Attached metadata for the message (time range, task result, and tool trace). */
  meta?: ChatMessageMeta
}

export interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ChatMessageRecord {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'error'
  content: string
  meta_json: string | null
  created_at: string
}

export interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessageRecord[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

export function recordToChatMessage(r: ChatMessageRecord): ChatMessage {
  const msg: ChatMessage = { role: r.role, content: r.content }
  if (r.meta_json) {
    try {
      msg.meta = JSON.parse(r.meta_json) as ChatMessageMeta
    } catch { /* ignore parse errors */ }
  }
  return msg
}

export function chatMessageToMetaJson(m: ChatMessage): string | undefined {
  return m.meta ? JSON.stringify(m.meta) : undefined
}

function taskResultRecord(task: { result?: AiTaskJsonPayload | null } | null): Record<string, unknown> {
  return isRecord(task?.result) ? task.result : {}
}

export function chatTaskAnswer(task: { result?: AiTaskJsonPayload | null } | null): string | null {
  const result = taskResultRecord(task)
  return typeof result.answer === 'string' && result.answer.trim() ? result.answer.trim() : null
}

export function chatTaskError(
  task: { error?: string | null; result?: AiTaskJsonPayload | null } | null,
  fallback = '回答生成失败',
): string {
  const result = taskResultRecord(task)
  if (typeof task?.error === 'string' && task.error.trim()) return task.error
  if (typeof result.error === 'string' && result.error.trim()) return result.error
  return fallback
}

export function chatAgentMeta(
  task: { task_id?: string | null; result?: AiTaskJsonPayload | null } | null,
  toolCalls: AiToolCall[],
  overrides: Partial<ChatMessageMeta> = {},
): ChatMessageMeta {
  const result = task?.result ?? null
  const resultRecord = isRecord(result) ? result : {}
  const tools = Array.isArray(resultRecord.tools) ? resultRecord.tools : undefined
  return {
    success: overrides.success,
    answer: typeof resultRecord.answer === 'string' ? resultRecord.answer : overrides.answer,
    error: typeof resultRecord.error === 'string' ? resultRecord.error : overrides.error ?? null,
    task_id: task?.task_id ?? overrides.task_id,
    result,
    tool_calls: toolCalls,
    tool_call_count: typeof resultRecord.tool_call_count === 'number'
      ? resultRecord.tool_call_count
      : toolCalls.length,
    tools,
    cancelled: overrides.cancelled,
  }
}
