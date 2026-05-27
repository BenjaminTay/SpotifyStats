// ── Settings ────────────────────────────────────────────────

export interface SettingsData {
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  bb_top_n: number
  bb_album_top_n: number
  bb_artist_top_n: number
  bb_week_start_dow: number
  bb_week_start_hour: number
  db_record_count: number
  account_data_imported: boolean
  // LLM translation
  llm_enabled: boolean
  llm_provider: string
  llm_model: string
  has_llm_key: boolean
}

export type SettingsUpdatePayload = Partial<Omit<SettingsData, 'db_record_count' | 'account_data_imported' | 'has_llm_key'> & {
  llm_api_key: string
  llm_base_url: string
}>

// ── Import ──────────────────────────────────────────────────

export interface ImportJob {
  job_id: string
  status: 'running' | 'done' | 'error' | 'not_found'
  progress_pct: number
  message: string
  result: Record<string, unknown> | null
}

// ── Version Merge — Query ───────────────────────────────────

export interface ReleaseGroup {
  group_id: number
  canonical_name: string
  artist_name: string
  primary_album_id: number | null
  primary_album_name: string | null
  is_manual: number
  created_at: string
}

export interface GroupMember {
  album_id: number
  album_name: string
  is_primary?: number
}

export interface UngroupedAlbum {
  album_id: number
  album_name: string
  artist_name: string
}

// ── Version Merge — Detection ───────────────────────────────

export interface DetectionMember {
  album_id: number
  album_name: string
  release_date: string | null
}

export interface OverlapDetail {
  album_name: string
  album_id: number
  overlap: number
}

export interface DetectionResult {
  artist_name: string
  artist_id: number
  canonical_name: string
  primary_album_name: string
  primary_album_id: number
  member_count: number
  confidence: 'high' | 'low'
  members: DetectionMember[]
  group_type: string
  reason: string
  overlap_details: OverlapDetail[]
}

// ── Version Merge — Track Comparison ────────────────────────

export type TrackRow = [string, string, number | null, number | null]

export interface TrackComparison {
  shared: TrackRow[]
  only_in_a: TrackRow[]
  only_in_b: TrackRow[]
}

// ── Rebuild Agg ─────────────────────────────────────────────

export interface RebuildResult {
  status: string
  [key: string]: unknown
}

// ── LLM Profiles ────────────────────────────────────────────

export interface LLMProfile {
  id: number
  profile_name: string
  llm_provider: string
  llm_model: string
  created_at: string | null
  updated_at: string | null
}

export interface LLMProfileDetail extends LLMProfile {
  llm_api_key: string
  llm_base_url: string
}

export interface LLMProfileCreatePayload {
  profile_name: string
  llm_provider: string
  llm_model: string
  llm_api_key: string
  llm_base_url: string
}

export type LLMProfileUpdatePayload = Partial<LLMProfileCreatePayload>

export interface LLMProfileCreateResult {
  id: number
  status: string
}
