import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { format, startOfWeek, endOfWeek, startOfMonth, endOfMonth, startOfYear, endOfYear, parseISO } from 'date-fns'
import type { AnalysisMetric, AnalysisPeriod, LeaderboardEntity } from '@/types/analysis'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const PERIOD_VALUES: AnalysisPeriod[] = [
  'lifetime', 'last_6_months', 'last_4_weeks', 'year', 'month', 'week', 'day', 'custom',
]

function isPeriod(value: string | null): value is AnalysisPeriod {
  return PERIOD_VALUES.includes(value as AnalysisPeriod)
}

function isMetric(value: string | null): value is AnalysisMetric {
  return value === 'plays' || value === 'hours'
}

function isEntity(value: string | null): value is LeaderboardEntity {
  return value === 'track' || value === 'album' || value === 'artist'
}

function todayAnchor(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

function parsePeriodAnchor(period: AnalysisPeriod, value: string | null): Date {
  const fallback = todayAnchor()
  if (!value) return fallback
  try {
    if (period === 'year') {
      const y = parseInt(value, 10)
      return isNaN(y) ? fallback : new Date(y, 0, 1)
    }
    if (period === 'month') {
      const [y, m] = value.split('-').map(Number)
      return isNaN(y) || isNaN(m) ? fallback : new Date(y, m - 1, 1)
    }
    if (period === 'week' || period === 'day') {
      const d = parseISO(value)
      return isNaN(d.getTime()) ? fallback : d
    }
  } catch {
    // fall through
  }
  return fallback
}

function computeNavigableDates(period: AnalysisPeriod, anchor: Date): { start_date: string; end_date: string } {
  const fmt = (d: Date) => format(d, 'yyyy-MM-dd')
  if (period === 'year') {
    return { start_date: fmt(startOfYear(anchor)), end_date: fmt(endOfYear(anchor)) }
  }
  if (period === 'month') {
    return { start_date: fmt(startOfMonth(anchor)), end_date: fmt(endOfMonth(anchor)) }
  }
  if (period === 'week') {
    return { start_date: fmt(startOfWeek(anchor, { weekStartsOn: 1 })), end_date: fmt(endOfWeek(anchor, { weekStartsOn: 1 })) }
  }
  // day
  return { start_date: fmt(anchor), end_date: fmt(anchor) }
}

export function useAnalysisQueryState(defaultEntity: LeaderboardEntity = 'track') {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawPeriod = searchParams.get('period')
  const rawMetric = searchParams.get('metric')
  const rawEntity = searchParams.get('entity')
  const rawPeriodValue = searchParams.get('period_value')
  const period = isPeriod(rawPeriod) ? rawPeriod : 'lifetime'
  const metric = isMetric(rawMetric) ? rawMetric : 'plays'
  const entity = isEntity(rawEntity) ? rawEntity : defaultEntity
  const startDate = searchParams.get('start') || ''
  const endDate = searchParams.get('end') || ''

  const setQuery = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (value) next.set(key, value)
      else next.delete(key)
    })
    setSearchParams(next, { replace: true })
  }

  const apiParams = useMemo(() => {
    // 首页等有明确数据截止日的入口仍显示“最近4周”，但沿用入口给出的同一 28 天窗口。
    if (period === 'last_4_weeks' && startDate && endDate) {
      return { period: 'custom' as AnalysisPeriod, start_date: startDate, end_date: endDate }
    }
    // Named periods: send period directly to backend
    if (period === 'lifetime' || period === 'last_6_months' || period === 'last_4_weeks') {
      return { period }
    }
    // Navigable periods: compute date range and send as custom
    if (period === 'year' || period === 'month' || period === 'week' || period === 'day') {
      const anchor = parsePeriodAnchor(period, rawPeriodValue)
      return {
        period: 'custom' as AnalysisPeriod,
        ...computeNavigableDates(period, anchor),
      }
    }
    // Custom period: send user-provided dates
    return {
      period: 'custom' as AnalysisPeriod,
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
    }
  }, [period, rawPeriodValue, startDate, endDate])

  return { period, metric, entity, periodValue: rawPeriodValue, startDate, endDate, setQuery, apiParams }
}

export function MetricToggle({
  metric,
  onChange,
}: {
  metric: AnalysisMetric
  onChange: (metric: AnalysisMetric) => void
}) {
  return (
    <div className="flex gap-1 rounded-[9px] border border-border bg-muted/30 p-1">
      <Button type="button" size="sm" variant={metric === 'plays' ? 'default' : 'ghost'} onClick={() => onChange('plays')} className="h-8 rounded-[7px] px-3">
        播放次数
      </Button>
      <Button type="button" size="sm" variant={metric === 'hours' ? 'default' : 'ghost'} onClick={() => onChange('hours')} className="h-8 rounded-[7px] px-3">
        播放时长
      </Button>
    </div>
  )
}

export function EntityTabs({
  entity,
  onChange,
}: {
  entity: LeaderboardEntity
  onChange: (entity: LeaderboardEntity) => void
}) {
  return (
    <Tabs value={entity} onValueChange={(value) => onChange(value as LeaderboardEntity)}>
      <TabsList className="rounded-[9px]">
        <TabsTrigger value="track">歌曲</TabsTrigger>
        <TabsTrigger value="album">专辑</TabsTrigger>
        <TabsTrigger value="artist">艺人</TabsTrigger>
      </TabsList>
    </Tabs>
  )
}
