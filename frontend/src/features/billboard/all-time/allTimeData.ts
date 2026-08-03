import type {
  AlbumTrackCounts,
  ArtistTrackCounts,
  BillboardAllTimeResponse,
  PowerScoreEntry,
  TrackSummary,
} from '@/types/billboard'
import { displayName } from '@/lib/chinese'

export type EntityTab = 'tracks' | 'albums' | 'artists'
export type PeakFilter = 'all' | 'no1' | 'top5' | 'top10' | 'debut_no1'

export interface MergedTrackRow {
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
  album_name: string
  cover_url: string | null
  weeks_on_chart: number
  peak_position: number
  weeks_at_peak: number
  weeks_top5: number
  weeks_top10: number
  power_score: number
  power_rank: number
  total_chart_plays: number
  is_debut_no1: boolean
}

export interface MergedAlbumRow {
  album_name: string
  artist_name: string
  cover_url: string | null
  weeks_on_chart: number
  peak_position: number
  weeks_at_peak: number
  weeks_top5: number
  weeks_top10: number
  total_tracks: number
  top1_tracks: number
  top5_tracks: number
  top10_tracks: number
  track_power_sum: number
  track_power_rank: number | null
  power_score: number
  power_rank: number
  total_plays: number
  is_debut_no1: boolean
}

export interface MergedArtistRow {
  artist_name: string
  cover_url: string | null
  weeks_on_chart: number
  peak_position: number
  weeks_at_peak: number
  weeks_top5: number
  weeks_top10: number
  total_tracks: number
  top1_tracks: number
  top5_tracks: number
  top10_tracks: number
  num_no1_albums: number
  top5_albums: number
  top10_albums: number
  track_power_sum: number
  track_power_rank: number | null
  album_power_sum: number
  album_power_rank: number | null
  power_score: number
  power_rank: number
  total_plays: number
  is_debut_no1: boolean
}

export type AllTimeRow = MergedTrackRow | MergedAlbumRow | MergedArtistRow
export type ColumnGroup = '榜单核心' | '歌曲相关' | '专辑相关' | '个人数据'

export interface AllTimeRows {
  tracks: MergedTrackRow[]
  albums: MergedAlbumRow[]
  artists: MergedArtistRow[]
}

export interface ColumnDef<T> {
  key: string
  label: string
  group: ColumnGroup
  defaultVisible: boolean
  fixed?: boolean
  minWidth: number
  mobilePriority: number
  description?: string
  align: 'left' | 'right' | 'center'
  getValue: (row: T) => number | string | null
  format: (row: T) => string
  sortable: boolean
  rankStyle?: boolean
}

export const ALL_TIME_FIXED_COLUMNS = [
  { key: 'current_rank', label: '当前排名', group: '榜单核心' as const, fixed: true, minWidth: 44, mobilePriority: 0 },
  { key: 'entity', label: '名称', group: '榜单核心' as const, fixed: true, minWidth: 200, mobilePriority: 0 },
] as const

interface WeeklyStats {
  weeksAtPeak: number
  weeksTop5: number
  weeksTop10: number
  totalPlays: number
  firstWeek: string
}

interface WeeklyStatsDraft extends WeeklyStats {
  minRank: number
}

export const ALL_TIME_PAGE_SIZE = 50

export const EMPTY_ALL_TIME_ROWS: AllTimeRows = {
  tracks: [],
  albums: [],
  artists: [],
}

export const PEAK_FILTER_OPTIONS: { value: PeakFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'no1', label: 'No.1 冠军' },
  { value: 'top5', label: 'Top 5' },
  { value: 'top10', label: 'Top 10' },
  { value: 'debut_no1', label: '空冠' },
]

export const TABS: { key: EntityTab; label: string }[] = [
  { key: 'tracks', label: '单曲榜' },
  { key: 'albums', label: '专辑榜' },
  { key: 'artists', label: '艺人榜' },
]

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

export function rankColorClass(rank: number): string {
  if (rank === 1) return 'text-accent-foreground'
  if (rank === 2) return 'text-muted-foreground'
  if (rank === 3) return 'text-[#C17A4E] dark:text-[#C97B6B]'
  return 'text-muted-foreground'
}

