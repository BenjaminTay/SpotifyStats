import { lazy, Suspense } from 'react'
import type { MonthlyTrendPoint } from '@/types/dashboard'

const MonthlyTrendEChart = lazy(() => import('./MonthlyTrendEChart'))

interface MonthlyTrendChartProps {
  data: MonthlyTrendPoint[]
}

export function MonthlyTrendChart({ data }: MonthlyTrendChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center rounded-lg border border-dashed border-border/70 font-sans text-[13px] text-muted-foreground">
        暂无月度趋势数据
      </div>
    )
  }

  return (
    <Suspense
      fallback={
        <div className="h-[240px] animate-pulse rounded-lg bg-muted/40" />
      }
    >
      <MonthlyTrendEChart data={data} />
    </Suspense>
  )
}
