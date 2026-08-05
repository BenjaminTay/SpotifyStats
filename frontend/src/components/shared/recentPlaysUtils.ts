import type { RecentPlayRow } from '@/types/analysis'

export function recentPlayRowKey(row: RecentPlayRow, index: number): string {
  return [
    row.play_id,
    row.ts,
    row.track_id ?? 'trackless',
    row.artist_name,
    index,
  ].join(':')
}
