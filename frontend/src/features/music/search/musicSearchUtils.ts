import type { MusicSearchKind, MusicSearchResponse } from '@/types/music-search'

export const MUSIC_SEARCH_KIND_LABELS: Record<MusicSearchKind, string> = {
  track: '单曲',
  album: '专辑',
  artist: '艺人',
}

export const MUSIC_SEARCH_KIND_PLURAL_LABELS: Record<MusicSearchKind, string> = {
  track: '单曲结果',
  album: '专辑结果',
  artist: '艺人结果',
}

export function trimSearchQuery(query: string): string {
  return query.trim()
}

export function hasSearchQuery(query: string): boolean {
  return trimSearchQuery(query).length > 0
}

export function groupedSearchTotal(data: MusicSearchResponse | null): number {
  if (!data) return 0
  return data.tracks.length + data.albums.length + data.artists.length
}

export function fullSearchHref(query: string): string {
  const trimmed = trimSearchQuery(query)
  return trimmed ? `/music/search?q=${encodeURIComponent(trimmed)}` : '/music/search'
}

export function formatPlayEvents(count: number): string {
  return `${count.toLocaleString('zh-CN')} 次播放`
}
