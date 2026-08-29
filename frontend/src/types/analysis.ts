import type { DashboardSummary, MonthlyTrendPoint } from './dashboard'
import type { ConsumerTasteProfile } from './yearly-review'

export type AnalysisTimeRange = 'all' | 'this_year' | 'this_month' | 'custom'
export type AnalysisPeriod = 'lifetime' | 'last_6_months' | 'last_4_weeks' | 'year' | 'month' | 'week' | 'day' | 'custom'
export type AnalysisMetric = 'plays' | 'hours'
export type LeaderboardEntity = 'track' | 'artist' | 'album'

export interface AnalysisFilters {
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  dynamic_threshold: boolean
  max_merge_gap_minutes?: number
  merge_level: number
  include_compilations: boolean
  bb_top_n?: number
  bb_album_top_n?: number
  bb_artist_top_n?: number
  bb_week_start_dow?: number
  bb_week_start_hour?: number
}

export interface AnalysisTrendSummary {
  peak_period: string | null
  peak_plays: number
  low_period: string | null
  low_plays: number
  latest_period: string | null
  latest_plays: number
  previous_period: string | null
  previous_plays: number
  month_delta_pct: number | null
}

export interface AnalysisListeningSummary {
  peak_hour: number | null
  peak_hour_count: number
  late_night_rate: number
  weekend_rate: number
  day_type_preference: 'weekday' | 'weekend' | 'unknown'
}

export interface AnalysisTopTrack {
  track_id: number
  track_name: string
  artist_name: string
  plays: number
  hours: number
  cover_url: string | null
}

export interface AnalysisTopArtist {
  artist_name: string
  plays: number
  hours: number
  tracks: number
  cover_url: string | null
}

export interface AnalysisTopAlbum {
  album_name: string
  artist_name: string
  plays: number
  hours: number
  cover_url: string | null
}

export interface AnalysisBehaviorSummary {
  forward_rate: number
  shuffle_rate: number
  primary_platform: string
  primary_platform_rate: number
  top_end_reason: string
}

export interface AnalysisModuleCard {
  key: string
  title: string
  metric: string
  detail: string
  to: string
  cover_url: string | null
}

export interface AnalysisOverviewResponse {
  summary: DashboardSummary
  monthly_trend: MonthlyTrendPoint[]
  trend_summary: AnalysisTrendSummary
  listening_summary: AnalysisListeningSummary
  top_tracks: AnalysisTopTrack[]
  top_artists: AnalysisTopArtist[]
  top_albums: AnalysisTopAlbum[]
  behavior_summary: AnalysisBehaviorSummary
  module_cards: AnalysisModuleCard[]
}

export interface TimelineAnnualPoint {
  year: number
  plays: number
  hours: number
  unique_tracks: number
  unique_artists: number
  top_track: string
  top_artist: string
}

export interface TimelineDrilldownTrack {
  track_id: number
  track_name: string
  artist_name: string
  plays: number
  hours: number
  cover_url: string | null
}

export interface TimelineMonthlyResponse {
  months: MonthlyTrendPoint[]
  drilldown: TimelineDrilldownTrack[] | null
}

export interface TimelineWeekPoint {
  label: string
  plays: number
  hours: number
}

export interface TimelineWeeklyResponse {
  weeks: TimelineWeekPoint[]
  drilldown: TimelineDrilldownTrack[] | null
}

export interface LeaderboardRow {
  rank: number
  plays: number
  hours: number
  track_id?: number
  track_name?: string
  artist_name?: string
  artist_names?: string[]
  album_name?: string
  unique_tracks?: number
  cover_url?: string | null
}

export interface LeaderboardResponse {
  time_label: string
  total_records: number
  rows: LeaderboardRow[]
}

export interface ReasonDist {
  reason: string
  count: number
}

export interface FwdbtnByHour {
  hour: number
  count: number
}

export interface MostForwarded {
  track_name: string
  artist_name: string
  count: number
}

export interface PlatformMonthly {
  period: string
  platform: string
  count: number
}

export interface PlatformHourly {
  platform: string
  hour: number
  count: number
}

export interface ShufflePlatformRate {
  platform: string
  rate: number
}

export interface ShuffleMonthly {
  period: string
  rate: number
}

export interface BehaviorResponse {
  reason_end: ReasonDist[]
  reason_start: ReasonDist[]
  fwdbtn_by_hour: FwdbtnByHour[]
  most_forwarded: MostForwarded[]
  platform_monthly: PlatformMonthly[]
  platform_hourly: PlatformHourly[]
  shuffle_rate_by_platform: ShufflePlatformRate[]
  shuffle_monthly: ShuffleMonthly[]
}

export interface HeatmapResponse {
  z: number[][]
  x: number[]
  y: string[]
}

