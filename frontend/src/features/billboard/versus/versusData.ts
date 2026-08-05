import type { VersusRankPoint } from '@/types/billboard'

export type VersusKind = 'track' | 'album' | 'artist'

export const MAX_QUEUE_SIZE = 4

export const KIND_TABS: { key: VersusKind; label: string }[] = [
  { key: 'track', label: '单曲' },
  { key: 'album', label: '专辑' },
  { key: 'artist', label: '艺人' },
]

/** Color palette for the 2–4 entities supported by the comparison flow. */
export const ENTITY_COLORS = ['#D4836F', '#4A9C8C', '#7B9EC7', '#D4A857', '#9B7EC4']

export type MetricGroup = '榜单成绩' | '单曲成绩' | '专辑成绩' | '其他'

export interface VersusMetricDef {
  key: string
  label: string
  group: MetricGroup
  higherIsBetter: boolean
  format: (v: unknown, entity?: Record<string, unknown>) => string
  description?: string
  /** Only show for specific kind(s), undefined = all */
  only?: VersusKind | VersusKind[]
}

export function formatInt(v: unknown): string {
  if (v === null || v === undefined) return '—'
  return String(v)
}

export function formatRank(v: unknown): string {
  if (v === null || v === undefined) return '—'
  return `#${v}`
}

export const METRIC_GROUPS: MetricGroup[] = ['榜单成绩', '单曲成绩', '专辑成绩', '其他']

function formatScoreRank(v: unknown, entity?: Record<string, unknown>, rankKey?: string): string {
  if (v === null || v === undefined) return '—'
  if (entity && rankKey) {
    const rank = entity[rankKey]
    return rank != null ? `${v} (#${rank})` : String(v)
  }
  return String(v)
}

export const METRIC_DEFS: VersusMetricDef[] = [
  // ── 榜单成绩 ──
  { key: 'power_score', label: '走势点数', group: '榜单成绩', higherIsBetter: true, format: (v, e) => formatScoreRank(v, e, 'power_rank'), description: '括号内名次是本次统计上下文中同类实体按走势点数计算的派生排名，详情页没有同名原始字段。' },
  { key: 'peak_position', label: '入榜峰值', group: '榜单成绩', higherIsBetter: false, format: formatRank },
  { key: 'weeks_on_chart', label: '在榜周数', group: '榜单成绩', higherIsBetter: true, format: formatInt },
  { key: 'no1_weeks', label: '夺冠周数', group: '榜单成绩', higherIsBetter: true, format: formatInt },
  { key: 'top5_weeks', label: '前 5 周数', group: '榜单成绩', higherIsBetter: true, format: formatInt, only: 'track' },
  { key: 'total_chart_plays', label: '总上榜播放', group: '榜单成绩', higherIsBetter: true, format: formatInt, only: 'track', description: '仅累计进入个人榜单的周内播放，不等于全部有效播放。' },
  // ── 单曲成绩 ──
  { key: 'track_power_sum', label: '歌曲总走势点数', group: '单曲成绩', higherIsBetter: true, format: (v, e) => formatScoreRank(v, e, 'track_power_rank'), only: ['album', 'artist'], description: '汇总详情页同一归属口径下各入榜歌曲的走势点数；括号内为同类实体派生排名。' },
  { key: 'track_peak_position', label: '单曲排名峰值', group: '单曲成绩', higherIsBetter: false, format: formatRank, only: ['album', 'artist'] },
  { key: 'num_no1_tracks', label: '冠单数量', group: '单曲成绩', higherIsBetter: true, format: formatInt, only: ['album', 'artist'] },
  { key: 'total_no1_track_weeks', label: '冠军单曲周数', group: '单曲成绩', higherIsBetter: true, format: formatInt, only: ['album', 'artist'] },
  { key: 'num_tracks', label: '入榜曲目数', group: '单曲成绩', higherIsBetter: true, format: formatInt, only: ['album', 'artist'] },
  { key: 'total_track_weeks', label: '歌曲入榜总周数', group: '单曲成绩', higherIsBetter: true, format: formatInt, only: ['album', 'artist'] },
  // ── 专辑成绩 ──
  { key: 'album_power_sum', label: '专辑总走势点数', group: '专辑成绩', higherIsBetter: true, format: (v, e) => formatScoreRank(v, e, 'album_power_rank'), only: 'artist', description: '汇总详情页同一归属口径下各入榜专辑的走势点数；括号内为同类实体派生排名。' },
  { key: 'album_peak_position', label: '专辑排名峰值', group: '专辑成绩', higherIsBetter: false, format: formatRank, only: 'artist' },
  { key: 'num_no1_albums', label: '冠专数量', group: '专辑成绩', higherIsBetter: true, format: formatInt, only: 'artist' },
  { key: 'total_no1_album_weeks', label: '冠军专辑周数', group: '专辑成绩', higherIsBetter: true, format: formatInt, only: 'artist' },
  { key: 'num_albums', label: '入榜专辑数', group: '专辑成绩', higherIsBetter: true, format: formatInt, only: 'artist' },
  { key: 'total_album_weeks', label: '专辑入榜总周数', group: '专辑成绩', higherIsBetter: true, format: formatInt, only: 'artist' },
]

/** Find the best (lowest or highest) value index among row values, or -1 if no winner */
/** Returns all winning indices. Empty = no valid data, [idx] = clear winner, [a,b,…] = tie. */
export function bestIndices(values: (unknown)[], higherIsBetter: boolean): number[] {
  const nums: { idx: number; val: number }[] = []
  for (let i = 0; i < values.length; i++) {
    const v = values[i]
    if (v !== null && v !== undefined) {
      const n = Number(v)
      if (!isNaN(n)) nums.push({ idx: i, val: n })
    }
  }
  if (nums.length === 0) return []
  if (nums.length === 1) return [nums[0].idx]
  nums.sort((a, b) => higherIsBetter ? b.val - a.val : a.val - b.val)
  const bestVal = nums[0].val
  return nums.filter((n) => Math.abs(n.val - bestVal) < 1e-9).map((n) => n.idx)
}

export function toChartData(points: VersusRankPoint[]): { week: string; rank: number | null }[] {
  return points.map((p) => ({ week: p.week, rank: p.rank }))
}
