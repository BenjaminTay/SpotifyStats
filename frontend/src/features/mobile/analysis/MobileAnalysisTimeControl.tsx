import { useRef, useState } from 'react'
import { CalendarRange, ChevronRight } from 'lucide-react'

import { MobileTimeRangeSheet, type MobileTimeRangeValue } from '@/components/mobile'
import type { AnalysisPeriod } from '@/types/analysis'

const PERIOD_LABELS: Record<AnalysisPeriod, string> = {
  lifetime: '全部时间',
  last_6_months: '近 6 个月',
  last_4_weeks: '近 4 周',
  year: '按年',
  month: '按月',
  week: '按周',
  day: '按日',
  custom: '自定义范围',
}

interface MobileAnalysisTimeControlProps {
  period: AnalysisPeriod
  periodValue: string | null
  startDate: string
  endDate: string
  onChange: (patch: Record<string, string | undefined>) => void
}

export function MobileAnalysisTimeControl({
  period,
  periodValue,
  startDate,
  endDate,
  onChange,
}: MobileAnalysisTimeControlProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const detail = period === 'custom'
    ? [startDate, endDate].filter(Boolean).join(' — ')
    : periodValue || '使用当前数据范围'

  const apply = (value: MobileTimeRangeValue) => {
    onChange({
      period: value.period,
      period_value: value.periodValue,
      start: value.start,
      end: value.end,
    })
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="mobile-time-range-trigger"
        onClick={() => setOpen(true)}
        aria-label={`选择时间范围，当前${PERIOD_LABELS[period]}`}
      >
        <span className="mobile-time-range-icon"><CalendarRange aria-hidden="true" /></span>
        <span className="min-w-0 flex-1 text-left">
          <strong>{PERIOD_LABELS[period]}</strong>
          <small>{detail}</small>
        </span>
        <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </button>
      <MobileTimeRangeSheet
        open={open}
        onOpenChange={setOpen}
        triggerRef={triggerRef}
        value={{
          period,
          periodValue: periodValue ?? undefined,
          start: startDate || undefined,
          end: endDate || undefined,
        }}
        onApply={apply}
      />
    </>
  )
}
