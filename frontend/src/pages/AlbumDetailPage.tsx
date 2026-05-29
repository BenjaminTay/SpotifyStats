import { useState, useEffect, useCallback } from 'react'
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { CoverCell } from '@/components/shared/CoverCell'
import { FormattedText } from '@/components/shared/FormattedText'
import { AlbumEnrichmentView } from '@/components/shared/AlbumEnrichmentView'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { ReleaseTimelineChart } from '@/components/charts/ReleaseTimelineChart'
import { displayName } from '@/lib/chinese'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function dateOnly(iso: string): string {
  if (!iso) return ''
  return iso.split('T')[0].split(' ')[0]
}

function formatWeekStart(iso: string): string {
  if (!iso) return ''
  const dateStr = dateOnly(iso)
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return iso
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function formatDateShort(iso: string): string {
  if (!iso) return '—'
  const dateStr = dateOnly(iso)
  const d = new Date(dateStr + 'T00:00:00')
  if (isNaN(d.getTime())) return dateStr || iso
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function formatTimeSpan(start: string, end: string): string {
  if (!start || !end) return '—'
  const s = new Date(dateOnly(start) + 'T00:00:00')
  const e = new Date(dateOnly(end) + 'T00:00:00')
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

function formatReleaseDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const mi = parseInt(m) - 1
  if (mi < 0 || mi >= 12) return iso
  return `${parseInt(d)} ${months[mi]} ${y}`
}

function formatAlbumType(t: string): string {
  switch (t) {
    case 'album': return 'Album'
    case 'single': return 'Single'
    case 'compilation': return 'Compilation'
    default: return t
  }
}

// Module-level enrichment cache — survives page navigation
const enrichmentCache = new Map<string, AlbumEnrichmentResponse>()
const releaseCycleCache = new Map<string, ReleaseCycleAlbumDetailResponse>()

type TabKey = 'overview' | 'stats' | 'tracks' | 'era'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Billboard' },
  { key: 'stats', label: '播放统计' },
  { key: 'tracks', label: '曲目表现' },
  { key: 'era', label: '发行档案' },
]

function AlbumDetailSkeleton() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-2 h-[44px] w-80" />
      <Skeleton className="mb-2 h-5 w-48" />
      <Skeleton className="mb-6 h-4 w-72" />
      <div className="mb-5 flex gap-7">
        <Skeleton className="h-6 w-16" />
        <Skeleton className="h-6 w-16" />
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

// ── Plays Bar ─────────────────────────────────────────────

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

// ── Album Story Card (collapsible) ─────────────────────────

function AlbumStoryCard({
  summary,
  background,
  url,
}: {
  summary: string
  background: string
  url: string
}) {
  const [expanded, setExpanded] = useState(false)
  const text = (background || summary || '').trim()
  if (!text) return null

  const preview = text.slice(0, 280)
  const hasMore = text.length > 280

  return (
    <GlassCard className="p-5">
      <FormattedText
        text={expanded || !hasMore ? text : `${preview}...`}
        className="font-sans text-[14px] leading-relaxed text-foreground/85"
      />
      <div className="mt-3 flex items-center gap-3">
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center gap-1 font-sans text-[12px] font-semibold text-accent-foreground transition-opacity hover:opacity-80"
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                收起
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                展开全文
              </>
            )}
          </button>
        )}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
          >
            <ExternalLink className="h-3 w-3" />
            Wikipedia
          </a>
        )}
      </div>
    </GlassCard>
  )
}

// ── Info Row ────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 font-sans text-[13px] text-foreground/85">{value}</dd>
    </div>
  )
}

// ── Mini Stat ───────────────────────────────────────────────

