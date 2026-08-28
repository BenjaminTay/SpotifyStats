import type {
  MusicSearchCandidateFreshness,
  MusicSearchCandidateResponse,
  MusicSearchCandidateStatus,
  MusicSearchContextResponse,
  MusicSearchKind,
  MusicSearchStatisticsFreshness,
  MusicSearchStatisticsStatus,
} from '@/types/music-search'

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

export function musicSearchCandidateStatus(
  data: MusicSearchCandidateResponse,
): MusicSearchCandidateStatus {
  if (data.candidate_status) return data.candidate_status
  if (data.snapshot_status === 'ready' || data.total > 0) return 'ready'
  return 'unavailable'
}

export function musicSearchCandidateFreshness(
  data: MusicSearchCandidateResponse,
): MusicSearchCandidateFreshness {
  if (data.candidate_freshness) return data.candidate_freshness
  return data.snapshot_status === 'ready' ? 'current' : 'last_known_good'
}

export function musicSearchStatisticsStatus(
  data: MusicSearchCandidateResponse | MusicSearchContextResponse,
): MusicSearchStatisticsStatus {
  return data.statistics_status ?? data.snapshot_status
}

export function musicSearchStatisticsFreshness(
  data: MusicSearchCandidateResponse | MusicSearchContextResponse,
): MusicSearchStatisticsFreshness {
  if (data.statistics_freshness) return data.statistics_freshness
  return musicSearchStatisticsStatus(data) === 'ready' ? 'current' : 'unavailable'
}

export function musicSearchServedFilterFingerprint(
  data: MusicSearchCandidateResponse | MusicSearchContextResponse | null | undefined,
): string | null {
  return data?.served_filter_fingerprint ?? data?.filter_fingerprint ?? null
}