const base = (group: ColumnGroup, defaultVisible: boolean, minWidth = 80, mobilePriority = 3) => ({ group, defaultVisible, minWidth, mobilePriority })

const TRACK_COLUMNS: ColumnDef<MergedTrackRow>[] = [
  { key: 'peak_position', label: '排名峰值', ...base('榜单核心', true, 78, 1), align: 'right', getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true, rankStyle: true },
  { key: 'weeks_at_peak', label: '峰值周数', ...base('榜单核心', true), align: 'right', getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true },
  { key: 'weeks_on_chart', label: '在榜周数', ...base('榜单核心', true, 80, 1), align: 'right', getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true },
  { key: 'weeks_top5', label: 'Top5周数', ...base('榜单核心', false), align: 'right', getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true },
  { key: 'weeks_top10', label: 'Top10周数', ...base('榜单核心', false), align: 'right', getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true },
  { key: 'power_score', label: '走势评分', ...base('榜单核心', true, 88, 0), description: '当前完整总榜按周榜走势计算的主评分。', align: 'right', getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true },
  { key: 'power_rank', label: '走势排名', ...base('榜单核心', true, 84, 0), description: '按走势评分在当前完整单曲榜中的固定名次；前端排序不会改变。', align: 'right', getValue: (r) => r.power_rank, format: (r) => formatNumber(r.power_rank), sortable: true, rankStyle: true },
  { key: 'total_chart_plays', label: '入榜播放', ...base('个人数据', true, 112, 2), align: 'right', getValue: (r) => r.total_chart_plays, format: (r) => formatNumber(r.total_chart_plays), sortable: true },
]

const ALBUM_COLUMNS: ColumnDef<MergedAlbumRow>[] = [
  { key: 'peak_position', label: '排名峰值', ...base('榜单核心', true, 78, 1), align: 'right', getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true, rankStyle: true },
  { key: 'weeks_at_peak', label: '峰值周数', ...base('榜单核心', true), align: 'right', getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true },
  { key: 'weeks_on_chart', label: '在榜周数', ...base('榜单核心', true, 80, 1), align: 'right', getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true },
  { key: 'weeks_top5', label: 'Top5周数', ...base('榜单核心', false), align: 'right', getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true },
  { key: 'weeks_top10', label: 'Top10周数', ...base('榜单核心', false), align: 'right', getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true },
  { key: 'total_tracks', label: '入榜曲数', ...base('歌曲相关', true, 82, 1), align: 'right', getValue: (r) => r.total_tracks, format: (r) => formatNumber(r.total_tracks), sortable: true },
  { key: 'top1_tracks', label: '冠军歌曲数', ...base('歌曲相关', true, 92), align: 'right', getValue: (r) => r.top1_tracks, format: (r) => formatNumber(r.top1_tracks), sortable: true },
  { key: 'top5_tracks', label: 'Top5曲数', ...base('歌曲相关', false), align: 'right', getValue: (r) => r.top5_tracks, format: (r) => formatNumber(r.top5_tracks), sortable: true },
  { key: 'top10_tracks', label: 'Top10曲数', ...base('歌曲相关', false), align: 'right', getValue: (r) => r.top10_tracks, format: (r) => formatNumber(r.top10_tracks), sortable: true },
  { key: 'track_power_sum', label: '歌曲总点数', ...base('歌曲相关', true, 104, 0), description: '该专辑已入榜成员曲的走势点数之和。', align: 'right', getValue: (r) => r.track_power_sum, format: (r) => formatNumber(r.track_power_sum), sortable: true },
  { key: 'track_power_rank', label: '歌曲总点数排名', ...base('歌曲相关', true, 116, 1), description: '基于当前完整专辑榜可比较集合计算；无入榜成员曲时不排名。', align: 'right', getValue: (r) => r.track_power_rank, format: (r) => r.track_power_rank == null ? '—' : formatNumber(r.track_power_rank), sortable: true, rankStyle: true },
  { key: 'power_score', label: '专辑走势评分', ...base('专辑相关', true, 104, 0), description: '专辑自身在当前总榜的走势评分。', align: 'right', getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true },
  { key: 'power_rank', label: '专辑走势排名', ...base('专辑相关', true, 104, 0), description: '按专辑走势评分在当前完整专辑榜中的固定名次；前端排序不会改变。', align: 'right', getValue: (r) => r.power_rank, format: (r) => formatNumber(r.power_rank), sortable: true, rankStyle: true },
  { key: 'total_plays', label: '总播放次数', ...base('个人数据', true, 112, 2), align: 'right', getValue: (r) => r.total_plays, format: (r) => formatNumber(r.total_plays), sortable: true },
]

