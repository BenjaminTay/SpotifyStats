import { useEffect, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { ArtistDetailResponse } from '@/types/billboard'
import { EntityStatsPanel, EntityStatsPrefetch } from '@/components/shared/EntityStatsPanel'
import { Skeleton } from '@/components/ui/skeleton'
import { displayName } from '@/lib/chinese'
import { getBillboardName } from '@/lib/billboard-name'
import { AlertCircle } from 'lucide-react'
import { ArtistDetailHero, DetailTabs } from './MusicDetailHeader'
import { ArtistDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicChartEmptyState } from './MusicChartEmptyState'
import { MusicTracksSection } from './MusicTracksSection'
import { ArtistAlbumsSection } from './ArtistAlbumsSection'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileMusicDetailHero, MobileMusicDetailNav } from '@/features/mobile/music/MobileMusicDetail'

type TabKey = 'stats' | 'overview' | 'tracks' | 'albums'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
  { key: 'albums', label: '专辑成绩' },
]

export function ArtistDetailExperience() {
  const { artistName } = useParams<{ artistName: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab: TabKey = TABS.some((tab) => tab.key === requestedTab) ? requestedTab as TabKey : 'stats'
  const isPhone = useViewportMode() === 'phone'
  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams)
    if (tab === 'stats') next.delete('tab')
    else next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams(filters)
  const trackPageSize = isPhone ? 20 : 50
  const trackPageContext = `${artistName ?? ''}:${trackPageSize}`
  const [trackPageState, setTrackPageState] = useState({ context: trackPageContext, page: 1 })
  const trackPage = trackPageState.context === trackPageContext ? trackPageState.page : 1
  const setTrackPage = (page: number) => setTrackPageState({ context: trackPageContext, page })

  const summaryParams = { ...billboardParams, view: 'summary' }
  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? '', summaryParams),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!, summaryParams),
    enabled: !!artistName && !filtersLoading,
  })
  const { data: overviewData, isPending: overviewPending } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? '', { ...billboardParams, view: 'overview' }),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!, { ...billboardParams, view: 'overview' }),
    enabled: activeTab === 'overview' && !!artistName && !filtersLoading,
  })
  const { data: tracksData, isPending: tracksPending } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? '', { ...billboardParams, view: 'tracks', limit: trackPageSize, offset: (trackPage - 1) * trackPageSize }),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!, { ...billboardParams, view: 'tracks', limit: trackPageSize, offset: (trackPage - 1) * trackPageSize }),
    enabled: activeTab === 'tracks' && !!artistName && !filtersLoading,
  })
  const { data: albumsData, isPending: albumsPending } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? '', { ...billboardParams, view: 'albums' }),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!, { ...billboardParams, view: 'albums' }),
    enabled: activeTab === 'albums' && !!artistName && !filtersLoading,
  })
  const isCharted = data?.chart_status === 'charted' || !!data?.chart_summary
  const summaryTrackChartStatus = data?.track_chart_status
  const summaryAlbumChartStatus = data?.album_chart_status

  useEffect(() => {
    if (!data?.found || !artistName || data.artist_name === artistName) return
    const query = searchParams.toString()
    navigate(
      `/music/artists/${encodeURIComponent(data.artist_name)}${query ? `?${query}` : ''}`,
      { replace: true },
    )
  }, [artistName, data?.artist_name, data?.found, navigate, searchParams])

  useEffect(() => {
    if (!requestedTab || TABS.some((tab) => tab.key === requestedTab)) return
    const next = new URLSearchParams(searchParams)
    next.delete('tab')
    setSearchParams(next, { replace: true })
  }, [requestedTab, searchParams, setSearchParams])

  return (
    <>
      {activeTab === 'stats' && artistName && (
        <EntityStatsPrefetch kind="artist" artistName={artistName} />
      )}
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
                返回 {getBillboardName()}
              </button>
            </div>
          ) : (
            <>
              {isPhone ? (
                <div className="mobile-m5-page mobile-music-detail-page" data-mobile-page="artist-detail">
                  <MobileMusicDetailHero
                    kind="artist"
                    title={displayName(data.artist_name)}
                    coverUrl={data.cover_url}
                    meta={data.meta?.genres?.slice(0, 4).join(' · ') || undefined}
                    facts={[
                      { label: '有效播放', value: `${(data.effective_play_count ?? 0).toLocaleString('zh-CN')} 次` },
                      { label: '艺人榜', value: data.chart_summary ? `PK #${data.chart_summary.peak_position}` : '尚未入榜', accent: data.chart_summary?.peak_position === 1 },
                      {
                        label: '入榜歌曲',
                        value: summaryTrackChartStatus == null
                          ? '进入查看'
                          : summaryTrackChartStatus === 'charted'
                            ? `${data.info?.total_tracks ?? 0} 首`
                            : '暂无',
                      },
                      {
                        label: '入榜专辑',
                        value: summaryAlbumChartStatus == null
                          ? '进入查看'
                          : summaryAlbumChartStatus === 'charted'
                            ? `${data.info?.total_albums ?? 0} 张`
                            : '暂无',
                      },
                    ]}
                  />
                </div>
              ) : <ArtistDetailHero data={data} onBack={() => navigate(-1)} />}

              {isPhone ? (
                <MobileMusicDetailNav
                  activeTab={activeTab}
                  primaryTabs={[
                    { key: 'stats', label: '统计' },
                    { key: 'overview', label: '榜单' },
                    { key: 'tracks', label: '歌曲' },
                  ]}
                  moreTabs={[
                    { key: 'albums', label: '专辑', description: '专辑榜成绩与固定走势排名' },
                  ]}
                  scrollable
                  onChange={setActiveTab}
                />
              ) : <DetailTabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />}

              {activeTab === 'overview' && (
                overviewPending || !overviewData
                  ? <Skeleton className="h-[420px] w-full rounded-[16px]" />
                  : <MusicChartOverviewSection
                      kind="artist"
                      chartSummary={overviewData.chart_summary}
                      weeklyHistory={overviewData.artist_weekly_history}
                      bestSinglesOverlay={overviewData.best_singles_overlay}
                      bestAlbumsOverlay={overviewData.best_albums_overlay}
                      effectivePlayCount={overviewData.effective_play_count}
                    />
              )}

              {/* ═══ Tab 2: 单曲成绩 ═══ */}
              {activeTab === 'stats' && (
                <EntityStatsPanel kind="artist" artistName={data?.artist_name} />
              )}

              {activeTab === 'tracks' && (
                tracksPending || !tracksData ? (
                  <Skeleton className="h-[420px] w-full rounded-[16px]" />
                ) : tracksData.track_chart_status === 'charted' && tracksData.info ? (
                  <MusicTracksSection
                    artistName={tracksData.artist_name}
                    info={tracksData.info}
                    tracks={tracksData.tracks}
                    maxChartPlays={tracksData.tracks_max_chart_plays}
                    pagination={{
                      total: tracksData.tracks_total ?? tracksData.tracks.length,
                      page: trackPage,
                      pageSize: trackPageSize,
                      onPageChange: setTrackPage,
                    }}
                  />
                ) : (
                  <MusicChartEmptyState
                    title="暂无歌曲进入单曲榜"
                    description="该艺人目前没有歌曲进入当前单曲榜统计范围。"
                  />
                )
              )}

              {/* ═══ Tab 3: 专辑成绩 ═══ */}
              {activeTab === 'albums' && (
                albumsPending || !albumsData ? (
                  <Skeleton className="h-[420px] w-full rounded-[16px]" />
                ) : albumsData.album_chart_status === 'charted' && albumsData.info ? (
                  <ArtistAlbumsSection
                    artistName={albumsData.artist_name}
                    info={albumsData.info}
                    albums={albumsData.albums}
                  />
                ) : (
                  <MusicChartEmptyState
                    title="暂无专辑进入专辑榜"
                    description="该艺人目前没有专辑进入当前专辑榜统计范围。"
                  />
                )
              )}

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                {displayName(data.artist_name)} ·{' '}
                {isCharted && data.info
                  ? `共 ${data.info.total_tracks} 首曲目入榜`
                  : `已有 ${new Intl.NumberFormat('zh-CN').format(data.effective_play_count ?? 0)} 次有效播放`}
              </p>
            </>
          )}
        </>
      )}
    </>
  )
}
