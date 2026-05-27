import { lazy, Suspense } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import { getChartColors } from '@/lib/theme'
import type { MonthlyTrendPoint } from '@/types/dashboard'

const ReactECharts = lazy(() => import('echarts-for-react'))

interface MonthlyTrendChartProps {
  data: MonthlyTrendPoint[]
}

export function MonthlyTrendChart({ data }: MonthlyTrendChartProps) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = [...getChartColors(isDark)]

  const labels = data.map((d) => {
    const [, month] = d.period.split('-')
    return `${parseInt(month, 10)}月`
  })
  const values = data.map((d) => d.plays)

  const option = {
    ...base,
    xAxis: {
      ...base.xAxis,
      data: labels,
    },
    yAxis: {
      ...base.yAxis,
      name: '播放次数',
      nameTextStyle: {
        color: isDark ? '#A09888' : '#6B5E58',
        fontSize: 11,
      },
    },
    series: [
      {
        type: 'bar',
        data: values.map((v, i) => ({
          value: v,
          itemStyle: {
            color: colors[i % colors.length],
            borderRadius: [3, 3, 0, 0],
          },
        })),
        barMaxWidth: 36,
        emphasis: {
          itemStyle: {
            opacity: 0.85,
          },
        },
      },
    ],
    tooltip: {
      ...base.tooltip,
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
    },
  }

  return (
    <Suspense fallback={<div className="h-[240px] animate-pulse rounded-lg bg-muted/40" />}>
      <ReactECharts option={option} style={{ height: 240 }} notMerge />
    </Suspense>
  )
}
