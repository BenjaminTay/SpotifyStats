/** AI Insights feature types. */

export interface WeeklyDigestResponse {
  success: boolean
  report: string | null
  cached: boolean
  error: string | null
}

export interface MonthlyPersonalityResponse {
  success: boolean
  report: string | null
  cached: boolean
  error: string | null
}

export interface YearlyStoryResponse {
  success: boolean
  report: string | null
  cached: boolean
  error: string | null
}

export interface AskResponse {
  success: boolean
  answer: string
  error: string | null
}

export type ReportType = 'weekly' | 'monthly' | 'yearly'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
