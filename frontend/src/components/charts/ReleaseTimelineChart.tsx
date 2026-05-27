import { lazy, Suspense } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import type { WikiSingle } from '@/types/billboard'

const ReactECharts = lazy(() => import('echarts-for-react'))

interface AlbumHistoryEntry {
  week: string
  rank: number
  play_count: number
}

interface ReleaseTimelineChartProps {
  albumHistory: AlbumHistoryEntry[]
  singlesOverlay: { week: string; rank: number }[]
  wikiSingles: WikiSingle[]
  albumReleaseDate: string  // ISO date like "2020-07-24"
}

function parseWeek(str: string): Date | null {
  const parts = str.split('-')
  if (parts.length !== 3) return null
  const [y, m, d] = parts.map(Number)
  if (isNaN(y) || isNaN(m) || isNaN(d)) return null
  return new Date(y, m - 1, d)
}

function formatWeekISO(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatDateDisplay(date: Date): string {
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
}

/** Parse a Wikipedia-style date like "July 27, 2020" or "27 July 2020" to Date. */
function parseWikiDate(dateStr: string | null): Date | null {
  if (!dateStr) return null
  const cleaned = dateStr.replace(/(\d+)(st|nd|rd|th)/g, '$1')
  const d = new Date(cleaned)
  return isNaN(d.getTime()) ? null : d
}

export function ReleaseTimelineChart({
  albumHistory,
  singlesOverlay,
  wikiSingles,
  albumReleaseDate,
}: ReleaseTimelineChartProps) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)

  // Build complete timeline from the album history
  const dates = albumHistory
    .map((e) => parseWeek(e.week))
    .filter((d): d is Date => d !== null)
    .sort((a, b) => a.getTime() - b.getTime())

  if (dates.length === 0) return null

  const minDate = new Date(dates[0])
  const maxDate = new Date(dates[dates.length - 1])

  // Extend range to include Wikipedia dates
  const releaseDate = albumReleaseDate ? new Date(albumReleaseDate + 'T00:00:00') : null
  for (const s of wikiSingles) {
    const d = parseWikiDate(s.date)
    if (d && d < minDate) minDate.setTime(d.getTime())
    if (d && d > maxDate) maxDate.setTime(d.getTime())
  }
  if (releaseDate && releaseDate < minDate) minDate.setTime(releaseDate.getTime())
  if (releaseDate && releaseDate > maxDate) maxDate.setTime(releaseDate.getTime())

  // Build timeline with 7-day intervals
  const labels: string[] = []
  const albumRanks: (number | null)[] = []
  const albumPlays: (number | null)[] = []
  const singlesRanks: (number | null)[] = []

  const rankByWeek = new Map(albumHistory.map((e) => [e.week, e.rank]))
  const playsByWeek = new Map(albumHistory.map((e) => [e.week, e.play_count]))
  const singlesByWeek = new Map(singlesOverlay.map((e) => [e.week, e.rank]))

  const current = new Date(minDate)
  while (current <= maxDate) {
    const weekStr = formatWeekISO(current)
    labels.push(formatDateDisplay(current))
    albumRanks.push(rankByWeek.has(weekStr) ? rankByWeek.get(weekStr)! : null)
    albumPlays.push(playsByWeek.has(weekStr) ? playsByWeek.get(weekStr)! : null)
    singlesRanks.push(singlesByWeek.has(weekStr) ? singlesByWeek.get(weekStr)! : null)
    current.setDate(current.getDate() + 7)
  }

  const textColor = isDark ? '#A09888' : '#6B5E58'
  const albumRankColor = isDark ? '#D4A84B' : '#B8860B'
  const playColor = isDark ? 'rgba(212, 168, 75, 0.18)' : 'rgba(184, 134, 11, 0.12)'
  const singleLineColor = isDark ? '#7BA587' : '#4A7C59'

  // Build markLines for Wikipedia singles and album release
  const markLines: any[] = []

  if (releaseDate && !isNaN(releaseDate.getTime())) {
    // Find the label index closest to releaseDate
    let releaseIdx = -1
    let minDiff = Infinity
    for (let i = 0; i < labels.length; i++) {
      const parts = labels[i].split('/')
      const labelDate = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
      const diff = Math.abs(labelDate.getTime() - releaseDate.getTime())
      if (diff < minDiff) {
        minDiff = diff
        releaseIdx = i
      }
    }

    if (releaseIdx >= 0) {
      markLines.push({
        name: '专辑发行',
        xAxis: releaseIdx,
        lineStyle: { color: albumRankColor, type: 'solid', width: 1.5, opacity: 0.7 },
        label: { formatter: '专辑发行', position: 'start', fontSize: 10, color: albumRankColor },
      })
    }
  }

  for (const s of wikiSingles) {
    const d = parseWikiDate(s.date)
    if (!d) continue
    let idx = -1
    let minDiff = Infinity
    for (let i = 0; i < labels.length; i++) {
      const parts = labels[i].split('/')
      const labelDate = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
      const diff = Math.abs(labelDate.getTime() - d.getTime())
      if (diff < minDiff) {
        minDiff = diff
        idx = i
      }
    }
    if (idx >= 0) {
      markLines.push({
        name: s.name,
        xAxis: idx,
        lineStyle: { color: singleLineColor, type: 'dotted', width: 1, opacity: 0.5 },
        label: { formatter: s.name, position: 'insideEndTop', fontSize: 9, color: singleLineColor },
      })
    }
  }

  const option: any = {
    ...base,
    tooltip: {
      ...base.tooltip,
      trigger: 'axis',
    },
    legend: {
      show: true,
      bottom: 0,
      textStyle: { color: textColor, fontSize: 11 },
      data: ['专辑排名', '最佳单曲排名', '播放量'],
    },
    grid: {
      left: 50,
      right: 55,
      top: 12,
      bottom: markLines.length > 0 ? 44 : 32,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: textColor } },
      axisLabel: {
        color: textColor,
        fontSize: 10,
        interval: labels.length > 52 ? Math.floor(labels.length / 8) : labels.length > 26 ? Math.floor(labels.length / 6) : 0,
        rotate: labels.length > 26 ? 45 : 0,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '排名',
        inverse: true,
        min: 1,
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLabel: { color: textColor, fontSize: 10 },
        axisLine: { show: false },
        splitLine: { show: false },
      },
      {
        type: 'value',
        name: '播放',
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLabel: { color: textColor, fontSize: 10, formatter: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v) },
        axisLine: { show: false },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '专辑排名',
        type: 'line',
        yAxisIndex: 0,
        data: albumRanks,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2, color: albumRankColor },
        itemStyle: { color: albumRankColor },
        markLine: markLines.length > 0 ? {
          silent: true,
          symbol: 'none',
          animation: false,
          data: markLines,
        } : undefined,
        z: 10,
      },
      {
        name: '最佳单曲排名',
        type: 'line',
        yAxisIndex: 0,
        data: singlesRanks,
        connectNulls: false,
        symbol: 'diamond',
        symbolSize: 6,
        lineStyle: { width: 1.5, color: singleLineColor, type: 'dashed' },
        itemStyle: { color: singleLineColor },
        z: 5,
      },
      {
        name: '播放量',
        type: 'bar',
        yAxisIndex: 1,
        data: albumPlays,
        itemStyle: { color: playColor, borderRadius: [2, 2, 0, 0] },
        barWidth: '70%',
        z: 1,
      },
    ],
  }

  return (
    <Suspense fallback={<div className="h-[380px] animate-pulse rounded-lg bg-muted/40" />}>
      <ReactECharts option={option} style={{ height: 380 }} />
    </Suspense>
  )
}