export interface YearlyHeatmapEntry {
  year: number
  z: number[][]
}

export interface LateNightEntry {
  year: number
  rate: number
}

export interface WeekdayWeekendResponse {
  hours: string[]
  weekend: number[]
  weekday: number[]
}

export interface PlatformHourlyResponse {
  platform_hourly: PlatformHourly[]
  platform_pct: Array<{ platform: string; hour: number; pct: number }>
  platform_peaks: Array<{
    platform: string
    peak_hour: number
    peak_count: number
    total_count: number
    total_pct: number
  }>
}

export interface ArtistListEntry {
  artist_id: number
  artist_name: string
  play_count: number
  cover_url: string | null
}

export interface ArtistDeepDiveResponse {
  found: boolean
  artist_name?: string
  cover_url?: string | null
  info?: {
    total_plays: number
    total_hours: number
    unique_tracks: number
    unique_albums: number
  }
  heatmap?: HeatmapResponse
  top_tracks?: Array<{ track_id: number; track_name: string; plays: number; hours: number; cover_url: string | null }>
  monthly_trend?: MonthlyTrendPoint[]
  album_breakdown?: Array<{ album_name: string; plays: number; hours: number; cover_url: string | null }>
}

export interface AnalysisResolvedPeriod {
  period: AnalysisPeriod
  label: string
  start_date: string | null
  end_date: string | null
}

export interface AnalysisDistributionPoint {
  plays: number
  hours: number
}

export interface AnalysisHourlyPoint extends AnalysisDistributionPoint {
  hour: number
}

export interface AnalysisDailyPoint extends AnalysisDistributionPoint {
  date: string
}

export interface AnalysisCumulativePoint {
  date: string
  cumulative_plays: number
  cumulative_hours: number
}

export interface AnalysisWeekdayPoint extends AnalysisDistributionPoint {
  day: string
}

export interface AnalysisMonthPoint extends AnalysisDistributionPoint {
  month: number
}

export interface AnalysisYearPoint extends AnalysisDistributionPoint {
  year: number
}

export interface AnalysisStatsSummary {
  total_plays: number
  total_hours: number
  unique_tracks: number
  unique_albums: number
  unique_artists: number
  active_days: number
}

export interface AnalysisDailyMetrics {
  avg_daily_plays: number
  avg_daily_hours: number
  avg_active_day_plays: number
  avg_active_day_hours: number
}

export interface AnalysisStatsBehaviorSummary {
  forward_rate: number
  shuffle_rate: number
  primary_platform: string
  primary_platform_rate: number
  top_start_reason: string
  top_end_reason: string
}

export interface RecentPlayRow {
  play_id: number
  ts: string
  date: string
  track_id: number | null
  track_name: string
  artist_name: string
  artist_names?: string[]
  album_name: string | null
  ms_played: number
  hours: number
  platform: string
  cover_url: string | null
}

export interface EntityPlaysResponse {
  total: number
  limit: number
  offset: number
  rows: RecentPlayRow[]
}

export interface AnalysisStatsResponse {
  period: AnalysisResolvedPeriod
  summary: AnalysisStatsSummary
  daily_metrics: AnalysisDailyMetrics
  hourly_distribution: AnalysisHourlyPoint[]
  daily_trend: AnalysisDailyPoint[]
  cumulative_trend: AnalysisCumulativePoint[]
  weekday_distribution: AnalysisWeekdayPoint[]
  month_distribution: AnalysisMonthPoint[]
  year_distribution: AnalysisYearPoint[]
  behavior_summary: AnalysisStatsBehaviorSummary
  taste_profile: ConsumerTasteProfile
  recent_plays: RecentPlayRow[]
}

export interface AnalysisChartRow {
  rank: number
  plays: number
  hours: number
  first_played: string
  last_played: string
  avg_daily_plays: number
  avg_daily_hours: number
  share_pct: number
  track_id?: number
  track_name?: string
  album_name?: string
  artist_name?: string
  artist_names?: string[]
  unique_tracks?: number
  unique_albums?: number
  cover_url: string | null
}

export interface AnalysisChartsResponse {
  period: AnalysisResolvedPeriod
  entity: LeaderboardEntity
  metric: AnalysisMetric
  total: number
  limit: number
  offset: number
  rows: AnalysisChartRow[]
}

export interface EntityStatsResponse extends AnalysisStatsResponse {
  found: boolean
  entity?: {
    track_id?: number
    track_name?: string
    album_name?: string
    artist_name?: string
    cover_url?: string | null
  }
  first_played?: string
  last_played?: string
  ranks?: {
    lifetime: number | null
    last_6_months: number | null
    last_4_weeks: number | null
    current_period: number | null
  } | null
  recent_plays: RecentPlayRow[]
  top250_counts?: {
    lifetime: number
    last_6_months: number
    last_4_weeks: number
  } | null
  recent_50_count?: number | null
  track_breakdown?: AnalysisChartRow[]
  top_tracks?: AnalysisChartRow[]
  top_albums?: AnalysisChartRow[]
}

