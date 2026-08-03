// ── Spotify Profile ──────────────────────────────────────────

export interface SpotifyProfile {
  id: string
  display_name: string
  email: string
  country: string
  product: string
  followers: number
  images: { url: string; height: number | null; width: number | null }[]
  uri: string
  external_urls: Record<string, string>
}

// ── Settings ────────────────────────────────────────────────

export interface SettingsData {
  spotify_profile: SpotifyProfile | null
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  bb_top_n: number
  bb_album_top_n: number
  bb_artist_top_n: number
  bb_week_start_dow: number
  bb_week_start_hour: number
  include_compilations: boolean
  db_record_count: number
  account_data_imported: boolean
  spotify_connected: boolean
  // LLM translation
  llm_enabled: boolean
  llm_provider: string
  llm_model: string
  has_llm_key: boolean
  llm_active_profile_id: number | null
  llm_active_profile_name: string | null
  rebuild_pending: boolean
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

export type VersionMergeScope = 'release' | 'composition'
export type TrackGroupScope = 'recording' | 'composition'

export interface ReleaseGroup {
  group_id: number
  canonical_name: string
  artist_name: string
  primary_album_id: number | null
  primary_album_name: string | null
  scope: VersionMergeScope
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

export interface TrackGroupCandidate {
  original_track_id: number
  original_track_name: string
  candidate_track_id: number
  candidate_track_name: string
  primary_artist_id: number
}

export interface TrackGroupConfirmResult {
  status: string
  group_id?: number | null
  scope?: TrackGroupScope | null
  member_count?: number | null
  album_projects_rebuilt: boolean
  message?: string | null
}

export interface AlbumRelationTrackPair {
  original_track_id: number
  original_track_name: string
  candidate_track_id: number
  candidate_track_name: string
  candidate_album_id: number
}

export interface AlbumRelationExclusiveTrack {
  track_id: number
  track_name: string
  source_album_id: number
}

export interface AlbumRelationConfirmResult {
  status: string
  release_group_id?: number | null
  scope?: VersionMergeScope | null
  relation_type?: string | null
  candidate_track_pair_count: number
  confirmed_track_pair_count: number
  exclusive_track_count: number
  track_pairs: AlbumRelationTrackPair[]
  exclusive_tracks: AlbumRelationExclusiveTrack[]
  album_projects_rebuilt: boolean
  message?: string | null
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

// ── Artist Identity ─────────────────────────────────────────

export interface ArtistIdentityState {
  current_revision: number
  active_aggregate_revision: number
  rebuild_status: 'ready' | 'pending' | 'running' | 'failed'
  last_error: string | null
  updated_at?: string
}

export interface ArtistIdentityCandidate {
  artist_id: number
  artist_name: string
  play_count: number
  first_play_date: string | null
  last_play_date: string | null
  cover_url: string | null
  identity_id: number | null
  canonical_artist_id: number
  canonical_display_name: string
  external_ids: Array<{
    provider: string
    external_id: string
    evidence_type: string
    confidence: number
    verified: number
  }>
}

export interface ArtistIdentityMember {
  artist_id: number
  artist_name: string
  role: 'canonical' | 'alias'
  evidence_type: string
  evidence_json: string
  confidence: number
  cover_url: string | null
}

export interface ArtistIdentityGroup {
  identity_id: number
  canonical_artist_id: number
  display_artist_id: number
  display_name: string
  display_source: string
  provider_metadata_artist_id?: number | null
  revision: number
  members: ArtistIdentityMember[]
}

export interface ArtistIdentityOverview {
  state: ArtistIdentityState
  groups: ArtistIdentityGroup[]
}

export interface ArtistIdentityPreview {
  members: ArtistIdentityCandidate[]
  canonical_artist_id: number
  display_name: string
  combined_play_count_before_dedupe: number
  duplicate_play_events: number
  shared_stable_tracks: Array<{ spotify_track_id: string; track_name: string; artists: number }>
  external_id_conflicts: Array<Record<string, unknown>>
  metadata_conflicts: Record<string, unknown>
  blocked: boolean
  affected_scopes: string[]
}

export interface ArtistIdentityEvent {
  event_id: number
  identity_id: number | null
  action: string
  actor: string
  reason: string
  revision: number
  undo_of_event_id: number | null
  created_at: string
}

export interface ArtistIdentityMutation {
  event_id: number
  identity_id: number | null
  revision: number
  rebuild_job_id: string | null
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
  llm_base_url: string
  has_llm_key: boolean
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
