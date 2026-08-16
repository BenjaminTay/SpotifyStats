export type MusicSearchKind = 'track' | 'album' | 'artist'
export type MusicSearchSnapshotStatus = 'ready' | 'warming' | 'unavailable' | 'stale' | 'failed'
export type MusicSearchMatchField = 'label' | 'artist' | 'album' | 'alias'
export type MusicSearchMatchQuality = 'exact' | 'prefix' | 'token' | 'substring' | 'fuzzy'
export type MusicSearchMatchType = 'original' | 'simplified' | 'traditional' | 'fuzzy'

export interface MusicSearchChartSummary {
  peak_position: number | null
  peak_weeks: number | null
  weeks_on_chart: number | null
  weeks_at_no1: number | null
  power_score: number | null
  power_rank: number | null
  first_week: string | null
  latest_week: string | null
  first_peak_week: string | null
}

export interface MusicSearchResult {
  kind: MusicSearchKind
  label: string
  subtitle: string | null
  href: string
  play_events: number
  total_ms: number
  track_id: number | null
  artist_id: number | null
  album_name: string | null
  artist_name: string | null
  cover_url: string | null
  chart?: MusicSearchChartSummary | null
}

export interface MusicSearchResponse {
  query: string
  limit_per_type: number
  total: number
  tracks: MusicSearchResult[]
  albums: MusicSearchResult[]
  artists: MusicSearchResult[]
}

export interface MusicSearchCandidate {
  entity_key: string
  kind: MusicSearchKind
  label: string
  subtitle: string | null
  href: string
  track_id: number | null
  artist_id: number | null
  album_name: string | null
  artist_name: string | null
  cover_url: string | null
  match_field: MusicSearchMatchField
  match_quality: MusicSearchMatchQuality
  match_type?: MusicSearchMatchType
}

export interface MusicSearchKindTotals {
  track: number
  album: number
  artist: number
}

export interface MusicSearchCandidateResponse {
  response_version: 'music_search_v2'
  query: string
  normalized_query: string
  snapshot_status: MusicSearchSnapshotStatus
  filter_fingerprint: string | null
  candidate_index_version?: string | null
  kind: MusicSearchKind | null
  page: number
  page_size: number
  total: number
  total_by_kind: MusicSearchKindTotals
  tracks: MusicSearchCandidate[]
  albums: MusicSearchCandidate[]
  artists: MusicSearchCandidate[]
}

export interface MusicSearchContextItem {
  play_events: number
  total_ms: number
  chart: MusicSearchChartSummary | null
}

export interface MusicSearchContextResponse {
  response_version: 'music_search_context_v1'
  snapshot_status: MusicSearchSnapshotStatus
  filter_fingerprint: string | null
  items: Record<string, MusicSearchContextItem>
}

export interface MusicSearchCandidateView extends MusicSearchCandidate {
  context: MusicSearchContextItem | null
}
