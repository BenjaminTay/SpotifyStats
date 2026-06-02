import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, CalendarIcon } from 'lucide-react'
import {
  format,
  addDays,
  addWeeks,
  addMonths,
  addYears,
  getISOWeek,
  parseISO,
} from 'date-fns'
import { cn } from '@/lib/utils'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import type { AnalysisPeriod } from '@/types/analysis'

const QUICK_OPTIONS: Array<{ value: AnalysisPeriod; label: string }> = [
  { value: 'lifetime', label: '全部时间' },
  { value: 'last_6_months', label: '最近6月' },
  { value: 'last_4_weeks', label: '最近4周' },
  { value: 'year', label: '年' },
  { value: 'month', label: '月' },
  { value: 'week', label: '周' },
  { value: 'day', label: '天' },
  { value: 'custom', label: '自定义' },
]

function todayAnchor(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

function parsePeriodValue(period: AnalysisPeriod, value: string | null): Date {
  const fallback = todayAnchor()
  if (!value) return fallback
  try {
    if (period === 'year') {
      const y = parseInt(value, 10)
      return isNaN(y) ? fallback : new Date(y, 0, 1)
    }
    if (period === 'month') {
      const parts = value.split('-')
      const y = parseInt(parts[0], 10)
      const m = parseInt(parts[1], 10) - 1
      return isNaN(y) || isNaN(m) ? fallback : new Date(y, m, 1)
    }
    if (period === 'week') {
      const d = parseISO(value)
      return isNaN(d.getTime()) ? fallback : d
    }
    if (period === 'day') {
      const d = parseISO(value)
      return isNaN(d.getTime()) ? fallback : d
    }
  } catch {
    // fall through
  }
  return fallback
}

function formatPeriodValue(period: AnalysisPeriod, anchor: Date): string {
  if (period === 'year') return `${anchor.getFullYear()}年`
  if (period === 'month') return format(anchor, 'yyyy年M月')
  if (period === 'week') return `${anchor.getFullYear()}年第${getISOWeek(anchor)}周`
  if (period === 'day') return format(anchor, 'yyyy年M月d日')
  return ''
}

function encodePeriodValue(period: AnalysisPeriod, anchor: Date): string {
  if (period === 'year') return `${anchor.getFullYear()}`
  if (period === 'month') return format(anchor, 'yyyy-MM')
  if (period === 'week' || period === 'day') return format(anchor, 'yyyy-MM-dd')
  return ''
}


function navigateAnchor(period: AnalysisPeriod, anchor: Date, direction: -1 | 1): Date {
  if (period === 'year') return addYears(anchor, direction)
  if (period === 'month') return addMonths(anchor, direction)
  if (period === 'week') return addWeeks(anchor, direction)
  return addDays(anchor, direction)
}

export function AnalysisTimeRangeSelector({
  period,
  periodValue,
  startDate,
  endDate,
  onChange,
  quickFirst = false,
}: {
  period: AnalysisPeriod
  periodValue: string | null
  startDate: string
  endDate: string
  onChange: (patch: Record<string, string | undefined>) => void
  quickFirst?: boolean
}) {
  const anchor = useMemo(() => parsePeriodValue(period, periodValue), [period, periodValue])

  // ── Custom date range state ──
  const [startOpen, setStartOpen] = useState(false)
  const [endOpen, setEndOpen] = useState(false)
  const today = todayAnchor()

  const startParsed = startDate ? parseISO(startDate) : undefined
  const endParsed = endDate ? parseISO(endDate) : undefined
  const startValid = startParsed && !isNaN(startParsed.getTime())
  const endValid = endParsed && !isNaN(endParsed.getTime())

  const isNavigable = period === 'year' || period === 'month' || period === 'week' || period === 'day'

  function handleQuickSelect(p: AnalysisPeriod) {
    if (p === 'lifetime' || p === 'last_6_months' || p === 'last_4_weeks') {
      onChange({ period: p, period_value: undefined, start: undefined, end: undefined })
    } else if (p === 'custom') {
      onChange({ period: p, period_value: undefined })
    } else {
      const now = todayAnchor()
      onChange({ period: p, period_value: encodePeriodValue(p, now), start: undefined, end: undefined })
    }
  }

  function handleNavigate(dir: -1 | 1) {
    const next = navigateAnchor(period, anchor, dir)
    onChange({ period_value: encodePeriodValue(period, next) })
  }

  function handleStartDayClick(day: Date) {
    const endD = endParsed && !isNaN(endParsed.getTime()) ? endParsed : day
    const start = format(day, 'yyyy-MM-dd')
    const end = format(day > endD ? day : endD, 'yyyy-MM-dd')
    onChange({ start, end })
    setStartOpen(false)
  }

  function handleEndDayClick(day: Date) {
    const startD = startParsed && !isNaN(startParsed.getTime()) ? startParsed : day
    const end = format(day, 'yyyy-MM-dd')
    const start = format(day < startD ? day : startD, 'yyyy-MM-dd')
    onChange({ start, end })
    setEndOpen(false)
  }

  const isAtToday =
    isNavigable && formatPeriodValue(period, anchor) === formatPeriodValue(period, today)

  const navigatorBlock = isNavigable && (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => handleNavigate(-1)}
        className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </button>
      <span className="min-w-[90px] text-center font-sans text-[13px] font-semibold text-foreground tabular-nums">
        {formatPeriodValue(period, anchor)}
      </span>
      <button
        type="button"
        onClick={() => handleNavigate(1)}
        disabled={isAtToday}
        className={cn(
          'flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground transition-colors',
          isAtToday
            ? 'cursor-not-allowed opacity-25'
            : 'cursor-pointer hover:bg-muted hover:text-foreground',
        )}
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </div>
  )

  const customBlock = period === 'custom' && (
    <div className="flex items-center gap-2">
      <Popover open={startOpen} onOpenChange={setStartOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              'flex items-center gap-1.5 rounded-[6px] border border-border bg-background px-2.5 py-1 cursor-pointer transition-colors hover:border-foreground/20',
              !startValid && 'text-muted-foreground',
            )}
          >
            <CalendarIcon className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-sans text-[12px] tabular-nums">
              {startValid ? format(startParsed!, 'yyyy-MM-dd') : '起始日'}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" side="bottom" align="start" sideOffset={8}>
          <Calendar
            mode="single"
            month={startParsed ?? undefined}
            startMonth={endParsed ? new Date(2000, 0, 1) : undefined}
            endMonth={endParsed ?? today}
            onDayClick={handleStartDayClick}
            footer="点击选择起始日期"
          />
        </PopoverContent>
      </Popover>
      <span className="text-[11px] text-muted-foreground">至</span>
      <Popover open={endOpen} onOpenChange={setEndOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              'flex items-center gap-1.5 rounded-[6px] border border-border bg-background px-2.5 py-1 cursor-pointer transition-colors hover:border-foreground/20',
              !endValid && 'text-muted-foreground',
            )}
          >
            <CalendarIcon className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-sans text-[12px] tabular-nums">
              {endValid ? format(endParsed!, 'yyyy-MM-dd') : '结束日'}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" side="bottom" align="start" sideOffset={8}>
          <Calendar
            mode="single"
            month={endParsed ?? undefined}
            startMonth={startParsed ?? new Date(2000, 0, 1)}
            endMonth={today}
            onDayClick={handleEndDayClick}
            footer="点击选择结束日期"
          />
        </PopoverContent>
      </Popover>
    </div>
  )

  const quickBlock = (
    <div className="flex gap-1 rounded-[8px] border border-border bg-muted/30 p-1">
      {QUICK_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => handleQuickSelect(opt.value)}
          className={cn(
            'cursor-pointer rounded-[6px] px-2.5 py-1 font-sans text-[12px] font-medium transition-colors whitespace-nowrap',
            period === opt.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-background/50',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )

  return (
    <div className="flex items-center gap-2.5">
      {quickFirst ? (
        <>
          {quickBlock}
          {navigatorBlock}
          {customBlock}
        </>
      ) : (
        <>
          {navigatorBlock}
          {customBlock}
          {quickBlock}
        </>
      )}
    </div>
  )
}
