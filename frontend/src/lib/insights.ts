import type { MonthlyTrendPoint, HourlyDist } from '@/types/dashboard'

type Season = '春季' | '夏季' | '秋季' | '冬季'

function seasonOf(month: number): Season {
  if (month >= 3 && month <= 5) return '春季'
  if (month >= 6 && month <= 8) return '夏季'
  if (month >= 9 && month <= 11) return '秋季'
  return '冬季'
}

function seasonLabel(season: Season): string {
  return season
}

/** Aggregate all data points by calendar month (1-12), summing plays across years. */
function aggregateByMonth(data: MonthlyTrendPoint[]): Map<number, number> {
  const map = new Map<number, number>()
  for (const p of data) {
    const month = parseInt(p.period.split('-')[1], 10)
    map.set(month, (map.get(month) ?? 0) + p.plays)
  }
  return map
}

/** Aggregate plays by season. */
function aggregateBySeason(byMonth: Map<number, number>): Map<Season, number> {
  const map = new Map<Season, number>()
  for (const [m, plays] of byMonth) {
    const s = seasonOf(m)
    map.set(s, (map.get(s) ?? 0) + plays)
  }
  return map
}

export function generateMonthlyInsight(data: MonthlyTrendPoint[]): string {
  if (data.length < 2) return ''

  const byMonth = aggregateByMonth(data)
  const bySeason = aggregateBySeason(byMonth)

  // Sorted months by total plays
  const ranked = [...byMonth.entries()].sort((a, b) => b[1] - a[1])
  const peakMonth = ranked[0]
  const secondMonth = ranked.length > 1 ? ranked[1] : null
  const lowMonth = ranked[ranked.length - 1]

  // Dominant season
  const seasonRanked = [...bySeason.entries()].sort((a, b) => b[1] - a[1])
  const topSeason = seasonRanked[0]

  // Trend: compare second half vs first half
  const mid = Math.floor(data.length / 2)
  const firstHalf = data.slice(0, mid)
  const secondHalf = data.slice(mid)
  const firstAvg = firstHalf.reduce((s, p) => s + p.plays, 0) / firstHalf.length
  const secondAvg = secondHalf.reduce((s, p) => s + p.plays, 0) / secondHalf.length
  const trendPct = firstAvg > 0 ? ((secondAvg - firstAvg) / firstAvg) * 100 : 0

  let trendText: string
  if (trendPct > 10) {
    trendText = `后期播放量较前期增长${Math.round(trendPct)}%，呈明显上升趋势`
  } else if (trendPct > 3) {
    trendText = `后期播放量较前期增长${Math.round(trendPct)}%，稳中有升`
  } else if (trendPct < -10) {
    trendText = `后期播放量较前期下降${Math.round(Math.abs(trendPct))}%`
  } else if (trendPct < -3) {
    trendText = `后期播放量较前期略有回落`
  } else {
    trendText = '整体播放量走势平稳'
  }

  const parts: string[] = []

  // Seasonal pattern
  const monthsInTopSeason = ranked.filter(([m]) => seasonOf(m) === topSeason[0])

  if (monthsInTopSeason.length >= 2) {
    parts.push(
      `${seasonLabel(topSeason[0])}是聆听的高峰期，${peakMonth[0]}月达到最高（${peakMonth[1].toLocaleString('zh-CN')}次）`,
    )
    if (secondMonth && seasonOf(secondMonth[0]) === topSeason[0]) {
      parts.push(`${secondMonth[0]}月紧随其后（${secondMonth[1].toLocaleString('zh-CN')}次）`)
    }
  } else {
    parts.push(
      `${peakMonth[0]}月是聆听的最高峰（${peakMonth[1].toLocaleString('zh-CN')}次）`,
    )
    if (secondMonth) {
      parts.push(`${secondMonth[0]}月紧随其后（${secondMonth[1].toLocaleString('zh-CN')}次）`)
    }
  }

  parts.push(`${trendText}`)

  // Low month (only mention if notably different from peak)
  if (lowMonth[1] < peakMonth[1] * 0.65) {
    parts.push(`${lowMonth[0]}月为全年最低（${lowMonth[1].toLocaleString('zh-CN')}次）`)
  }

  return parts.join('。') + '。'
}

export function generatePeakHourInsight(hourly: HourlyDist[]): { peak: number; text: string } {
  if (!hourly || hourly.length === 0) return { peak: 0, text: '' }

  // Absolute peak
  const sorted = [...hourly].sort((a, b) => b.count - a.count)
  const peak = sorted[0]

  // Look for secondary peaks in commute bands, excluding the absolute peak
  const morningCommute = hourly.filter(h => h.hour >= 7 && h.hour <= 9 && h.hour !== peak.hour)
  const eveningCommute = hourly.filter(h => h.hour >= 17 && h.hour <= 19 && h.hour !== peak.hour)

  const peakLabel = `${String(peak.hour).padStart(2, '0')}:00`

  let secondary = ''
  if (peak.hour >= 17 && peak.hour <= 22) {
    // Evening peak → look for morning commute
    const morningPeak = morningCommute.sort((a, b) => b.count - a.count)[0]
    if (morningPeak) {
      secondary = `，其次是通勤高峰${String(morningPeak.hour).padStart(2, '0')}:00`
    }
  } else {
    // Morning or other peak → look for evening
    const eveningPeak = eveningCommute.sort((a, b) => b.count - a.count)[0]
    if (eveningPeak) {
      secondary = `，其次是晚间${String(eveningPeak.hour).padStart(2, '0')}:00`
    }
  }

  const text = `一天中${peakLabel}是播放最密集的时段${secondary}`
  return { peak: peak.hour, text }
}
