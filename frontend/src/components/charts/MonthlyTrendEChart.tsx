import { useTheme } from '@/hooks/useTheme'
import { getChartColors } from '@/lib/theme'
import type { MonthlyTrendPoint } from '@/types/dashboard'
import { buildChartBase } from './EChartsTheme'
import { LazyEChart } from './LazyEChart'

interface MonthlyTrendEChartProps {
  data: MonthlyTrendPoint[]
}

export default function MonthlyTrendEChart({ data }: MonthlyTrendEChartProps) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = [...getChartColors(isDark)]

  const labels = data.map((d) => {
    const [, month] = d.period.split('-')
    return `${parseInt(month, 10)}月`
  })

  const option = {
    ...base,
    xAxis: {
      ...base.xAxis,
      type: 'category' as const,
      data: labels,
    },
    yAxis: {
      ...base.yAxis,
      type: 'value' as const,
    },
    series: [
      {
        type: 'bar' as const,
        data: data.map((point, index) => ({
          value: point.plays,
          itemStyle: {
            color: colors[index % colors.length],
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
      valueFormatter: (value: unknown) =>
        typeof value === 'number' ? `${value.toLocaleString('zh-CN')} 次播放` : value,
    },
  }

  return <LazyEChart option={option} style={{ height: 240 }} notMerge />
}
