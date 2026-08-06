import { CalendarRange } from 'lucide-react'

import type { WrappedReportingPeriod } from '@/types/yearly-review'

interface YearlyPeriodNoticeProps {
  period: WrappedReportingPeriod
}

export function YearlyPeriodNotice({ period }: YearlyPeriodNoticeProps) {
  if (!period.is_partial_year || !period.end_date) return null

  const isCurrentYear = period.year === new Date().getFullYear()

  return (
    <aside className="yearly-period-notice" aria-label="年度数据范围">
      <span className="yearly-period-notice-icon" aria-hidden="true">
        <CalendarRange />
      </span>
      <span>
        <strong>{isCurrentYear ? '年度进行中' : '年度数据不完整'}</strong>
        <small>数据截至 {period.end_date}</small>
      </span>
    </aside>
  )
}
