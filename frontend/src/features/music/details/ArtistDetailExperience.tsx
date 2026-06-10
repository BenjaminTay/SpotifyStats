import { useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { ArtistDetailResponse, ArtistEnrichmentResponse, ReleaseCycleArtistOverviewResponse } from '@/types/billboard'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { displayName } from '@/lib/chinese'
import { AlertCircle } from 'lucide-react'
import { ArtistDetailHero, DetailTabs } from './MusicDetailHeader'
import { ArtistDetailSkeleton } from './MusicDetailSkeletons'
import { MusicChartOverviewSection } from './MusicChartOverviewSection'
import { MusicTracksSection } from './MusicTracksSection'
import { ArtistAlbumsSection } from './ArtistAlbumsSection'
import { ArtistCareerSection } from './ArtistCareerSection'
import { ArtistReleasesSection } from './ArtistReleasesSection'

type TabKey = 'stats' | 'releases' | 'career' | 'overview' | 'tracks' | 'albums'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'releases', label: '发行周期' },
  { key: 'career', label: '艺人生涯' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
  { key: 'albums', label: '专辑成绩' },
]

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
                  bestSinglesOverlay={data.best_singles_overlay}
                  bestAlbumsOverlay={data.best_albums_overlay}
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
                <ArtistReleasesSection
                  artistName={data.artist_name}
                  releaseCycle={releaseCycle}
                  releaseCycleLoading={releaseCycleLoading}
                  releaseCycleError={releaseCycleError}
                />
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