function MiniStat({
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
      <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </p>
      <p
        className="mt-1 font-serif text-[26px] font-bold leading-none"
        style={accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
    </div>
  )
}

function formatOptionalRank(rank: number | null | undefined): string {
  return rank ? `#${rank}` : '—'
}

function formatHalfLife(weeks: number | null | undefined): string {
  if (weeks == null) return '>24 周'
  return `${weeks} 周`
}

function MatrixCell({ value, max }: { value: number; max: number }) {
  const opacity = value <= 0 ? 0 : 0.15 + 0.75 * (value / Math.max(max, 1))
  return (
    <td className="min-w-12 border-b border-border/50 px-2 py-2 text-right font-sans text-[12px] tabular-nums">
      <span
        className="inline-flex min-w-8 justify-end rounded-[4px] px-1.5 py-0.5"
        style={value > 0 ? { backgroundColor: `rgba(184,134,11,${opacity})` } : undefined}
      >
        {value > 0 ? value : '·'}
      </span>
    </td>
  )
}

// ═══════════════════════════════════════════════════════════
// Page
// ═══════════════════════════════════════════════════════════

export function AlbumDetailPage() {
  const { albumName } = useParams<{ albumName: string }>()
  const [searchParams] = useSearchParams()
  const artistName = searchParams.get('artist') || ''
  const navigate = useNavigate()

  const [data, setData] = useState<AlbumDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  // Enrichment (Wikipedia, Genius) — fetched on demand when user clicks 发行档案 tab
  const [enrichment, setEnrichment] = useState<AlbumEnrichmentResponse | null>(null)
  const [enrichmentLoading, setEnrichmentLoading] = useState(false)
  const [releaseCycle, setReleaseCycle] = useState<ReleaseCycleAlbumDetailResponse | null>(null)
  const [releaseCycleLoading, setReleaseCycleLoading] = useState(false)
  const [releaseCycleError, setReleaseCycleError] = useState<string | null>(null)

  const fetchData = useCallback(() => {
    if (!albumName) return
    setLoading(true)
    setError(null)
    api
      .get<AlbumDetailResponse>('/billboard/album/' + albumName, {
        artist_name: artistName,
      })
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [albumName, artistName])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Fetch enrichment when user switches to the 发行档案 tab (with module-level cache)
  useEffect(() => {
    if (activeTab === 'era' && data?.found && !enrichment && !enrichmentLoading) {
      const cacheKey = `${data.artist_name}:${data.album_name}`
      const cached = enrichmentCache.get(cacheKey)
      if (cached) {
        setEnrichment(cached)
        return
      }
      setEnrichmentLoading(true)
      api
        .get<AlbumEnrichmentResponse>('/billboard/enrichment/album/' + encodeURIComponent(data.album_name), {
          artist_name: data.artist_name,
        })
        .then((result) => {
          enrichmentCache.set(cacheKey, result)
          setEnrichment(result)
        })
        .catch(() => setEnrichment(null))
        .finally(() => setEnrichmentLoading(false))
    }
  }, [activeTab, data, enrichment, enrichmentLoading])

  useEffect(() => {
    if (activeTab === 'era' && data?.found && !releaseCycle && !releaseCycleLoading) {
      const cacheKey = `${data.artist_name}:${data.album_name}`
      const cached = releaseCycleCache.get(cacheKey)
      if (cached) {
        setReleaseCycle(cached)
        return
      }
      setReleaseCycleLoading(true)
      setReleaseCycleError(null)
      api
        .get<ReleaseCycleAlbumDetailResponse>(
          `/billboard/release-cycle/artist/${encodeURIComponent(data.artist_name)}/album/${encodeURIComponent(data.album_name)}`,
          { weeks_before: 12, weeks_after: 24 },
        )
        .then((result) => {
          releaseCycleCache.set(cacheKey, result)
          setReleaseCycle(result)
          if (result.error) setReleaseCycleError(result.error)
        })
        .catch((e: Error) => setReleaseCycleError(e.message))
        .finally(() => setReleaseCycleLoading(false))
    }
  }, [activeTab, data, releaseCycle, releaseCycleLoading])

  return (
    <>
      {loading && <AlbumDetailSkeleton />}

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
              <p className="text-muted-foreground">未找到该专辑的榜单数据</p>
              <button
                onClick={() => navigate(-1)}
                className="rounded-full border border-border px-6 py-2 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                返回 Billboard
              </button>
            </div>
          ) : (
            <>
              {/* Hero */}
              <section className="mb-6">
                <button
                  onClick={() => navigate(-1)}
                  className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
                >
                  <ArrowLeft className="h-3 w-3" />
                  Music / 专辑详情
                </button>
                <div className="flex items-start gap-6">
                  {data.cover_url && (
                    <img
                      src={data.cover_url}
                      alt={data.album_name}
                      className="h-[120px] w-[120px] flex-shrink-0 rounded-[12px] object-cover shadow-lg"
                    />
                  )}
                  <div>
                    <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
                      {displayName(data.album_name)}
                    </h1>
                    <p className="mt-2 font-sans text-[17px] text-muted-foreground">
                      <Link
                        to={`/music/artists/${encodeURIComponent(data.artist_name)}`}
                        className="transition-colors hover:text-accent-foreground"
                      >
                        {displayName(data.artist_name)}
                      </Link>
                    </p>
                    {data.meta && (
                      <p className="mt-1 font-sans text-[14px] text-muted-foreground">
                        {[
                          data.meta.album_type && formatAlbumType(data.meta.album_type),
                          data.meta.release_date && formatReleaseDate(data.meta.release_date),
                          data.meta.total_tracks && `${data.meta.total_tracks} tracks`,
                          data.meta.label,
                        ].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
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
                  {data.album_weekly_history.length > 0 && (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">专辑排名趋势</h3>
                      <GlassCard className="p-6">
                        <RankTrendChart
                          data={data.album_weekly_history.map((e) => ({
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
                  {data.album_weekly_history.length > 0 && (
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
                                ...data.album_weekly_history.map((e) => e.play_count),
                                1,
                              )
                              return data.album_weekly_history.map((entry) => {
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

              {/* ═══ Tab 2: 曲目表现 ═══ */}
              {activeTab === 'stats' && (
                <EntityStatsPanel kind="album" albumName={data.album_name} artistName={data.artist_name} />
              )}

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
                                  to={`/music/tracks/${t.track_id}`}
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

              {/* ═══ Tab 3: 发行档案 ═══ */}
              {activeTab === 'era' && (
                <div className="mb-8">
                  {releaseCycle && !releaseCycle.error && (
                    <>
                      <div className="mb-8">
                        <h3 className="mb-4 font-serif text-xl font-semibold">发行概览</h3>
                        <GlassCard className="p-5">
                          <div className="flex flex-col gap-5 md:flex-row md:items-start">
                            {data.cover_url && (
                              <img
                                src={data.cover_url}
                                alt={data.album_name}
                                className="h-[104px] w-[104px] flex-shrink-0 rounded-[12px] object-cover shadow-md"
                                loading="lazy"
                              />
                            )}
                            <div className="min-w-0 flex-1">
                              <p className="font-serif text-[24px] font-semibold leading-tight">
                                {displayName(releaseCycle.primary_name || releaseCycle.album_name)}
                              </p>
                              <p className="mt-1 font-sans text-[13px] text-muted-foreground">
                                {formatDateShort(releaseCycle.release_date_iso || releaseCycle.release_date)} · {formatAlbumType(releaseCycle.album_type)}
                              </p>
                              <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                                <MiniStat label="主版本" value={displayName(releaseCycle.primary_name || releaseCycle.canonical_name)} />
                                <MiniStat label="合并版本" value={releaseCycle.is_grouped ? `${releaseCycle.group_albums.length}` : '1'} />
                                <MiniStat label="先行单曲" value={formatNumber(releaseCycle.advance_singles.length)} />
                                <MiniStat label="周期窗口" value="发行前后" />
                              </div>
                            </div>
                          </div>
                        </GlassCard>
                      </div>

                      <div className="mb-8 grid grid-cols-2 gap-5 lg:grid-cols-4">
                        <KpiCard
                          label="空降排名"
                          value={formatOptionalRank(releaseCycle.metrics.debut_rank)}
                          sub={`发行周播放 ${formatNumber(releaseCycle.metrics.release_week_plays)}`}
                          accent={releaseCycle.metrics.debut_rank === 1}
                        />
                        <KpiCard
                          label="周期峰值"
                          value={formatOptionalRank(releaseCycle.metrics.peak_rank)}
                          sub={releaseCycle.metrics.weeks_to_peak != null ? `登顶/达峰需 ${releaseCycle.metrics.weeks_to_peak} 周` : '未入专辑榜'}
                          accent={releaseCycle.metrics.peak_rank === 1}
                        />
                        <KpiCard
                          label="半衰期"
                          value={formatHalfLife(releaseCycle.metrics.half_life)}
                          sub={`峰值播放 ${formatNumber(releaseCycle.metrics.peak_play_count)}`}
                        />
                        <KpiCard
                          label="收听冲击力"
                          value={releaseCycle.metrics.artist_impact_fmt ?? '—'}
                          sub={releaseCycle.metrics.market_impact_fmt ? `大盘 ${releaseCycle.metrics.market_impact_fmt}` : undefined}
                          accent
                        />
                      </div>
                    </>
                  )}

                  {/* Release Timeline Chart */}
                  <div className="mb-8">
                    <h3 className="mb-4 font-serif text-xl font-semibold">发行走势</h3>
                    <GlassCard className="p-6">
                      {releaseCycleLoading ? (
                        <Skeleton className="h-[380px] w-full rounded-[12px]" />
                      ) : (
                        <ReleaseTimelineChart
                          albumHistory={
                            releaseCycle && !releaseCycle.error
                              ? releaseCycle.album_ranks.map((e) => ({
                                  week: e.billboard_week,
                                  week_offset: e.week_offset,
                                  rank: e.rank,
                                  play_count: e.play_count,
                                }))
                              : data.album_weekly_history.map((e) => ({
                                  week: e.week,
                                  rank: e.rank,
                                  play_count: e.play_count,
                                }))
                          }
                          singlesOverlay={releaseCycle ? releaseCycle.best_track_ranks?.ranks ?? [] : data.best_singles_overlay}
                          wikiSingles={enrichment?.wiki?.infobox?.singles ?? []}
                          albumReleaseDate={releaseCycle?.release_date_iso ?? data.meta?.release_date ?? ''}
                          albumTimeline={releaseCycle?.album_timeline ?? []}
                          advanceSingleRanks={releaseCycle?.advance_single_ranks ?? []}
                          bestTrackRanks={releaseCycle?.best_track_ranks ?? null}
                        />
                      )}
                      {releaseCycleError && (
                        <p className="mt-2 font-sans text-[11px] text-destructive">
                          发行周期数据加载失败：{releaseCycleError}
                        </p>
                      )}
                      {(releaseCycle || enrichment?.wiki) && (
                        <p className="mt-2 font-sans text-[11px] text-muted-foreground">
                          发行周期来自本地播放数据
                          {enrichment?.wiki && <span> · 单曲发行标记来自 Wikipedia</span>}
                          {(enrichment?.wiki?.infobox?.singles.length ?? 0) > 0 && (
                            <span> · 共识别 {enrichment?.wiki?.infobox?.singles.length} 支单曲</span>
                          )}
                        </p>
                      )}
                    </GlassCard>
                  </div>

                  {releaseCycle && !releaseCycle.error && (
                    <>
                      {(releaseCycle.is_grouped || releaseCycle.advance_singles.length > 0 || (enrichment?.wiki?.infobox?.singles.length ?? 0) > 0) && (
                        <div className="mb-8">
                          <h3 className="mb-4 font-serif text-xl font-semibold">发行构成</h3>
                          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                            {releaseCycle.is_grouped && (
                              <GlassCard className="p-5">
                                <h4 className="mb-3 font-serif text-[18px] font-semibold">版本家族</h4>
                                <p className="font-sans text-[13px] text-muted-foreground">
                                  主版本：{displayName(releaseCycle.primary_name || releaseCycle.canonical_name)}
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  {releaseCycle.group_albums.map((name) => (
                                    <span key={name} className="rounded-full border border-border px-3 py-1 font-sans text-[12px] text-foreground/75">
                                      {displayName(name)}
                                    </span>
                                  ))}
                                </div>
                              </GlassCard>
                            )}
                            {releaseCycle.advance_singles.length > 0 && (
                              <GlassCard className="p-5">
                                <h4 className="mb-3 font-serif text-[18px] font-semibold">先行单曲</h4>
                                <div className="space-y-2">
                                  {releaseCycle.advance_singles.map((single) => (
                                    <div key={`${single.single_name}-${single.release_date}`} className="flex items-center justify-between gap-4 border-b border-border/60 pb-2 last:border-0 last:pb-0">
                                      <span className="font-sans text-[13px] font-semibold">{displayName(single.single_name)}</span>
                                      <span className="font-sans text-[12px] text-muted-foreground">{formatDateShort(single.release_date)}</span>
                                    </div>
                                  ))}
                                </div>
                              </GlassCard>
                            )}
                            {enrichment?.wiki?.infobox?.singles && enrichment.wiki.infobox.singles.length > 0 && (
                              <GlassCard className="p-5">
                                <h4 className="mb-3 font-serif text-[18px] font-semibold">单曲发行</h4>
                                <div className="space-y-2">
                                  {enrichment.wiki.infobox.singles.slice(0, 12).map((s, i) => (
                                    <div key={`${s.name}-${i}`} className="flex items-center justify-between gap-4 border-b border-border/60 pb-2 last:border-0 last:pb-0">
                                      <span className="font-sans text-[13px] font-semibold">{displayName(s.name)}</span>
                                      {s.date && <span className="font-sans text-[12px] text-muted-foreground">{s.date}</span>}
                                    </div>
                                  ))}
                                </div>
                              </GlassCard>
                            )}
                          </div>
                        </div>
                      )}

                      {releaseCycle.track_matrix && (
                        <div className="mb-8">
                          <h3 className="mb-4 font-serif text-xl font-semibold">收听展开</h3>
                          <GlassCard className="overflow-auto p-0">
                            <table className="mx-6 my-0 min-w-full border-collapse">
                              <thead>
                                <tr>
                                  <th className="sticky left-0 bg-card pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                    曲目
                                  </th>
                                  {releaseCycle.track_matrix.weeks.map((week) => (
                                    <th key={week} className="min-w-12 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                      {week >= 0 ? `+${week}` : week}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {(() => {
                                  const max = Math.max(...releaseCycle.track_matrix!.data.flat(), 1)
                                  return releaseCycle.track_matrix!.tracks.map((track, rowIndex) => (
                                    <tr key={track} className="transition-colors hover:bg-muted/40">
                                      <td className="sticky left-0 max-w-[220px] bg-card py-2 pr-4 font-sans text-[12px] font-semibold">
                                        {displayName(track)}
                                      </td>
                                      {releaseCycle.track_matrix!.data[rowIndex].map((value, colIndex) => (
                                        <MatrixCell key={`${track}-${colIndex}`} value={value} max={max} />
                                      ))}
                                    </tr>
                                  ))
                                })()}
                              </tbody>
                            </table>
                          </GlassCard>
                          <p className="mt-2 font-sans text-[11px] text-muted-foreground">数字为距发行周的周播放次数，横轴 0 为发行周。</p>
                        </div>
                      )}

                      {(releaseCycle.catalog_reentries.length > 0 || releaseCycle.bonus_tracks.length > 0) && (
                        <div className="mb-8">
                          <h3 className="mb-4 font-serif text-xl font-semibold">外溢影响</h3>
                          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                            {releaseCycle.catalog_reentries.length > 0 && (
                              <div>
                                <h4 className="mb-3 font-serif text-[18px] font-semibold">老歌回榜</h4>
                              <GlassCard className="overflow-hidden p-0">
                                <table className="mx-6 my-0 w-[calc(100%-48px)] border-collapse">
                                  <tbody>
                                    {releaseCycle.catalog_reentries.map((item) => (
                                      <tr key={`${item.track_name}-${item.reentry_offset}`} className="border-b border-border/60 last:border-0">
                                        <td className="py-3 font-sans text-[13px] font-semibold">{displayName(item.track_name)}</td>
                                        <td className="py-3 font-sans text-[12px] text-muted-foreground">{displayName(item.source_album)}</td>
                                        <td className="py-3 text-right font-sans text-[12px] text-muted-foreground">+{item.reentry_offset} 周</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </GlassCard>
                              </div>
                            )}
                            {releaseCycle.bonus_tracks.length > 0 && (
                              <div>
                                <h4 className="mb-3 font-serif text-[18px] font-semibold">加曲来源</h4>
                              <GlassCard className="overflow-hidden p-0">
                                <table className="mx-6 my-0 w-[calc(100%-48px)] border-collapse">
                                  <tbody>
                                    {releaseCycle.bonus_tracks.slice(0, 12).map((item) => (
                                      <tr key={`${item.track_name}-${item.source_album}`} className="border-b border-border/60 last:border-0">
                                        <td className="py-3 font-sans text-[13px] font-semibold">{displayName(item.track_name)}</td>
                                        <td className="py-3 font-sans text-[12px] text-muted-foreground">{displayName(item.source_album)}</td>
                                        <td className="py-3 text-right font-sans text-[12px] tabular-nums">{formatNumber(item.play_count)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </GlassCard>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {/* Structured enrichment (LLM) or fallback */}
                  {enrichment?.wiki?.structured ? (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">专辑简介</h3>
                      <AlbumEnrichmentView data={enrichment.wiki.structured} />
                      <div className="mt-4">
                        <a
                          href={enrichment.wiki.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Wikipedia
                        </a>
                      </div>
                    </div>
                  ) : (
                    <>
                      {/* Fallback: plain text sections */}
                      {(enrichment?.wiki?.sections?.background || enrichment?.wiki?.summary) && (
                        <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
                          <div>
                            <h3 className="mb-4 font-serif text-xl font-semibold">专辑故事</h3>
                            <AlbumStoryCard
                              summary={enrichment.wiki.summary_zh || enrichment.wiki.summary}
                              background={enrichment.wiki.sections_zh?.background || enrichment.wiki.sections.background}
                              url={enrichment.wiki.url}
                            />
                          </div>
                          <div>
                            <h3 className="mb-4 font-serif text-xl font-semibold">制作信息</h3>
                            <GlassCard className="p-5">
                              <dl className="space-y-3">
                                {enrichment.wiki.infobox.genre && (
                                  <InfoRow label="流派" value={enrichment.wiki.infobox.genre.replace(/^\*\s*/gm, '').replace(/\*/g, ' · ')} />
                                )}
                                {enrichment.wiki.infobox.label && (
                                  <InfoRow label="厂牌" value={enrichment.wiki.infobox.label.replace(/^\*\s*/gm, '').replace(/\*/g, ' · ')} />
                                )}
                                {enrichment.wiki.infobox.producer && (
                                  <InfoRow label="制作人" value={enrichment.wiki.infobox.producer.replace(/^\*\s*/gm, '').replace(/\*/g, ' · ')} />
                                )}
                                {enrichment.wiki.infobox.recorded && (
                                  <InfoRow label="录制" value={enrichment.wiki.infobox.recorded} />
                                )}
                                {enrichment.wiki.infobox.studio && (
                                  <InfoRow label="录音室" value={enrichment.wiki.infobox.studio} />
                                )}
                                {enrichment.wiki.infobox.length && (
                                  <InfoRow label="时长" value={enrichment.wiki.infobox.length} />
                                )}
                                {data.meta?.popularity != null && (
                                  <InfoRow label="Spotify 流行度" value={`${data.meta.popularity}/100`} />
                                )}
                              </dl>
                            </GlassCard>
                          </div>
                        </div>
                      )}
                      {enrichment?.wiki?.sections?.reception && (
                        <div className="mb-8">
                          <h3 className="mb-4 font-serif text-xl font-semibold">专业评价</h3>
                          <AlbumStoryCard
                            summary=""
                            background={enrichment.wiki.sections_zh?.reception || enrichment.wiki.sections.reception}
                            url={enrichment.wiki.url}
                          />
                        </div>
                      )}
                    </>
                  )}

                  {/* Personal Story */}
                  <div className="mb-8">
                    <h3 className="mb-4 font-serif text-xl font-semibold">你的收听故事</h3>
                    <GlassCard className="p-5">
                      <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
                        <MiniStat
                          label="首次收听"
                          value={(() => {
                            const firstWeek = data.album_weekly_history[0]
                            return firstWeek ? formatDateShort(firstWeek.week) : '—'
                          })()}
                        />
                        <MiniStat
                          label="总播放次数"
                          value={formatNumber(
                            data.album_weekly_history.reduce((sum, e) => sum + e.play_count, 0)
                          )}
                        />
                        <MiniStat
                          label="在榜周数"
                          value={formatNumber(data.chart_summary.weeks_on_chart)}
                        />
                        <MiniStat
                          label="最高排名"
                          value={`#${data.chart_summary.peak_position}`}
                          accent={data.chart_summary.peak_position === 1}
                        />
                      </div>
                    </GlassCard>
                  </div>
                </div>
              )}

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                {displayName(data.album_name)} · {displayName(data.artist_name)} · 共{' '}
                {data.info.total_tracks} 首曲目入榜
              </p>
            </>
          )}
        </>
      )}
    </>
  )
}
