export type ImportHealthStatus = 'healthy' | 'partial' | 'blocked' | 'stale' | 'failed'

export type ImportHealthIssueCategory = 'database' | 'relationship' | 'metadata' | 'derived'

export type ImportHealthIssueSeverity = 'critical' | 'high' | 'medium' | 'low'

export type ImportFileStatus = 'missing' | 'ok' | 'empty' | 'invalid'

export interface ImportFileReport {
  source_key: string
  label: string
  file_name: string
  required: boolean
  status: ImportFileStatus
  size_bytes: number
  record_count: number
  duplicate_record_count: number
  first_date: string | null
  last_date: string | null
  errors: string[]
  warnings: string[]
}

export interface ImportDuplicateFileGroup {
  file_names: string[]
  sha256: string
}

export interface ImportDateOverlap {
  left_file: string
  right_file: string
  overlap_start: string
  overlap_end: string
  overlap_days: number
  shared_record_count: number
}

export type ImportAccountIdentityStatus = 'unknown' | 'not_provided' | 'matched' | 'mismatched'

export type ImportFingerprintBaselineStatus = 'missing' | 'ready' | 'incompatible'

export type ImportDetectedRelation =
  | 'unknown'
  | 'baseline_required'
  | 'identical'
  | 'snapshot_superset'
  | 'delta_tail'
  | 'reconciled_snapshot'
  | 'truncated_or_regressive'
  | 'different_account'
  | 'ambiguous'

export type ImportRequestedMode = 'auto' | 'append' | 'replace'

export type ImportEstimatedStrategy = 'noop' | 'incremental' | 'mixed' | 'full'

export interface StreamingImportOptions {
  mode?: ImportRequestedMode
  confirmWarnings?: boolean
  confirmPlan?: boolean
  confirmationToken?: string
}

export interface ImportDatasetDateRange {
  first_date: string | null
  last_date: string | null
}

export interface ImportPreflightResponse {
  status: ImportHealthStatus
  streaming_files: ImportFileReport[]
  account_files: ImportFileReport[]
  duplicate_file_groups: ImportDuplicateFileGroup[]
  date_overlaps: ImportDateOverlap[]
  blockers: string[]
  warnings: string[]
  /** Phase A fields are optional so the UI can still consume older preflight payloads. */
  account_identity_status?: ImportAccountIdentityStatus
  fingerprint_baseline_status?: ImportFingerprintBaselineStatus
  detected_relation?: ImportDetectedRelation
  requested_mode?: ImportRequestedMode
  requires_confirmation?: boolean
  confirmation_token?: string | null
  existing_record_count?: number
  incoming_record_count?: number
  unchanged_record_count?: number
  added_record_count?: number
  removed_record_count?: number
  existing_date_range?: ImportDatasetDateRange | null
  incoming_date_range?: ImportDatasetDateRange | null
  affected_weeks_count?: number
  affected_years_count?: number
  planned_actions?: string[]
  estimated_strategy?: ImportEstimatedStrategy
}

export interface ImportHealthIssue {
  code: string
  category: ImportHealthIssueCategory
  severity: ImportHealthIssueSeverity
  title: string
  count: number
  affected_play_count: number
  impact: string
  recommended_action: string
  evidence: Record<string, unknown>
}

export interface ImportHealthResponse {
  status: ImportHealthStatus
  checked_at: string
  database: {
    play_count: number
    audio_play_count: number
    video_play_count: number
    valid_audio_play_count: number
    active_day_count: number
    first_play_date: string | null
    last_play_date: string | null
    null_track_audio_count: number
    negative_duration_count: number
    sqlite_integrity: string
    foreign_key_issue_count: number
    foreign_key_issue_breakdown: Record<string, number>
    artist_count: number
    album_count: number
    track_count: number
  }
  relationships: {
    orphan_play_track_count: number
    orphan_play_album_count: number
    tracks_without_primary_credit_count: number
    orphan_track_artist_track_count: number
    orphan_track_artist_artist_count: number
  }
  metadata: {
    since_date: string
    recent_plays: number
    recent_tracks: number
    recent_source_albums: number
    unresolved_recent_tracks: number
    unresolved_recent_albums: number
  }
  derived: {
    weekly_track_rows: number
    weekly_album_rows: number
    weekly_artist_rows: number
    album_project_count: number
    album_projects_ready: boolean
    billboard_aggregates_ready: boolean
    rebuild_pending: boolean
    stale_revision_count: number
    artist_identity: Record<string, unknown>
    track_credits: Record<string, unknown>
  }
  issues: ImportHealthIssue[]
  blockers: string[]
  warnings: string[]
}
