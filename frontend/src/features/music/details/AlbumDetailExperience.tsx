import { useEffect } from 'react'
import { Link, useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { AlbumDetailResponse } from '@/types/billboard'
import { EntityStatsPanel, EntityStatsPrefetch } from '@/components/shared/EntityStatsPanel'
import { Skeleton } from '@/components/ui/skeleton'
import { displayName } from '@/lib/chinese'
import { getBillboardName } from '@/lib/billboard-name'
import { AlertCircle } from 'lucide-react'
import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'
import { AlbumDetailHero, DetailTabs } from './MusicDetailHeader'
import { AlbumDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicChartEmptyState } from './MusicChartEmptyState'
import { MusicTracksSection } from './MusicTracksSection'
import { VersionGroupSection } from './VersionGroupSection'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileMusicDetailHero, MobileMusicDetailNav } from '@/features/mobile/music/MobileMusicDetail'

type TabKey = 'stats' | 'overview' | 'tracks'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
]

export function AlbumDetailExperience() {
  const { albumName } = useParams<{ albumName: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const artistName = searchParams.get('artist') || ''
  const navigate = useNavigate()
  const mergeLevel = normalizeMergeLevel(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams({ ...filters, merge_level: mergeLevel })

  const requestedTab = searchParams.get('tab')
  const activeTab: TabKey = TABS.some((tab) => tab.key === requestedTab) ? requestedTab as TabKey : 'stats'
  const isPhone = useViewportMode() === 'phone'
  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams)
    if (tab === 'stats') next.delete('tab')
    else next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }

  const summaryParams = { ...billboardParams, artist_name: artistName, view: 'summary' }
  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.albumDetail(albumName ?? '', artistName, mergeLevel, summaryParams),
    queryFn: () => api.get<AlbumDetailResponse>('/billboard/album/' + albumName!, summaryParams),
    enabled: !!albumName && !filtersLoading,
  })
  const { data: overviewData, isPending: overviewPending } = useQuery({
    queryKey: queryKeys.music.albumDetail(albumName ?? '', artistName, mergeLevel, { ...billboardParams, artist_name: artistName, view: 'overview' }),
    queryFn: () => api.get<AlbumDetailResponse>('/billboard/album/' + albumName!, { ...billboardParams, artist_name: artistName, view: 'overview' }),
    enabled: activeTab === 'overview' && !!albumName && !filtersLoading,
  })
  const { data: tracksData, isPending: tracksPending } = useQuery({
    queryKey: queryKeys.music.albumDetail(albumName ?? '', artistName, mergeLevel, { ...billboardParams, artist_name: artistName, view: 'tracks' }),
    queryFn: () => api.get<AlbumDetailResponse>('/billboard/album/' + albumName!, { ...billboardParams, artist_name: artistName, view: 'tracks' }),
    enabled: activeTab === 'tracks' && !!albumName && !filtersLoading,
  })
  const { data: projectData } = useQuery({
    queryKey: queryKeys.music.albumDetail(albumName ?? '', artistName, mergeLevel, { ...billboardParams, artist_name: artistName, view: 'project' }),
    queryFn: () => api.get<AlbumDetailResponse>('/billboard/album/' + albumName!, { ...billboardParams, artist_name: artistName, view: 'project' }),
    enabled: activeTab === 'stats' && data?.found === true && !!albumName && !filtersLoading,
  })
  const isCharted = data?.chart_status === 'charted' || !!data?.chart_summary
  const summaryTrackChartStatus = data?.track_chart_status

  useEffect(() => {
    if (!requestedTab || TABS.some((tab) => tab.key === requestedTab)) return
    const next = new URLSearchParams(searchParams)
    next.delete('tab')
    setSearchParams(next, { replace: true })
  }, [requestedTab, searchParams, setSearchParams])

  return (
    <>
      {activeTab === 'stats' && albumName && (
        <EntityStatsPrefetch kind="album" albumName={albumName} artistName={artistName} mergeLevel={mergeLevel} />
      )}
      {isPending && <AlbumDetailSkeleton />}

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
              <p className="text-muted-foreground">未找到该专辑的榜单数据</p>
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
                <div className="mobile-m5-page mobile-music-detail-page" data-mobile-page="album-detail">
                  <MobileMusicDetailHero
                    kind="album"
                    title={displayName(data.album_name)}
                    coverUrl={data.cover_url}
                    subtitle={<Link to={`/music/artists/${encodeURIComponent(data.artist_name)}`}>{displayName(data.artist_name)}</Link>}
                    meta={data.meta ? [
                      data.meta.release_date,
                      projectData?.album_project?.unique_canonical_songs
                        ? `${projectData.album_project.unique_canonical_songs} 首曲目`
                        : data.meta.total_tracks ? `${data.meta.total_tracks} 首曲目` : null,
                    ].filter(Boolean).join(' · ') : undefined}
                    facts={[
                      { label: '有效播放', value: `${(data.effective_play_count ?? 0).toLocaleString('zh-CN')} 次` },
                      { label: '专辑榜', value: data.chart_summary ? `PK #${data.chart_summary.peak_position}` : '尚未入榜', accent: data.chart_summary?.peak_position === 1 },
                      {
                        label: '成员单曲',
                        value: summaryTrackChartStatus == null
                          ? '进入查看'
                          : summaryTrackChartStatus === 'charted'
                            ? `${data.info?.total_tracks ?? 0} 首入榜`
                            : '暂无入榜',
                      },
                      { label: '走势排名', value: data.chart_summary?.power_rank ? `#${data.chart_summary.power_rank}` : '—' },
                    ]}
                  />
                </div>
              ) : (
                <AlbumDetailHero
                  data={data}
                  onBack={() => navigate(-1)}
                  projectTrackCount={projectData?.album_project?.unique_canonical_songs}
                />
              )}

              {isPhone ? (
                <MobileMusicDetailNav
                  activeTab={activeTab}
                  primaryTabs={[
                    { key: 'stats', label: '统计' },
                    { key: 'overview', label: '榜单' },
                    { key: 'tracks', label: '曲目' },
                  ]}
                  onChange={setActiveTab}
                />
              ) : <DetailTabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />}

              {activeTab === 'overview' && (
                overviewPending || !overviewData
                  ? <Skeleton className="h-[420px] w-full rounded-[16px]" />
                  : <MusicChartOverviewSection
                      kind="album"
                      chartSummary={overviewData.chart_summary}
                      weeklyHistory={overviewData.album_weekly_history}
                      bestSinglesOverlay={overviewData.best_singles_overlay}
                      effectivePlayCount={overviewData.effective_play_count}
                      yearEndStatus={overviewData.year_end_status}
                      yearEndSummary={overviewData.year_end_summary}
                      yearEndHistory={overviewData.year_end_history ?? []}
                    />
              )}

              {activeTab === 'stats' && (
                <>
                  <EntityStatsPanel kind="album" albumName={data.album_name} artistName={data.artist_name} mergeLevel={mergeLevel} releaseDate={data.meta?.release_date} />
                  {projectData?.meta?.release_group && projectData.meta.release_group.versions && projectData.meta.release_group.versions.length >= 2 && (
                    <div className="mt-8">
                      <VersionGroupSection
                        kind="album"
                        data={projectData.meta.release_group}
                        sourceBreakdown={projectData.album_project?.source_breakdown ?? null}
                        collapsible={isPhone}
                      />
                    </div>
                  )}
                </>
              )}

              {activeTab === 'tracks' && (
                tracksPending || !tracksData ? (
                  <Skeleton className="h-[420px] w-full rounded-[16px]" />
                ) : tracksData.track_chart_status === 'charted' && tracksData.info ? (
                  <MusicTracksSection
                    artistName={tracksData.artist_name}
                    info={tracksData.info}
                    tracks={tracksData.tracks}
                  />
                ) : (
                  <MusicChartEmptyState
                    title="暂无歌曲进入单曲榜"
                    description="这张专辑目前没有成员歌曲进入当前单曲榜统计范围。"
                  />
                )
              )}

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                {displayName(data.album_name)} · {displayName(data.artist_name)} ·{' '}
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
