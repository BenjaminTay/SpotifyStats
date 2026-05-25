import { getChartColors } from '@/lib/theme'

export function buildChartBase(isDark: boolean) {
  const colors = [...getChartColors(isDark)]
  const textColor = isDark ? '#A09888' : '#6B5E58'
  const gridColor = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'

  return {
    color: colors,
    backgroundColor: 'transparent',
    textStyle: {
      fontFamily: "'Inter Variable', 'Inter', -apple-system, sans-serif",
      fontSize: 12,
      color: textColor,
    },
    grid: {
      left: 0,
      right: 16,
      top: 16,
      bottom: 0,
      containLabel: true,
    },
    xAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: textColor,
        fontSize: 11,
      },
      splitLine: { show: false },
    },
    yAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: textColor,
        fontSize: 11,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: gridColor,
          type: 'dashed',
        },
      },
    },
    tooltip: {
      backgroundColor: isDark ? 'rgba(30,30,34,0.9)' : 'rgba(255,255,255,0.9)',
      borderColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
      textStyle: {
        color: isDark ? '#F0EBE3' : '#2D2420',
        fontSize: 12,
      },
    },
  }
}
