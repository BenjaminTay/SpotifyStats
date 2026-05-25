import ReactECharts from 'echarts-for-react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import { getChartColors } from '@/lib/theme'

interface RankDataPoint {
  week: string
  rank: number | null
}

interface RankTrendChartProps {
  data: RankDataPoint[]
  topN: number
  peakPosition?: number
  overlayData?: RankDataPoint[]
  overlayLabel?: string
}

export function RankTrendChart({
  data,
  topN,
  peakPosition,
  overlayData,
  overlayLabel,
}: RankTrendChartProps) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = [...getChartColors(isDark)]

  const labels = data.map((d) => {
    if (!d.week) return ''
    const parts = d.week.split('-')
    if (parts.length >= 3) return `${parts[0]}/${parts[1]}/${parts[2]}`
    return d.week
  })

  const values = data.map((d) => d.rank)
  const hasGaps = values.some((v) => v === null)
  const totalPoints = values.length

  // Show sparse x-axis labels — only major time boundaries, not every data point
  const labelInterval =
    totalPoints > 52 ? Math.floor(totalPoints / 8)   // ~8 labels per year of weekly data
    : totalPoints > 26 ? Math.floor(totalPoints / 6)  // ~6 labels for 6-month data
    : totalPoints > 12 ? Math.floor(totalPoints / 4)  // ~4 labels for quarterly data
    : 0

  const textColor = isDark ? '#A09888' : '#6B5E58'
  const rankColor = isDark ? '#D4836F' : '#C84C3D'
  const overlayColor = isDark ? '#7BA587' : '#4A7C59'

  const series: any[] = [
    {
      name: '排名',
      type: 'line',
      data: values,
      connectNulls: false,
      smooth: false,
      symbol: 'circle',
      symbolSize: hasGaps ? 5 : 4,
      showSymbol: totalPoints < 40,
      emphasis: {
        focus: 'series',
        symbolSize: 8,
      },
      lineStyle: {
        width: 2,
        color: rankColor,
        cap: 'round',
      },
      itemStyle: {
        color: rankColor,
        borderColor: isDark ? '#1C1C20' : '#FFFFFF',
        borderWidth: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: isDark ? 'rgba(212,131,111,0.15)' : 'rgba(200,76,61,0.10)' },
            { offset: 1, color: 'transparent' },
          ],
        },
      },
      markLine: peakPosition
        ? {
            silent: true,
            symbol: 'none',
            animation: false,
            lineStyle: {
              color: rankColor,
              type: 'dashed',
              width: 1,
              opacity: 0.35,
            },
            label: {
              formatter: `峰值 #${peakPosition}`,
              position: 'insideEndTop',
              fontSize: 11,
              fontWeight: 500,
              color: textColor,
              distance: [0, 6],
            },
            data: [{ yAxis: peakPosition }],
          }
        : undefined,
      // Highlight #1 positions with larger emphasis
      markPoint: totalPoints <= 30
        ? {
            silent: true,
            symbol: 'pin',
            symbolSize: 24,
            animation: false,
            label: {
              fontSize: 9,
              color: '#fff',
            },
            data: values
              .map((v, i) => (v === 1 ? { coord: [i, 1], value: '#1' } : null))
              .filter(Boolean),
          }
        : undefined,
    },
  ]

  if (overlayData && overlayData.length > 0) {
    const overlayMap = new Map(overlayData.map((d) => [d.week, d.rank]))
    const overlayValues = data.map((d) => overlayMap.get(d.week) ?? null)

    series.push({
      name: overlayLabel || '最佳单曲',
      type: 'line',
      data: overlayValues,
      connectNulls: false,
      smooth: false,
      symbol: 'diamond',
      symbolSize: 5,
      showSymbol: totalPoints < 30,
      emphasis: {
        focus: 'series',
        symbolSize: 9,
      },
      lineStyle: {
        width: 1.5,
        color: overlayColor,
        type: 'dashed',
        dashOffset: 2,
      },
      itemStyle: {
        color: overlayColor,
        borderColor: isDark ? '#1C1C20' : '#FFFFFF',
        borderWidth: 2,
      },
    })
  }

  // Compute nice tick values (show rank milestones)
  const tickValues: number[] = [1]
  if (topN >= 5) tickValues.push(5)
  if (topN >= 10) tickValues.push(10)
  if (topN >= 20) tickValues.push(20)
  if (topN >= 30) tickValues.push(30)
  if (topN >= 50) tickValues.push(50)
  if (topN >= 75) tickValues.push(75)
  if (topN >= 100) tickValues.push(100)

  const option = {
    ...base,
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
    grid: {
      ...base.grid,
      left: 8,
      right: 20,
      top: 20,
      bottom: labels.length > 20 ? 40 : 8,
    },
    xAxis: {
      ...base.xAxis,
      data: labels,
      axisLabel: {
        ...base.xAxis.axisLabel,
        interval: labelInterval,
        rotate: labels.length > 30 ? 45 : labels.length > 20 ? 30 : 0,
        fontSize: 10,
      },
    },
    yAxis: {
      ...base.yAxis,
      inverse: true,
      min: 1,
      max: topN,
      interval: undefined,
      axisLabel: {
        color: textColor,
        fontSize: 11,
        formatter: (v: number) => (v === 1 ? '#1' : `#${v}`),
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
          type: 'dashed',
        },
      },
    },
    series,
    tooltip: {
      ...base.tooltip,
      trigger: 'axis',
      padding: [10, 14],
      extraCssText: 'border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12);',
      formatter: (params: any) => {
        const items = Array.isArray(params) ? params : [params]
        if (!items.length) return ''
        const week = items[0].axisValue
        let html = `<div style="font-weight:600;font-size:13px;margin-bottom:6px;font-family:'Inter Variable',sans-serif">${week}</div>`
        items.forEach((p: any) => {
          const val = p.value
          const display = val === null || val === undefined
            ? '<span style="opacity:0.4">—</span>'
            : `<span style="font-weight:600">#${val}</span>`
          html += `<div style="font-size:11px;line-height:1.7;font-family:'Inter Variable',sans-serif">${p.marker} ${p.seriesName}: ${display}</div>`
        })
        return html
      },
    },
    legend: overlayData && overlayData.length > 0
      ? {
          show: true,
          bottom: 0,
          left: 'center',
          textStyle: { color: textColor, fontSize: 11 },
          itemWidth: 16,
          itemHeight: 2,
          icon: 'roundRect',
        }
      : undefined,
  }

  return <ReactECharts option={option} style={{ height: 360 }} notMerge />
}
