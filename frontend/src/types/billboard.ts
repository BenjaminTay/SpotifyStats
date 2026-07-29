export interface BillboardMeta {
  [key: string]: any
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
  [key: string]: any
  billboard_week: string
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
  power_score: number
  peak_position: number
  weeks_on_chart: number
  weeks_top5: number
  weeks_top10: number
  weeks_at_no1: number
  power_rank: number
}

export interface AlbumPowerScoreEntry {
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  meta: BillboardMeta
  weekly: WeeklyTrackEntry[]
  weekly_album: WeeklyAlbumEntry[]
  weekly_artist: WeeklyArtistEntry[]
}

/** Records-only response from GET /api/billboard/records */
export interface BillboardRecordsResponse {
  [key: string]: any
  records: BillboardRecords
}

/** Power scores response from GET /api/billboard/power-scores */
export interface BillboardPowerScoresResponse {
  [key: string]: any
  album_power_scores: AlbumPowerScoreEntry[]
  artist_power_scores: ArtistPowerScoreEntry[]
}

/** Summaries response from GET /api/billboard/summaries */
export interface BillboardSummariesResponse {
  [key: string]: any
  artist_summary: ArtistSummary[]
  album_track_counts: AlbumTrackCounts[]
  artist_track_counts: ArtistTrackCounts[]
}

/** Combined all-time response from GET /api/billboard/all-time */
export interface BillboardAllTimeResponse {
  [key: string]: any
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

/** Year-end response from GET /api/billboard/year-end */
export interface BillboardYearEndMeta {
  year: number | null
  available_years: number[]
  total_weeks: number
  top_n: number
  album_top_n: number
  artist_top_n: number
  year_end_top_n: number
  year_end_album_top_n: number
  year_end_artist_top_n: number
  weekly_top_n: number
  weekly_album_top_n: number
  weekly_artist_top_n: number
  week_start_dow: number
  week_start_hour: number
  score_label: string
  semantics_version: string
  coverage_status: 'empty' | 'complete' | 'incomplete' | 'partial_start' | 'year_to_date' | 'partial_range'
  is_complete_year: boolean
  period_start: string | null
  period_end: string | null
  first_billboard_week: string | null
  last_billboard_week: string | null
  observed_weeks: number
  expected_weeks: number
  has_internal_gaps: boolean
}

export interface BillboardYearEndRow {
  year_end_score: number
  year_end_rank: number
  peak_position: number
  weeks_on_chart: number
  weeks_at_peak: number
  weeks_at_no1: number
  weeks_top5: number
  weeks_top10: number
  chart_plays: number
  annual_plays: number
  first_week: string | null
  last_week: string | null
  true_first_week?: string | null
  cover_url?: string | null
}

export interface BillboardYearEndTrackRow extends BillboardYearEndRow {
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
  album_name?: string
  is_true_debut_no1: boolean
}

export interface BillboardYearEndAlbumRow extends BillboardYearEndRow {
  album_name: string
  artist_name: string
  release_date?: string | null
  album_type?: string | null
  is_new_entry?: boolean
}

export interface BillboardYearEndArtistRow extends BillboardYearEndRow {
  artist_name: string
  is_new_entry?: boolean
}

export interface BillboardYearEndHonors {
  year_end_no1_track: BillboardYearEndTrackRow | null
  year_end_no1_album: BillboardYearEndAlbumRow | null
  year_end_no1_artist: BillboardYearEndArtistRow | null
  longest_charting_track: BillboardYearEndTrackRow | null
  longest_charting_album: BillboardYearEndAlbumRow | null
  longest_charting_artist: BillboardYearEndArtistRow | null
  biggest_no1_run_track: BillboardYearEndTrackRow | null
  biggest_no1_run_album: BillboardYearEndAlbumRow | null
  biggest_no1_run_artist: BillboardYearEndArtistRow | null
  top_new_entry_track: BillboardYearEndTrackRow | null
  breakthrough_artist: BillboardYearEndArtistRow | null
  album_era_of_the_year: BillboardYearEndAlbumRow | null
}

export interface BillboardYearEndResponse {
  meta: BillboardYearEndMeta
  tracks: BillboardYearEndTrackRow[]
  albums: BillboardYearEndAlbumRow[]
  artists: BillboardYearEndArtistRow[]
  honors: BillboardYearEndHonors
}

// ── Billboard Records ──────────────────────────────────────────

export interface BillboardRecords {
  [key: string]: any
  artist_most_no1: ArtistMostNo1Record[]
  debut_no1: DebutNo1Record[]
  debut_no1_album: DebutNo1AlbumRecord[]
  return_to_no1: ReturnToNo1Record[]
  return_to_no1_album: ReturnToNo1AlbumRecord[]
  return_to_no1_artist: ReturnToNo1ArtistRecord[]
  self_replacement_no1: SelfReplacementRecord[]
  self_replacement_no1_album: SelfReplacementAlbumRecord[]
  blocker_king: BlockerKingRecord[]
  blocked_tracks_map: Record<number, BlockedTrackInfo[]>
  blocker_king_album: BlockerKingAlbumRecord[]
  blocked_albums_map: Record<string, BlockedAlbumInfo[]>
  blocker_king_artist: BlockerKingArtistRecord[]
  blocked_artists_map: Record<string, BlockedArtistInfo[]>
  longest_to_no1: ClimbToNo1Record[]
  longest_to_no1_album: ClimbToNo1AlbumRecord[]
  longest_to_no1_artist: ClimbToNo1ArtistRecord[]

