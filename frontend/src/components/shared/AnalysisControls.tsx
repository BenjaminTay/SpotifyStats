import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { AnalysisMetric, AnalysisPeriod, LeaderboardEntity } from '@/types/analysis'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

export const PERIOD_OPTIONS: Array<{ value: AnalysisPeriod; label: string }> = [
  { value: 'lifetime', label: 'Lifetime' },
  { value: 'today', label: '今天' },
  { value: 'this_week', label: '本周' },
  { value: 'this_year', label: '今年' },
  { value: 'last_4_weeks', label: '最近 4 周' },
  { value: 'last_6_months', label: '最近 6 月' },
  { value: 'custom', label: '自定义' },
]

function isPeriod(value: string | null): value is AnalysisPeriod {
  return PERIOD_OPTIONS.some((item) => item.value === value)
}

function isMetric(value: string | null): value is AnalysisMetric {
  return value === 'plays' || value === 'hours'
}

function isEntity(value: string | null): value is LeaderboardEntity {
  return value === 'track' || value === 'album' || value === 'artist'
}

export function useAnalysisQueryState(defaultEntity: LeaderboardEntity = 'track') {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawPeriod = searchParams.get('period')
  const rawMetric = searchParams.get('metric')
  const rawEntity = searchParams.get('entity')
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

  const apiParams = useMemo(() => ({
    period,
    ...(period === 'custom' && startDate ? { start_date: startDate } : {}),
    ...(period === 'custom' && endDate ? { end_date: endDate } : {}),
  }), [endDate, period, startDate])

  return { period, metric, entity, startDate, endDate, setQuery, apiParams }
}

export function AnalysisPeriodControl({
  period,
  startDate,
  endDate,
  onChange,
  className,
}: {
  period: AnalysisPeriod
  startDate: string
  endDate: string
  onChange: (patch: Record<string, string | undefined>) => void
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-end gap-3', className)}>
      <label className="grid gap-1.5">
        <span className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">范围</span>
        <Select value={period ?? 'lifetime'} onValueChange={(value) => onChange({ period: value ?? 'lifetime', ...(value !== 'custom' ? { start: undefined, end: undefined } : {}) })}>
          <SelectTrigger className="h-10 w-[156px] rounded-[8px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PERIOD_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </label>
      {period === 'custom' && (
        <>
          <label className="grid gap-1.5">
            <span className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">开始</span>
            <input
              type="date"
              value={startDate}
              onChange={(event) => onChange({ start: event.target.value })}
              className="h-10 rounded-[8px] border border-input bg-background px-3 font-sans text-[13px]"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">结束</span>
            <input
              type="date"
              value={endDate}
              onChange={(event) => onChange({ end: event.target.value })}
              className="h-10 rounded-[8px] border border-input bg-background px-3 font-sans text-[13px]"
            />
          </label>
        </>
      )}
    </div>
  )
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
