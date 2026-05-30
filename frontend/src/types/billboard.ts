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
  is_debut_no1: boolean
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
  power_rank: number
}

export interface AlbumPowerScoreEntry {
  album_name: string
  artist_name: string
  power_score: number
  peak_position: number
  weeks_on_chart: number
  weeks_top1: number
  weeks_top5: number
  weeks_top10: number
  power_rank: number
}

export interface ArtistPowerScoreEntry {
  artist_name: string
  power_score: number
  peak_position: number
  weeks_on_chart: number
  weeks_top1: number
  weeks_top5: number
  weeks_top10: number
  power_rank: number
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
  records: BillboardRecords
}

/** Weekly-only response from GET /api/billboard/weekly */
export interface BillboardWeeklyResponse {
  meta: BillboardMeta
  weekly: WeeklyTrackEntry[]
  weekly_album: WeeklyAlbumEntry[]
  weekly_artist: WeeklyArtistEntry[]
}

/** Records-only response from GET /api/billboard/records */
export interface BillboardRecordsResponse {
  records: BillboardRecords
}

/** Power scores response from GET /api/billboard/power-scores */
export interface BillboardPowerScoresResponse {
  power_scores: PowerScoreEntry[]
  album_power_scores: AlbumPowerScoreEntry[]
  artist_power_scores: ArtistPowerScoreEntry[]
}

/** Summaries response from GET /api/billboard/summaries */
export interface BillboardSummariesResponse {
  track_summary: TrackSummary[]
  artist_summary: ArtistSummary[]
  album_track_counts: AlbumTrackCounts[]
  artist_track_counts: ArtistTrackCounts[]
}

/** Combined all-time response from GET /api/billboard/all-time */
export interface BillboardAllTimeResponse {
  meta: BillboardMeta
  weekly: WeeklyTrackEntry[]
  weekly_album: WeeklyAlbumEntry[]
  weekly_artist: WeeklyArtistEntry[]
  power_scores: PowerScoreEntry[]
  album_power_scores: AlbumPowerScoreEntry[]
  artist_power_scores: ArtistPowerScoreEntry[]
  track_summary: TrackSummary[]
  artist_summary: ArtistSummary[]
  album_track_counts: AlbumTrackCounts[]
  artist_track_counts: ArtistTrackCounts[]
}

// ── Billboard Records ──────────────────────────────────────────

export interface BillboardRecords {
  // Section 1: 冠军圣殿
  artist_most_no1: ArtistMostNo1Record[]
  debut_no1: DebutNo1Record[]
  debut_no1_album: DebutNo1AlbumRecord[]
  return_to_no1: ReturnToNo1Record[]
  return_to_no1_album: ReturnToNo1AlbumRecord[]
  self_replacement_no1: SelfReplacementRecord[]
  self_replacement_no1_album: SelfReplacementAlbumRecord[]
  blocker_king: BlockerKingRecord[]
  blocked_tracks_map: Record<number, BlockedTrackInfo[]>
  blocker_king_album: BlockerKingAlbumRecord[]
  blocked_albums_map: Record<string, BlockedAlbumInfo[]>
  longest_to_no1: ClimbToNo1Record[]
  fastest_to_no1: ClimbToNo1Record[]

  // Section 2: 持久传奇
  longest_charting: LongestChartingRecord[]
  longest_charting_album: LongestChartingAlbumRecord[]
  longest_streak: LongestStreakRecord[]
  longest_streak_album: LongestStreakAlbumRecord[]
  longest_no_top5: LongestNoTop5Record[]
  longest_no_top5_album: LongestNoTop5AlbumRecord[]
  most_weeks_no2_no_no1: MostWeeksNo2Record[]
  most_weeks_no2_no_no1_album: MostWeeksNo2AlbumRecord[]
  most_reentries: MostReentriesRecord[]
  most_reentries_album: MostReentriesAlbumRecord[]
  longest_consecutive_same_rank: LongestSameRankRecord[]
  longest_consecutive_same_rank_album: LongestSameRankAlbumRecord[]
  longest_artist_span: LongestArtistSpanRecord[]

