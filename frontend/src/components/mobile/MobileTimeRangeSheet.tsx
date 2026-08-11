import { useMemo, useState, type RefObject } from 'react'
import { CalendarDays, Check, ChevronDown } from 'lucide-react'
import {
  addDays,
  endOfMonth,
  format,
  isValid,
  parseISO,
  startOfMonth,
  startOfWeek,
} from 'date-fns'
import type { DateRange } from 'react-day-picker'

import type { AnalysisMetric, AnalysisPeriod } from '@/types/analysis'
import { cn } from '@/lib/utils'
import { MobileBottomSheet } from './MobileBottomSheet'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

export interface MobileTimeRangeValue {
  period: AnalysisPeriod
  periodValue?: string
  start?: string
  end?: string
  metric?: AnalysisMetric
}

interface MobileTimeRangeSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: MobileTimeRangeValue
  onApply: (value: MobileTimeRangeValue) => void
  triggerRef?: RefObject<HTMLElement | null>
}

const PERIOD_OPTIONS: Array<{ value: AnalysisPeriod; label: string; hint: string }> = [
  { value: 'lifetime', label: '全部时间', hint: '完整播放历史' },
  { value: 'last_6_months', label: '近 6 个月', hint: '滚动半年窗口' },
  { value: 'last_4_weeks', label: '近 4 周', hint: '最近 28 天' },
  { value: 'year', label: '按年', hint: '选择自然年' },
  { value: 'month', label: '按月', hint: '选择自然月' },
  { value: 'week', label: '按周', hint: '选择自然周' },
  { value: 'day', label: '按日', hint: '选择具体日期' },
  { value: 'custom', label: '自定义', hint: '指定开始与结束日期' },
]

function periodInputType(period: AnalysisPeriod): 'number' | 'month' | 'week' | 'date' | null {
  if (period === 'year') return 'number'
  if (period === 'month') return 'month'
  if (period === 'week') return 'date'
  if (period === 'day') return 'date'
  return null
}

