import type { AnalysisChartRow } from '@/types/analysis'
import { displayName } from '@/lib/chinese'

export const PERSONAL_RANK_PAGE_SIZE = 20

export function matchesPersonalRankSearch(
  row: AnalysisChartRow,
  entity: 'track' | 'album' | 'artist',
  query: string,
): boolean {
  const normalized = query.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim()
  if (!normalized) return true
  const fields = entity === 'track'
    ? [row.track_name, row.artist_name, ...(row.artist_names ?? []), row.album_name]
    : entity === 'album'
      ? [row.album_name, row.artist_name]
      : [row.artist_name]
  return fields.some((field) => field && [field, displayName(field)].some((candidate) =>
    candidate.normalize('NFKC').toLocaleLowerCase().includes(normalized),
  ))
}
