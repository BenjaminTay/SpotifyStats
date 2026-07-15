export interface ArtistGenreMissingItem {
  artist_name: string
  hours: number
}

export interface ArtistGenreCoverageResponse {
  known_hours: number
  unknown_hours: number
  known_pct: number
  unknown_pct: number
  source_hours: Record<string, number>
  top_missing: ArtistGenreMissingItem[]
  artist_count: number
  total_hours: number
  excluded_unattributed_hours: number
}

export interface ArtistGenreCanonicalItem {
  name: string
  axis: string
  label: string | null
  interpretation: string | null
  confidence_tier: string
  hours: number
  share_pct: number
  overall_share_pct: number
  source_mix: ArtistGenreSourceMixItem[]
  top_artists: ArtistGenreTopArtistItem[]
  dominance_warning: string | null
  risk_flags: ArtistGenreRiskFlag[]
}

export interface ArtistGenreRiskFlag {
  code: string
  severity: string
  message: string
}

export interface ArtistGenreAxisSummaryItem {
  axis: string
  label: string
  hours: number
  share_pct: number
  coverage_pct: number
  unknown_hours: number
  unknown_pct: number
  canonical_count: number
  interpretation: string
}

export interface ArtistGenreSourceMixItem {
  source: string
  hours: number
  share_pct: number
  confidence: number
  evidence_pct: number
}

export interface ArtistGenreTopArtistItem {
  artist_name: string
  hours: number
  share_pct: number
  source: string
  raw_genres: string[]
}

export interface ArtistGenreRawMappingItem {
  raw_genre: string
  canonical_genres: string[]
  hours: number
  artist_count: number
  sources: string[]
}

export interface ArtistGenrePassthroughItem {
  raw_genre: string
  hours: number
}

export interface ArtistGenreTaxonomyResponse {
  raw_genre_count: number
  canonical_genre_count: number
  noncanonical_passthrough_count: number
  unknown_hours: number
  axis_summary: ArtistGenreAxisSummaryItem[]
  top_canonical_genres: ArtistGenreCanonicalItem[]
  top_raw_genres: ArtistGenreRawMappingItem[]
  mapping_examples: ArtistGenreRawMappingItem[]
  noncanonical_passthrough: ArtistGenrePassthroughItem[]
  caveat: string
}

export interface ArtistGenreReviewItem {
  review_id: number
  artist_name: string
  play_hours: number
  reason: string
  source_id: number
  source: string
  source_key: string
  source_status: string
  genres: string[]
  primary_genre: string | null
  language: string | null
  region: string | null
  confidence: number
  evidence_summary: string | null
  evidence_url: string | null
  review_status: 'open' | 'approved' | 'rejected' | string
  reviewed_by: string | null
  reviewed_at: string | null
  resolution_note: string | null
  created_at: string
  updated_at: string
}

export interface ArtistGenreReviewListResponse {
  items: ArtistGenreReviewItem[]
  total: number
}

export interface ArtistGenreEvidenceUpdateRequest {
  evidence_url: string
  evidence_summary: string
}

export interface ArtistGenreReviewDecisionResponse {
  review_id: number
  artist_name: string
  decision: string
  source_id: number
  source_status: string
  review_status: string
}

export interface ArtistGenreBackfillTaskRequest {
  limit: number
  min_hours: number
  include_ai: boolean
  approve_high_confidence_external: boolean
}
