import type { MusicSearchKind } from '@/types/music-search'

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

export function fullSearchHref(
  query: string,
  kind?: MusicSearchKind,
  page = 1,
): string {
  const trimmed = trimSearchQuery(query)
  const params = new URLSearchParams()
  if (trimmed) params.set('q', trimmed)
  if (kind) params.set('kind', kind)
  if (kind && page > 1) params.set('page', String(page))
  const search = params.toString()
  return search ? `/music/search?${search}` : '/music/search'
}

export function formatPlayEvents(count: number): string {
  return `${count.toLocaleString('zh-CN')} 次播放`
}

export function musicSearchOptionId(entityKey: string): string {
  return `music-search-option-${entityKey.replace(/[^a-z0-9_-]/gi, '-')}`
}