const ARTIST_COLUMNS: ColumnDef<MergedArtistRow>[] = [
  { key: 'peak_position', label: '排名峰值', ...base('榜单核心', true, 78, 1), align: 'right', getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true, rankStyle: true },
  { key: 'weeks_at_peak', label: '峰值周数', ...base('榜单核心', true), align: 'right', getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true },
  { key: 'weeks_on_chart', label: '在榜周数', ...base('榜单核心', true, 80, 1), align: 'right', getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true },
  { key: 'weeks_top5', label: 'Top5周数', ...base('榜单核心', false), align: 'right', getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true },
  { key: 'weeks_top10', label: 'Top10周数', ...base('榜单核心', false), align: 'right', getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true },
  { key: 'total_tracks', label: '入榜曲数', ...base('歌曲相关', true, 82, 1), align: 'right', getValue: (r) => r.total_tracks, format: (r) => formatNumber(r.total_tracks), sortable: true },
  { key: 'top1_tracks', label: '冠军歌曲数', ...base('歌曲相关', true, 92), align: 'right', getValue: (r) => r.top1_tracks, format: (r) => formatNumber(r.top1_tracks), sortable: true },
  { key: 'top5_tracks', label: 'Top5曲数', ...base('歌曲相关', false), align: 'right', getValue: (r) => r.top5_tracks, format: (r) => formatNumber(r.top5_tracks), sortable: true },
  { key: 'top10_tracks', label: 'Top10曲数', ...base('歌曲相关', false), align: 'right', getValue: (r) => r.top10_tracks, format: (r) => formatNumber(r.top10_tracks), sortable: true },
  { key: 'track_power_sum', label: '歌曲总点数', ...base('歌曲相关', true, 104, 0), description: '该艺人所有已入榜 credited 歌曲的走势点数之和。', align: 'right', getValue: (r) => r.track_power_sum, format: (r) => formatNumber(r.track_power_sum), sortable: true },
  { key: 'track_power_rank', label: '歌曲总点数排名', ...base('歌曲相关', true, 116, 1), description: '基于当前完整艺人榜可比较集合计算；无歌曲贡献时不排名。', align: 'right', getValue: (r) => r.track_power_rank, format: (r) => r.track_power_rank == null ? '—' : formatNumber(r.track_power_rank), sortable: true, rankStyle: true },
  { key: 'num_no1_albums', label: '#1专辑数', ...base('专辑相关', true, 90), align: 'right', getValue: (r) => r.num_no1_albums, format: (r) => formatNumber(r.num_no1_albums), sortable: true },
  { key: 'top5_albums', label: 'Top5专辑数', ...base('专辑相关', false, 92), align: 'right', getValue: (r) => r.top5_albums, format: (r) => formatNumber(r.top5_albums), sortable: true },
  { key: 'top10_albums', label: 'Top10专辑数', ...base('专辑相关', false, 96), align: 'right', getValue: (r) => r.top10_albums, format: (r) => formatNumber(r.top10_albums), sortable: true },
  { key: 'album_power_sum', label: '专辑总点数', ...base('专辑相关', true, 104, 0), description: '该艺人所有已入榜专辑的走势点数之和。', align: 'right', getValue: (r) => r.album_power_sum, format: (r) => formatNumber(r.album_power_sum), sortable: true },
  { key: 'album_power_rank', label: '专辑总点数排名', ...base('专辑相关', true, 116, 1), description: '基于当前完整艺人榜可比较集合计算；无专辑贡献时不排名。', align: 'right', getValue: (r) => r.album_power_rank, format: (r) => r.album_power_rank == null ? '—' : formatNumber(r.album_power_rank), sortable: true, rankStyle: true },
  { key: 'power_score', label: '艺人走势评分', ...base('榜单核心', true, 104, 0), description: '艺人自身在当前总榜的走势评分。', align: 'right', getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true },
  { key: 'power_rank', label: '艺人走势排名', ...base('榜单核心', true, 104, 0), description: '按艺人走势评分在当前完整艺人榜中的固定名次；前端排序不会改变。', align: 'right', getValue: (r) => r.power_rank, format: (r) => formatNumber(r.power_rank), sortable: true, rankStyle: true },
  { key: 'total_plays', label: '总播放次数', ...base('个人数据', true, 112, 2), align: 'right', getValue: (r) => r.total_plays, format: (r) => formatNumber(r.total_plays), sortable: true },
]

