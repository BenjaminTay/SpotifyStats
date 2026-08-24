import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { cn } from '@/lib/utils'
import {
  KpiCard,
  formatDateShort,
  formatNumber,
  formatTimeSpan,
  formatWeekStart,
} from './MusicDetailPrimitives'
import { MusicChartEmptyState } from './MusicChartEmptyState'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileChartHistoryList } from '@/features/mobile/music/MobileMusicDetail'
import type { DetailYearEndFields } from '@/types/billboard'
import { YearEndHistorySection } from './YearEndHistorySection'
import { YearEndSummaryKpis } from './YearEndSummaryKpis'

type ChartSummary = {
  peak_position: number
  peak_weeks: number
  first_peak_week: string
  weeks_on_chart: number
  first_week: string
  latest_week: string
  power_score: number
  power_rank: number | null
}

type WeeklyHistoryEntry = {
  week: string
  rank: number
  play_count: number
  change: string
  running_peak: number
  running_wks: number
  running_peak_wks: number
}

type ChangeDescriptor =
  | { type: 'new' }
  | { type: 're' }
  | { type: 'same' }
  | { type: 'up'; delta: number }
  | { type: 'down'; delta: number }

function parseChange(change: string | null | undefined): ChangeDescriptor {
  if (!change) return { type: 'new' }
  if (change === 'NEW') return { type: 'new' }
  if (change === 'RE') return { type: 're' }
  if (change === '—') return { type: 'same' }
  const up = change.match(/^▲(\d+)$/)
  if (up) return { type: 'up', delta: parseInt(up[1]) }
  const down = change.match(/^▼(\d+)$/)
  if (down) return { type: 'down', delta: parseInt(down[1]) }
  return { type: 'same' }
}

function rankColor(rank: number): string | undefined {
  if (rank === 1) return 'var(--accent-foreground)'
  if (rank === 3) return '#C17A4E'
  return undefined
}

