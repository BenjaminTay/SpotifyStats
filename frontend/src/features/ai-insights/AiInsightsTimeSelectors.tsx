import { parseISO } from 'date-fns'
import { Calendar as CalendarIcon } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import type { ReportType } from '@/types/ai-insights'

// ── Date helpers ──────────────────────────────────────────────────────────

const DAY_MS = 86400000

const fmt = (d: Date) => {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseLocalDate(value: string) {
  return new Date(`${value}T00:00:00`)
}

function weekRange(offset: number) {
  const now = new Date()
  const end = new Date(now.getTime() + offset * 7 * DAY_MS)
  const start = new Date(end.getTime() - 6 * DAY_MS)
  return { start: fmt(start), end: fmt(end) }
}

export function weekRangeEndingAt(endDate: string, offsetWeeks = 0) {
  const end = parseLocalDate(endDate)
  end.setDate(end.getDate() + offsetWeeks * 7)
  const start = new Date(end.getTime() - 6 * DAY_MS)
  return { start: fmt(start), end: fmt(end) }
}

function monthValue(offset: number) {
  const now = new Date()
  const d = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function monthValueFrom(dateString: string, offset: number) {
  const anchor = parseLocalDate(dateString)
  const d = new Date(anchor.getFullYear(), anchor.getMonth() + offset, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function currentWeekRange() {
  return weekRange(0)
}

export function currentMonthValue() {
  return monthValue(0)
}

// ── QuickPills ────────────────────────────────────────────────────────────

function QuickPills({
  options,
  current,
  onSelect,
}: {
  options: { label: string; value: string }[]
  current: string
  onSelect: (v: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map((opt) => (
        <button
          key={`${opt.label}:${opt.value}`}
          onClick={() => onSelect(opt.value)}
          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.6px] transition-all ${
            current === opt.value
              ? 'bg-accent-foreground/10 text-accent-foreground'
              : 'text-muted-foreground/50 hover:text-muted-foreground'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ── Time selectors ────────────────────────────────────────────────────────

const dateInputClass =
  'w-[132px] rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] backdrop-blur-[8px] outline-none sm:w-auto'

interface TimeSelectorProps {
  reportType: ReportType
  /** Weekly */
  weekStart: string
  weekEnd: string
  onWeekChange: (start: string, end: string) => void
  weekPickerOpen: boolean
  onWeekPickerOpenChange: (open: boolean) => void
  latestDate: string | null
  weeklyQuickOptions: { label: string; value: string }[]
  weeklyQuickValue: string
  onWeeklyQuick: (v: string) => void
  /** Monthly */
  month: string
  onMonthChange: (month: string, year: number) => void
  monthPickerOpen: boolean
  onMonthPickerOpenChange: (open: boolean) => void
  monthlyQuickOptions: { label: string; value: string }[]
  onMonthlyQuick: (v: string) => void
  /** Yearly */
  year: number
  onYearChange: (year: number) => void
  nowYear: number
  yearlyQuickOptions: { label: string; value: string }[]
  onYearlyQuick: (v: string) => void
}

export function AiInsightsTimeSelectors({
  reportType,
  weekStart,
  weekEnd,
  onWeekChange,
  weekPickerOpen,
  onWeekPickerOpenChange,
  latestDate,
  weeklyQuickOptions,
  weeklyQuickValue,
  onWeeklyQuick,
  month,
  onMonthChange,
  monthPickerOpen,
  onMonthPickerOpenChange,
  monthlyQuickOptions,
  onMonthlyQuick,
  year,
  onYearChange,
  nowYear,
  yearlyQuickOptions,
  onYearlyQuick,
}: TimeSelectorProps) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-3 text-[13px]">
      {reportType === 'weekly' && (
        <>
          <QuickPills
            options={weeklyQuickOptions}
            current={weeklyQuickValue}
            onSelect={onWeeklyQuick}
          />
          <Popover open={weekPickerOpen} onOpenChange={onWeekPickerOpenChange}>
            <PopoverTrigger asChild>
              <button className={`${dateInputClass} cursor-pointer flex items-center gap-1.5 hover:border-accent-foreground/20 transition-colors`}>
                <CalendarIcon className="h-3 w-3 text-muted-foreground/50 shrink-0" />
                <span className="truncate">{weekStart} ~ {weekEnd}</span>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" align="start" sideOffset={8}>
              <Calendar
                mode="single"
                month={parseISO(weekStart)}
                endMonth={latestDate ? parseISO(latestDate) : undefined}
                modifiers={{
                  selectedWeek: [{ from: parseISO(weekStart), to: parseISO(weekEnd) }]
                }}
                modifiersClassNames={{
                  selectedWeek: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-none first:rounded-l-full last:rounded-r-full'
                }}
                onDayClick={(day) => {
                  const start = day
                  const end = new Date(start.getTime() + 6 * DAY_MS)
                  onWeekChange(fmt(start), fmt(end))
                  onWeekPickerOpenChange(false)
                }}
                footer="点击日期选择以该日开始的 7 天"
              />
            </PopoverContent>
          </Popover>
        </>
      )}

      {reportType === 'monthly' && (
        <>
          <QuickPills
            options={monthlyQuickOptions}
            current={month}
            onSelect={onMonthlyQuick}
          />
          <Popover open={monthPickerOpen} onOpenChange={onMonthPickerOpenChange}>
            <PopoverTrigger asChild>
              <button className={`${dateInputClass} cursor-pointer flex items-center gap-1.5 hover:border-accent-foreground/20 transition-colors`}>
                <CalendarIcon className="h-3 w-3 text-muted-foreground/50 shrink-0" />
                <span>{month}</span>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" align="start" sideOffset={8}>
              <Calendar
                mode="single"
                defaultView="months"
                month={parseISO(`${month}-01`)}
                endMonth={latestDate ? parseISO(latestDate) : undefined}
                onMonthSelect={(monthIdx, yr) => {
                  onMonthChange(`${yr}-${String(monthIdx + 1).padStart(2, '0')}`, yr)
                  onMonthPickerOpenChange(false)
                }}
              />
            </PopoverContent>
          </Popover>
        </>
      )}

      {reportType === 'yearly' && (
        <>
          <QuickPills
            options={yearlyQuickOptions}
            current={String(year)}
            onSelect={onYearlyQuick}
          />
          <select
            value={year}
            onChange={(e) => onYearChange(parseInt(e.target.value, 10))}
            className={`${dateInputClass} cursor-pointer appearance-none`}
          >
            {Array.from({ length: nowYear - 2009 }, (_, i) => nowYear - i).map(
              (y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ),
            )}
          </select>
        </>
      )}
    </div>
  )
}