function weeklyStatsByKey<T extends { rank: number; play_count: number; billboard_week: string }>(
  entries: T[],
  keyOf: (entry: T) => string,
): Map<string, WeeklyStats> {
  const draft = new Map<string, WeeklyStatsDraft>()
  for (const entry of entries) {
    const key = keyOf(entry)
    const cur = draft.get(key)
    if (cur) {
      if (entry.rank < cur.minRank) {
        cur.minRank = entry.rank
        cur.weeksAtPeak = 1
      } else if (entry.rank === cur.minRank) {
        cur.weeksAtPeak++
      }
      if (entry.rank <= 5) cur.weeksTop5++
      if (entry.rank <= 10) cur.weeksTop10++
      cur.totalPlays += entry.play_count
      if (entry.billboard_week < cur.firstWeek) cur.firstWeek = entry.billboard_week
    } else {
      draft.set(key, {
        minRank: entry.rank,
        weeksAtPeak: 1,
        weeksTop5: entry.rank <= 5 ? 1 : 0,
        weeksTop10: entry.rank <= 10 ? 1 : 0,
        totalPlays: entry.play_count,
        firstWeek: entry.billboard_week,
      })
    }
  }

  const result = new Map<string, WeeklyStats>()
  for (const [key, value] of draft) {
    result.set(key, {
      weeksAtPeak: value.weeksAtPeak,
      weeksTop5: value.weeksTop5,
      weeksTop10: value.weeksTop10,
      totalPlays: value.totalPlays,
      firstWeek: value.firstWeek,
    })
  }
  return result
}

function coverMapByKey<T extends { cover_url: string | null }>(
  entries: T[],
  keyOf: (entry: T) => string,
): Map<string, string | null> {
  const map = new Map<string, string | null>()
  for (const entry of entries) {
    const key = keyOf(entry)
    if (!map.has(key) && entry.cover_url) map.set(key, entry.cover_url)
  }
  return map
}

function buildArtistAlbumStats(data: BillboardAllTimeResponse): Map<string, { top5Albums: number; top10Albums: number }> {
  const albumPeaks = new Map<string, { artist: string; peak: number }>()
  for (const entry of data.weekly_album) {
    const key = `${entry.artist_name}||${entry.album_name}`
    const cur = albumPeaks.get(key)
    if (!cur || entry.rank < cur.peak) {
      albumPeaks.set(key, { artist: entry.artist_name, peak: entry.rank })
    }
  }

  const artistMap = new Map<string, { top5Albums: number; top10Albums: number }>()
  for (const value of albumPeaks.values()) {
    const cur = artistMap.get(value.artist) ?? { top5Albums: 0, top10Albums: 0 }
    if (value.peak <= 5) cur.top5Albums++
    if (value.peak <= 10) cur.top10Albums++
    artistMap.set(value.artist, cur)
  }
  return artistMap
}

