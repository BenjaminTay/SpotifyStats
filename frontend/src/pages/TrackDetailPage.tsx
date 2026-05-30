import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { TrackDetailResponse, LyricsData, TrackEnrichmentResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { FormattedText } from '@/components/shared/FormattedText'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { displayName } from '@/lib/chinese'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
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

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

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

// Module-level enrichment cache — survives navigation away and back
const enrichmentCache = new Map<string, TrackEnrichmentResponse>()

type TabKey = 'stats' | 'lyrics' | 'overview'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'lyrics', label: '歌词' },
  { key: 'overview', label: '榜单成绩' },
]

function TrackDetailSkeleton() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-2 h-[44px] w-96" />
      <Skeleton className="mb-2 h-5 w-64" />
      <Skeleton className="mb-8 h-4 w-80" />
      <div className="mb-5 flex gap-7">
        {TABS.map((_, i) => (
          <Skeleton key={i} className="h-6 w-16" />
        ))}
      </div>
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
  const navigate = useNavigate()
  const [data, setData] = useState<TrackDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('stats')
  const [lyrics, setLyrics] = useState<LyricsData | null>(null)
  const [lyricsLoading, setLyricsLoading] = useState(false)

  // Enrichment (Genius + Wikipedia)
  const [enrichment, setEnrichment] = useState<TrackEnrichmentResponse | null>(null)
  const [enrichmentLoading, setEnrichmentLoading] = useState(false)

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

  const fetchLyrics = useCallback(() => {
    if (!trackId || lyrics) return
    setLyricsLoading(true)
    api
      .get<LyricsData>('/lyrics/' + trackId)
      .then(setLyrics)
      .catch(() => {})
      .finally(() => setLyricsLoading(false))
  }, [trackId, lyrics])

  const fetchEnrichment = useCallback(() => {
    if (!data?.found || enrichment || enrichmentLoading) return
    const cacheKey = `${data.track_name}:${data.artist_name}`
    const cached = enrichmentCache.get(cacheKey)
    if (cached) {
      setEnrichment(cached)
      return
    }
    setEnrichmentLoading(true)
    api
      .get<TrackEnrichmentResponse>('/billboard/enrichment/track/' + encodeURIComponent(data.track_name), {
        artist_name: data.artist_name,
      })
      .then((result) => {
        enrichmentCache.set(cacheKey, result)
        setEnrichment(result)
      })
      .catch(() => setEnrichment(null))
      .finally(() => setEnrichmentLoading(false))
  }, [data, enrichment, enrichmentLoading])

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab)
    if (tab === 'lyrics') {
      fetchLyrics()
      fetchEnrichment()
    }
  }

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
                  Music / 单曲详情
                </button>
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
                          data.meta.spotify_album_name && (
                            <Link
                              key="album"
                              to={`/music/albums/${encodeURIComponent(data.meta.spotify_album_name)}?artist=${encodeURIComponent(data.artist_name)}`}
                              className="transition-colors hover:text-accent-foreground"
                            >
                              {displayName(data.meta.spotify_album_name)}
                            </Link>
                          ),
                          data.meta.track_number && `Track ${data.meta.track_number}`,
                          data.meta.duration_ms && formatDuration(data.meta.duration_ms),
                          data.meta.explicit ? '🅴 Explicit' : null,
                        ].filter(Boolean).reduce<React.ReactNode[]>((acc, item, i) => {
                          if (i === 0) return [item]
                          return [...acc, ' · ', item]
                        }, [])}
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
                    onClick={() => handleTabChange(tab.key)}
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
                  {/* KPI Row */}
                  <div className="mb-8 grid grid-cols-4 gap-x-10 gap-y-6 pb-8">
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
                            return data.history.map((entry) => {
                              const change = parseChange(entry.change)
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

              {activeTab === 'stats' && (
                <EntityStatsPanel kind="track" trackId={trackId} />
              )}

              {/* ═══ Tab 2: 歌词 ═══ */}
              {activeTab === 'lyrics' && (
                <div className="mb-8">
                  {/* Genius Song Info */}
                  {enrichment?.genius && (
                    <div className="mb-6">
                      <h3 className="mb-3 font-serif text-xl font-semibold">歌曲信息</h3>
                      <GlassCard className="p-5">
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                          {enrichment.genius.album_name && (
                            <div>
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                收录专辑
                              </p>
                              <p className="mt-1 font-sans text-[13px] font-semibold">{enrichment.genius.album_name}</p>
                            </div>
                          )}
                          {enrichment.genius.release_date && (
                            <div>
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                发行日期
                              </p>
                              <p className="mt-1 font-sans text-[13px] font-semibold">{enrichment.genius.release_date}</p>
                            </div>
                          )}
                          {data.meta?.popularity != null && (
                            <div>
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                Spotify 流行度
                              </p>
                              <p className="mt-1 font-sans text-[13px] font-semibold">{data.meta.popularity}/100</p>
                            </div>
                          )}
                          {data.meta?.duration_ms && (
                            <div>
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                时长
                              </p>
                              <p className="mt-1 font-sans text-[13px] font-semibold">{formatDuration(data.meta.duration_ms)}</p>
                            </div>
                          )}
                        </div>
                        {enrichment.genius.url && (
                          <a
                            href={enrichment.genius.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-3 inline-flex items-center gap-1.5 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                          >
                            在 Genius 上查看歌曲详情
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </GlassCard>
                    </div>
                  )}

                  {/* Wikipedia Song Info */}
                  {enrichment?.wiki && (
                    <div className="mb-6">
                      <h3 className="mb-3 font-serif text-xl font-semibold">歌曲背景</h3>
                      <GlassCard className="p-5">
                        <FormattedText
                          text={enrichment.wiki.summary_zh || enrichment.wiki.summary || enrichment.wiki.sections_zh?.background || enrichment.wiki.sections.background || '暂无详细信息'}
                          className="font-sans text-[14px] leading-relaxed text-foreground/85"
                        />
                        {enrichment.wiki.url && (
                          <a
                            href={enrichment.wiki.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-3 inline-flex items-center gap-1.5 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                          >
                            在 Wikipedia 上阅读更多
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </GlassCard>
                    </div>
                  )}

                  {lyricsLoading ? (
                    <GlassCard className="p-8">
                      <div className="space-y-3">
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-5/6" />
                        <Skeleton className="h-4 w-4/6" />
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-3/6" />
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-4/6" />
                      </div>
                    </GlassCard>
                  ) : lyrics && lyrics.found ? (
                    <GlassCard className="p-8">
                      <div>
                        {lyrics.lyrics.split('\n').map((line, i) => {
                          const trimmed = line.trim()
                          const isSection = trimmed.startsWith('[') && trimmed.endsWith(']')
                          return (
                            <p
                              key={i}
                              className={
                                isSection
                                  ? 'mt-6 mb-3 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground first:mt-0'
                                  : line === ''
                                    ? 'h-4'
                                    : 'font-serif text-[17px] leading-[1.85]'
                              }
                            >
                              {isSection ? trimmed : (line || ' ')}
                            </p>
                          )
                        })}
                        {lyrics.genius_url && (
                          <a
                            href={lyrics.genius_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-8 inline-flex items-center gap-1.5 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                          >
                            在 Genius 上查看完整歌词
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    </GlassCard>
                  ) : (
                    <GlassCard className="p-8 text-center">
                      <p className="font-sans text-[14px] text-muted-foreground">
                        未找到 Genius 歌词
                      </p>
                    </GlassCard>
                  )}
                </div>
              )}
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
