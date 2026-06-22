import type {
  AlbumTrackCounts,
  ArtistTrackCounts,
  BillboardAllTimeResponse,
  PowerScoreEntry,
  TrackSummary,
} from '@/types/billboard'

export type EntityTab = 'tracks' | 'albums' | 'artists'
export type PeakFilter = 'all' | 'no1' | 'top5' | 'top10' | 'debut_no1'

export interface MergedTrackRow {
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
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
  power_score: number
  power_rank: number
  total_plays: number
  is_debut_no1: boolean
}

export type AllTimeRow = MergedTrackRow | MergedAlbumRow | MergedArtistRow

export interface AllTimeRows {
  tracks: MergedTrackRow[]
  albums: MergedAlbumRow[]
  artists: MergedArtistRow[]
}

export interface ColumnDef<T> {
  key: string
  label: string
  align: 'left' | 'right' | 'center'
  getValue: (row: T) => number | string
  format: (row: T) => string
  sortable: boolean
  rankStyle?: boolean
}

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
  { value: 'no1', label: '#1 冠军' },
  { value: 'top5', label: 'Top 5' },
  { value: 'top10', label: 'Top 10' },
  { value: 'debut_no1', label: '空冠' },
]

export const TABS: { key: EntityTab; label: string }[] = [
  { key: 'tracks', label: '歌曲' },
  { key: 'albums', label: '专辑' },
  { key: 'artists', label: '艺人' },
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

const TRACK_COLUMNS: ColumnDef<MergedTrackRow>[] = [
  { key: 'peak_position', label: '排名峰值', align: 'right', getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true, rankStyle: true },
  { key: 'weeks_at_peak', label: '峰值周数', align: 'right', getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true },
  { key: 'weeks_on_chart', label: '在榜周数', align: 'right', getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true },
  { key: 'weeks_top5', label: 'Top5周数', align: 'right', getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true },
  { key: 'weeks_top10', label: 'Top10周数', align: 'right', getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true },
  { key: 'power_score', label: '走势评分', align: 'right', getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true },
  { key: 'power_rank', label: '走势排名', align: 'right', getValue: (r) => r.power_rank, format: (r) => String(r.power_rank), sortable: true, rankStyle: true },
  { key: 'total_chart_plays', label: '总播放次数', align: 'right', getValue: (r) => r.total_chart_plays, format: (r) => formatNumber(r.total_chart_plays), sortable: true },
]

const ALBUM_COLUMNS: ColumnDef<MergedAlbumRow>[] = [
  { key: 'peak_position', label: '排名峰值', align: 'right', getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true, rankStyle: true },
  { key: 'weeks_at_peak', label: '峰值周数', align: 'right', getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true },
  { key: 'weeks_on_chart', label: '在榜周数', align: 'right', getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true },
  { key: 'weeks_top5', label: 'Top5周数', align: 'right', getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true },
  { key: 'weeks_top10', label: 'Top10周数', align: 'right', getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true },
  { key: 'total_tracks', label: '入榜曲数', align: 'right', getValue: (r) => r.total_tracks, format: (r) => formatNumber(r.total_tracks), sortable: true },
  { key: 'top1_tracks', label: '冠军歌曲数', align: 'right', getValue: (r) => r.top1_tracks, format: (r) => formatNumber(r.top1_tracks), sortable: true },
  { key: 'top5_tracks', label: 'Top5曲数', align: 'right', getValue: (r) => r.top5_tracks, format: (r) => formatNumber(r.top5_tracks), sortable: true },
  { key: 'top10_tracks', label: 'Top10曲数', align: 'right', getValue: (r) => r.top10_tracks, format: (r) => formatNumber(r.top10_tracks), sortable: true },
  { key: 'power_score', label: '走势评分', align: 'right', getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true },
  { key: 'power_rank', label: '走势排名', align: 'right', getValue: (r) => r.power_rank, format: (r) => String(r.power_rank), sortable: true, rankStyle: true },
  { key: 'total_plays', label: '总播放次数', align: 'right', getValue: (r) => r.total_plays, format: (r) => formatNumber(r.total_plays), sortable: true },
]

const ARTIST_COLUMNS: ColumnDef<MergedArtistRow>[] = [
  { key: 'peak_position', label: '排名峰值', align: 'right', getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true, rankStyle: true },
  { key: 'weeks_at_peak', label: '峰值周数', align: 'right', getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true },
  { key: 'weeks_on_chart', label: '在榜周数', align: 'right', getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true },
  { key: 'weeks_top5', label: 'Top5周数', align: 'right', getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true },
  { key: 'weeks_top10', label: 'Top10周数', align: 'right', getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true },
  { key: 'total_tracks', label: '入榜曲数', align: 'right', getValue: (r) => r.total_tracks, format: (r) => formatNumber(r.total_tracks), sortable: true },
  { key: 'top1_tracks', label: '冠军歌曲数', align: 'right', getValue: (r) => r.top1_tracks, format: (r) => formatNumber(r.top1_tracks), sortable: true },
  { key: 'top5_tracks', label: 'Top5曲数', align: 'right', getValue: (r) => r.top5_tracks, format: (r) => formatNumber(r.top5_tracks), sortable: true },
  { key: 'top10_tracks', label: 'Top10曲数', align: 'right', getValue: (r) => r.top10_tracks, format: (r) => formatNumber(r.top10_tracks), sortable: true },
  { key: 'num_no1_albums', label: '#1专辑数', align: 'right', getValue: (r) => r.num_no1_albums, format: (r) => formatNumber(r.num_no1_albums), sortable: true },
  { key: 'top5_albums', label: 'Top5专辑数', align: 'right', getValue: (r) => r.top5_albums, format: (r) => formatNumber(r.top5_albums), sortable: true },
  { key: 'top10_albums', label: 'Top10专辑数', align: 'right', getValue: (r) => r.top10_albums, format: (r) => formatNumber(r.top10_albums), sortable: true },
  { key: 'power_score', label: '走势评分', align: 'right', getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true },
  { key: 'power_rank', label: '走势排名', align: 'right', getValue: (r) => r.power_rank, format: (r) => String(r.power_rank), sortable: true, rankStyle: true },
  { key: 'total_plays', label: '总播放次数', align: 'right', getValue: (r) => r.total_plays, format: (r) => formatNumber(r.total_plays), sortable: true },
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
      power_score: score.power_score,
      power_rank: score.power_rank,
      total_plays: (score as any).total_plays ?? stats?.totalPlays ?? 0,
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
): { rows: AllTimeRow[]; columns: ColumnDef<AllTimeRow>[]; total: number } {
  const sourceRows = getRowsForTab(rows, activeTab)
  const columns = getColumnsForTab(activeTab)
  const filtered = applyPeakFilter(sourceRows, peakFilter)
  const column = columns.find((candidate) => candidate.key === sortKey)

  if (!column) return { rows: filtered, columns, total: sourceRows.length }

  const sorted = [...filtered].sort((a, b) => {
    const valueA = column.getValue(a)
    const valueB = column.getValue(b)
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