export function buildAllTimeRows(data: BillboardAllTimeResponse): AllTimeRows {
  const albumWeeklyStats = weeklyStatsByKey(data.weekly_album, (entry) => `${entry.album_name}||${entry.artist_name}`)
  const albumCoverMap = coverMapByKey(data.weekly_album, (entry) => `${entry.album_name}||${entry.artist_name}`)
  const artistWeeklyStats = weeklyStatsByKey(data.weekly_artist, (entry) => entry.artist_name)
  const artistCoverMap = coverMapByKey(data.weekly_artist, (entry) => entry.artist_name)
  const artistAlbumStats = buildArtistAlbumStats(data)

  const trackSummaryMap = new Map<number, TrackSummary>()
  for (const summary of data.track_summary) trackSummaryMap.set(summary.track_id, summary)

  const trackCoverMap = new Map<number, string | null>()
  for (const week of data.weekly) {
    if (!trackCoverMap.has(week.track_id) && week.cover_url) trackCoverMap.set(week.track_id, week.cover_url)
  }

  const tracks: MergedTrackRow[] = data.power_scores.map((score: PowerScoreEntry) => {
    const summary = trackSummaryMap.get(score.track_id)
    return {
      track_id: score.track_id,
      track_name: score.track_name,
      artist_name: score.artist_name,
      artist_names: score.artist_names,
      album_name: summary?.album_name ?? '',
      cover_url: trackCoverMap.get(score.track_id) ?? null,
      weeks_on_chart: score.weeks_on_chart,
      peak_position: score.peak_position,
      weeks_at_peak: summary?.weeks_at_peak ?? 0,
      weeks_top5: score.weeks_top5,
      weeks_top10: score.weeks_top10,
      power_score: score.power_score,
      power_rank: score.power_rank,
      total_chart_plays: summary?.total_chart_plays ?? 0,
      is_debut_no1: summary?.is_debut_no1 ?? false,
    }
  })

  const albumTrackCounts = new Map<string, AlbumTrackCounts>()
  for (const count of data.album_track_counts) albumTrackCounts.set(`${count.album_name}||${count.artist_name}`, count)

  const albumDebutNo1Keys = new Set<string>()
  for (const score of data.album_power_scores) {
    const key = `${score.album_name}||${score.artist_name}`
    const firstWeek = albumWeeklyStats.get(key)?.firstWeek ?? ''
    if (
      firstWeek &&
      score.peak_position === 1 &&
      data.weekly_album.some((entry) =>
        entry.album_name === score.album_name &&
        entry.artist_name === score.artist_name &&
        entry.billboard_week === firstWeek &&
        entry.rank === 1
      )
    ) {
      albumDebutNo1Keys.add(key)
    }
  }

  const albums: MergedAlbumRow[] = data.album_power_scores.map((score) => {
    const key = `${score.album_name}||${score.artist_name}`
    const counts = albumTrackCounts.get(key)
    const stats = albumWeeklyStats.get(key)
    return {
      album_name: score.album_name,
      artist_name: score.artist_name,
      cover_url: albumCoverMap.get(key) ?? null,
      weeks_on_chart: score.weeks_on_chart,
      peak_position: score.peak_position,
      weeks_at_peak: stats?.weeksAtPeak ?? 0,
      weeks_top5: stats?.weeksTop5 ?? 0,
      weeks_top10: stats?.weeksTop10 ?? 0,
      total_tracks: counts?.total_tracks ?? 0,
      top1_tracks: counts?.top1 ?? 0,
      top5_tracks: counts?.top5 ?? 0,
      top10_tracks: counts?.top10 ?? 0,
      track_power_sum: score.track_power_sum ?? 0,
      track_power_rank: score.track_power_rank ?? null,
      power_score: score.power_score,
      power_rank: score.power_rank,
      total_plays: score.total_plays ?? stats?.totalPlays ?? 0,
      is_debut_no1: albumDebutNo1Keys.has(key),
    }
  })

  const artistTrackCounts = new Map<string, ArtistTrackCounts>()
  for (const count of data.artist_track_counts) artistTrackCounts.set(count.artist_name, count)

  const artistDebutNo1Keys = new Set<string>()
  for (const score of data.artist_power_scores) {
    const firstWeek = artistWeeklyStats.get(score.artist_name)?.firstWeek ?? ''
    if (
      firstWeek &&
      score.peak_position === 1 &&
      data.weekly_artist.some((entry) =>
        entry.artist_name === score.artist_name &&
        entry.billboard_week === firstWeek &&
        entry.rank === 1
      )
    ) {
      artistDebutNo1Keys.add(score.artist_name)
    }
  }

  const artists: MergedArtistRow[] = data.artist_power_scores.map((score) => {
    const counts = artistTrackCounts.get(score.artist_name)
    const stats = artistWeeklyStats.get(score.artist_name)
    const albumStats = artistAlbumStats.get(score.artist_name)
    return {
      artist_name: score.artist_name,
      cover_url: artistCoverMap.get(score.artist_name) ?? null,
      weeks_on_chart: score.weeks_on_chart,
      peak_position: score.peak_position,
      weeks_at_peak: stats?.weeksAtPeak ?? 0,
      weeks_top5: stats?.weeksTop5 ?? 0,
      weeks_top10: stats?.weeksTop10 ?? 0,
      total_tracks: counts?.total_tracks ?? 0,
      top1_tracks: counts?.top1 ?? 0,
      top5_tracks: counts?.top5 ?? 0,
      top10_tracks: counts?.top10 ?? 0,
      num_no1_albums: counts?.num_no1_albums ?? 0,
      top5_albums: albumStats?.top5Albums ?? 0,
      top10_albums: albumStats?.top10Albums ?? 0,
      track_power_sum: score.track_power_sum ?? 0,
      track_power_rank: score.track_power_rank ?? null,
      album_power_sum: score.album_power_sum ?? 0,
      album_power_rank: score.album_power_rank ?? null,
      power_score: score.power_score,
      power_rank: score.power_rank,
      total_plays: stats?.totalPlays ?? 0,
      is_debut_no1: artistDebutNo1Keys.has(score.artist_name),
    }
  })

  return { tracks, albums, artists }
}

