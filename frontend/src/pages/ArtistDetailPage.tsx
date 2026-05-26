import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ArtistDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { CoverCell } from '@/components/shared/CoverCell'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { displayName } from '@/lib/chinese'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
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

function formatTimeSpan(start: string, end: string): string {
  if (!start || !end) return '—'
  const s = new Date(start + 'T00:00:00')
  const e = new Date(end + 'T00:00:00')
  if (isNaN(s.getTime()) || isNaN(e.getTime())) return '—'
  const diffMs = e.getTime() - s.getTime()
  const diffWeeks = Math.round(diffMs / (7 * 24 * 60 * 60 * 1000))
  const totalMonths = (e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth())
  if (totalMonths < 1) return `${diffWeeks} 周`
  const years = Math.floor(totalMonths / 12)
  const months = totalMonths % 12
  if (years > 0 && months > 0) return `${years} 年 ${months} 个月`
  if (years > 0) return `${years} 年`
  return `${months} 个月`
}

type TabKey = 'overview' | 'tracks' | 'albums'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: '榜单表现' },
  { key: 'tracks', label: '单曲成绩' },
  { key: 'albums', label: '专辑成绩' },
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
      <div className="mb-6 grid grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[80px] w-full rounded-[16px]" />
        ))}
      </div>
      <Skeleton className="h-[360px] w-full rounded-[16px]" />
    </>
  )
}

