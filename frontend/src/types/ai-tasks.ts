export type AiTaskStatus = 'queued' | 'running' | 'done' | 'error' | 'cancelled'

export type AiTaskJsonPayload = Record<string, unknown> | unknown[]

export interface AiEvidenceMetric {
  name: string
  label: string
  value?: string | number | boolean | null
  unit?: string | null
  note?: string | null
}

export interface AiEvidenceSource {
  tool_name: string
  source_range?: string | null
  params_summary?: string | null
  result_summary?: string | null
}

export interface AiEvidenceCard {
  card_id: string
  title: string
  entity_name?: string | null
  entity_type?: string | null
  question_axis?: string | null
  source: AiEvidenceSource
  metrics: AiEvidenceMetric[]
  observations?: string[]
  limitations?: string[]
}

export interface AiTaskRun {
  found: boolean
  task_id?: string | null
  task_type?: string | null
  status?: AiTaskStatus | string | null
  stage?: string | null
  progress_pct?: number | null
  message?: string | null
  request?: AiTaskJsonPayload | null
  result?: AiTaskJsonPayload | null
  error?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface AiTaskEvent {
  event_id: number
  task_id: string
  event_type: string
  stage: string
  message: string
  payload?: AiTaskJsonPayload | null
  created_at: string
}

export interface AiToolCall {
  tool_call_id: number
  task_id: string
  tool_name: string
  status: string
  params_summary: string
  result_summary: string
  source_range: string
  error?: string | null
  started_at: string
  completed_at?: string | null
}

export interface AiTaskEventsPayload {
  found: boolean
  events: AiTaskEvent[]
  tool_calls: AiToolCall[]
}

export interface AiTaskCreatePayload {
  task_id: string
  status: AiTaskStatus | string
  stage: string
  progress_pct: number
  message: string
  result?: AiTaskJsonPayload | null
}
