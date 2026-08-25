import { billboardDetailLink } from '@/lib/navigation'
import type { RankChange } from '@/components/shared/ChangeCell'
import type {
  WeeklyAlbumEntry,
  WeeklyArtistEntry,
  WeeklyTrackEntry,
} from '@/types/billboard'

export type BillboardWeeklyTab = 'tracks' | 'albums' | 'artists'
export type BillboardWeeklyEntry = WeeklyTrackEntry | WeeklyAlbumEntry | WeeklyArtistEntry

export interface BillboardWeeklySummary {
  maxPlays: number
  totalPlays: number
  newCount: number
  reCount: number
  total: number
}

export const BILLBOARD_WEEKLY_TABS: { key: BillboardWeeklyTab; label: string }[] = [
  { key: 'tracks', label: '单曲榜' },
  { key: 'albums', label: '专辑榜' },
  { key: 'artists', label: '艺人榜' },
]

export function isBillboardWeeklyTab(value: string | null): value is BillboardWeeklyTab {
  return value === 'tracks' || value === 'albums' || value === 'artists'
}

export function weeklyChartHref(week: string, tab: BillboardWeeklyTab): string {
  return `/billboard?week=${encodeURIComponent(week)}&tab=${tab}`
}

export function formatWeekLabel(iso: string): string {
  if (!iso) return ''
  const date = new Date(`${iso}T00:00:00`)
  const yearStart = new Date(date.getFullYear(), 0, 1)
  const elapsedDays = (date.getTime() - yearStart.getTime()) / 86400000
  const weekNumber = Math.ceil((elapsedDays + yearStart.getDay() + 1) / 7)
  return `Week ${weekNumber}, ${date.getFullYear()}`
}

export function formatDateRange(iso: string): string {
  if (!iso) return ''
  const formatDate = (date: Date) =>
    `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
  const start = new Date(`${iso}T00:00:00`)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  return `${formatDate(start)} — ${formatDate(end)}`
}

export function formatBillboardNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function entryIdentity(entry: BillboardWeeklyEntry, tab: BillboardWeeklyTab): string | number {
  if (tab === 'tracks') return (entry as WeeklyTrackEntry).track_id
  if (tab === 'albums') {
    const album = entry as WeeklyAlbumEntry
    return `${album.album_name}\u0000${album.artist_name}`
  }
  return (entry as WeeklyArtistEntry).artist_name
}

export function computeWeeklyRankChange(
  entry: BillboardWeeklyEntry,
  previousEntries: BillboardWeeklyEntry[],
  historicalEntries: BillboardWeeklyEntry[],
  tab: BillboardWeeklyTab,
): RankChange {
  const identity = entryIdentity(entry, tab)
  const previous = previousEntries.find((candidate) => entryIdentity(candidate, tab) === identity)
  if (previous) {
    const delta = previous.rank - entry.rank
    if (delta > 0) return { type: 'up', delta }
    if (delta < 0) return { type: 'down', delta: Math.abs(delta) }
    return { type: 'same' }
  }
  return historicalEntries.some((candidate) => entryIdentity(candidate, tab) === identity)
    ? { type: 're' }
    : { type: 'new' }
}

export function buildWeeklySummary(
  entries: BillboardWeeklyEntry[],
  previousEntries: BillboardWeeklyEntry[],
  historicalEntries: BillboardWeeklyEntry[],
  tab: BillboardWeeklyTab,
): BillboardWeeklySummary {
  let maxPlays = 0
  let totalPlays = 0
  let newCount = 0
  let reCount = 0

  entries.forEach((entry) => {
    maxPlays = Math.max(maxPlays, entry.play_count)
    totalPlays += entry.play_count
    const change = computeWeeklyRankChange(entry, previousEntries, historicalEntries, tab)
    if (change.type === 'new') newCount += 1
    if (change.type === 're') reCount += 1
  })

  return { maxPlays, totalPlays, newCount, reCount, total: entries.length }
}

export function weeklyEntryName(entry: BillboardWeeklyEntry, tab: BillboardWeeklyTab): string {
  if (tab === 'tracks') return (entry as WeeklyTrackEntry).track_name
  if (tab === 'albums') return (entry as WeeklyAlbumEntry).album_name
  return (entry as WeeklyArtistEntry).artist_name
}

export function weeklyEntrySubtitle(entry: BillboardWeeklyEntry, tab: BillboardWeeklyTab): string {
  if (tab === 'artists') return `${(entry as WeeklyArtistEntry).tracks_count} 首入榜曲目`
  return (entry as WeeklyTrackEntry | WeeklyAlbumEntry).artist_name
}

export function weeklyEntryDetailLink(entry: BillboardWeeklyEntry, tab: BillboardWeeklyTab): string {
  if (tab === 'tracks') {
    return billboardDetailLink(`/music/tracks/${(entry as WeeklyTrackEntry).track_id}`)
  }
  if (tab === 'albums') {
    const album = entry as WeeklyAlbumEntry
    return billboardDetailLink(
      `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`,
    )
  }
  return billboardDetailLink(
    `/music/artists/${encodeURIComponent((entry as WeeklyArtistEntry).artist_name)}`,
  )
}

export function weeklyChangeLabel(change: RankChange): string {
  if (change.type === 'up') return `↑ ${change.delta}`
  if (change.type === 'down') return `↓ ${change.delta}`
  if (change.type === 'new') return 'NEW'
  if (change.type === 're') return 'RE'
  return '—'
}

export function weeklyEntityLabel(tab: BillboardWeeklyTab): string {
  if (tab === 'tracks') return '首曲目'
  if (tab === 'albums') return '张专辑'
  return '组艺人'
}