function todayAnchor(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

function parseCalendarAnchor(period: AnalysisPeriod, value: MobileTimeRangeValue): Date {
  if (period === 'custom' && value.start) {
    const start = parseISO(value.start)
    if (isValid(start)) return start
  }
  if (period === 'year' && value.periodValue) {
    const year = Number(value.periodValue)
    if (Number.isInteger(year)) return new Date(year, 0, 1)
  }
  if (period === 'month' && value.periodValue) {
    const month = parseISO(`${value.periodValue}-01`)
    if (isValid(month)) return month
  }
  if ((period === 'week' || period === 'day') && value.periodValue) {
    const day = parseISO(value.periodValue)
    if (isValid(day)) return day
  }
  return todayAnchor()
}

function formatDay(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

function formatDateLabel(value?: string): string {
  if (!value) return '尚未选择'
  const date = parseISO(value)
  return isValid(date) ? format(date, 'yyyy年M月d日') : value
}

function formatPeriodLabel(period: AnalysisPeriod, value?: string): string {
  if (!value) return '尚未选择'
  if (period === 'year') return `${value}年`
  const date = parseISO(period === 'month' ? `${value}-01` : value)
  if (!isValid(date)) return value
  if (period === 'month') return format(date, 'yyyy年M月')
  if (period === 'week') return `${format(date, 'M月d日')} 至 ${format(addDays(date, 6), 'M月d日')}`
  return formatDateLabel(value)
}

type MobileTimeRangeSessionProps = Omit<MobileTimeRangeSheetProps, 'open'>

function MobileTimeRangeSession({ onOpenChange, value, onApply, triggerRef }: MobileTimeRangeSessionProps) {
  const [draft, setDraft] = useState<MobileTimeRangeValue>(() => ({ ...value }))
  const [calendarOpen, setCalendarOpen] = useState(false)
  const inputType = periodInputType(draft.period)
  const today = todayAnchor()
  const calendarAnchor = useMemo(() => parseCalendarAnchor(draft.period, draft), [draft])
  const showMetric = value.metric != null
  const calendarRange: DateRange | undefined = draft.start
    ? { from: parseISO(draft.start), to: draft.end ? parseISO(draft.end) : undefined }
    : undefined
  const weekStart = draft.period === 'week' && draft.periodValue ? calendarAnchor : undefined
  const weekEnd = weekStart ? addDays(weekStart, 6) : undefined
  const monthStart = draft.period === 'month' && draft.periodValue ? startOfMonth(calendarAnchor) : undefined
  const monthEndCandidate = monthStart ? endOfMonth(calendarAnchor) : undefined
  const monthEnd = monthEndCandidate && monthEndCandidate > today ? today : monthEndCandidate
  const validationMessage = useMemo(() => {
    if (inputType && !draft.periodValue) return '请选择具体时间。'
    if (draft.period === 'custom' && (!draft.start || !draft.end)) return '请选择开始和结束日期。'
    if (draft.period === 'custom' && draft.start && draft.end && draft.start > draft.end) {
      return '开始日期不能晚于结束日期。'
    }
    return ''
  }, [draft.end, draft.period, draft.periodValue, draft.start, inputType])

  const handleDayClick = (day: Date) => {
    if (draft.period === 'week') {
      setDraft((current) => ({
        ...current,
        periodValue: formatDay(startOfWeek(day, { weekStartsOn: 1 })),
      }))
      return
    }
    if (draft.period === 'month') {
      setDraft((current) => ({ ...current, periodValue: format(day, 'yyyy-MM') }))
      return
    }
    if (draft.period === 'year') {
      setDraft((current) => ({ ...current, periodValue: format(day, 'yyyy') }))
      return
    }
    setDraft((current) => ({ ...current, periodValue: formatDay(day) }))
  }

  const handleMonthSelect = (monthIndex: number, year: number) => {
    setDraft((current) => ({
      ...current,
      periodValue: current.period === 'year'
        ? String(year)
        : format(new Date(year, monthIndex, 1), 'yyyy-MM'),
    }))
  }

  const handleRangeSelect = (range: DateRange | undefined) => {
    const completingRange = Boolean(draft.start && !draft.end && range?.from && range?.to)
    setDraft((current) => ({
      ...current,
      start: range?.from ? formatDay(range.from) : undefined,
      end: completingRange && range?.to ? formatDay(range.to) : undefined,
    }))
  }

  const calendar = draft.period === 'custom'
    ? (
        <Calendar
          key={draft.period}
          className="mobile-time-range-calendar"
          mode="range"
          month={calendarAnchor}
          startMonth={new Date(2000, 0, 1)}
          endMonth={today}
          disabled={(date) => date > today}
          selected={calendarRange}
          onSelect={(range) => handleRangeSelect(range as DateRange | undefined)}
          modifiersClassNames={{
            range_start: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-l-full',
            range_middle: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-none',
            range_end: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-r-full',
          }}
          footer="先选起始日，再选终止日"
        />
      )
    : (
        <Calendar
          key={draft.period}
          className="mobile-time-range-calendar"
          mode="single"
          defaultView={draft.period === 'year' ? 'months' : undefined}
          month={calendarAnchor}
          startMonth={new Date(2000, 0, 1)}
          endMonth={today}
          disabled={(date) => date > today}
          selected={draft.period === 'day' && draft.periodValue ? calendarAnchor : undefined}
          modifiers={weekStart && weekEnd
            ? {
                weekStart,
                weekMiddle: { from: addDays(weekStart, 1), to: addDays(weekStart, 5) },
                weekEnd,
              }
            : monthStart && monthEnd
              ? {
                  monthStart,
                  monthMiddle: { from: addDays(monthStart, 1), to: addDays(monthEnd, -1) },
                  monthEnd,
                }
              : undefined}
          modifiersClassNames={weekStart && weekEnd
            ? {
                weekStart: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-l-full',
                weekMiddle: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-none',
                weekEnd: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-r-full',
              }
            : monthStart && monthEnd
              ? {
                  monthStart: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-l-full',
                  monthMiddle: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-none',
                  monthEnd: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-r-full',
                }
              : draft.period === 'day'
                ? { selected: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-full' }
                : undefined}
          onDayClick={handleDayClick}
          onMonthSelect={handleMonthSelect}
          footer={draft.period === 'year'
            ? '点击月份确定年份'
            : draft.period === 'month'
              ? '点击日期或月份确定月份'
              : draft.period === 'week'
                ? '点击任意日期选择所在周'
                : '点击日期确定当天'}
        />
      )

  return (
    <MobileBottomSheet
      open
      onOpenChange={onOpenChange}
      title="时间范围"
      eyebrow="Time / Range"
      description="选择时间窗口与统计口径；日期类范围使用日历。"
      triggerRef={triggerRef}
      dataSheet="time-range"
      footer={(
        <div className="mobile-sheet-actions mobile-sheet-actions-end">
          <button
            type="button"
            className="mobile-primary-button"
            disabled={Boolean(validationMessage)}
            onClick={() => {
              onApply({ ...draft })
              onOpenChange(false)
            }}
          >
            应用时间范围
          </button>
        </div>
      )}
    >
      <div className="mobile-time-grid" role="radiogroup" aria-label="时间范围类型">
        {PERIOD_OPTIONS.map((option) => {
          const selected = option.value === draft.period
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              className={cn('mobile-time-option', selected && 'mobile-time-option-selected')}
              onClick={() => setDraft((current) => ({ period: option.value, metric: current.metric }))}
            >
              <span>
                <strong>{option.label}</strong>
                <small>{option.hint}</small>
              </span>
              {selected && <Check className="h-4 w-4" aria-hidden="true" />}
            </button>
          )
        })}
      </div>

      {showMetric && (
        <section className="mobile-time-metric-section" aria-label="统计口径">
          <div>
            <strong>统计口径</strong>
            <small>应用后同步影响所有图表</small>
          </div>
          <div className="mobile-time-metric-options" role="radiogroup" aria-label="统计口径">
            {([
              ['plays', '播放次数'],
              ['hours', '播放时长'],
            ] as const).map(([metric, label]) => (
              <button
                key={metric}
                type="button"
                role="radio"
                aria-checked={(draft.metric ?? 'plays') === metric}
                className={cn('mobile-time-metric-option', (draft.metric ?? 'plays') === metric && 'selected')}
                onClick={() => setDraft((current) => ({ ...current, metric }))}
              >
                {label}
                {(draft.metric ?? 'plays') === metric && <Check className="h-4 w-4" aria-hidden="true" />}
              </button>
            ))}
          </div>
        </section>
      )}

      {inputType && <div className="mobile-time-calendar-section">
        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="mobile-time-calendar-trigger"
              aria-label="打开日期选择器"
            >
              <span><CalendarDays className="h-4 w-4" aria-hidden="true" />选择具体时间</span>
              <strong>{formatPeriodLabel(draft.period, draft.periodValue)}</strong>
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
          </PopoverTrigger>
          <PopoverContent
            side="top"
            align="center"
            className="mobile-time-calendar-popover"
          >
            {calendar}
          </PopoverContent>
        </Popover>
      </div>}

      {draft.period === 'custom' && (
        <div className="mobile-time-calendar-section">
          <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="mobile-time-calendar-trigger"
                aria-label="打开日期范围选择器"
              >
                <span><CalendarDays className="h-4 w-4" aria-hidden="true" />选择日期范围</span>
                <strong>{draft.start && draft.end
                  ? `${formatDateLabel(draft.start)} 至 ${formatDateLabel(draft.end)}`
                  : draft.start
                    ? `${formatDateLabel(draft.start)} — 请选择终止日`
                    : '请选择起始日和终止日'}</strong>
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
              </button>
            </PopoverTrigger>
            <PopoverContent
              side="top"
              align="center"
              className="mobile-time-calendar-popover"
            >
              {calendar}
            </PopoverContent>
          </Popover>
        </div>
      )}

      {validationMessage && <p className="mobile-field-message" role="status">{validationMessage}</p>}
    </MobileBottomSheet>
  )
}

export function MobileTimeRangeSheet(props: MobileTimeRangeSheetProps) {
  if (!props.open) return null
  return <MobileTimeRangeSession {...props} />
}
