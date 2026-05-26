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
  running_peak: number
  running_wks: number
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
  running_peak: number
  running_wks: number
  running_peak_wks: number
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
  running_peak: number
  running_wks: number
  running_peak_wks: number
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

export interface AlbumTrackCounts {
  album_name: string
  artist_name: string
  total_tracks: number
  best_peak: number
  total_weeks: number
  avg_weeks: number
  top1: number
  top5: number
  top10: number
  best_peak_track: string
  weeks_at_no1: number
  album_chart_no1_weeks: number
}

export interface ArtistTrackCounts {
  artist_name: string
  total_tracks: number
  best_peak: number
  total_weeks: number
  avg_weeks: number
  top1: number
  top5: number
  top10: number
  best_peak_track: string
  weeks_at_no1: number
  num_no1_albums: number
  album_no1_weeks: number
  artist_chart_no1_weeks: number
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
  album_track_counts: AlbumTrackCounts[]
  artist_track_counts: ArtistTrackCounts[]
}

// ── Track Detail ────────────────────────────────────────────

export interface TrackHistoryEntry {
  week: string
  rank: number
  play_count: number
  change: string
  running_peak: number
  running_wks: number
  running_peak_wks: number
}

export interface TrackChartData {
  x: string[]
  y: (number | null)[]
  texts: string[]
  top_n: number
  peak_position: number
}

export interface TrackDetailResponse {
  found: boolean
  track_id: number
  track_name: string
  artist_name: string
  cover_url: string | null
  summary: {
    peak_position: number
    weeks_on_chart: number
    weeks_at_peak: number
    first_week: string
    last_week: string
    first_peak_week: string | null
    total_chart_plays: number
    total_plays: number
    weeks_at_no1: number
    power_score: number
    power_rank: number | null
  }
  history: TrackHistoryEntry[]
  chart_data: TrackChartData
}

// ── Artist Detail ───────────────────────────────────────────

export interface ArtistChartSummary {
  peak_position: number
  weeks_on_chart: number
  first_week: string
  first_peak_week: string
  latest_week: string
  no1_weeks: number
  peak_weeks: number
  power_score: number
  power_rank: number | null
}

export interface ArtistInfo {
  total_tracks: number
  best_peak: number
  total_weeks: number
  avg_weeks: number
  top1: number
  top5: number
  top10: number
  weeks_at_no1: number
  num_no1_albums: number
  album_no1_weeks: number
  total_track_power: number
  total_album_power: number
}

export interface ArtistWeeklyHistoryEntry {
  week: string
  rank: number
  play_count: number
  tracks_count: number
  albums_count: number
  change: string
  running_peak: number
  running_wks: number
  running_peak_wks: number
}

export interface ArtistNo1ByWeek {
  week: string
  no1_track_names: string
  no1_track_id: number | null
  no1_count: number
}

export interface ArtistTrackEntry {
  track_id: number
  track_name: string
  cover_url: string | null
  peak_position: number
  weeks_on_chart: number
  weeks_at_peak: number
  first_week: string
  first_peak_week: string
  last_week: string
  total_chart_plays: number
  power_score: number
  power_rank: number | null
}

export interface ArtistAlbumEntry {
  album_name: string
  cover_url: string | null
  peak: number
  weeks: number
  pk_wks: number
  first_week: string
  first_peak_week: string
  last_week: string
  total_plays: number
  power_score: number
  power_rank: number | null
}

export interface ArtistDetailResponse {
  found: boolean
  artist_name: string
  cover_url: string | null
  info: ArtistInfo
  chart_summary: ArtistChartSummary
  artist_weekly_history: ArtistWeeklyHistoryEntry[]
  artist_no1_by_week: ArtistNo1ByWeek[]
  week_no1_albums: { week: string; album_name: string; artist_name: string }[]
  best_singles_overlay: { week: string; rank: number }[]
  tracks: ArtistTrackEntry[]
  albums: ArtistAlbumEntry[]
}

// ── Album Detail ────────────────────────────────────────────

export interface AlbumChartSummary {
  peak_position: number
  weeks_on_chart: number
  first_week: string
  first_peak_week: string
  latest_week: string
  no1_weeks: number
  peak_weeks: number
  power_score: number
  power_rank: number | null
}

export interface AlbumInfo {
  total_tracks: number
  best_peak: number
  total_weeks: number
  avg_weeks: number
  top1: number
  top5: number
  top10: number
  weeks_at_no1: number
  album_chart_no1_weeks: number
  total_track_power: number
}

export interface AlbumWeeklyHistoryEntry {
  week: string
  rank: number
  play_count: number
  tracks_count: number
  change: string
  running_peak: number
  running_wks: number
  running_peak_wks: number
}

export interface AlbumTrackEntry {
  track_id: number
  track_name: string
  cover_url: string | null
  peak_position: number
  weeks_on_chart: number
  weeks_at_peak: number
  first_week: string
  first_peak_week: string
  last_week: string
  total_chart_plays: number
  power_score: number
  power_rank: number | null
}

export interface AlbumDetailResponse {
  found: boolean
  album_name: string
  artist_name: string
  cover_url: string | null
  info: AlbumInfo
  chart_summary: AlbumChartSummary
  album_weekly_history: AlbumWeeklyHistoryEntry[]
  album_no1_by_week: { week: string; no1_track_names: string; no1_track_id: number | null; no1_count: number }[]
  best_singles_overlay: { week: string; rank: number }[]
  tracks: AlbumTrackEntry[]
}
