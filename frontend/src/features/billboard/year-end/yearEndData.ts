import type {
  BillboardYearEndAlbumRow,
  BillboardYearEndArtistRow,
  BillboardYearEndResponse,
  BillboardYearEndTrackRow,
} from '@/types/billboard'

export type YearEndTab = 'tracks' | 'albums' | 'artists'
export type YearEndRow = BillboardYearEndTrackRow | BillboardYearEndAlbumRow | BillboardYearEndArtistRow
export type YearEndSortKey =
  | 'year_end_rank'
  | 'year_end_score'
  | 'peak_position'
  | 'weeks_on_chart'
  | 'weeks_at_no1'
  | 'weeks_top5'
  | 'weeks_top10'
  | 'chart_plays'
export type YearEndSortDir = 'asc' | 'desc'

export interface YearEndColumn {
  key: YearEndSortKey
  label: string
  width: number
  align: 'left' | 'right' | 'center'
  sortable: boolean
  rankStyle?: boolean
}

export const YEAR_END_PAGE_SIZE = 50

export const YEAR_END_TABS: { key: YearEndTab; label: string }[] = [
  { key: 'tracks', label: '单曲榜' },
  { key: 'albums', label: '专辑榜' },
  { key: 'artists', label: '艺人榜' },
]

export const YEAR_END_COLUMNS: YearEndColumn[] = [
  { key: 'year_end_score', label: '年度积分', width: 108, align: 'right', sortable: true },
  { key: 'peak_position', label: '年度最高', width: 92, align: 'center', sortable: true, rankStyle: true },
  { key: 'weeks_on_chart', label: '年度在榜', width: 92, align: 'right', sortable: true },
  { key: 'weeks_at_no1', label: '年度#1周', width: 96, align: 'right', sortable: true },
  { key: 'weeks_top5', label: '年度Top5', width: 92, align: 'right', sortable: true },
  { key: 'weeks_top10', label: '年度Top10', width: 96, align: 'right', sortable: true },
  { key: 'chart_plays', label: '在榜播放', width: 100, align: 'right', sortable: true },
]

export function formatYearEndNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat('zh-CN').format(Number(value ?? 0))
}

export function rowsForTab(data: BillboardYearEndResponse | null, tab: YearEndTab): YearEndRow[] {
  if (!data) return []
  if (tab === 'tracks') return data.tracks
  if (tab === 'albums') return data.albums
  return data.artists
}

export function entityNameForRow(tab: YearEndTab, row: YearEndRow): string {
  if (tab === 'tracks') return (row as BillboardYearEndTrackRow).track_name
  if (tab === 'albums') return (row as BillboardYearEndAlbumRow).album_name
  return (row as BillboardYearEndArtistRow).artist_name
}

export function subtitleForRow(tab: YearEndTab, row: YearEndRow): string {
  if (tab === 'tracks') return (row as BillboardYearEndTrackRow).artist_name
  if (tab === 'albums') return (row as BillboardYearEndAlbumRow).artist_name
  return `${formatYearEndNumber(row.weeks_on_chart)} 周在榜`
}

export function rowKeyForYearEnd(tab: YearEndTab, row: YearEndRow): string {
  if (tab === 'tracks') return String((row as BillboardYearEndTrackRow).track_id)
  if (tab === 'albums') {
    const album = row as BillboardYearEndAlbumRow
    return `${album.album_name}||${album.artist_name}`
  }
  return (row as BillboardYearEndArtistRow).artist_name
}

export function defaultSortForTab(_tab: YearEndTab): { key: YearEndSortKey; dir: YearEndSortDir } {
  return { key: 'year_end_score', dir: 'desc' }
}

export function nextSortDir(
  currentKey: YearEndSortKey,
  currentDir: YearEndSortDir,
  nextKey: YearEndSortKey,
): YearEndSortDir {
  if (currentKey !== nextKey) return nextKey === 'peak_position' || nextKey === 'year_end_rank' ? 'asc' : 'desc'
  return currentDir === 'desc' ? 'asc' : 'desc'
}

export function sortYearEndRows(
  rows: YearEndRow[],
  sortKey: YearEndSortKey,
  sortDir: YearEndSortDir,
): YearEndRow[] {
  const direction = sortDir === 'desc' ? -1 : 1
  return [...rows].sort((a, b) => {
    const av = Number(a[sortKey] ?? 0)
    const bv = Number(b[sortKey] ?? 0)
    if (av !== bv) return (av > bv ? 1 : -1) * direction
    return a.year_end_rank - b.year_end_rank
  })
}