  // Section 3: 爆发时刻
  artist_simul: ArtistSimulHighlight
  artist_simul_list: ArtistSimulEntry[]
  album_simul: AlbumSimulHighlight
  album_simul_list: AlbumSimulEntry[]
  most_top10_simul: Top10SimulHighlight
  biggest_jump: RankChangeRecord[]
  biggest_drop: RankChangeRecord[]
  fastest_exit_after_no1: FastestExitRecord[]
  strongest_week: StrongestWeekHighlight

  // Section 4: 名人堂
  all_time_greatest: AllTimeGreatestRecord[]
  album_power_ranking: AlbumPowerRankingRecord[]
  artist_power_ranking: ArtistPowerRankingRecord[]
  year_end_no1: YearEndNo1Record[]
  decade_best: DecadeBestRecord[]

  // Section 5: 奇趣纪录
  double_debut: DoubleDebutRecord[]
  triple_no1: TripleNo1Record[]

  // Section 6: 每周大盘
  week_total_plays: WeekTotalPlaysRecord[]
  closest_no1_vs_no2: No1VsNo2Highlight
  largest_no1_vs_no2: No1VsNo2Highlight
  new_entry_ratio: NewEntryRatioRecord[]
}

// ── Section 1: 冠军圣殿 ──────────────────────────────────────

export interface ArtistMostNo1Record {
  artist_name: string
  '冠单数': number
  '单曲冠军周数': number
  '冠军专辑数': number
  '专辑冠军周数': number
}

export interface DebutNo1Record {
  track_id: number
  track_name: string
  artist_name: string
  first_week: string
  weeks_at_no1: number
  weeks_on_chart: number
}

export interface DebutNo1AlbumRecord {
  album_name: string
  artist_name: string
  first_week: string
  weeks_at_no1: number
  weeks_on_chart: number
}

export interface ReturnToNo1Record {
  track_id: number
  track_name: string
  artist_name: string
  '首次冠单': string
  '回冠日期': string
  '间隔周数': number
}

export interface ReturnToNo1AlbumRecord {
  album_name: string
  artist_name: string
  '首次冠专': string
  '回冠日期': string
  '间隔周数': number
}

export interface SelfReplacementRecord {
  '周次': string
  '艺人': string
  '前冠单_id': number
  '前冠单': string
  '新冠单_id': number
  '新冠单': string
}

export interface SelfReplacementAlbumRecord {
  '周次': string
  '艺人': string
  '前冠专': string
  '新冠专': string
}

export interface BlockerKingRecord {
  track_id: number
  track_name: string
  artist_name: string
  '阻挡数': number
  '走势评分': number
}

export interface BlockerKingAlbumRecord {
  album_name: string
  artist_name: string
  '阻挡数': number
  '走势评分': number
}

export interface BlockedTrackInfo {
  track_id: number
  track_name: string
  artist_name: string
}

export interface BlockedAlbumInfo {
  album_name: string
  artist_name: string
}

export interface ClimbToNo1Record {
  track_id: number
  track_name: string
  artist_name: string
  first_week: string
  first_peak_week: string
  '登顶周数': number
}

// ── Section 2: 持久传奇 ──────────────────────────────────────

export interface LongestChartingRecord {
  track_id: number
  track_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
  weeks_at_no1: number
}

