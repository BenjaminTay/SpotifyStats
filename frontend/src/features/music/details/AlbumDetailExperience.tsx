import { useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { displayName } from '@/lib/chinese'
import { AlertCircle } from 'lucide-react'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { AlbumDetailHero, DetailTabs } from './MusicDetailHeader'
import { AlbumDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicTracksSection } from './MusicTracksSection'
import { AlbumEraSection } from './AlbumEraSection'
import { VersionGroupSection } from './VersionGroupSection'
import { AlbumProjectSection } from './AlbumProjectSection'

type TabKey = 'stats' | 'era' | 'overview' | 'tracks'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'era', label: '发行档案' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
]

export function AlbumDetailExperience() {
  const { albumName } = useParams<{ albumName: string }>()
  const [searchParams] = useSearchParams()
  const artistName = searchParams.get('artist') || ''
  const navigate = useNavigate()
  const mergeLevel = Number(searchParams.get('merge_level') ?? getDefaultMergeLevel())

  const [activeTab, setActiveTab] = useState<TabKey>((searchParams.get('tab') as TabKey | null) ?? 'stats')

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.albumDetail(albumName ?? '', artistName, mergeLevel),
    queryFn: () => api.get<AlbumDetailResponse>('/billboard/album/' + albumName!, { artist_name: artistName, merge_level: mergeLevel }),
    enabled: !!albumName,
  })

  const releaseCycleParams = { weeks_before: 12, weeks_after: 24 }
  const { data: enrichment = null } = useQuery({
    queryKey: queryKeys.music.albumEnrichment(data?.album_name ?? '', data?.artist_name ?? ''),
    queryFn: () =>
      api.get<AlbumEnrichmentResponse>(
        '/billboard/enrichment/album/' + encodeURIComponent(data!.album_name),
        { artist_name: data!.artist_name },
      ),
    enabled: activeTab === 'era' && !!data?.found,
  })
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
                返回 Billboard
              </button>
            </div>
          ) : (
            <>
              <AlbumDetailHero data={data} onBack={() => navigate(-1)} />

              {data.meta?.release_group && (
                <VersionGroupSection
                  kind="album"
                  data={data.meta.release_group}
                />
              )}

              {data.album_project && <AlbumProjectSection project={data.album_project} />}

              <DetailTabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

              {activeTab === 'overview' && (
                <MusicChartOverviewSection
                  kind="album"
                  chartSummary={data.chart_summary}
                  weeklyHistory={data.album_weekly_history}
                  bestSinglesOverlay={data.best_singles_overlay}
                />
              )}

              <div className={activeTab === 'stats' ? '' : 'hidden'}>
                <EntityStatsPanel kind="album" albumName={data.album_name} artistName={data.artist_name} />
              </div>

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
