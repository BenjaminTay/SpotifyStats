export type MusicSearchKind = 'track' | 'album' | 'artist'

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
