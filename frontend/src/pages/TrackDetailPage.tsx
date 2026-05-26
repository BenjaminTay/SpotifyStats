import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { TrackDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { displayName } from '@/lib/chinese'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatWeekLabel(iso: string): string {
  if (!iso) return ''
  // Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
  const dateStr = iso.includes(' ') ? iso.split(' ')[0] : iso
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  const end = new Date(d)
  end.setDate(end.getDate() + 6)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} — ${end.getFullYear()}/${end.getMonth() + 1}/${end.getDate()}`
}

function formatDateShort(iso: string): string {
  if (!iso) return '—'
  const dateStr = iso.includes(' ') ? iso.split(' ')[0] : iso
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function formatWeekStart(iso: string): string {
  if (!iso) return ''
  const dateStr = iso.includes(' ') ? iso.split(' ')[0] : iso
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function computeChange(history: TrackDetailResponse['history'], index: number): { type: 'up' | 'down' | 'same' | 'new' | 're'; delta?: number } {
  if (index === 0) return { type: 'new' }
  const prev = history[index - 1]
  const cur = history[index]
  const delta = prev.rank - cur.rank
  if (delta > 0) return { type: 'up', delta }
  if (delta < 0) return { type: 'down', delta: Math.abs(delta) }
  return { type: 'same' }
}

function TrackDetailSkeleton() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-2 h-[44px] w-96" />
      <Skeleton className="mb-8 h-5 w-64" />
      <div className="mb-8 grid grid-cols-4 gap-6">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="mb-2 h-10 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
      <Skeleton className="mb-6 h-[360px] w-full rounded-[16px]" />
      <Skeleton className="h-[400px] w-full rounded-[16px]" />
    </>
  )
}

export function TrackDetailPage() {
  const { trackId } = useParams<{ trackId: string }>()
  const [data, setData] = useState<TrackDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(() => {
    if (!trackId) return
    setLoading(true)
    setError(null)
    api
      .get<TrackDetailResponse>('/billboard/track/' + trackId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [trackId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <>
      {loading && <TrackDetailSkeleton />}

      {error && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <AlertCircle className="h-8 w-8 text-accent-foreground" />
          <p className="text-muted-foreground">加载失败：{error}</p>
          <button
            onClick={fetchData}
            className="rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
          >
            重新加载
          </button>
        </div>
      )}

      {data && !loading && (
        <>
          {!data.found ? (
            <div className="flex flex-col items-center gap-4 py-20 text-center">
              <AlertCircle className="h-8 w-8 text-accent-foreground" />
              <p className="text-muted-foreground">未找到该曲目的榜单数据</p>
              <Link
                to="/billboard"
                className="rounded-full border border-border px-6 py-2 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                返回 Billboard
              </Link>
            </div>
          ) : (
            <>
              {/* Breadcrumb + Hero */}
              <section className="mb-8">
                <Link
                  to="/billboard"
                  className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
                >
                  <ArrowLeft className="h-3 w-3" />
                  Billboard / 单曲详情
                </Link>
                <div className="flex items-start gap-6">
                  {data.cover_url && (
                    <img
                      src={data.cover_url}
                      alt={data.track_name}
                      className="h-[120px] w-[120px] flex-shrink-0 rounded-[12px] object-cover shadow-lg"
                    />
                  )}
                  <div>
                    <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
                      {displayName(data.track_name)}
                    </h1>
                    <p className="mt-2 font-sans text-[17px] text-muted-foreground">
                      {displayName(data.artist_name)}
                    </p>
                  </div>
                </div>
              </section>

              {/* KPI Row — reorganized */}
              <div className="mb-8 grid grid-cols-4 gap-x-10 gap-y-6 border-b border-border pb-8">
                <KpiItem
                  label="入榜峰值"
                  value={`#${data.summary.peak_position}${data.summary.weeks_at_peak > 0 ? ` (${data.summary.weeks_at_peak}wks)` : ''}`}
                  accent={data.summary.peak_position === 1}
                />
                <KpiItem
                  label="在榜周数"
                  value={formatNumber(data.summary.weeks_on_chart)}
                />
                <KpiItem
                  label="首次入榜"
                  value={formatDateShort(data.summary.first_week)}
                />
                <KpiItem
                  label="首次达峰"
                  value={data.summary.first_peak_week ? formatDateShort(data.summary.first_peak_week) : '—'}
                />
                <KpiItem
                  label="总上榜播放"
                  value={formatNumber(data.summary.total_chart_plays)}
                />
                <KpiItem
                  label="总播放次数"
                  value={formatNumber(data.summary.total_plays)}
                />
                <KpiItem
                  label="走势总榜排名"
                  value={data.summary.power_rank ? `#${formatNumber(data.summary.power_rank)}` : '—'}
                />
                <KpiItem
                  label="走势点数"
                  value={formatNumber(data.summary.power_score)}
                  accent
                />
              </div>

              {/* Rank Trend Chart */}
              {data.chart_data.x.length > 0 && (
                <div className="mb-8">
                  <h3 className="mb-4 font-serif text-xl font-semibold">排名趋势</h3>
                  <GlassCard className="p-6">
                    <RankTrendChart
                      data={data.chart_data.x.map((x, i) => ({
                        week: x,
                        rank: data.chart_data.y[i],
                      }))}
                      topN={data.chart_data.top_n}
                      peakPosition={data.chart_data.peak_position}
                    />
                  </GlassCard>
                </div>
              )}

              {/* History Table */}
              <div className="mb-8">
                <h3 className="mb-4 font-serif text-xl font-semibold">榜单历史</h3>
                <GlassCard className="overflow-hidden p-0">
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
                        return data.history.map((entry, i) => {
                          const change = computeChange(data.history, i)
                          const isNewOrRe = change.type === 'new' || change.type === 're'
                          const rankColor = entry.rank === 1 ? 'var(--accent-foreground)' : entry.rank === 2 ? undefined : entry.rank === 3 ? '#C17A4E' : undefined
                          return (
                            <tr
                              key={entry.week}
                              className="transition-colors hover:bg-muted/50"
                            >
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
                                  (isNewOrRe ? entry.rank : entry.running_peak) === 1 ? 'font-bold text-accent-foreground' : 'text-muted-foreground',
                                )}
                              >
                                {isNewOrRe ? entry.rank : entry.running_peak}
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
                </GlassCard>
              </div>

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                共 {data.history.length} 周在榜 · 首发 {data.summary.first_week} · 末次 {data.summary.last_week}
              </p>
            </>
          )}
        </>
      )}
    </>
  )
}

function KpiItem({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div>
      <p className="mb-1.5 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </p>
      <p
        className="font-serif text-[36px] font-bold leading-none tracking-[-0.5px]"
        style={accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
    </div>
  )
}
