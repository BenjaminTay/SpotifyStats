export type LanguageClassification = 'single_language' | 'multilingual' | 'instrumental'
export type LanguageOrigin = 'manual' | 'curated_seed' | 'legacy_import'
export type ArtistLanguageEvidenceKind =
  | 'artist_profile'
  | 'artist_repertoire'
  | 'editorial_source'
  | 'track_credit'
  | 'track_language'
export type ArtistLanguagePerformerAttribution =
  | 'artist_vocal_confirmed'
  | 'artist_instrumental_confirmed'
  | 'track_language_only'
  | 'not_applicable'
export type ArtistLanguageSourceStatus = 'suggested' | 'approved' | 'rejected' | 'superseded'
export type ArtistLanguageReviewStatus = 'open' | 'approved' | 'rejected' | 'insufficient_evidence'
export type ArtistLanguageReviewAction = 'approve' | 'reject' | 'insufficient_evidence'
export type LanguageBucketClassification =
  | LanguageClassification
  | 'unknown'

export interface ArtistLanguagePlayFilters {
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  dynamic_threshold: boolean
  max_merge_gap_minutes?: number
}

export interface ArtistLanguageEvidenceInput {
  local_track_id?: number | null
  claimed_language_code?: string | null
  claimed_language_variant?: string | null
  evidence_kind: ArtistLanguageEvidenceKind
  performer_attribution: ArtistLanguagePerformerAttribution
  evidence_url: string
  evidence_title: string
  evidence_summary: string
}

export interface ArtistLanguageSourceInput {
  classification: LanguageClassification
  primary_language_code?: string | null
  language_variant?: string | null
  raw_language?: string | null
  evidence?: ArtistLanguageEvidenceInput[]
}

export interface ArtistLanguageReviewCreateRequest {
  artist_id: number
  reason?: string
}

export interface ArtistLanguageReviewDecisionRequest {
  action: ArtistLanguageReviewAction
  resolution_note: string
}

export interface LanguageBucket {
  key: string
  label: string
  classification: LanguageBucketClassification
  hours: number
  share_pct: number
  artist_count: number
}

export interface ArtistLanguageMissingItem {
  artist_id: number
  artist_name: string
  hours: number
}

export interface ArtistLanguageCoverage {
  eligible_hours: number
  excluded_unattributed_hours: number
  classified_hours: number
  unknown_hours: number
  classified_pct: number
  unknown_pct: number
  buckets: LanguageBucket[]
  source_hours: Record<string, number>
  top_missing: ArtistLanguageMissingItem[]
  caveat: string
}

export type ArtistLanguageCoverageResponse = ArtistLanguageCoverage

export interface ArtistLanguageEvidenceItem {
  evidence_id: number
  source_id: number
  local_track_id: number | null
  claimed_language_code: string | null
  claimed_language_variant: string | null
  evidence_kind: ArtistLanguageEvidenceKind
  performer_attribution: ArtistLanguagePerformerAttribution
  evidence_url: string
  evidence_title: string
  evidence_accessed_at: string
  evidence_summary: string
  created_at: string
}

export interface ArtistLanguageSourceItem {
  source_id: number
  artist_id: number
  classification: LanguageClassification
  primary_language_code: string | null
  language_variant: string | null
  raw_language: string | null
  origin: LanguageOrigin
  source_key: string
  status: ArtistLanguageSourceStatus
  replaces_source_id: number | null
  created_at: string
  updated_at: string
  evidence: ArtistLanguageEvidenceItem[]
}

export interface ArtistLanguageReviewItem {
  review_id: number
  artist_id: number
  artist_name: string
  suggested_source_id: number | null
  play_hours_snapshot: number
  reason: string
  status: ArtistLanguageReviewStatus
  pre_review_recommendation?: string | null
  pre_review_confidence?: number | null
  pre_review_note?: string | null
  pre_reviewed_by?: string | null
  pre_reviewed_at?: string | null
  resolution_note: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
  source: ArtistLanguageSourceItem | null
}

export interface ArtistLanguageReviewListResponse {
  items: ArtistLanguageReviewItem[]
  total: number
}

export interface ArtistLanguageReviewMutationResponse {
  review_id: number
  review_status: ArtistLanguageReviewStatus
  source_id: number | null
  source_status: ArtistLanguageSourceStatus | null
}