export function MusicChartOverviewSection({
  kind,
  chartSummary,
  weeklyHistory,
  bestSinglesOverlay,
  bestAlbumsOverlay,
  effectivePlayCount,
  yearEndStatus = 'unavailable',
  yearEndSummary = null,
  yearEndHistory = [],
}: {
  kind: 'artist' | 'album'
  chartSummary: ChartSummary | null
  weeklyHistory: WeeklyHistoryEntry[]
  bestSinglesOverlay: { week: string; rank: number; track_name: string }[]
  bestAlbumsOverlay?: { week: string; rank: number; album_name: string }[]
  effectivePlayCount?: number
  yearEndStatus?: DetailYearEndFields['year_end_status']
  yearEndSummary?: DetailYearEndFields['year_end_summary']
  yearEndHistory?: DetailYearEndFields['year_end_history']
}) {
  const isPhone = useViewportMode() === 'phone'
  const historyPageSize = 50
  const [historyPageState, setHistoryPageState] = useState({ source: weeklyHistory, page: 1 })
  const historyPage = historyPageState.source === weeklyHistory ? historyPageState.page : 1
  const historyPageCount = Math.max(1, Math.ceil(weeklyHistory.length / historyPageSize))
  const safeHistoryPage = Math.min(historyPage, historyPageCount)
  const pagedWeeklyHistory = weeklyHistory.slice(
    (safeHistoryPage - 1) * historyPageSize,
    safeHistoryPage * historyPageSize,
  )
  const setHistoryPage = (page: number) => {
    setHistoryPageState({ source: weeklyHistory, page })
  }
  if (!chartSummary) {
    return (
      <MusicChartEmptyState
        title={kind === 'artist' ? '暂未进入艺人榜' : '暂未进入专辑榜'}
        effectivePlayCount={effectivePlayCount}
      />
    )
  }

  return (
    <>
      <div className={cn('mb-8 grid grid-cols-2 gap-5', isPhone && 'mobile-detail-kpi-grid')}>
        <KpiCard
          label="最高排名"
          value={`#${chartSummary.peak_position}${chartSummary.peak_weeks > 1 ? ` (${chartSummary.peak_weeks}wks)` : ''}`}
          sub={`首次达峰 ${formatDateShort(chartSummary.first_peak_week)}`}
          accent={chartSummary.peak_position === 1}
        />
        <KpiCard
          label="在榜周数"
          value={formatNumber(chartSummary.weeks_on_chart)}
          sub={`首次入榜 ${formatDateShort(chartSummary.first_week)}`}
        />
        <KpiCard
          label="走势点数"
          value={formatNumber(chartSummary.power_score)}
          sub={chartSummary.power_rank ? `走势排名 #${chartSummary.power_rank}` : '—'}
          accentColor="#d94a4a"
        />
        <KpiCard
          label="在榜跨度"
          value={formatTimeSpan(chartSummary.first_week, chartSummary.latest_week)}
          sub={`${formatDateShort(chartSummary.first_week)} — ${formatDateShort(chartSummary.latest_week)}`}
        />
        <YearEndSummaryKpis status={yearEndStatus} summary={yearEndSummary} variant="cards" />
      </div>

      {weeklyHistory.length > 0 && (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">
            {kind === 'artist' ? '艺人排名趋势' : '专辑排名趋势'}
          </h3>
          <GlassCard className={cn('p-6', isPhone && 'mobile-detail-chart-card')}>
            <RankTrendChart
              data={weeklyHistory.map((entry) => ({
                week: entry.week,
                rank: entry.rank,
              }))}
              topN={30}
              peakPosition={chartSummary.peak_position}
              compact={isPhone}
              height={isPhone ? 248 : undefined}
              detailWindowSize={isPhone ? 26 : undefined}
              detailWindowPosition={isPhone ? 'end' : undefined}
              overlays={[
                ...(bestSinglesOverlay.length > 0
                  ? [{
                      name: '最佳单曲' as const,
                      data: bestSinglesOverlay.map((d) => ({
                        week: d.week,
                        rank: d.rank,
                        label: d.track_name,
                      })),
                    }]
                  : []),
                ...(bestAlbumsOverlay && bestAlbumsOverlay.length > 0
                  ? [{
                      name: '最佳专辑' as const,
                      data: bestAlbumsOverlay.map((d) => ({
                        week: d.week,
                        rank: d.rank,
                        label: d.album_name,
                      })),
                    }]
                  : []),
              ]}
            />
          </GlassCard>
        </div>
      )}

      {weeklyHistory.length > 0 && (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">周榜历史</h3>
          {isPhone ? (
            <MobileChartHistoryList entries={weeklyHistory.map((entry) => ({
              week: entry.week,
              rank: entry.rank,
              change: entry.change,
              playCount: entry.play_count,
              runningPeak: entry.running_peak,
              runningWeeks: entry.running_wks,
              runningPeakWeeks: entry.running_peak_wks,
            }))} />
          ) : <GlassCard className="overflow-hidden p-0">
            <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
              <thead>
                <tr>
                  <th className="w-[104px] pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    榜单周
                  </th>
                  <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    排名
                  </th>
                  <th className="w-16 pb-3.5 pt-4 text-center font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    变动
                  </th>
                  <th className="pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    播放
                  </th>
                  <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    PK
                  </th>
                  <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    PK Wks
                  </th>
                  <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    在榜
                  </th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const maxPlays = Math.max(...weeklyHistory.map((entry) => entry.play_count), 1)
                  return pagedWeeklyHistory.map((entry) => {
                    const change = parseChange(entry.change)

                    return (
                      <tr key={entry.week} className="transition-colors hover:bg-muted/50">
                        <td className="pb-3.5 pt-3.5">
                          <Link
                            to={`/billboard?week=${entry.week}`}
                            className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                          >
                            {formatWeekStart(entry.week)}
                          </Link>
                        </td>
                        <td
                          className="pb-3.5 pt-3.5 text-right font-serif text-[22px] font-semibold"
                          style={rankColor(entry.rank) ? { color: rankColor(entry.rank) } : undefined}
                        >
                          {String(entry.rank).padStart(2, '0')}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-center">
                          <ChangeCell change={change} />
                        </td>
                        <td className="pb-3.5 pt-3.5 text-right font-sans text-[15px] font-semibold tabular-nums">
                          {formatNumber(entry.play_count)}
                          <span className="ml-2 inline-block h-[3px] w-[70px] rounded-[2px] bg-muted align-middle">
                            <span
                              className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
                              style={{
                                width: `${Math.round((entry.play_count / maxPlays) * 100)}%`,
                              }}
                            />
                          </span>
                        </td>
                        <td
                          className={cn(
                            'pb-3.5 pt-3.5 text-right font-sans text-[13px]',
                            entry.running_peak === 1
                              ? 'font-bold text-accent-foreground'
                              : 'text-muted-foreground',
                          )}
                        >
                          {entry.running_peak}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                          {entry.running_peak_wks > 0 ? (
                            <span className="font-semibold">{entry.running_peak_wks}</span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                          {entry.running_wks}
                        </td>
                      </tr>
                    )
                  })
                })()}
              </tbody>
            </table>
            {historyPageCount > 1 && (
              <div className="flex items-center justify-between border-t border-border px-7 py-3">
                <span className="text-[12px] text-muted-foreground tabular-nums">
                  显示 {(safeHistoryPage - 1) * historyPageSize + 1}–{Math.min(safeHistoryPage * historyPageSize, weeklyHistory.length)} / 总数 {weeklyHistory.length} 周
                </span>
                <div className="flex items-center gap-2 text-[12px]">
                  <button
                    type="button"
                    disabled={safeHistoryPage <= 1}
                    onClick={() => setHistoryPage(Math.max(1, safeHistoryPage - 1))}
                    className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-30"
                  >
                    上一页
                  </button>
                  <span className="min-w-14 text-center text-muted-foreground tabular-nums">
                    {safeHistoryPage} / {historyPageCount}
                  </span>
                  <button
                    type="button"
                    disabled={safeHistoryPage >= historyPageCount}
                    onClick={() => setHistoryPage(Math.min(historyPageCount, safeHistoryPage + 1))}
                    className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-30"
                  >
                    下一页
                  </button>
                </div>
              </div>
            )}
          </GlassCard>}
        </div>
      )}
      <YearEndHistorySection status={yearEndStatus} history={yearEndHistory} />
    </>
  )
}