  // Section 2: 持久传奇
  longest_charting: LongestChartingRecord[]
  longest_charting_album: LongestChartingAlbumRecord[]
  longest_charting_artist: LongestChartingArtistRecord[]
  longest_streak: LongestStreakRecord[]
  longest_streak_album: LongestStreakAlbumRecord[]
  longest_streak_artist: LongestStreakArtistRecord[]
  longest_no_top5: LongestNoTop5Record[]
  longest_no_top5_album: LongestNoTop5AlbumRecord[]
  longest_no_top5_artist: LongestNoTop5ArtistRecord[]
  most_weeks_no2_no_no1: MostWeeksNo2Record[]
  most_weeks_no2_no_no1_album: MostWeeksNo2AlbumRecord[]
  most_weeks_no2_no_no1_artist: MostWeeksNo2ArtistRecord[]
  most_reentries: MostReentriesRecord[]
  most_reentries_album: MostReentriesAlbumRecord[]
  most_reentries_artist: MostReentriesArtistRecord[]
  longest_consecutive_same_rank: LongestSameRankRecord[]
  longest_consecutive_same_rank_album: LongestSameRankAlbumRecord[]
  longest_consecutive_same_rank_artist: LongestSameRankArtistRecord[]
  longest_artist_span: LongestArtistSpanRecord[]

  // Section 3: 爆发时刻
  artist_simul: ArtistSimulHighlight
  artist_simul_list: ArtistSimulEntry[]
  album_simul: AlbumSimulHighlight
  album_simul_list: AlbumSimulEntry[]
  biggest_jump: RankChangeRecord[]
  biggest_drop: RankChangeRecord[]
  fastest_exit_after_no1: FastestExitRecord[]

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
  [key: string]: any
  '冠单数': number
  '单曲冠军周数': number
  '冠军专辑数': number
  '专辑冠军周数': number
}

export interface DebutNo1Record {
  [key: string]: any
  track_name: string
  artist_name: string
  first_week: string
  weeks_at_no1: number
  weeks_on_chart: number
}

export interface DebutNo1AlbumRecord {
  [key: string]: any
  artist_name: string
  first_week: string
  weeks_at_no1: number
  weeks_on_chart: number
}

export interface ReturnToNo1Record {
  [key: string]: any
  track_name: string
  artist_name: string
  '首次冠单': string
  '回冠日期': string
  '间隔周数': number
}

export interface ReturnToNo1AlbumRecord {
  [key: string]: any
  artist_name: string
  '首次冠专': string
  '回冠日期': string
  '间隔周数': number
}

export interface ReturnToNo1ArtistRecord {
  [key: string]: any
  artist_name: string
  '首次夺艺冠': string
  '回冠日期': string
  '间隔周数': number
}

export interface SelfReplacementRecord {
  [key: string]: any
  '艺人': string
  '前冠单_id': number
  '前冠单': string
  '新冠单_id': number
  '新冠单': string
}

export interface SelfReplacementAlbumRecord {
  [key: string]: any
  '艺人': string
  '前冠专': string
  '新冠专': string
}

export interface BlockerKingRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  '阻挡数': number
  '走势评分': number
}

