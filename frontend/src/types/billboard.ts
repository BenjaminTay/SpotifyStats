export interface BillboardMeta {
  total_weeks: number
  total_filtered_records: number
  all_weeks_asc: string[]
  all_weeks_desc: string[]
  dow_name: string
  dow_short: string
  top_n: number
  album_top_n: number
  artist_top_n: number
  week_start_dow: number
  week_start_hour: number
}

export interface WeeklyTrackEntry {
  billboard_week: string
  track_id: number
  track_name: string
  artist_name: string
  album_name: string
  play_count: number
  total_ms: number
  rank: number
  running_peak_wks: number
  cover_url: string | null
}

export interface WeeklyAlbumEntry {
  billboard_week: string
  album_name: string
  artist_name: string
  play_count: number
  total_ms: number
  tracks_count: number
  rank: number
  album_type: string | null
  release_date: string | null
  cover_url: string | null
}

export interface WeeklyArtistEntry {
  billboard_week: string
  artist_name: string
  play_count: number
  total_ms: number
  tracks_count: number
  rank: number
  albums_count: number
  cover_url: string | null
}

export interface TrackSummary {
  track_id: number
  track_name: string
  artist_name: string
  album_name: string
  peak_position: number
  weeks_on_chart: number
  weeks_at_peak: number
  first_week: string
  last_week: string
  total_chart_plays: number
  total_plays: number
  weeks_at_no1: number
  first_peak_week: string | null
}

export interface ArtistSummary {
  artist_name: string
  track_id: number
  track_name: string
  album_name: string
  peak_position: number
  weeks_on_chart: number
  weeks_at_peak: number
  first_week: string
  last_week: string
  total_chart_plays: number
}

export interface PowerScoreEntry {
  track_id: number
  track_name: string
  artist_name: string
  power_score: number
  peak_position: number
  weeks_on_chart: number
  weeks_top5: number
  weeks_top10: number
  weeks_at_no1: number
}

export interface AlbumPowerScoreEntry {
  album_name: string
  artist_name: string
  power_score: number
  peak_position: number
  weeks_on_chart: number
  weeks_top1: number
}

export interface ArtistPowerScoreEntry {
  artist_name: string
  power_score: number
  peak_position: number
  weeks_on_chart: number
  weeks_top1: number
}

export interface BillboardDataResponse {
  meta: BillboardMeta
  weekly: WeeklyTrackEntry[]
  weekly_album: WeeklyAlbumEntry[]
  weekly_artist: WeeklyArtistEntry[]
  track_summary: TrackSummary[]
  artist_summary: ArtistSummary[]
  power_scores: PowerScoreEntry[]
  album_power_scores: AlbumPowerScoreEntry[]
  artist_power_scores: ArtistPowerScoreEntry[]
}
