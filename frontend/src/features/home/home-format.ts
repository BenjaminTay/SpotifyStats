import type { HomePeriod } from '@/types/home'

export function formatHomeNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

export function formatHomeHours(value: number): string {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: value < 10 ? 1 : 0 }).format(value)
}

export function formatHomeDate(value: string | null, compact = false): string {
  if (!value) return '暂无记录'
  const [year, month, day] = value.slice(0, 10).split('-')
  return compact ? `${month}.${day}` : `${year}.${month}.${day}`
}

export function homeRecentAnalysisRoute(period: HomePeriod | null | undefined): string {
  const params = new URLSearchParams({ period: 'last_4_weeks' })
  if (period) {
    params.set('start', period.start_date)
    params.set('end', period.end_date)
  }
  return `/analysis/stats?${params.toString()}`
}
