import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { addDays, isWithinInterval, parseISO } from 'date-fns'
import { cn } from '@/lib/utils'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'

interface WeekSelectorProps {
  weekLabel: string
  dateRange?: string
  onPrev: () => void
  onNext: () => void
  disablePrev?: boolean
  disableNext?: boolean
  allWeeks: string[]
  selectedWeek: string
  onGoToWeek: (week: string) => void
}

export function WeekSelector({
  weekLabel,
  dateRange,
  onPrev,
  onNext,
  disablePrev,
  disableNext,
  allWeeks,
  selectedWeek,
  onGoToWeek,
}: WeekSelectorProps) {
  const [open, setOpen] = useState(false)

  const weekIntervals = useMemo(() => {
    return allWeeks.map((w) => {
      const start = parseISO(w)
      return { start, end: addDays(start, 6) }
    })
  }, [allWeeks])

  const bounds = useMemo(() => {
    if (weekIntervals.length === 0) return { from: undefined, to: undefined }
    return {
      from: weekIntervals[weekIntervals.length - 1].start, // oldest
      to: weekIntervals[0].start, // newest
    }
  }, [weekIntervals])

  const selectedWeekDays = useMemo(() => {
    if (!selectedWeek) return undefined
    const start = parseISO(selectedWeek)
    return { from: start, to: addDays(start, 6) }
  }, [selectedWeek])

  // Disable dates that don't belong to any Billboard week
  const disabledMatcher = useMemo(() => {
    if (weekIntervals.length === 0) return undefined
    return (date: Date) => {
      return !weekIntervals.some(({ start, end }) =>
        isWithinInterval(date, { start, end }),
      )
    }
  }, [weekIntervals])

  function handleDayClick(day: Date) {
    // Shouldn't be called for disabled days, but double-check
    if (disabledMatcher?.(day)) return
    const match = allWeeks.find((w) => {
      const weekStart = parseISO(w)
      return isWithinInterval(day, { start: weekStart, end: addDays(weekStart, 6) })
    })
    if (match) {
      onGoToWeek(match)
      setOpen(false)
    }
  }

  return (
    <div className="mb-6 flex items-center gap-3.5">
      <button
        onClick={onPrev}
        disabled={disablePrev}
        className={cn(
          'flex h-[34px] w-[34px] items-center justify-center rounded-full border border-border bg-card backdrop-blur-[12px] text-muted-foreground transition-[background,border,color] duration-400',
          disablePrev
            ? 'cursor-not-allowed opacity-40'
            : 'cursor-pointer hover:border-foreground/15 hover:text-foreground',
        )}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button className="cursor-pointer rounded-lg text-left transition-colors hover:bg-muted/50 -mx-1.5 px-1.5 py-0.5">
            <div className="font-serif text-[28px] font-semibold leading-[1.1]">
              {weekLabel}
            </div>
            {dateRange && (
              <div className="font-sans text-[13px] text-muted-foreground">
                {dateRange}
              </div>
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent
          className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl"
          side="right"
          align="start"
          sideOffset={12}
          alignOffset={-72}
        >
          <Calendar
            mode="single"
            month={selectedWeek ? parseISO(selectedWeek) : undefined}
            startMonth={bounds.from}
            endMonth={bounds.to}
            disabled={disabledMatcher}
            modifiers={
              selectedWeekDays
                ? { currentWeek: [selectedWeekDays] }
                : undefined
            }
            modifiersClassNames={{
              currentWeek: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-none first:rounded-l-full last:rounded-r-full',
            }}
            onDayClick={handleDayClick}
            footer="点击日期跳转到对应周"
          />
        </PopoverContent>
      </Popover>

      <button
        onClick={onNext}
        disabled={disableNext}
        className={cn(
          'flex h-[34px] w-[34px] items-center justify-center rounded-full border border-border bg-card backdrop-blur-[12px] text-muted-foreground transition-[background,border,color] duration-400',
          disableNext
            ? 'cursor-not-allowed opacity-40'
            : 'cursor-pointer hover:border-foreground/15 hover:text-foreground',
        )}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  )
}