// ── KPI Card ──────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  accent,
  accentColor,
}: {
  label: string
  value: string
  sub?: string
  accent?: boolean
  accentColor?: string
}) {
  return (
    <GlassCard className="p-5">
      <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </p>
      <p
        className="mt-1 font-serif text-[32px] font-bold leading-none"
        style={accentColor ? { color: accentColor } : accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
      {sub && (
        <p className="mt-1 font-sans text-[12px] text-muted-foreground">{sub}</p>
      )}
    </GlassCard>
  )
}

// ── KPI Strip ─────────────────────────────────────────────

function KpiStrip({ items }: { items: { label: string; value: string; accent?: boolean }[] }) {
  return (
    <div className="mb-5 flex flex-wrap gap-x-6 gap-y-2 border-b border-border pb-5">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span className="font-sans text-[11px] font-bold uppercase tracking-[1px] text-muted-foreground">
            {item.label}
          </span>
          <span
            className="font-serif text-[22px] font-bold leading-none"
            style={item.accent ? { color: 'var(--accent-foreground)' } : undefined}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Plays Bar (inline visual) ─────────────────────────────

function PlaysCell({ plays, maxPlays }: { plays: number; maxPlays: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-sans text-[13px] tabular-nums">{formatNumber(plays)}</span>
      <span className="inline-block h-[3px] w-[60px] rounded-[2px] bg-muted align-middle">
        <span
          className="block h-full rounded-[2px] bg-accent-foreground"
          style={{ width: `${Math.round((plays / maxPlays) * 100)}%` }}
        />
      </span>
    </span>
  )
}

// ═══════════════════════════════════════════════════════════
// Page
// ═══════════════════════════════════════════════════════════

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
                    {displayName(data.artist_name)}
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

              {/* ═══ Tab 1: 榜单表现 ═══ */}
              {activeTab === 'overview' && (
                <>
                  {/* KPI Cards — 2 rows × 2 */}
                  {data.chart_summary && (
                    <div className="mb-8 grid grid-cols-2 gap-5">
                      <KpiCard
                        label="最高排名"
                        value={`#${data.chart_summary.peak_position}${data.chart_summary.peak_weeks > 1 ? ` (${data.chart_summary.peak_weeks}wks)` : ''}`}
                        sub={`首次达峰 ${formatDateShort(data.chart_summary.first_peak_week)}`}
                        accent={data.chart_summary.peak_position === 1}
                      />
                      <KpiCard
                        label="在榜周数"
                        value={formatNumber(data.chart_summary.weeks_on_chart)}
                        sub={`首次入榜 ${formatDateShort(data.chart_summary.first_week)}`}
                      />
                      <KpiCard
                        label="走势点数"
                        value={formatNumber(data.chart_summary.power_score)}
                        sub={
                          data.chart_summary.power_rank
                            ? `走势排名 #${data.chart_summary.power_rank}`
                            : '—'
                        }
                        accentColor="#d94a4a"
                      />
                      <KpiCard
                        label="在榜跨度"
                        value={formatTimeSpan(
                          data.chart_summary.first_week,
                          data.chart_summary.latest_week,
                        )}
                        sub={`${formatDateShort(data.chart_summary.first_week)} — ${formatDateShort(data.chart_summary.latest_week)}`}
                      />
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

                  {/* Weekly History Table */}
                  {data.artist_weekly_history.length > 0 && (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">周榜历史</h3>
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
                              const maxPlays = Math.max(
                                ...data.artist_weekly_history.map((e) => e.play_count),
                                1,
                              )
                              return data.artist_weekly_history.map((entry) => {
                                const change = entry.change
                                  ? (() => {
                                      if (entry.change === 'NEW') return { type: 'new' as const }
                                      if (entry.change === 'RE') return { type: 're' as const }
                                      if (entry.change === '—') return { type: 'same' as const }
                                      const match = entry.change.match(/^▲(\d+)$/)
                                      if (match)
                                        return { type: 'up' as const, delta: parseInt(match[1]) }
                                      const matchD = entry.change.match(/^▼(\d+)$/)
                                      if (matchD)
                                        return { type: 'down' as const, delta: parseInt(matchD[1]) }
                                      return { type: 'same' as const }
                                    })()
                                  : { type: 'new' as const }
                                const isNewOrRe = change.type === 'new' || change.type === 're'
                                const rankColor =
                                  entry.rank === 1
                                    ? 'var(--accent-foreground)'
                                    : entry.rank === 2
                                      ? undefined
                                      : entry.rank === 3
                                        ? '#C17A4E'
                                        : undefined

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
                                          style={{
                                            width: `${Math.round((entry.play_count / maxPlays) * 100)}%`,
                                          }}
                                        />
                                      </span>
                                    </td>
                                    <td
                                      className={cn(
                                        'pb-3.5 pt-3.5 text-right font-sans text-[13px]',
                                        (isNewOrRe ? entry.rank : entry.running_peak) === 1
                                          ? 'font-bold text-accent-foreground'
                                          : 'text-muted-foreground',
                                      )}
                                    >
                                      {isNewOrRe ? entry.rank : entry.running_peak}
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
                      </GlassCard>
                    </div>
                  )}
                </>
              )}

              {/* ═══ Tab 2: 单曲成绩 ═══ */}
              {activeTab === 'tracks' && (
                <div className="mb-8">
                  <KpiStrip
                    items={[
                      { label: '入榜曲目', value: formatNumber(data.info.total_tracks) },
                      { label: '#1 曲目', value: formatNumber(data.info.top1), accent: data.info.top1 > 0 },
                      { label: 'Top 5', value: formatNumber(data.info.top5) },
                      { label: 'Top 10', value: formatNumber(data.info.top10) },
                      { label: '冠军周数', value: formatNumber(data.info.weeks_at_no1), accent: data.info.weeks_at_no1 > 0 },
                    ]}
                  />

                  <GlassCard className="overflow-hidden p-0">
                    <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                      <thead>
                        <tr>
                          <th className="w-[44px] pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground" />
                          <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            曲目
                          </th>
                          <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            峰值
                          </th>
                          <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            峰位周
                          </th>
                          <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            在榜
                          </th>
                          <th className="w-28 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            上榜播放
                          </th>
                          <th className="w-[72px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            走势点数
                          </th>
                          <th className="w-[60px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            走势排名
                          </th>
                          <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            首周
                          </th>
                          <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            首次达峰
                          </th>
                          <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            末周
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const maxPlays = Math.max(
                            ...data.tracks.map((t) => t.total_chart_plays),
                            1,
                          )
                          return data.tracks.map((t, i) => (
                            <tr key={t.track_id} className="transition-colors hover:bg-muted/50">
                              <td className="py-3.5 pr-2">
                                <CoverCell index={i} coverUrl={t.cover_url} />
                              </td>
                              <td className="py-3.5 pl-1">
                                <Link
                                  to={`/billboard/track/${t.track_id}`}
                                  className="font-sans text-sm font-semibold leading-snug transition-colors hover:text-accent-foreground"
                                >
                                  {displayName(t.track_name)}
                                </Link>
                                <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                                  {displayName(data.artist_name)}
                                </div>
                              </td>
                              <td
                                className="py-3.5 text-right font-serif text-[22px] font-bold italic"
                                style={{ color: t.peak_position === 1 ? 'var(--accent-foreground)' : undefined }}
                              >
                                {t.peak_position}
                              </td>
                              <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                {t.weeks_at_peak}
                              </td>
                              <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                {t.weeks_on_chart}
                              </td>
                              <td className="py-3.5 text-right">
                                <PlaysCell plays={t.total_chart_plays} maxPlays={maxPlays} />
                              </td>
                              <td className="py-3.5 text-right font-sans text-[13px] tabular-nums">
                                {t.power_score > 0 ? formatNumber(t.power_score) : '—'}
                              </td>
                              <td className="py-3.5 text-right font-serif text-[22px] italic text-muted-foreground">
                                {t.power_rank ?? '—'}
                              </td>
                              <td className="py-3.5 text-right">
                                <Link
                                  to={`/billboard?week=${t.first_week}`}
                                  className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  {formatDateShort(t.first_week)}
                                </Link>
                              </td>
                              <td className="py-3.5 text-right">
                                <Link
                                  to={`/billboard?week=${t.first_peak_week}`}
                                  className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  {formatDateShort(t.first_peak_week)}
                                </Link>
                              </td>
                              <td className="py-3.5 text-right">
                                <Link
                                  to={`/billboard?week=${t.last_week}`}
                                  className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  {formatDateShort(t.last_week)}
                                </Link>
                              </td>
                            </tr>
                          ))
                        })()}
                      </tbody>
                    </table>
                  </GlassCard>
                </div>
              )}

              {/* ═══ Tab 3: 专辑成绩 ═══ */}
              {activeTab === 'albums' && (
                <div className="mb-8">
                  <KpiStrip
                    items={[
                      { label: '#1 专辑', value: formatNumber(data.info.num_no1_albums), accent: data.info.num_no1_albums > 0 },
                      { label: '冠军周数', value: formatNumber(data.info.album_no1_weeks), accent: data.info.album_no1_weeks > 0 },
                      { label: '入榜专辑', value: formatNumber(data.albums.length) },
                    ]}
                  />

                  {data.albums.length > 0 ? (
                    <GlassCard className="overflow-hidden p-0">
                      <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                        <thead>
                          <tr>
                            <th className="w-[44px] pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground" />
                            <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              专辑
                            </th>
                            <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              峰值
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              峰位周
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              在榜
                            </th>
                            <th className="w-28 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              总播放
                            </th>
                            <th className="w-[72px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              走势点数
                            </th>
                            <th className="w-[60px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              走势
                            </th>
                            <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              首周
                            </th>
                            <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              首次达峰
                            </th>
                            <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              末周
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {(() => {
                            const maxPlays = Math.max(
                              ...data.albums.map((a) => a.total_plays),
                              1,
                            )
                            return data.albums.map((a, i) => (
                              <tr key={a.album_name} className="transition-colors hover:bg-muted/50">
                                <td className="py-3.5 pr-2">
                                  <CoverCell index={i} coverUrl={a.cover_url} />
                                </td>
                                <td className="py-3.5 pl-1">
                                  <Link
                                    to={`/billboard/album/${encodeURIComponent(a.album_name)}?artist=${encodeURIComponent(data.artist_name)}`}
                                    className="font-sans text-sm font-semibold leading-snug transition-colors hover:text-accent-foreground"
                                  >
                                    {displayName(a.album_name)}
                                  </Link>
                                  <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                                    {displayName(data.artist_name)}
                                  </div>
                                </td>
                                <td
                                  className="py-3.5 text-right font-serif text-[22px] font-bold italic"
                                  style={{ color: a.peak === 1 ? 'var(--accent-foreground)' : undefined }}
                                >
                                  {a.peak}
                                </td>
                                <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                  {a.pk_wks}
                                </td>
                                <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                  {a.weeks}
                                </td>
                                <td className="py-3.5 text-right">
                                  <PlaysCell plays={a.total_plays} maxPlays={maxPlays} />
                                </td>
                                <td className="py-3.5 text-right font-sans text-[13px] tabular-nums">
                                  {a.power_score > 0 ? formatNumber(a.power_score) : '—'}
                                </td>
                                <td className="py-3.5 text-right font-serif text-[22px] italic text-muted-foreground">
                                  {a.power_rank ?? '—'}
                                </td>
                                <td className="py-3.5 text-right">
                                  <Link
                                    to={`/billboard?week=${a.first_week}`}
                                    className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                  >
                                    {formatDateShort(a.first_week)}
                                  </Link>
                                </td>
                                <td className="py-3.5 text-right">
                                  <Link
                                    to={`/billboard?week=${a.first_peak_week}`}
                                    className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                  >
                                    {formatDateShort(a.first_peak_week)}
                                  </Link>
                                </td>
                                <td className="py-3.5 text-right">
                                  <Link
                                    to={`/billboard?week=${a.last_week}`}
                                    className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                  >
                                    {formatDateShort(a.last_week)}
                                  </Link>
                                </td>
                              </tr>
                            ))
                          })()}
                        </tbody>
                      </table>
                    </GlassCard>
                  ) : (
                    <p className="py-12 text-center font-sans text-[13px] text-muted-foreground">
                      暂无专辑入榜数据
                    </p>
                  )}
                </div>
              )}

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                {displayName(data.artist_name)} · 共 {data.info.total_tracks} 首曲目入榜
              </p>
            </>
          )}
        </>
      )}
    </>
  )
}