export function getRowsForTab(rows: AllTimeRows, activeTab: EntityTab): AllTimeRow[] {
  if (activeTab === 'tracks') return rows.tracks
  if (activeTab === 'albums') return rows.albums
  return rows.artists
}

export function getColumnsForTab(activeTab: EntityTab): ColumnDef<AllTimeRow>[] {
  if (activeTab === 'tracks') return TRACK_COLUMNS as ColumnDef<AllTimeRow>[]
  if (activeTab === 'albums') return ALBUM_COLUMNS as ColumnDef<AllTimeRow>[]
  return ARTIST_COLUMNS as ColumnDef<AllTimeRow>[]
}

const COLUMN_STORAGE_VERSION = 2
const COLUMN_STORAGE_PREFIX = 'spotify_stats_billboard_all_time_columns'
const VERSION_TWO_ADDITIONS = ['power_rank']

export function recommendedVisibleColumnIds(activeTab: EntityTab): string[] {
  return getColumnsForTab(activeTab)
    .filter((column) => column.fixed || column.defaultVisible)
    .map((column) => column.key)
}

// Compatibility name for callers/tests written before the recommendation became user-editable.
export const defaultVisibleColumnIds = recommendedVisibleColumnIds

export function sanitizeVisibleColumnIds(activeTab: EntityTab, candidate: unknown): string[] {
  const columns = getColumnsForTab(activeTab)
  const allowed = new Set(columns.map((column) => column.key))
  const fixed = columns.filter((column) => column.fixed).map((column) => column.key)
  const raw = Array.isArray(candidate)
    ? candidate
    : candidate && typeof candidate === 'object' && Array.isArray((candidate as { visible?: unknown }).visible)
      ? (candidate as { visible: unknown[] }).visible
      : null
  if (!raw) return recommendedVisibleColumnIds(activeTab)
  return [...new Set([...fixed, ...raw.filter((value): value is string => typeof value === 'string' && allowed.has(value))])]
}

function migrateVisibleColumnIds(activeTab: EntityTab, candidate: unknown, version: number | undefined): string[] {
  const migrated = sanitizeVisibleColumnIds(activeTab, candidate)
  if (version === COLUMN_STORAGE_VERSION) return migrated

  // v2 introduced an independently configurable entity Power Score rank. It is recommended for
  // every chart, so legacy selections receive it once; later v2 choices are preserved exactly.
  return sanitizeVisibleColumnIds(activeTab, [...migrated, ...VERSION_TWO_ADDITIONS])
}

export function loadVisibleColumnIds(activeTab: EntityTab): string[] {
  try {
    const raw = localStorage.getItem(`${COLUMN_STORAGE_PREFIX}:${activeTab}`)
    if (!raw) return recommendedVisibleColumnIds(activeTab)
    const parsed = JSON.parse(raw) as { version?: number; visible?: unknown } | unknown[]
    if (Array.isArray(parsed)) return migrateVisibleColumnIds(activeTab, parsed, undefined)
    if (parsed.version !== COLUMN_STORAGE_VERSION) {
      return migrateVisibleColumnIds(activeTab, parsed.visible, parsed.version)
    }
    return sanitizeVisibleColumnIds(activeTab, parsed.visible)
  } catch {
    return recommendedVisibleColumnIds(activeTab)
  }
}