export interface BlockerKingAlbumRecord {
  [key: string]: any
  artist_name: string
  '阻挡数': number
  '走势评分': number
}

export interface BlockerKingArtistRecord {
  [key: string]: any
  artist_name: string
  '阻挡数': number
  '走势评分': number
}

export interface BlockedTrackInfo {
  [key: string]: any
  track_name: string
  artist_name: string
}

export interface BlockedAlbumInfo {
  [key: string]: any
  artist_name: string
}

export interface BlockedArtistInfo {
  [key: string]: any
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

export interface ClimbToNo1AlbumRecord {
  album_name: string
  artist_name: string
  first_week: string
  first_peak_week: string
  '登顶周数': number
}

export interface ClimbToNo1ArtistRecord {
  artist_name: string
  first_week: string
  first_peak_week: string
  '登顶周数': number
}

// ── Section 2: 持久传奇 ──────────────────────────────────────

export interface LongestChartingRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
  weeks_at_no1: number
}

export interface LongestStreakRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestChartingAlbumRecord {
  [key: string]: any
  artist_name: string
  weeks_on_chart: number
  peak_position: number
  weeks_at_no1: number
}

export interface LongestChartingArtistRecord {
  [key: string]: any
  artist_name: string
  weeks_on_chart: number
  peak_position: number
  weeks_at_no1: number
}

