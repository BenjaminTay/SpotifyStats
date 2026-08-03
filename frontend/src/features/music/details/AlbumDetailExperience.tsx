import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import type { AiTaskRun } from '@/types/ai-tasks'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { displayName } from '@/lib/chinese'
import { getBillboardName } from '@/lib/billboard-name'
import { AlertCircle } from 'lucide-react'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { useAiTask, useStartAlbumEnrichmentTask } from '@/hooks/useAiTasks'
import { AlbumDetailHero, DetailTabs } from './MusicDetailHeader'
import { AlbumDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicTracksSection } from './MusicTracksSection'
import { AlbumEraSection } from './AlbumEraSection'
import { VersionGroupSection } from './VersionGroupSection'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'

type TabKey = 'stats' | 'era' | 'overview' | 'tracks'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'era', label: '发行档案' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
]

function albumEnrichmentFromTask(task: AiTaskRun | null): AlbumEnrichmentResponse | null {
  if (task?.status !== 'done' || !task.result || Array.isArray(task.result)) return null
  return task.result as AlbumEnrichmentResponse
}

export function AlbumDetailExperience() {
  const { albumName } = useParams<{ albumName: string }>()
  const [searchParams] = useSearchParams()
  const artistName = searchParams.get('artist') || ''
  const navigate = useNavigate()
  const mergeLevel = Number(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams({ ...filters, merge_level: mergeLevel })

  const [activeTab, setActiveTab] = useState<TabKey>((searchParams.get('tab') as TabKey | null) ?? 'stats')

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.albumDetail(albumName ?? '', artistName, mergeLevel, billboardParams),
    queryFn: () => api.get<AlbumDetailResponse>('/billboard/album/' + albumName!, { ...billboardParams, artist_name: artistName }),
    enabled: !!albumName && !filtersLoading,
  })

  const [albumEnrichmentTaskId, setAlbumEnrichmentTaskId] = useState<string | null>(null)
  const albumEnrichmentStartedKeyRef = useRef<string | null>(null)
  const {
    mutateAsync: startAlbumEnrichmentTask,
    isPending: albumEnrichmentStarting,
  } = useStartAlbumEnrichmentTask()
  const albumEnrichmentTask = useAiTask(albumEnrichmentTaskId)

  const releaseCycleParams = { ...billboardParams, weeks_before: 12, weeks_after: 24 }
  const {
    data: releaseCycle = null,
    isFetching: releaseCycleLoading,
    error: releaseCycleQueryError,
  } = useQuery({
    queryKey: queryKeys.music.albumReleaseCycle(
      data?.album_name ?? '',
      data?.artist_name ?? '',
      releaseCycleParams,
    ),
    queryFn: () =>
      api.get<ReleaseCycleAlbumDetailResponse>(
        `/billboard/release-cycle/artist/${encodeURIComponent(data!.artist_name)}/album/${encodeURIComponent(data!.album_name)}`,
        releaseCycleParams,
      ),
    enabled: activeTab === 'era' && !!data?.found,
  })
  const releaseCycleError = releaseCycle?.error || releaseCycleQueryError?.message || null
  const enrichment = albumEnrichmentFromTask(albumEnrichmentTask.task)
  const enrichmentLoading =
    albumEnrichmentStarting ||
    (Boolean(albumEnrichmentTaskId) && albumEnrichmentTask.loading && !albumEnrichmentTask.task)

  useEffect(() => {
    if (activeTab !== 'era' || !data?.found) return
    const album = data.album_name.trim()
    const artist = data.artist_name.trim()
    const key = `${artist}\u0000${album}`
    if (!album || !artist || albumEnrichmentStartedKeyRef.current === key) return

    let ignored = false
    albumEnrichmentStartedKeyRef.current = key
    setAlbumEnrichmentTaskId(null)

    startAlbumEnrichmentTask({ album_name: album, artist_name: artist })
      .then((task) => {
        if (!ignored) setAlbumEnrichmentTaskId(task.task_id)
      })
      .catch(() => {
        if (!ignored && albumEnrichmentStartedKeyRef.current === key) {
          albumEnrichmentStartedKeyRef.current = null
        }
      })

    return () => {
      ignored = true
    }
  }, [activeTab, data?.album_name, data?.artist_name, data?.found, startAlbumEnrichmentTask])

  return (
    <>
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
              <AlbumDetailHero
                data={data}
                onBack={() => navigate(-1)}
                projectTrackCount={data.album_project?.unique_canonical_songs}
              />

              <DetailTabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

              {activeTab === 'overview' && (
                <MusicChartOverviewSection
                  kind="album"
                  chartSummary={data.chart_summary}
                  weeklyHistory={data.album_weekly_history}
                  bestSinglesOverlay={data.best_singles_overlay}
                />
              )}

              {activeTab === 'stats' && (
                <>
                  <EntityStatsPanel kind="album" albumName={data.album_name} artistName={data.artist_name} mergeLevel={mergeLevel} releaseDate={data.meta?.release_date} />
                  {data.meta?.release_group && data.meta.release_group.versions && data.meta.release_group.versions.length >= 2 && (
                    <div className="mt-8">
                      <VersionGroupSection
                        kind="album"
                        data={data.meta.release_group}
                        sourceBreakdown={data.album_project?.source_breakdown ?? null}
                      />
                    </div>
                  )}
                </>
              )}

              {activeTab === 'tracks' && (
                <MusicTracksSection
                  artistName={data.artist_name}
                  info={data.info}
                  tracks={data.tracks}
                />
              )}

              {activeTab === 'era' && (
                <AlbumEraSection
                  data={data}
                  enrichment={enrichment}
                  enrichmentLoading={enrichmentLoading}
                  enrichmentTask={albumEnrichmentTask.task}
                  enrichmentTaskEvents={albumEnrichmentTask.events}
                  releaseCycle={releaseCycle}
                  releaseCycleLoading={releaseCycleLoading}
                  releaseCycleError={releaseCycleError}
                />
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
