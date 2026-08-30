export type HomeState = 'ready' | 'limited' | 'empty'
export type HomeFreshness = 'recent' | 'aging' | 'old' | 'unknown'
export type HomeEntityType = 'track' | 'album' | 'artist'
export type HomeChartMovement = 'new' | 're' | 'up' | 'down' | 'same'

export interface HomeEntityRef {
  entity_type: HomeEntityType
  entity_id: number | string | null
  name: string
  artist_name: string | null
  cover_url: string | null
  deep_link: string
}

export interface HomeCoverage {
  first_source_date: string | null
  source_latest_date: string | null
  first_effective_play_date: string | null
  latest_effective_play_date: string | null
  first_play_date: string | null
  latest_play_date: string | null
  freshness: HomeFreshness
  has_account_data: boolean
}

export interface HomeArchive {
  total_plays: number
  total_hours: number
  unique_tracks: number
  unique_artists: number
  unique_albums: number
  active_days: number
}

export interface HomeHeadline {
  kind: 'comeback' | 'discovery' | 'surge' | 'habit_shift' | 'leader' | 'archive'
  title: string
  statement: string
  entity: HomeEntityRef | null
}

export interface HomePeriod {
  start_date: string
  end_date: string
  label: string
}

export interface HomeRecentSummary {
  plays: number
  hours: number
  active_days: number
  plays_delta_pct: number | null
  hours_delta_pct: number | null
  late_night_pct: number
  weekend_pct: number
}

export interface HomeTrendPoint {
  date: string
  plays: number
  hours: number
}

export interface HomeEntityMetric {
  entity: HomeEntityRef
  plays: number
  hours: number
}

export interface HomeRecent {
  period: HomePeriod | null
  comparison_period: HomePeriod | null
  comparison_available: boolean
  summary: HomeRecentSummary
  trend: HomeTrendPoint[]
  leaders: {
    track: HomeEntityMetric | null
    album: HomeEntityMetric | null
    artist: HomeEntityMetric | null
  }
}

export interface HomeChartChampion {
  entity: HomeEntityRef
  rank: number
  plays: number
  hours: number
  movement: HomeChartMovement
  previous_rank: number | null
  rank_change: number | null
}

export interface HomeBillboard {
  state: 'ready' | 'unavailable'
  week: string | null
  track: HomeChartChampion | null
  album: HomeChartChampion | null
  artist: HomeChartChampion | null
}

export interface HomeYearlyReviewPreview {
  state: 'ready' | 'not_generated' | 'unavailable'
  year: number | null
  headline: string | null
  statement: string | null
  entity: HomeEntityRef | null
}

export interface HomeRediscoveryTrack {
  entity: HomeEntityRef
  total_plays: number
  days_since_last_play: number
  last_played: string
}

export interface HomeOverviewResponse {
  schema_version: 'home_overview_v2' | string
  generated_at: string
  cache_state?: 'fresh' | 'warming' | 'stale'
  filter_fingerprint: string
  state: HomeState
  coverage: HomeCoverage
  archive: HomeArchive
  headline: HomeHeadline
  recent: HomeRecent | null
  billboard: HomeBillboard
  yearly_review: HomeYearlyReviewPreview
  rediscovery: HomeRediscoveryTrack | null
  rediscovery_candidates?: HomeRediscoveryTrack[]
}