export interface ArtistPersonalRankingResponse {
  found: boolean
  artist_name?: string
  entity: 'track' | 'album'
  metric: AnalysisMetric
  total: number
  limit: number
  offset: number
  rows: AnalysisChartRow[]
}

export interface AlbumPersonalRankingResponse {
  found: boolean
  album_name?: string
  artist_name?: string
  entity: 'track'
  metric: AnalysisMetric
  total: number
  limit: number
  offset: number
  rows: AnalysisChartRow[]
}

// ── /analysis/records ──

export type EntityRecordType = 'track' | 'album' | 'artist'

export interface PlaybackRecordRow {
  rank: number
  entity_type?: EntityRecordType | null
  entity_id?: string | null
  name: string
  artist_name?: string | null
  artist_names?: string[] | null
  artist_cover_urls?: (string | null)[] | null
  artist_play_counts?: number[] | null
  value: number
  unit: string
  secondary_value?: number | null
  secondary_unit?: string | null
  date?: string | null
  start_date?: string | null
  end_date?: string | null
  total_plays?: number | null
  total_ms?: number | null
  total_hours?: number | null
  unique_tracks?: number | null
  top_track_name?: string | null
  top_track_entity_id?: string | null
  top_track_artist_name?: string | null
  top_track_plays?: number | null
  top_track_cover_url?: string | null
  top_album_name?: string | null
  top_album_artist_name?: string | null
  top_album_plays?: number | null
  top_album_cover_url?: string | null
  top_artist_name?: string | null
  top_artist_plays?: number | null
  top_artist_cover_url?: string | null
  share_pct?: number | null
  cover_url?: string | null
  caption?: string | null
  qualified?: boolean | null
}

export interface EntityRecordFamily {
  track: PlaybackRecordRow[]
  album: PlaybackRecordRow[]
  artist: PlaybackRecordRow[]
}

export interface PlaybackObsessionRecords {
  daily_binge: EntityRecordFamily
  daily_duration: EntityRecordFamily
  consecutive_marathon: EntityRecordFamily
  daily_total_record: PlaybackRecordRow[]
}

export interface PlaybackTimePatternRecords {
  hourly_dominance: EntityRecordFamily
  monthly_peak: EntityRecordFamily
  yearly_peak: EntityRecordFamily
  late_night_peak_day: PlaybackRecordRow[]
  late_night_trajectory?: {
    monthly: PlaybackRecordRow[]
    quarterly: PlaybackRecordRow[]
    monthly_min_plays: number
    quarterly_min_plays: number
  }
  weekday_preference: PlaybackRecordRow[]
}

export interface PlaybackReignRecords {
  daily_champion: EntityRecordFamily
  monthly_reign: EntityRecordFamily
  yearly_reign: EntityRecordFamily
  fastest_milestone: EntityRecordFamily
  consecutive_champion_days: EntityRecordFamily
}

export interface PlaybackLongevityRecords {
  longest_streak_days: EntityRecordFamily
  longest_span: EntityRecordFamily
  comeback_after_sleep: EntityRecordFamily
  most_active_months: EntityRecordFamily
  user_active_streak: PlaybackRecordRow[]
}

export interface PlaybackDiscoveryRecords {
  discovery_day: EntityRecordFamily
  longest_no_repeat: EntityRecordFamily
  album_completionist: EntityRecordFamily
  same_name_diff_artist: PlaybackRecordRow[]
  feat_lover: EntityRecordFamily
}

export interface PlaybackBehaviorRecords {
  skip_storm: EntityRecordFamily
  shuffle_peak: PlaybackRecordRow[]
  platform_reign: PlaybackRecordRow[]
  platform_switch_day: PlaybackRecordRow[]
  playback_milestones: PlaybackRecordRow[]
}

export interface PlaybackRecordsData {
  obsession: PlaybackObsessionRecords
  time_patterns: PlaybackTimePatternRecords
  reigns: PlaybackReignRecords
  longevity: PlaybackLongevityRecords
  discovery: PlaybackDiscoveryRecords
  behavior: PlaybackBehaviorRecords
}

export interface PlaybackRecordsMeta {
  total_plays: number
  total_hours: number
  active_days: number
  merge_level: number
  min_sample_plays: number
  generated_at: string
}

export interface PlaybackRecordsResponse {
  period: AnalysisResolvedPeriod
  meta: PlaybackRecordsMeta
  records: PlaybackRecordsData
}
