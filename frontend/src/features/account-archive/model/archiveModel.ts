import type {
  ArchiveLibraryEntityType,
  ArchiveLibrarySort,
  ArchiveSectionKey,
} from '@/types/accountArchive'

export const ARCHIVE_SECTIONS: Array<{
  key: ArchiveSectionKey
  number: string
  label: string
  shortLabel: string
}> = [
  { key: 'cover', number: '00', label: '档案封面', shortLabel: '封面' },
  { key: 'journey', number: '01', label: '收藏旅程', shortLabel: '旅程' },
  { key: 'cohorts', number: '02', label: '从遇见到收藏', shortLabel: '遇见收藏' },
  { key: 'relationships', number: '03', label: '收藏之后', shortLabel: '收藏之后' },
  { key: 'returns', number: '04', label: '找回音乐', shortLabel: '找回音乐' },
  { key: 'discovery', number: '05', label: '发现路径', shortLabel: '发现路径' },
  { key: 'library', number: '06', label: '收藏库', shortLabel: '收藏库' },
  { key: 'other-media', number: '07', label: '音乐之外', shortLabel: '音乐之外' },
]

export const LIBRARY_LABELS: Record<ArchiveLibraryEntityType, string> = {
  tracks: '歌曲',
  albums: '专辑',
  artists: '艺人',
  playlists: '歌单',
}

export const LIBRARY_SORTS: Record<
  ArchiveLibraryEntityType,
  Array<{ value: ArchiveLibrarySort; label: string }>
> = {
  tracks: [
    { value: 'recent', label: '最近收藏' },
    { value: 'oldest', label: '最早收藏' },
    { value: 'name', label: '歌曲名称' },
    { value: 'artist', label: '艺人名称' },
  ],
  albums: [
    { value: 'name', label: '专辑名称' },
    { value: 'artist', label: '艺人名称' },
  ],
  artists: [{ value: 'name', label: '艺人名称' }],
  playlists: [
    { value: 'name', label: '歌单名称' },
    { value: 'recent', label: '最近修改' },
    { value: 'tracks', label: '曲目数量' },
  ],
}

export const DEFAULT_LIBRARY_SORT: Record<ArchiveLibraryEntityType, ArchiveLibrarySort> = {
  tracks: 'recent',
  albums: 'name',
  artists: 'name',
  playlists: 'name',
}

export function formatArchiveNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

export function formatArchiveHours(ms: number, digits = 1): string {
  return `${(ms / 3_600_000).toFixed(digits)} 小时`
}

export function formatArchiveDate(value: string | null): string {
  if (!value) return '暂无日期'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'Asia/Shanghai',
  }).format(date)
}

export function formatArchiveMonth(value: string | null): string {
  if (!value) return '暂无记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 7)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    timeZone: 'Asia/Shanghai',
  }).format(date)
}

export function isArchiveSection(value: string | null): value is ArchiveSectionKey {
  return ARCHIVE_SECTIONS.some((section) => section.key === value)
}

export function isLibraryEntity(value: string | null): value is ArchiveLibraryEntityType {
  return value === 'tracks' || value === 'albums' || value === 'artists' || value === 'playlists'
}

export function librarySortFor(
  entityType: ArchiveLibraryEntityType,
  value: string | null,
): ArchiveLibrarySort {
  const allowed = LIBRARY_SORTS[entityType].map((item) => item.value)
  return value && allowed.includes(value as ArchiveLibrarySort)
    ? (value as ArchiveLibrarySort)
    : DEFAULT_LIBRARY_SORT[entityType]
}
