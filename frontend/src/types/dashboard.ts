export interface DashboardSummary {
  total_plays: number
  total_hours: number
  total_tracks: number
  total_artists: number
  total_albums: number
  total_days: number
  avg_daily_hours: number
}

export interface AccountKpi {
  saved_tracks: number
  playlists: number
  search_queries: number
  video_plays: number
}

export interface MonthlyTrendPoint {
  period: string
  plays: number
  hours: number
}

export interface TopTrack {
  track_name: string
  artist_name: string
  plays: number
}

export interface PlatformDist {
  platform: string
  count: number
}

export interface DowDist {
  day: string
  count: number
}

export interface HourlyDist {
  hour: number
  count: number
}

export interface RandomTrack {
  track_name: string
  artist_name: string
  album_name?: string | null
  last_played: string
  total_plays: number
}

export interface DashboardFullResponse {
  summary: DashboardSummary
  account_kpis: AccountKpi | null
  monthly_trend: MonthlyTrendPoint[]
  top_tracks: TopTrack[]
  platform_dist: PlatformDist[]
  dow_dist: DowDist[]
  hourly_dist: HourlyDist[]
  random_track: RandomTrack | null
}
