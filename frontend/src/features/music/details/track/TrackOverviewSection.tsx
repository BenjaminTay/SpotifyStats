import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { KpiCard, formatNumber, formatDateShort, formatWeekStart } from '../MusicDetailPrimitives'
import { cn } from '@/lib/utils'
import type { TrackDetailResponse } from '@/types/billboard'
import { MusicChartEmptyState } from '../MusicChartEmptyState'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileChartHistoryList } from '@/features/mobile/music/MobileMusicDetail'
import { weeklyChartHref } from '@/features/billboard/weekly/weeklyPresentation'
import { YearEndHistorySection } from '../YearEndHistorySection'
import { YearEndSummaryKpis } from '../YearEndSummaryKpis'

function parseChange(change: string | undefined): { type: 'up' | 'down' | 'same' | 'new' | 're'; delta?: number } {
  if (change === 'NEW') return { type: 'new' }
  if (change === 'RE') return { type: 're' }
  if (change === '─' || change === '—') return { type: 'same' }
  const up = change?.match(/^▲(\d+)$/)
  if (up) return { type: 'up', delta: parseInt(up[1]) }
  const down = change?.match(/^▼(\d+)$/)
  if (down) return { type: 'down', delta: parseInt(down[1]) }
  return { type: 'same' }
}

interface Props {
  data: TrackDetailResponse
}

export function TrackOverviewSection({ data }: Props) {
  const isPhone = useViewportMode() === 'phone'
  const hasYearEndSummary = data.year_end_status === 'ready' && data.year_end_summary != null
  if (data.chart_status === 'not_charted' || !data.summary) {
    return (
      <MusicChartEmptyState
        title="暂未进入单曲榜"
        effectivePlayCount={data.effective_play_count}
      />
    )
  }

  return (
    <>
      {/* KPI Row */}
      <div
        data-music-chart-kpi-grid
        data-track-chart-kpi-grid
        className={cn(
          'mb-8 grid grid-cols-2 gap-5',
          hasYearEndSummary ? 'lg:grid-cols-3' : 'lg:grid-cols-4',
          isPhone && 'mobile-detail-kpi-grid',
        )}
      >
        <KpiCard
          label="最高排名"
          value={`#${data.summary.peak_position}${data.summary.weeks_at_peak > 0 ? ` (${data.summary.weeks_at_peak}wks)` : ''}`}
          sub={`首次达峰 ${data.summary.first_peak_week ? formatDateShort(data.summary.first_peak_week) : '—'}`}
          accent={data.summary.peak_position === 1}
        />
        <KpiCard
          label="在榜周数"
          value={formatNumber(data.summary.weeks_on_chart)}
          sub={`首次入榜 ${formatDateShort(data.summary.first_week)}`}
        />
        <KpiCard
          label="走势点数"
          value={formatNumber(data.summary.power_score)}
          sub={data.summary.power_rank ? `走势排名 #${formatNumber(data.summary.power_rank)}` : '—'}
          accentColor="#d94a4a"
        />
        <KpiCard
          label="总上榜播放"
          value={formatNumber(data.summary.total_chart_plays)}
          sub={`总播放 ${formatNumber(data.summary.total_plays)}`}
        />
        <YearEndSummaryKpis status={data.year_end_status} summary={data.year_end_summary} variant="cards" />
      </div>

      {/* Rank Trend Chart */}
      {data.chart_data.x.length > 0 && (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">排名趋势</h3>
          <GlassCard className={cn('p-6', isPhone && 'mobile-detail-chart-card')}>
            <RankTrendChart
              data={data.chart_data.x.map((x, i) => ({
                week: x,
                rank: data.chart_data.y[i],
              }))}
              topN={data.chart_data.top_n}
              peakPosition={data.chart_data.peak_position}
              compact={isPhone}
              height={isPhone ? 248 : undefined}
              detailWindowSize={isPhone ? 26 : undefined}
              detailWindowPosition={isPhone ? 'end' : undefined}
            />
          </GlassCard>
        </div>
      )}

      {/* History Table */}
      <div className="mb-8">
        <h3 className="mb-4 font-serif text-xl font-semibold">周榜历史</h3>
        {isPhone ? (
          <MobileChartHistoryList
            tab="tracks"
            entries={data.history.map((entry) => ({
              week: entry.week,
              rank: entry.rank,
              change: entry.change,
              playCount: entry.play_count,
              runningPeak: entry.running_peak,
              runningWeeks: entry.running_wks,
              runningPeakWeeks: entry.running_peak_wks,
            }))}
          />
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
                const maxPlays = Math.max(...data.history.map((e) => e.play_count), 1)
                return data.history.map((entry) => {
                  const change = parseChange(entry.change)
                  const rankColor = entry.rank === 1 ? 'var(--accent-foreground)' : entry.rank === 2 ? undefined : entry.rank === 3 ? '#C17A4E' : undefined
                  return (
                    <tr
                      key={entry.week}
                      className="transition-colors hover:bg-muted/50"
                    >
                      <td className="pb-3.5 pt-3.5">
                        <Link
                          to={weeklyChartHref(entry.week, 'tracks')}
                          className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                        >
                          {formatWeekStart(entry.week)}
                        </Link>
                      </td>
                      <td
                        className="pb-3.5 pt-3.5 text-right font-serif text-[22px] font-semibold"
                        style={rankColor ? { color: rankColor } : undefined}
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
                            style={{ width: `${Math.round((entry.play_count / maxPlays) * 100)}%` }}
                          />
                        </span>
                      </td>
                      <td
                        className={cn(
                          'pb-3.5 pt-3.5 text-right font-sans text-[13px]',
                          entry.running_peak === 1 ? 'font-bold text-accent-foreground' : 'text-muted-foreground',
                        )}
                      >
                        {entry.running_peak}
                      </td>
                      <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                        {entry.running_peak_wks > 0 ? (
                          <span className="font-semibold">{entry.running_peak_wks}</span>
                        ) : '—'}
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
        </GlassCard>}
      </div>

      <p className="mb-8 mt-6 font-serif text-[13px] italic text-muted-foreground">
        共 {data.history.length} 周在榜 · 首发 {data.summary.first_week} · 末次 {data.summary.last_week}
      </p>

      <YearEndHistorySection
        status={data.year_end_status ?? 'unavailable'}
        history={data.year_end_history ?? []}
        kind="track"
        bestYear={data.year_end_summary?.best_year}
      />
    </>
  )
}
