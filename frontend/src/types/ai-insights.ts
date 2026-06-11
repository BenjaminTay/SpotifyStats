/** AI Insights feature types. */

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

export type ReportType = 'weekly' | 'monthly' | 'yearly'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'error'
  content: string
  /** Attached metadata for the message (e.g. time range info for assistant messages). */
  meta?: AskResponse
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