export interface LongestStreakAlbumRecord {
  [key: string]: any
  artist_name: string
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestStreakArtistRecord {
  [key: string]: any
  artist_name: string
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestNoTop5Record {
  [key: string]: any
  track_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface LongestNoTop5AlbumRecord {
  [key: string]: any
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface LongestNoTop5ArtistRecord {
  [key: string]: any
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface LongestNoTop10Record {
  [key: string]: any
  track_name: string
  artist_name: string
  weeks_on_chart: number
  peak_position: number
}

export interface MostWeeksNo2Record {
  [key: string]: any
  track_name: string
  artist_name: string
  peak_position: number
  weeks_at_no2: number
}

export interface MostWeeksNo2AlbumRecord {
  [key: string]: any
  artist_name: string
  peak_position: number
  weeks_at_no2: number
}

export interface MostWeeksNo2ArtistRecord {
  [key: string]: any
  artist_name: string
  peak_position: number
  weeks_at_no2: number
}

export interface MostReentriesRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  '回榜次数': number
  '在榜周数': number
}

export interface MostReentriesAlbumRecord {
  [key: string]: any
  artist_name: string
  '回榜次数': number
  '在榜周数': number
}

export interface MostReentriesArtistRecord {
  [key: string]: any
  artist_name: string
  '回榜次数': number
  '在榜周数': number
}

export interface LongestSameRankRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  '停留排名': number
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestSameRankAlbumRecord {
  [key: string]: any
  album_name: string
  artist_name: string
  '停留排名': number
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestSameRankArtistRecord {
  [key: string]: any
  artist_name: string
  '停留排名': number
  '连续周数': number
  '起始周': string
  '结束周': string
}

export interface LongestArtistSpanRecord {
  [key: string]: any
  artist_name: string
  '首次上榜': string
  '最近上榜': string
  '上榜歌曲数': number
  '跨度天数': number
}

// ── Section 3: 爆发时刻 ──────────────────────────────────────

export interface ArtistSimulHighlight {
  [key: string]: any
  artist: string
  week: string
  count: number
}

export interface ArtistSimulEntry {
  [key: string]: any
  billboard_week: string
  artist_name: string
  track_count: number
}

export interface AlbumSimulHighlight {
  [key: string]: any
  album: string
  artist: string
  week: string
  count: number
}

export interface AlbumSimulEntry {
  [key: string]: any
  billboard_week: string
  artist_name: string
  album_name: string
  track_count: number
}

export interface RankChangeRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  '日期': string
  '上周排名': number
  '本周排名': number
  '变化': number
}

export interface FastestExitRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  first_peak_week: string
  last_week: string
  '巅峰后周数': number
}


// ── Section 4: 名人堂 ─────────────────────────────────────────

export interface AllTimeGreatestRecord {
  [key: string]: any
  track_name: string
  artist_name: string
  peak_position: number
  weeks_on_chart: number
  weeks_at_no1: number
  '走势评分': number
}

export interface AlbumPowerRankingRecord {
  [key: string]: any
  artist_name: string
  peak_position: number
  weeks_on_chart: number
  '走势评分': number
}

export interface ArtistPowerRankingRecord {
  [key: string]: any
  peak_position: number
  weeks_on_chart: number
  '走势评分': number
}

export interface YearEndNo1Record {
  [key: string]: any
  track_id: number
  track_name: string
  artist_name: string
  peak: number
  weeks_on_chart: number
}

export interface DecadeBestRecord {
  [key: string]: any
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
  track_id: number
  '歌曲': string
  '专辑': string
}

// ── Section 6: 每周大盘 ──────────────────────────────────────

export interface WeekTotalPlaysRecord {
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  billboard_week: string
  '总歌曲数': number
  '新入榜歌曲数': number
  '新歌占比': number
}

// ── Track Detail ────────────────────────────────────────────

export interface TrackHistoryEntry {
  [key: string]: any
  week: string
  rank: number
  play_count: number
  change: string
  running_peak: number
  running_wks: number
  running_peak_wks: number
}

export interface TrackChartData {
  [key: string]: any
  x: string[]
  y: (number | null)[]
  texts: string[]
  top_n: number
  peak_position: number
}

export interface TrackDetailResponse {
  [key: string]: any
  found: boolean
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  no1_track_names: string
  no1_track_id: number | null
  no1_count: number
}

export interface ArtistTrackEntry {
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  found: boolean
  artist_name: string
  cover_url: string | null
  meta: ArtistSpotifyMeta | null
  info: ArtistInfo
  chart_summary: ArtistChartSummary
  artist_weekly_history: ArtistWeeklyHistoryEntry[]
  artist_no1_by_week: ArtistNo1ByWeek[]
  week_no1_albums: { week: string; album_name: string; artist_name: string }[]
  best_singles_overlay: { week: string; rank: number; track_name: string }[]
  best_albums_overlay: { week: string; rank: number; album_name: string }[]
  tracks: ArtistTrackEntry[]
  albums: ArtistAlbumEntry[]
}

// ── Album Detail ────────────────────────────────────────────

export interface AlbumChartSummary {
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
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

export interface AlbumProjectTrack {
  [key: string]: any
  project_id: number
  album_project_name: string
  canonical_song_key: string
  canonical_song_name: string
  track_id: number
  track_name: string
  membership_role: string
  source_bucket: string | null
  is_exclusive: number
}

export interface AlbumSourceBreakdownItem {
  [key: string]: any
  album_project_id: number
  album_project_name: string
  source_album_id: number | null
  source_album_name: string | null
  source_bucket: string
  play_count: number
  total_ms: number
  album_cover_url?: string | null
  release_date?: string | null
  track_count?: number | null
}

export interface AlbumProject {
  [key: string]: any
  album_project_id: number
  album_project_name: string
  artist_name: string
  release_date: string
  play_count: number
  total_ms: number
  unique_canonical_songs: number
  tracks: AlbumProjectTrack[]
  source_breakdown: AlbumSourceBreakdownItem[]
}

export interface AlbumDetailResponse {
  [key: string]: any
  found: boolean
  album_name: string
  artist_name: string
  cover_url: string | null
  meta: AlbumSpotifyMeta | null
  info: AlbumInfo
  chart_summary: AlbumChartSummary
  album_project?: AlbumProject | null
  album_weekly_history: AlbumWeeklyHistoryEntry[]
  album_no1_by_week: { week: string; no1_track_names: string; no1_track_id: number | null; no1_count: number }[]
  best_singles_overlay: { week: string; rank: number; track_name: string }[]
  tracks: AlbumTrackEntry[]
}

// ── Release Cycle ──────────────────────────────────────────

export interface ReleaseCycleMetrics {
  [key: string]: any
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
  [key: string]: any
  week_offset: number
  play_count: number
  total_ms?: number
  tracks_count?: number
}

export interface ReleaseCycleRankEntry {
  [key: string]: any
  billboard_week: string
  week_offset: number
  rank: number
  play_count?: number
}

export interface ReleaseCycleTrackTimelineEntry {
  [key: string]: any
  track_id: number
  track_name: string
  play_count: number
}

export interface AdvanceSingle {
  [key: string]: any
  single_name: string
  release_date: string
  cover_url?: string | null
}

export interface AdvanceSingleRank {
  [key: string]: any
  name?: string
  release_date?: string
  ranks: ReleaseCycleRankEntry[]
}

export interface CatalogReentry {
  [key: string]: any
  track_name: string
  source_album: string
  reentry_offset: number
  weeks_in_chart: number
}

export interface BonusTrack {
  [key: string]: any
  track_name: string
  play_count: number
  first_appearance: string
  source_album: string
}

export interface TrackMatrix {
  [key: string]: any
  weeks: number[]
  tracks: string[]
  data: number[][]
}

export interface ReleaseCycleAlbumDetailResponse {
  [key: string]: any
  error?: string | null
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
  [key: string]: any
  album_type: string
  release_date: string
  db_album_id?: number | null
  spotify_album_id?: string | null
  canonical_name?: string | null
  sub_albums?: string | null
  cover_url?: string | null
}

export interface ReleaseCycleArtistSummary {
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  popularity?: number
  duration_ms?: number
  explicit: boolean
  track_number?: number
  disc_number?: number
  spotify_album_name?: string
  version_group?: TrackVersionGroup
}

export interface ArtistSpotifyMeta {
  [key: string]: any
  followers?: number
  popularity?: number
  genres?: string[]
}

export interface AlbumSpotifyMeta {
  [key: string]: any
  album_type?: string
  release_date?: string
  popularity?: number
  label?: string
  total_tracks?: number
  release_group?: AlbumVersionGroup
}

// ── Version Group (Track & Album) ──────────────────────────

export interface VersionGroupItem {
  track_id?: number
  track_name?: string
  album_id?: number
  album_name?: string
  artist_name?: string
  plays: number
  total_ms?: number
  unique_tracks?: number
  is_primary: boolean
  recording_kind?: string | null
  album_cover_url?: string | null
  release_date?: string | null
  album_type?: string | null
  total_tracks?: number | null
}

export interface TrackVersionGroup {
  group_id: number
  canonical_name: string
  scope: 'recording' | 'composition'
  total_plays: number
  versions: VersionGroupItem[]
}

export interface TrackCoverageItem {
  track_id: number
  track_name: string
  album_ids: number[]
  is_exclusive: boolean
}

export interface AlbumVersionGroup {
  group_id: number
  canonical_name: string
  scope: 'release' | 'composition'
  total_plays: number
  versions: VersionGroupItem[]
  track_coverage?: TrackCoverageItem[]
}

// ── Genius Lyrics ──────────────────────────────────────────

export interface LyricsData {
  [key: string]: any
  found: boolean
  lyrics: string
  genius_url: string
  genius_song_id: number
  cached: boolean
}

export interface GeniusUrlData {
  [key: string]: any
  genius_url: string
}

// ── Wikipedia Enrichment ─────────────────────────────────────

// ── Structured Enrichment (LLM-generated JSON) ────────────

export interface KeyFact {
  [key: string]: any
  label: string
  value: string
}

export interface StatItem {
  [key: string]: any
  label: string
  value: string
}

export interface CareerEvent {
  [key: string]: any
  year: string
  event: string
  detail?: string
}

export interface Achievement {
  [key: string]: any
  year: number
  title: string
  detail?: string
}

export interface StructuredArtist {
  [key: string]: any
  summary: string
  key_facts: KeyFact[]
  career_timeline: CareerEvent[]
  genres: string[]
  stats: StatItem[]
  achievements: Achievement[]
}

export interface ChartEntry {
  [key: string]: any
  region: string
  peak: number
  detail?: string
}

export interface AlbumSingle {
  [key: string]: any
  name: string
  peak: number
  certification?: string
  cover_url?: string | null
}

export interface StructuredAlbum {
  [key: string]: any
  summary: string
  key_facts: KeyFact[]
  genres: string[]
  chart_performance: ChartEntry[]
  accolades: Achievement[]
  singles: AlbumSingle[]
}

// ── Wiki Data ──────────────────────────────────────────────

export interface WikiSingle {
  [key: string]: any
  name: string
  date: string | null
}

export interface AlbumWikiInfobox {
  [key: string]: any
  recorded: string
  studio: string
  genre: string
  length: string
  label: string
  producer: string
  singles: WikiSingle[]
}

export interface AlbumWikiSections {
  [key: string]: any
  background: string
  reception: string
  commercial: string
}

export interface AlbumWikiData {
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
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
  [key: string]: any
  wiki: ArtistWikiData | null
  genius: Record<string, unknown> | null
}

export interface TrackEnrichmentResponse {
  [key: string]: any
  wiki: {
    [key: string]: any
    summary?: string
    summary_zh?: string
    url?: string
    sections: {
      [key: string]: any
      background?: string
    }
    sections_zh?: {
      [key: string]: any
      background?: string
    }
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

// ── Versus ──────────────────────────────────────────────────

export interface VersusRankPoint {
  [key: string]: any
  week: string
  rank: number
  play_count: number
}

export interface VersusEntityData {
  [key: string]: any
  name: string | null
  cover_url: string | null
  popularity: number | null
  genres?: string[] | null
  rank_history: VersusRankPoint[] | null
  metrics: Record<string, unknown> | null
}

export interface VersusResponse {
  [key: string]: any
  found: boolean
  reason?: string | null
  entities?: VersusEntityData[] | null
}

export interface EntityListItem {
  [key: string]: any
  display: string
  track_id?: number
  album_name?: string
  artist_name?: string
}

export interface EntityListsResponse {
  [key: string]: any
  tracks: EntityListItem[]
  albums: EntityListItem[]
  artists: EntityListItem[]
}

export interface ReleaseCycleCompareItem {
  [key: string]: any
  artist_name: string
  album_name: string
  release_date: string
  label: string
  metrics: Record<string, unknown>
  album_timeline: { week_offset: number; play_count: number }[]
  album_ranks: { billboard_week: string; week_offset: number; rank: number }[]
}

export interface ReleaseCycleCompareResponse {
  [key: string]: any
  error?: string | null
  comparisons: ReleaseCycleCompareItem[]
}
