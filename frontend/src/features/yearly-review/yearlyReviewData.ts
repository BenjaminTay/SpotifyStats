import type { AnalysisFilters } from '@/types/analysis'
import type { YearlyEntityRef, YearlyMetric, YearlyReviewStatus } from '@/types/yearly-review-v2'
import { displayName } from '@/lib/chinese'

export type YearlyReviewQueryParams = Record<string, string | number | boolean>

export function buildYearlyReviewParams(filters: AnalysisFilters): YearlyReviewQueryParams {
  const params: YearlyReviewQueryParams = {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
    merge_level: filters.merge_level ?? 2,
    include_compilations: filters.include_compilations ?? false,
    bb_top_n: filters.bb_top_n ?? 30,
    bb_album_top_n: filters.bb_album_top_n ?? 20,
    bb_artist_top_n: filters.bb_artist_top_n ?? 20,
    bb_week_start_dow: filters.bb_week_start_dow ?? 4,
    bb_week_start_hour: filters.bb_week_start_hour ?? 0,
  }
  if (filters.max_merge_gap_minutes != null) {
    params.max_merge_gap_minutes = filters.max_merge_gap_minutes
  }
  return params
}

export function yearlyReviewFilterKey(params: YearlyReviewQueryParams): string {
  return Object.entries(params)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}:${String(value)}`)
    .join('|')
}

export const STATUS_COPY: Record<YearlyReviewStatus, { label: string }> = {
  complete: { label: '完整年度' },
  year_to_date: { label: '进行中' },
  observed_range: { label: '年度回顾' },
  insufficient: { label: '年度回顾' },
  empty: { label: '暂无记录' },
}

export const ENTITY_LABELS = { track: '歌曲', album: '专辑', artist: '艺人' } as const

export function displayYearlyText(value: string): string {
  return displayName(value)
}

export function formatMetric(metric: YearlyMetric): string {
  const value = typeof metric.value === 'number'
    ? metric.value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
    : metric.value
  return `${value}${metric.unit ?? ''}`
}

export type MetricComparison = {
  direction: 'up' | 'down' | 'flat'
  text: string
  ariaLabel: string
}

export function formatMetricComparison(metric: YearlyMetric): MetricComparison | null {
  if (typeof metric.value !== 'number' || typeof metric.comparison_value !== 'number') return null
  const difference = metric.value - metric.comparison_value
  const comparisonLabel = metric.comparison_label ?? '比去年'
  if (difference === 0) {
    return { direction: 'flat', text: '持平', ariaLabel: `${comparisonLabel}持平` }
  }
  if (metric.comparison_value === 0) return null
  const percentage = Math.abs(difference / metric.comparison_value * 100).toFixed(1)
  const direction = difference > 0 ? 'up' : 'down'
  const changeLabel = difference > 0 ? '高' : '低'
  return {
    direction,
    text: `${percentage}%`,
    ariaLabel: `${comparisonLabel}${changeLabel} ${percentage}%`,
  }
}

export function entitySubtitle(entity: YearlyEntityRef | null | undefined): string | null {
  if (!entity) return null
  return entity.artist_name ? displayName(entity.artist_name) : ENTITY_LABELS[entity.entity_type]
}

export function numberValue(row: Record<string, unknown>, key: string): number {
  const value = Number(row[key] ?? 0)
  return Number.isFinite(value) ? value : 0
}

export function stringValue(row: Record<string, unknown>, key: string): string {
  const value = row[key]
  return typeof value === 'string' ? value : ''
}