export function saveVisibleColumnIds(activeTab: EntityTab, visible: string[]): void {
  try {
    localStorage.setItem(
      `${COLUMN_STORAGE_PREFIX}:${activeTab}`,
      JSON.stringify({ version: COLUMN_STORAGE_VERSION, visible: sanitizeVisibleColumnIds(activeTab, visible) }),
    )
  } catch {
    // localStorage can be unavailable in private/restricted contexts.
  }
}

export function visibleColumnsForTab(activeTab: EntityTab, visible: string[]): ColumnDef<AllTimeRow>[] {
  const selected = new Set(sanitizeVisibleColumnIds(activeTab, visible))
  return getColumnsForTab(activeTab).filter((column) => column.fixed || selected.has(column.key))
}

export function normalizeAllTimeSearch(value: string): string {
  return value.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim()
}

export function matchesAllTimeSearch(row: AllTimeRow, activeTab: EntityTab, query: string): boolean {
  const normalized = normalizeAllTimeSearch(query)
  if (!normalized) return true
  const fields = activeTab === 'tracks'
    ? [(row as MergedTrackRow).track_name, (row as MergedTrackRow).artist_name, (row as MergedTrackRow).album_name]
    : activeTab === 'albums'
      ? [(row as MergedAlbumRow).album_name, (row as MergedAlbumRow).artist_name]
      : [(row as MergedArtistRow).artist_name]
  return fields.some((field) =>
    [field, displayName(field)].some((candidate) => normalizeAllTimeSearch(candidate).includes(normalized)),
  )
}

export function applyPeakFilter<T extends { peak_position: number; is_debut_no1: boolean }>(
  rows: T[],
  filter: PeakFilter,
): T[] {
  switch (filter) {
    case 'no1':
      return rows.filter((row) => row.peak_position === 1)
    case 'top5':
      return rows.filter((row) => row.peak_position <= 5)
    case 'top10':
      return rows.filter((row) => row.peak_position <= 10)
    case 'debut_no1':
      return rows.filter((row) => row.is_debut_no1)
    default:
      return rows
  }
}

export function selectAllTimeRows(
  rows: AllTimeRows,
  activeTab: EntityTab,
  peakFilter: PeakFilter,
  sortKey: string,
  sortDir: 'asc' | 'desc',
  searchQuery = '',
): { rows: AllTimeRow[]; columns: ColumnDef<AllTimeRow>[]; total: number } {
  const sourceRows = getRowsForTab(rows, activeTab)
  const columns = getColumnsForTab(activeTab)
  const filtered = applyPeakFilter(sourceRows, peakFilter).filter((row) =>
    matchesAllTimeSearch(row, activeTab, searchQuery),
  )
  const column = columns.find((candidate) => candidate.key === sortKey)

  if (!column) return { rows: filtered, columns, total: sourceRows.length }

  const sorted = [...filtered].sort((a, b) => {
    const valueA = column.getValue(a)
    const valueB = column.getValue(b)
    if (valueA == null && valueB == null) return 0
    if (valueA == null) return 1
    if (valueB == null) return -1
    const comparableA = typeof valueA === 'number' ? valueA : String(valueA)
    const comparableB = typeof valueB === 'number' ? valueB : String(valueB)
    if (comparableA < comparableB) return sortDir === 'asc' ? -1 : 1
    if (comparableA > comparableB) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  return { rows: sorted, columns, total: sourceRows.length }
}

export function getMaxBarValue(rows: AllTimeRow[], activeTab: EntityTab): number {
  if (rows.length === 0) return 1
  if (activeTab === 'tracks') {
    return Math.max(...(rows as MergedTrackRow[]).map((row) => row.total_chart_plays), 1)
  }
  return Math.max(...(rows as (MergedAlbumRow | MergedArtistRow)[]).map((row) => row.total_plays), 1)
}
