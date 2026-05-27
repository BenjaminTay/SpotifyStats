import * as React from "react"
import { useState, useEffect, useCallback } from "react"
import { DayPicker } from "react-day-picker"
import "react-day-picker/style.css"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { format } from "date-fns"

import { cn } from "@/lib/utils"

const MONTHS = [
  "1月", "2月", "3月", "4月",
  "5月", "6月", "7月", "8月",
  "9月", "10月", "11月", "12月",
]

type ViewMode = "calendar" | "months"

interface CalendarProps extends Omit<React.ComponentProps<typeof DayPicker>, 'month'> {
  month?: Date
  startMonth?: Date
  endMonth?: Date
}

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  month: controlledMonth,
  startMonth,
  endMonth,
  modifiers,
  modifiersClassNames,
  disabled,
  onDayClick,
  footer,
  ...props
}: CalendarProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("calendar")
  const [viewYear, setViewYear] = useState<number>(0) // displayed year in months view
  const [localMonth, setLocalMonth] = useState<Date>(() => {
    if (controlledMonth) return controlledMonth
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })

  // Sync when external month prop changes
  useEffect(() => {
    if (controlledMonth) {
      setLocalMonth(controlledMonth)
    }
  }, [controlledMonth?.getTime()])

  const currentMonth = localMonth

  const enterMonthsView = useCallback(() => {
    setViewYear(currentMonth.getFullYear())
    setViewMode("months")
  }, [currentMonth])

  const leaveMonthsView = useCallback(() => {
    setViewMode("calendar")
  }, [])

  const goPrev = useCallback(() => {
    if (viewMode === "calendar") {
      setLocalMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))
    } else {
      setViewYear((y) => y - 1)
    }
  }, [viewMode])

  const goNext = useCallback(() => {
    if (viewMode === "calendar") {
      setLocalMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))
    } else {
      setViewYear((y) => y + 1)
    }
  }, [viewMode])

  const handleMonthSelect = useCallback((monthIdx: number) => {
    setLocalMonth(new Date(viewYear, monthIdx, 1))
    setViewMode("calendar")
  }, [viewYear])

  const canGoPrev = (() => {
    if (!startMonth) return true
    if (viewMode === "calendar") {
      const target = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1)
      return target >= new Date(startMonth.getFullYear(), startMonth.getMonth(), 1)
    }
    return viewYear - 1 >= startMonth.getFullYear()
  })()

  const canGoNext = (() => {
    if (!endMonth) return true
    if (viewMode === "calendar") {
      const target = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1)
      return target <= new Date(endMonth.getFullYear(), endMonth.getMonth(), 1)
    }
    return viewYear + 1 <= endMonth.getFullYear()
  })()

  const dpFrom = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1)
  const dpTo = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0)

  const headerLabel = viewMode === "calendar"
    ? format(currentMonth, "yyyy年M月")
    : `${viewYear}年`
  const pickerProps = props as React.ComponentProps<typeof DayPicker>

  return (
    <div className={cn("p-4 select-none w-[320px]", className)}>
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-3">
        <button
          type="button"
          onClick={goPrev}
          disabled={!canGoPrev}
          className={cn(
            "inline-flex h-8 w-8 items-center justify-center rounded-full",
            "text-muted-foreground transition-colors",
            canGoPrev && "cursor-pointer hover:bg-muted hover:text-foreground",
            !canGoPrev && "opacity-25 cursor-default",
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <button
          type="button"
          onClick={() => viewMode === "calendar" ? enterMonthsView() : leaveMonthsView()}
          className={cn(
            "cursor-pointer rounded-lg px-3 py-1 transition-colors hover:bg-muted/60",
            "font-serif text-[15px] font-semibold tracking-wide text-foreground",
          )}
        >
          {headerLabel}
        </button>

        <button
          type="button"
          onClick={goNext}
          disabled={!canGoNext}
          className={cn(
            "inline-flex h-8 w-8 items-center justify-center rounded-full",
            "text-muted-foreground transition-colors",
            canGoNext && "cursor-pointer hover:bg-muted hover:text-foreground",
            !canGoNext && "opacity-25 cursor-default",
          )}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* ── Month Grid View ── */}
      {viewMode === "months" && (
        <div className="grid grid-cols-3 gap-2 px-1 pb-1">
          {MONTHS.map((name, idx) => {
            const isCurrent = viewYear === currentMonth.getFullYear() && idx === currentMonth.getMonth()
            const monthDate = new Date(viewYear, idx, 1)
            const isDisabled =
              (startMonth && monthDate < new Date(startMonth.getFullYear(), startMonth.getMonth(), 1)) ||
              (endMonth && monthDate > endMonth)
            return (
              <button
                key={name}
                type="button"
                disabled={isDisabled}
                onClick={() => handleMonthSelect(idx)}
                className={cn(
                  "rounded-xl py-3 px-2 text-center font-serif text-[14px] transition-all",
                  "border border-transparent",
                  isCurrent && !isDisabled && "bg-accent-foreground text-primary-foreground font-semibold",
                  !isCurrent && !isDisabled && "cursor-pointer hover:bg-muted hover:border-border text-foreground",
                  isDisabled && "opacity-20 cursor-default text-muted-foreground",
                )}
              >
                {name}
              </button>
            )
          })}
        </div>
      )}

      {/* ── Day Grid View ── */}
      {viewMode === "calendar" && (
        <DayPicker
          hideNavigation
          month={currentMonth}
          startMonth={dpFrom}
          endMonth={dpTo}
          showOutsideDays={showOutsideDays}
          disabled={disabled}
          modifiers={modifiers}
          modifiersClassNames={modifiersClassNames}
          onDayClick={onDayClick}
          {...pickerProps}
          classNames={{
            months: "flex flex-col",
            month: "flex flex-col",
            month_caption: "hidden",
            nav: "hidden",
            month_grid: "w-full border-collapse",
            weekdays: "flex mb-1",
            weekday: cn(
              "flex-1 text-center font-sans text-[10px] font-bold uppercase tracking-[1px]",
              "text-muted-foreground py-1.5",
            ),
            weeks: "flex flex-col gap-[2px]",
            week: "flex w-full",
            day: "flex-1 text-center p-0",
            day_button: cn(
              "flex h-9 w-full items-center justify-center",
              "font-sans text-[13px] font-medium rounded-full",
              "border-0 bg-transparent p-0",
              "cursor-pointer transition-colors",
              "hover:bg-muted",
            ),
            outside: "text-muted-foreground/25",
            today: "font-bold underline underline-offset-2",
            disabled: "text-muted-foreground/20 pointer-events-none cursor-not-allowed",
            hidden: "invisible",
            ...classNames,
          }}
        />
      )}

      {/* ── Footer ── */}
      {footer && (
        <div className="border-t border-border mt-3 pt-2 text-center font-sans text-[11px] text-muted-foreground">
          {footer}
        </div>
      )}
    </div>
  )
}

export { Calendar }