export interface LongestStreakRecord {
  track_id: number
  track_name: string
  artist_name: string
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestChartingAlbumRecord {
  album_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
  weeks_at_no1: number
}

export interface LongestStreakAlbumRecord {
  album_name: string
  artist_name: string
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestNoTop5Record {
  track_id: number
  track_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface LongestNoTop5AlbumRecord {
  album_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface LongestNoTop10Record {
  track_id: number
  track_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface MostWeeksNo2Record {
  track_id: number
  track_name: string
  artist_name: string
  peak_position: number
  weeks_at_no2: number
}

export interface MostWeeksNo2AlbumRecord {
  album_name: string
  artist_name: string
  peak_position: number
  weeks_at_no2: number
}

export interface MostReentriesRecord {
  track_id: number
  track_name: string
  artist_name: string
  '回榜次数': number
  '在榜周数': number
}

export interface MostReentriesAlbumRecord {
  album_name: string
  artist_name: string
  '回榜次数': number
  '在榜周数': number
}

export interface LongestSameRankRecord {
  track_id: number
  track_name: string
  artist_name: string
  '停留排名': number
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestSameRankAlbumRecord {
  album_name: string
  artist_name: string
  '停留排名': number
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestArtistSpanRecord {
  artist_name: string
  '首次上榜': string
  '最近上榜': string
  '上榜歌曲数': number
  '跨度天数': number
}

// ── Section 3: 爆发时刻 ──────────────────────────────────────

export interface ArtistSimulHighlight {
  artist: string
  week: string
  count: number
}

export interface ArtistSimulEntry {
  billboard_week: string
  artist_name: string
  track_count: number
}

export interface AlbumSimulHighlight {
  album: string
  artist: string
  week: string
  count: number
}

export interface AlbumSimulEntry {
  billboard_week: string
  artist_name: string
  album_name: string
  track_count: number
}

export interface Top10SimulHighlight {
  artist: string
  week: string
  count: number
}

export interface RankChangeRecord {
  track_id: number
  track_name: string
  artist_name: string
  '日期': string
  '上周排名': number
  '本周排名': number
  '变化': number
}

export interface FastestExitRecord {
  track_id: number
  track_name: string
  artist_name: string
  first_peak_week: string
  last_week: string
  '巅峰后周数': number
}

export interface StrongestWeekHighlight {
  week: string
  total_plays: number
  tracks_count: number
}

// ── Section 4: 名人堂 ─────────────────────────────────────────

export interface AllTimeGreatestRecord {
  track_id: number
  track_name: string
  artist_name: string
  peak_position: number
  weeks_on_chart: number
  weeks_at_no1: number
  '走势评分': number
}

export interface AlbumPowerRankingRecord {
  album_name: string
  artist_name: string
  peak_position: number
  weeks_on_chart: number
  '走势评分': number
}

export interface ArtistPowerRankingRecord {
  artist_name: string
  peak_position: number
  weeks_on_chart: number
  '走势评分': number
}

export interface YearEndNo1Record {
  year: number
  track_id: number
  track_name: string
  artist_name: string
  peak: number
  weeks_on_chart: number
}

export interface DecadeBestRecord {
  '年代': string
  track_id: number
  track_name: string
  artist_name: string
  peak: number
  weeks_on_chart: number
  '走势评分': number
}

// ── Section 5: 奇趣纪录 ──────────────────────────────────────

export interface DoubleDebutRecord {
  debut_track_id: number
  debut_track: string
  debut_artist: string
  debut_week: string
  debut_album: string
}

export interface TripleNo1Record {
  billboard_week: string
  '艺人': string
}

// ── Section 6: 每周大盘 ──────────────────────────────────────

export interface WeekTotalPlaysRecord {
  billboard_week: string
  total_plays: number
  tracks_count: number
  no1_track_id: number | null
  no1_track: string | null
  no1_track_artist: string | null
  no1_track_plays: number | null
  no1_album: string | null
  no1_album_artist: string | null
  no1_album_plays: number | null
  no1_chart_artist: string | null
  no1_chart_artist_plays: number | null
}

export interface No1VsNo2Highlight {
  week: string
  no1_track: string
  no1_artist: string
  no1_plays: number
  no2_track: string
  no2_artist: string
  no2_plays: number
  gap: number
  gap_pct: number
}

export interface NewEntryRatioRecord {
  billboard_week: string
  '总歌曲数': number
  '新入榜歌曲数': number
  '新歌占比': number
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
  meta: TrackSpotifyMeta | null
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
  meta: ArtistSpotifyMeta | null
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
  meta: AlbumSpotifyMeta | null
  info: AlbumInfo
  chart_summary: AlbumChartSummary
  album_weekly_history: AlbumWeeklyHistoryEntry[]
  album_no1_by_week: { week: string; no1_track_names: string; no1_track_id: number | null; no1_count: number }[]
  best_singles_overlay: { week: string; rank: number }[]
  tracks: AlbumTrackEntry[]
}

// ── Release Cycle ──────────────────────────────────────────

export interface ReleaseCycleMetrics {
  debut_rank: number | null
  peak_rank: number | null
  weeks_to_peak: number | null
  weeks_on_chart: number
  artist_impact: number | null
  market_impact: number | null
  artist_impact_fmt?: string
  market_impact_fmt?: string
  artist_impact_detail?: Record<string, unknown> | null
  market_impact_detail?: Record<string, unknown> | null
  half_life: number | null
  peak_play_count: number
  release_week_plays: number
  pre_release_avg: number
}

export interface ReleaseCycleTimelineEntry {
  week_offset: number
  play_count: number
  total_ms?: number
  tracks_count?: number
}

export interface ReleaseCycleRankEntry {
  billboard_week?: string
  week_offset: number
  rank: number
  play_count?: number
}

export interface ReleaseCycleTrackTimelineEntry {
  week_offset: number
  track_id: number
  track_name: string
  play_count: number
}

export interface AdvanceSingle {
  single_name: string
  release_date: string
}

export interface AdvanceSingleRank {
  name: string
  release_date?: string
  ranks: ReleaseCycleRankEntry[]
}

export interface CatalogReentry {
  track_name: string
  source_album: string
  reentry_offset: number
  weeks_in_chart: number
}

export interface BonusTrack {
  track_name: string
  play_count: number
  first_appearance: string
  source_album: string
}

export interface TrackMatrix {
  tracks: string[]
  weeks: number[]
  data: number[][]
}

export interface ReleaseCycleAlbumDetailResponse {
  error?: string
  album_name: string
  artist_name: string
  album_type: string
  release_date: string
  release_date_iso: string
  canonical_name: string
  primary_name: string
  group_albums: string[]
  is_grouped: boolean
  advance_singles: AdvanceSingle[]
  metrics: ReleaseCycleMetrics
  artist_timeline: ReleaseCycleTimelineEntry[]
  album_timeline: ReleaseCycleTimelineEntry[]
  track_timelines: ReleaseCycleTrackTimelineEntry[]
  artist_ranks: ReleaseCycleRankEntry[]
  album_ranks: ReleaseCycleRankEntry[]
  total_timeline: ReleaseCycleTimelineEntry[]
  artist_all_time_median: number | null
  clean_baseline_start: number | null
  advance_single_ranks: AdvanceSingleRank[]
  best_track_ranks: { name: string; ranks: ReleaseCycleRankEntry[] } | null
  catalog_reentries: CatalogReentry[]
  bonus_tracks: BonusTrack[]
  track_matrix: TrackMatrix | null
}

export interface ReleaseCycleRelease {
  album_name: string
  album_type: string
  release_date: string
  db_album_id?: number | null
  spotify_album_id?: string | null
  canonical_name?: string | null
  sub_albums?: string | null
  cover_url?: string | null
}

export interface ReleaseCycleArtistSummary {
  total_albums: number
  total_singles: number
  album_debut_no1_count: number
  single_debut_no1_count: number
  double_debut_count: number
  max_artist_impact: number | null
  max_artist_impact_album: string
  max_market_impact: number | null
  max_market_impact_album: string
  total_catalog_reentries: number
  max_artist_impact_fmt?: string
  max_market_impact_fmt?: string
}

export interface ReleaseCycleArtistOverviewResponse {
  artist_name: string
  summary: ReleaseCycleArtistSummary | null
  releases: ReleaseCycleRelease[]
  rank_trend: Array<{
    billboard_week: string
    play_count: number
    total_ms: number
    tracks_count: number
    rank: number | null
  }>
  release_events: Array<{
    album_name: string
    album_type: string
    release_date: string
    db_album_id?: number | null
    cover_url?: string | null
  }>
  first_play_week: string | null
  last_play_week: string | null
  cycles: Array<{
    album_name: string
    album_type: string
    release_date: string
    db_album_id?: number | null
    spotify_album_id?: string | null
    canonical_name?: string | null
    sub_albums?: string | null
    cover_url?: string | null
    metrics: ReleaseCycleMetrics
    artist_timeline: ReleaseCycleTimelineEntry[]
    album_timeline: ReleaseCycleTimelineEntry[]
    artist_ranks: ReleaseCycleRankEntry[]
    album_ranks: ReleaseCycleRankEntry[]
    total_timeline: ReleaseCycleTimelineEntry[]
    artist_all_time_median: number | null
  }>
}

// ── Spotify Metadata ────────────────────────────────────────

export interface TrackSpotifyMeta {
  duration_ms?: number
  popularity?: number
  explicit: boolean
  track_number?: number
  disc_number?: number
  spotify_album_name?: string
}

export interface ArtistSpotifyMeta {
  popularity?: number
  followers?: number
  genres?: string[]
}

export interface AlbumSpotifyMeta {
  album_type?: string
  release_date?: string
  popularity?: number
  label?: string
  total_tracks?: number
}

// ── Genius Lyrics ──────────────────────────────────────────

export interface LyricsData {
  found: boolean
  lyrics: string
  genius_url: string
  genius_song_id: number
  cached: boolean
}

export interface GeniusUrlData {
  found: boolean
  genius_url: string
}

// ── Wikipedia Enrichment ─────────────────────────────────────

// ── Structured Enrichment (LLM-generated JSON) ────────────

export interface KeyFact {
  label: string
  value: string
}

export interface StatItem {
  label: string
  value: string
}

export interface CareerEvent {
  year: number
  event: string
  detail?: string
}

export interface Achievement {
  title: string
  year: number
  detail?: string
}

export interface StructuredArtist {
  summary: string
  key_facts: KeyFact[]
  career_timeline: CareerEvent[]
  genres: string[]
  stats: StatItem[]
  achievements: Achievement[]
}

export interface ChartEntry {
  region: string
  peak: number
  detail?: string
}

export interface AlbumSingle {
  name: string
  peak: number
  certification?: string
}

export interface StructuredAlbum {
  summary: string
  key_facts: KeyFact[]
  genres: string[]
  chart_performance: ChartEntry[]
  accolades: Achievement[]
  singles: AlbumSingle[]
}

// ── Wiki Data ──────────────────────────────────────────────

export interface WikiSingle {
  name: string
  date: string | null
}

export interface AlbumWikiInfobox {
  release_date: string
  recorded: string
  studio: string
  genre: string
  length: string
  label: string
  producer: string
  singles: WikiSingle[]
}

export interface AlbumWikiSections {
  background: string
  reception: string
  commercial: string
}

export interface AlbumWikiData {
  url: string
  lang: string
  summary: string
  summary_zh: string
  description: string
  description_zh: string
  thumbnail: string
  infobox: AlbumWikiInfobox
  sections: AlbumWikiSections
  sections_zh: AlbumWikiSections
  structured?: StructuredAlbum
}

export interface AlbumEnrichmentResponse {
  wiki: AlbumWikiData | null
  genius: {
    name: string
    artist: string
    cover_url: string
    release_date: string
    url: string
  } | null
}

export interface ArtistWikiData {
  url: string
  lang: string
  summary: string
  summary_zh: string
  description: string
  description_zh: string
  thumbnail: string
  sections: {
    early_life: string
    discography: string
  }
  sections_zh: {
    early_life: string
    discography: string
  }
  structured?: StructuredArtist
}

export interface ArtistEnrichmentResponse {
  wiki: ArtistWikiData | null
  genius: Record<string, unknown> | null
}

export interface TrackEnrichmentResponse {
  wiki: {
    url: string
    lang: string
    summary: string
    summary_zh: string
    description: string
    description_zh: string
    sections: { background: string }
    sections_zh: { background: string }
  } | null
  genius: {
    title: string
    artist: string
    url: string
    album_name: string
    cover_url: string
    release_date: string
  } | null
}
