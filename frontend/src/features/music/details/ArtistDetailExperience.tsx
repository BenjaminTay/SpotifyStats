import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { ArtistDetailResponse, ArtistEnrichmentResponse, ReleaseCycleArtistOverviewResponse } from '@/types/billboard'
import type { AiTaskRun } from '@/types/ai-tasks'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { displayName } from '@/lib/chinese'
import { getBillboardName } from '@/lib/billboard-name'
import { AlertCircle } from 'lucide-react'
import { useAiTask, useStartArtistEnrichmentTask } from '@/hooks/useAiTasks'
import { ArtistDetailHero, DetailTabs } from './MusicDetailHeader'
import { ArtistDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicChartEmptyState } from './MusicChartEmptyState'
import { MusicTracksSection } from './MusicTracksSection'
import { ArtistAlbumsSection } from './ArtistAlbumsSection'
import { ArtistCareerSection } from './ArtistCareerSection'
import { ArtistReleasesSection } from './ArtistReleasesSection'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileMusicDetailHero, MobileMusicDetailNav } from '@/features/mobile/music/MobileMusicDetail'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

type TabKey = 'stats' | 'releases' | 'career' | 'overview' | 'tracks' | 'albums'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'releases', label: '发行周期' },
  { key: 'career', label: '艺人生涯' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
  { key: 'albums', label: '专辑成绩' },
]

function artistEnrichmentFromTask(task: AiTaskRun | null): ArtistEnrichmentResponse | null {
  if (task?.status !== 'done' || !task.result || Array.isArray(task.result)) return null
  return task.result as ArtistEnrichmentResponse
}

export function ArtistDetailExperience() {
  const { capabilities } = useRuntimeCapabilities()
  const { artistName } = useParams<{ artistName: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const availableTabs = capabilities.ai ? TABS : TABS.filter((tab) => tab.key !== 'career')
  const activeTab: TabKey = availableTabs.some((tab) => tab.key === requestedTab) ? requestedTab as TabKey : 'stats'
  const isPhone = useViewportMode() === 'phone'
  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams)
    if (tab === 'stats') next.delete('tab')
    else next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams(filters)

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? '', billboardParams),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!, billboardParams),
    enabled: !!artistName && !filtersLoading,
  })
  const isCharted = data?.chart_status === 'charted' || !!data?.chart_summary
  const hasTrackChart = data?.track_chart_status === 'charted' || Boolean(data?.tracks.length)
  const hasAlbumChart = data?.album_chart_status === 'charted' || Boolean(data?.albums.length)

  const [artistEnrichmentTaskId, setArtistEnrichmentTaskId] = useState<string | null>(null)
  const artistEnrichmentStartedKeyRef = useRef<string | null>(null)
  const {
    mutateAsync: startArtistEnrichmentTask,
    isPending: artistEnrichmentStarting,
  } = useStartArtistEnrichmentTask()
  const artistEnrichmentTask = useAiTask(artistEnrichmentTaskId)

  const releaseCycleParams = { ...billboardParams, weeks_before: 4, weeks_after: 24, cover_version: 2 }
  const {
    data: releaseCycle = null,
    isFetching: releaseCycleLoading,
    error: releaseCycleQueryError,
  } = useQuery({
    queryKey: queryKeys.music.artistReleaseCycle(data?.artist_name ?? '', releaseCycleParams),
    queryFn: () =>
      api.get<ReleaseCycleArtistOverviewResponse>(
        '/billboard/release-cycle/artist/' + encodeURIComponent(data!.artist_name),
        releaseCycleParams,
      ),
    enabled: activeTab === 'releases' && !!data?.found,
  })
  const releaseCycleError = releaseCycleQueryError?.message || null
  const enrichment = artistEnrichmentFromTask(artistEnrichmentTask.task)
  const enrichmentLoading =
    artistEnrichmentStarting ||
    (Boolean(artistEnrichmentTaskId) && artistEnrichmentTask.loading && !artistEnrichmentTask.task)

  useEffect(() => {
    if (!data?.found || !artistName || data.artist_name === artistName) return
    const query = searchParams.toString()
    navigate(
      `/music/artists/${encodeURIComponent(data.artist_name)}${query ? `?${query}` : ''}`,
      { replace: true },
    )
  }, [artistName, data?.artist_name, data?.found, navigate, searchParams])

  useEffect(() => {
    if (!capabilities.ai || activeTab !== 'career' || !data?.found) return
    const artist = data.artist_name.trim()
    if (!artist || artistEnrichmentStartedKeyRef.current === artist) return

    let ignored = false
    artistEnrichmentStartedKeyRef.current = artist
    setArtistEnrichmentTaskId(null)

    startArtistEnrichmentTask({ artist_name: artist })
      .then((task) => {
        if (!ignored) setArtistEnrichmentTaskId(task.task_id)
      })
      .catch(() => {
        if (!ignored && artistEnrichmentStartedKeyRef.current === artist) {
          artistEnrichmentStartedKeyRef.current = null
        }
      })

    return () => {
      ignored = true
    }
  }, [activeTab, capabilities.ai, data?.artist_name, data?.found, startArtistEnrichmentTask])

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
                      { label: '入榜歌曲', value: hasTrackChart ? `${data.tracks.length} 首` : '暂无' },
                      { label: '入榜专辑', value: hasAlbumChart ? `${data.albums.length} 张` : '暂无' },
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
                    { key: 'releases', label: '发行周期', description: '按发行项目查看表现变化' },
                    ...(capabilities.ai ? [{ key: 'career' as const, label: '艺人生涯', description: '简介、档案与生涯信息' }] : []),
                  ]}
                  scrollable
                  onChange={setActiveTab}
                />
              ) : <DetailTabs tabs={availableTabs} activeTab={activeTab} onChange={setActiveTab} />}

              {activeTab === 'overview' && (
                <MusicChartOverviewSection
                  kind="artist"
                  chartSummary={data.chart_summary}
                  weeklyHistory={data.artist_weekly_history}
                  bestSinglesOverlay={data.best_singles_overlay}
                  bestAlbumsOverlay={data.best_albums_overlay}
                  effectivePlayCount={data.effective_play_count}
                />
              )}

              {/* ═══ Tab 2: 单曲成绩 ═══ */}
              {activeTab === 'stats' && (
                <EntityStatsPanel kind="artist" artistName={data?.artist_name} />
              )}

              {activeTab === 'tracks' && (
                hasTrackChart && data.info ? (
                  <MusicTracksSection
                    artistName={data.artist_name}
                    info={data.info}
                    tracks={data.tracks}
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
                hasAlbumChart && data.info ? (
                  <ArtistAlbumsSection
                    artistName={data.artist_name}
                    info={data.info}
                    albums={data.albums}
                  />
                ) : (
                  <MusicChartEmptyState
                    title="暂无专辑进入专辑榜"
                    description="该艺人目前没有专辑进入当前专辑榜统计范围。"
                  />
                )
              )}

              {/* ═══ Tab 4: 发行周期 ═══ */}
              {activeTab === 'releases' && (
                <ArtistReleasesSection
                  artistName={data.artist_name}
                  releaseCycle={releaseCycle}
                  releaseCycleLoading={releaseCycleLoading}
                  releaseCycleError={releaseCycleError}
                />
              )}

              {capabilities.ai && activeTab === 'career' && (
                <ArtistCareerSection
                  enrichment={enrichment}
                  enrichmentLoading={enrichmentLoading}
                  enrichmentTask={artistEnrichmentTask.task}
                  enrichmentTaskEvents={artistEnrichmentTask.events}
                  meta={data.meta}
                />
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
