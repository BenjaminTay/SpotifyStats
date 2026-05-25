import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ArtistDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatWeekLabel(iso: string): string {
  if (!iso) return ''
  const dateStr = iso.includes(' ') ? iso.split(' ')[0] : iso
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  const end = new Date(d)
  end.setDate(end.getDate() + 6)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} — ${end.getFullYear()}/${end.getMonth() + 1}/${end.getDate()}`
}

function formatWeekStart(iso: string): string {
  if (!iso) return ''
  const dateStr = iso.includes(' ') ? iso.split(' ')[0] : iso
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function formatDateShort(iso: string): string {
  if (!iso) return '—'
  const dateStr = iso.includes(' ') ? iso.split(' ')[0] : iso
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

type TabKey = 'overview' | 'history' | 'tracks'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: '榜单表现' },
  { key: 'history', label: '周榜历史' },
  { key: 'tracks', label: '曲目表现' },
]

function ArtistDetailSkeleton() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-6 h-[44px] w-72" />
      <div className="mb-5 flex gap-7">
        {TABS.map((_, i) => (
          <Skeleton key={i} className="h-6 w-16" />
        ))}
      </div>
      <div className="mb-6 grid grid-cols-4 gap-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="mb-2 h-8 w-16" />
            <Skeleton className="h-3 w-12" />
          </div>
        ))}
      </div>
      <Skeleton className="h-[360px] w-full rounded-[16px]" />
    </>
  )
}

export function ArtistDetailPage() {
  const { artistName } = useParams<{ artistName: string }>()
  const [data, setData] = useState<ArtistDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  const fetchData = useCallback(() => {
    if (!artistName) return
    setLoading(true)
    setError(null)
    api
      .get<ArtistDetailResponse>('/billboard/artist/' + artistName)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [artistName])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const buildNo1Map = () => {
    if (!data) return new Map<string, string>()
    return new Map(
      data.artist_no1_by_week
        .filter((w) => w.no1_count > 0)
        .map((w) => [w.week, w.no1_track_names]),
    )
  }

  return (
    <>
      {loading && <ArtistDetailSkeleton />}

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
              <p className="text-muted-foreground">未找到该艺人的榜单数据</p>
              <Link
                to="/billboard"
                className="rounded-full border border-border px-6 py-2 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                返回 Billboard
              </Link>
            </div>
          ) : (
            <>
              {/* Hero */}
              <section className="mb-6">
                <Link
                  to="/billboard"
                  className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
                >
                  <ArrowLeft className="h-3 w-3" />
                  Billboard / 艺人详情
                </Link>
                <div className="flex items-start gap-6">
                  {data.cover_url && (
                    <img
                      src={data.cover_url}
                      alt={data.artist_name}
                      className="h-[120px] w-[120px] flex-shrink-0 rounded-full object-cover shadow-lg"
                    />
                  )}
                  <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
                    {data.artist_name}
                  </h1>
                </div>
              </section>

              {/* Tabs */}
              <div className="mb-6 flex gap-7 border-b border-border">
                {TABS.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={cn(
                      '-mb-px cursor-pointer border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
                      'border-b-2',
                      activeTab === tab.key
                        ? 'border-accent-foreground font-semibold text-foreground'
                        : 'border-transparent text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab 1: Overview */}
              {activeTab === 'overview' && (
                <>
                  {/* Info KPIs */}
                  <div className="mb-8 grid grid-cols-4 gap-x-6 gap-y-5 border-b border-border pb-8">
                    <KpiItem label="总入榜曲目" value={formatNumber(data.info.total_tracks)} />
                    <KpiItem label="最佳峰值" value={`#${data.info.best_peak}`} accent={data.info.best_peak === 1} />
                    <KpiItem label="总在榜周数" value={formatNumber(data.info.total_weeks)} />
                    <KpiItem label="平均在榜周数" value={String(data.info.avg_weeks)} />
                    <KpiItem label="#1 曲目数" value={formatNumber(data.info.top1)} accent={data.info.top1 > 0} />
                    <KpiItem label="Top 5 曲目数" value={formatNumber(data.info.top5)} />
                    <KpiItem label="Top 10 曲目数" value={formatNumber(data.info.top10)} />
                    <KpiItem label="歌曲冠军周数" value={formatNumber(data.info.weeks_at_no1)} accent={data.info.weeks_at_no1 > 0} />
                  </div>

                  {/* Chart Summary Cards */}
                  {data.chart_summary && (
                    <div className="mb-8 grid grid-cols-3 gap-6">
                      <GlassCard className="p-5">
                        <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                          艺人榜峰值
                        </p>
                        <p className="mt-1 font-serif text-[32px] font-bold leading-none text-accent-foreground">
                          #{data.chart_summary.peak_position}
                        </p>
                        <p className="mt-1 font-sans text-[12px] text-muted-foreground">
                          首次达峰 {formatDateShort(data.chart_summary.first_peak_week)}
                        </p>
                      </GlassCard>
                      <GlassCard className="p-5">
                        <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                          在榜周数
                        </p>
                        <p className="mt-1 font-serif text-[32px] font-bold leading-none">
                          {data.chart_summary.weeks_on_chart}
                        </p>
                        <p className="mt-1 font-sans text-[12px] text-muted-foreground">
                          自 {formatDateShort(data.chart_summary.first_week)}
                        </p>
                      </GlassCard>
                      <GlassCard className="p-5">
                        <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                          Power Score
                        </p>
                        <p className="mt-1 font-serif text-[32px] font-bold leading-none">
                          {formatNumber(data.chart_summary.power_score)}
                        </p>
                        <p className="mt-1 font-sans text-[12px] text-muted-foreground">
                          {data.chart_summary.power_rank ? `走势排名 #${data.chart_summary.power_rank}` : '—'}
                        </p>
                      </GlassCard>
                    </div>
                  )}

                  {/* Rank Trend Chart */}
                  {data.artist_weekly_history.length > 0 && (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">艺人排名趋势</h3>
                      <GlassCard className="p-6">
                        <RankTrendChart
                          data={data.artist_weekly_history.map((e) => ({
                            week: e.week,
                            rank: e.rank,
                          }))}
                          topN={30}
                          peakPosition={data.chart_summary?.peak_position}
                          overlayData={data.best_singles_overlay.length > 0 ? data.best_singles_overlay : undefined}
                          overlayLabel="最佳单曲"
                        />
                      </GlassCard>
                    </div>
                  )}

                  {/* Album #1 */}
                  {data.info.num_no1_albums > 0 && (
                    <GlassCard className="mb-8 p-5">
                      <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                        专辑表现
                      </p>
                      <div className="mt-2 flex gap-6">
                        <p className="font-serif text-[24px] font-semibold">
                          {data.info.num_no1_albums} <span className="font-sans text-[13px] font-normal text-muted-foreground">张 #1 专辑</span>
                        </p>
                        <p className="font-serif text-[24px] font-semibold">
                          {data.info.album_no1_weeks} <span className="font-sans text-[13px] font-normal text-muted-foreground">周冠军</span>
                        </p>
                      </div>
                    </GlassCard>
                  )}
                </>
              )}

              {/* Tab 2: Weekly History */}
              {activeTab === 'history' && (
                <div className="mb-8">
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
                          const maxPlays = Math.max(...data.artist_weekly_history.map((e) => e.play_count), 1)
                          return data.artist_weekly_history.map((entry) => {
                            const change = entry.change
                              ? (() => {
                                  if (entry.change === 'NEW') return { type: 'new' as const }
                                  if (entry.change === 'RE') return { type: 're' as const }
                                  if (entry.change === '—') return { type: 'same' as const }
                                  const match = entry.change.match(/^▲(\d+)$/)
                                  if (match) return { type: 'up' as const, delta: parseInt(match[1]) }
                                  const matchD = entry.change.match(/^▼(\d+)$/)
                                  if (matchD) return { type: 'down' as const, delta: parseInt(matchD[1]) }
                                  return { type: 'same' as const }
                                })()
                              : { type: 'new' as const }
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
              )}

              {/* Tab 3: Tracks */}
              {activeTab === 'tracks' && (
                <div className="mb-8 space-y-8">
                  {/* Tracks table */}
                  <div>
                    <h3 className="mb-4 font-serif text-xl font-semibold">入榜曲目</h3>
                    <GlassCard className="overflow-hidden p-0">
                      <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                        <thead>
                          <tr>
                            <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              曲目
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              峰值
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              在榜
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              峰位周
                            </th>
                            <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              首周
                            </th>
                            <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              末周
                            </th>
                            <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              上榜播放
                            </th>
                            <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              Power Score
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.tracks.map((t) => (
                            <tr
                              key={t.track_id}
                              className="transition-colors hover:bg-muted/50"
                            >
                              <td className="pb-3.5 pt-3.5">
                                <Link
                                  to={`/billboard/track/${t.track_id}`}
                                  className="font-sans text-[14px] font-semibold transition-colors hover:text-accent-foreground"
                                >
                                  {t.track_name}
                                </Link>
                              </td>
                              <td
                                className="pb-3.5 pt-3.5 text-right font-sans text-[13px] font-semibold"
                                style={{ color: t.peak_position === 1 ? 'var(--accent-foreground)' : undefined }}
                              >
                                #{t.peak_position}
                              </td>
                              <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                {t.weeks_on_chart}
                              </td>
                              <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                {t.weeks_at_peak}
                              </td>
                              <td className="pb-3.5 pt-3.5 text-right font-sans text-[12px] text-muted-foreground">
                                {formatDateShort(t.first_week)}
                              </td>
                              <td className="pb-3.5 pt-3.5 text-right font-sans text-[12px] text-muted-foreground">
                                {formatDateShort(t.last_week)}
                              </td>
                              <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] tabular-nums">
                                {formatNumber(t.total_chart_plays)}
                              </td>
                              <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] tabular-nums">
                                {t.power_score > 0 ? (
                                  <>
                                    {t.power_score}
                                    {t.power_rank && (
                                      <span className="ml-1 text-[11px] text-muted-foreground">
                                        #{t.power_rank}
                                      </span>
                                    )}
                                  </>
                                ) : (
                                  '—'
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </GlassCard>
                  </div>

                  {/* Albums table */}
                  {data.albums.length > 0 && (
                    <div>
                      <h3 className="mb-4 font-serif text-xl font-semibold">入榜专辑</h3>
                      <GlassCard className="overflow-hidden p-0">
                        <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                          <thead>
                            <tr>
                              <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                专辑
                              </th>
                              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                峰值
                              </th>
                              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                在榜
                              </th>
                              <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                首周
                              </th>
                              <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                末周
                              </th>
                              <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                总播放
                              </th>
                              <th className="w-20 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                Power Score
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {data.albums.map((a) => (
                              <tr
                                key={`${a.album_name}`}
                                className="transition-colors hover:bg-muted/50"
                              >
                                <td className="pb-3.5 pt-3.5">
                                  <Link
                                    to={`/billboard/album/${encodeURIComponent(a.album_name)}?artist=${encodeURIComponent(data.artist_name)}`}
                                    className="font-sans text-[14px] font-semibold transition-colors hover:text-accent-foreground"
                                  >
                                    {a.album_name}
                                  </Link>
                                </td>
                                <td
                                  className="pb-3.5 pt-3.5 text-right font-sans text-[13px] font-semibold"
                                  style={{ color: a.peak === 1 ? 'var(--accent-foreground)' : undefined }}
                                >
                                  #{a.peak}
                                </td>
                                <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                  {a.weeks}
                                </td>
                                <td className="pb-3.5 pt-3.5 text-right font-sans text-[12px] text-muted-foreground">
                                  {formatDateShort(a.first_week)}
                                </td>
                                <td className="pb-3.5 pt-3.5 text-right font-sans text-[12px] text-muted-foreground">
                                  {formatDateShort(a.last_week)}
                                </td>
                                <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] tabular-nums">
                                  {formatNumber(a.total_plays)}
                                </td>
                                <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] tabular-nums">
                                  {a.power_score > 0 ? (
                                    <>
                                      {a.power_score}
                                      {a.power_rank && (
                                        <span className="ml-1 text-[11px] text-muted-foreground">
                                          #{a.power_rank}
                                        </span>
                                      )}
                                    </>
                                  ) : (
                                    '—'
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </GlassCard>
                    </div>
                  )}
                </div>
              )}

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                {data.artist_name} · 共 {data.info.total_tracks} 首曲目入榜
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
