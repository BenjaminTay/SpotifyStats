import { useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { ArtistDetailResponse, ArtistEnrichmentResponse, ReleaseCycleArtistOverviewResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { CoverCell } from '@/components/shared/CoverCell'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { displayName } from '@/lib/chinese'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'
import {
  KpiCard,
  dateOnly,
  formatDateShort,
  formatNumber,
  formatTimeSpan,
} from './MusicDetailPrimitives'
import { ReleaseCycleSection } from './ArtistReleaseCycleSection'
import { ArtistDetailHero, DetailTabs } from './MusicDetailHeader'
import { ArtistDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicTracksSection } from './MusicTracksSection'
import { ArtistAlbumsSection } from './ArtistAlbumsSection'
import { ArtistCareerSection } from './ArtistCareerSection'

type ReleaseCoverSource = {
  cover_url?: string | null
  db_album_id?: number | null
}

function releaseCoverUrl(item: ReleaseCoverSource): string | null {
  if (item.cover_url) return item.cover_url
  if (item.db_album_id != null) return `/covers/albums/${item.db_album_id}.jpg`
  return null
}

type TabKey = 'stats' | 'releases' | 'career' | 'overview' | 'tracks' | 'albums'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'releases', label: '发行周期' },
  { key: 'career', label: '艺人生涯' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
  { key: 'albums', label: '专辑成绩' },
]

function formatReleaseType(type: string): string {
  if (type === 'album') return '专辑'
  if (type === 'single') return '单曲'
  return type
}

export function ArtistDetailExperience() {
  const { artistName } = useParams<{ artistName: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabKey>(
    (searchParams.get('tab') as TabKey | null) ?? 'stats',
  )

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? ''),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!),
    enabled: !!artistName,
  })

  const releaseCycleParams = { weeks_before: 4, weeks_after: 24, cover_version: 2 }
  const {
    data: enrichment = null,
    isFetching: enrichmentLoading,
  } = useQuery({
    queryKey: queryKeys.music.artistEnrichment(data?.artist_name ?? ''),
    queryFn: () =>
      api.get<ArtistEnrichmentResponse>(
        '/billboard/enrichment/artist/' + encodeURIComponent(data!.artist_name),
      ),
    enabled: activeTab === 'career' && !!data?.found,
  })
  const {
    data: releaseCycle = null,
    isFetching: releaseCycleLoading,
    error: releaseCycleQueryError,
  } = useQuery({
    queryKey: queryKeys.music.artistReleaseCycle(data?.artist_name ?? '', releaseCycleParams),
    queryFn: () =>
      api.get<ReleaseCycleArtistOverviewResponse>(
        '/billboard/release-cycle/artist/' + encodeURIComponent(data!.artist_name),
        { weeks_before: 4, weeks_after: 24 },
      ),
    enabled: activeTab === 'releases' && !!data?.found,
  })
  const releaseCycleError = releaseCycleQueryError?.message || null

  const releaseCycles = releaseCycle?.cycles ?? []
  const albumReleaseCycles = releaseCycles.filter((cycle) => cycle.album_type === 'album')
  const singleReleaseCycles = releaseCycles.filter((cycle) => cycle.album_type === 'single')
  const releaseTrendPoints = releaseCycle?.rank_trend
    .filter((entry) => entry.rank != null)
    .map((entry) => ({
      week: dateOnly(entry.billboard_week),
      rank: entry.rank,
    })) ?? []

  return (
    <>
      {isPending && <ArtistDetailSkeleton />}

      {error && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <AlertCircle className="h-8 w-8 text-accent-foreground" />
          <p className="text-muted-foreground">加载失败：{error.message}</p>
          <button
            onClick={() => refetch()}
            className="rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
          >
            重新加载
          </button>
        </div>
      )}

      {data && !isPending && (
        <>
          {!data.found ? (
            <div className="flex flex-col items-center gap-4 py-20 text-center">
              <AlertCircle className="h-8 w-8 text-accent-foreground" />
              <p className="text-muted-foreground">未找到该艺人的榜单数据</p>
              <button
                onClick={() => navigate(-1)}
                className="rounded-full border border-border px-6 py-2 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                返回 Billboard
              </button>
            </div>
          ) : (
            <>
              <ArtistDetailHero data={data} onBack={() => navigate(-1)} />
              <DetailTabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

              {activeTab === 'overview' && (
                <MusicChartOverviewSection
                  kind="artist"
                  chartSummary={data.chart_summary}
                  weeklyHistory={data.artist_weekly_history}
                  overlayData={data.best_singles_overlay}
                />
              )}

              {/* ═══ Tab 2: 单曲成绩 ═══ */}
              <div className={activeTab === 'stats' ? '' : 'hidden'}>
                <EntityStatsPanel kind="artist" artistName={data?.artist_name} />
              </div>

              {activeTab === 'tracks' && (
                <MusicTracksSection
                  artistName={data.artist_name}
                  info={data.info}
                  tracks={data.tracks}
                />
              )}

              {/* ═══ Tab 3: 专辑成绩 ═══ */}
              {activeTab === 'albums' && (
                <ArtistAlbumsSection
                  artistName={data.artist_name}
                  info={data.info}
                  albums={data.albums}
                />
              )}

              {/* ═══ Tab 4: 发行周期 ═══ */}
              {activeTab === 'releases' && (
                <div className="mb-8">
                  {releaseCycleLoading ? (
                    <div className="space-y-4">
                      <Skeleton className="h-[112px] w-full rounded-[16px]" />
                      <Skeleton className="h-[340px] w-full rounded-[16px]" />
                    </div>
                  ) : releaseCycleError ? (
                    <GlassCard className="p-8 text-center">
                      <p className="font-sans text-[14px] text-destructive">
                        发行周期数据加载失败：{releaseCycleError}
                      </p>
                    </GlassCard>
                  ) : releaseCycle?.summary ? (
                    <>
                      <div className="mb-8 grid grid-cols-2 gap-5 lg:grid-cols-4">
                        <KpiCard
                          label="发行总数"
                          value={`${releaseCycle.summary.total_albums}/${releaseCycle.summary.total_singles}`}
                          sub="专辑 / 单曲"
                        />
                        <KpiCard
                          label="空冠发行"
                          value={`${releaseCycle.summary.album_debut_no1_count + releaseCycle.summary.single_debut_no1_count}`}
                          sub={`专辑 ${releaseCycle.summary.album_debut_no1_count} · 单曲 ${releaseCycle.summary.single_debut_no1_count}`}
                          accent={releaseCycle.summary.album_debut_no1_count + releaseCycle.summary.single_debut_no1_count > 0}
                        />
                        <KpiCard
                          label="同周双空冠"
                          value={formatNumber(releaseCycle.summary.double_debut_count)}
                          sub="单曲榜与专辑榜同周空冠"
                          accent={releaseCycle.summary.double_debut_count > 0}
                        />
                        <KpiCard
                          label="老歌回榜"
                          value={formatNumber(releaseCycle.summary.total_catalog_reentries)}
                          sub="新发行带动旧作回流"
                        />
                        <KpiCard
                          label="最大艺人冲击"
                          value={releaseCycle.summary.max_artist_impact_fmt ?? '—'}
                          sub={releaseCycle.summary.max_artist_impact_album ? displayName(releaseCycle.summary.max_artist_impact_album) : undefined}
                          accent
                        />
                        <KpiCard
                          label="最大大盘冲击"
                          value={releaseCycle.summary.max_market_impact_fmt ?? '—'}
                          sub={releaseCycle.summary.max_market_impact_album ? displayName(releaseCycle.summary.max_market_impact_album) : undefined}
                        />
                        <KpiCard
                          label="发行事件"
                          value={formatNumber(releaseCycle.release_events.length)}
                          sub="落在播放历史附近的发行"
                        />
                        <KpiCard
                          label="统计跨度"
                          value={formatTimeSpan(releaseCycle.first_play_week ?? '', releaseCycle.last_play_week ?? '')}
                          sub={releaseCycle.first_play_week && releaseCycle.last_play_week ? `${formatDateShort(releaseCycle.first_play_week)} — ${formatDateShort(releaseCycle.last_play_week)}` : undefined}
                        />
                      </div>

                      <div className="mb-8">
                        <h3 className="mb-4 font-serif text-xl font-semibold">发行事件与艺人走势</h3>
                        <GlassCard className="p-6">
                          {releaseTrendPoints.length > 0 ? (
                            <RankTrendChart data={releaseTrendPoints} topN={30} />
                          ) : (
                            <div className="flex h-[220px] items-center justify-center rounded-[12px] border border-dashed border-border">
                              <p className="font-sans text-[13px] text-muted-foreground">
                                当前筛选范围内没有艺人榜排名点。
                              </p>
                            </div>
                          )}
                          {releaseCycle.release_events.length > 0 && (
                            <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
                              {releaseCycle.release_events.slice(0, 12).map((event, index) => (
                                <div
                                  key={`${event.album_name}-${event.release_date}`}
                                  className="flex items-center gap-3 rounded-[10px] border border-border/70 p-3"
                                >
                                  <CoverCell index={index} coverUrl={releaseCoverUrl(event)} />
                                  <div className="min-w-0">
                                    <p className="truncate font-sans text-[13px] font-semibold">
                                      {displayName(event.album_name)}
                                    </p>
                                    <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">
                                      {formatDateShort(event.release_date)} · {formatReleaseType(event.album_type)}
                                    </p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </GlassCard>
                      </div>

                      <div className="mb-8">
                        <h3 className="mb-4 font-serif text-xl font-semibold">发行列表</h3>
                        {albumReleaseCycles.length > 0 && (
                          <ReleaseCycleSection
                            title="专辑"
                            cycles={albumReleaseCycles}
                            artistName={data.artist_name}
                          />
                        )}
                        {singleReleaseCycles.length > 0 && (
                          <ReleaseCycleSection
                            title="单曲"
                            cycles={singleReleaseCycles}
                            artistName={data.artist_name}
                            startIndex={albumReleaseCycles.length}
                          />
                        )}
                      </div>
                    </>
                  ) : (
                    <GlassCard className="p-8 text-center">
                      <p className="font-sans text-[14px] text-muted-foreground">
                        未找到发行周期数据，可能缺少 Spotify 专辑元数据。
                      </p>
                    </GlassCard>
                  )}
                </div>
              )}

              {activeTab === 'career' && (
                <ArtistCareerSection
                  enrichment={enrichment}
                  enrichmentLoading={enrichmentLoading}
                  meta={data.meta}
                />
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
