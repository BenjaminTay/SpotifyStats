import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { TrackDetailResponse, LyricsData, TrackEnrichmentResponse } from '@/types/billboard'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { getBillboardName } from '@/lib/billboard-name'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { TrackOverviewSection } from './track/TrackOverviewSection'
import { TrackLyricsSection } from './track/TrackLyricsSection'
import { VersionGroupSection } from './VersionGroupSection'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileMusicDetailHero, MobileMusicDetailNav } from '@/features/mobile/music/MobileMusicDetail'
import { TrackDetailHero } from './MusicDetailHeader'
import { displayName } from '@/lib/chinese'

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

export function TrackDetailExperience() {
  const { trackId } = useParams<{ trackId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab: TabKey = TABS.some((tab) => tab.key === requestedTab) ? requestedTab as TabKey : 'stats'
  const isPhone = useViewportMode() === 'phone'
  const setActiveTab = (tab: TabKey) => {
    const next = new URLSearchParams(searchParams)
    if (tab === 'stats') next.delete('tab')
    else next.set('tab', tab)
    setSearchParams(next)
  }
  const mergeLevel = Number(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams({ ...filters, merge_level: mergeLevel })

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.trackDetail(trackId ?? '', mergeLevel, billboardParams),
    queryFn: () => api.get<TrackDetailResponse>('/billboard/track/' + trackId!, billboardParams),
    enabled: !!trackId && !filtersLoading,
  })
  const { data: enrichment = null } = useQuery({
    queryKey: queryKeys.music.trackEnrichment(data?.track_name ?? '', data?.artist_name ?? ''),
    queryFn: () =>
      api.get<TrackEnrichmentResponse>(
        '/billboard/enrichment/track/' + encodeURIComponent(data!.track_name),
        {
          artist_name:
            data!.primary_artist_name ?? data!.artist_names?.[0] ?? data!.artist_name,
        },
      ),
    enabled: activeTab === 'lyrics' && !!data?.found,
  })

  const { data: lyrics = null, isPending: lyricsLoading } = useQuery({
    queryKey: queryKeys.music.trackLyrics(trackId ?? ''),
    queryFn: () => api.get<LyricsData>('/lyrics/' + trackId!),
    enabled: activeTab === 'lyrics' && !!trackId,
  })

  return (
    <>
      {isPending && <TrackDetailSkeleton />}

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
              <p className="text-muted-foreground">未找到该曲目的榜单数据</p>
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
                <div className="mobile-m5-page mobile-music-detail-page" data-mobile-page="track-detail">
                  <MobileMusicDetailHero
                    kind="track"
                    eyebrow="Track / Personal Listening"
                    title={displayName(data.track_name)}
                    coverUrl={data.cover_url}
                    subtitle={(data.artist_names?.length ? data.artist_names : [data.artist_name]).map((name, index, artists) => (
                      <span key={name}>
                        <Link to={`/music/artists/${encodeURIComponent(name)}`}>{displayName(name)}</Link>
                        {index < artists.length - 1 ? ' · ' : ''}
                      </span>
                    ))}
                    meta={data.meta?.spotify_album_name ? (
                      <Link to={`/music/albums/${encodeURIComponent(data.meta.spotify_album_name)}?artist=${encodeURIComponent(data.primary_artist_name ?? data.artist_names?.[0] ?? data.artist_name)}`}>
                        {displayName(data.meta.spotify_album_name)}
                      </Link>
                    ) : undefined}
                    facts={[
                      { label: '有效播放', value: `${(data.effective_play_count ?? data.summary?.total_plays ?? 0).toLocaleString('zh-CN')} 次` },
                      { label: '单曲榜', value: data.summary ? `PK #${data.summary.peak_position}` : '尚未入榜', accent: data.summary?.peak_position === 1 },
                      { label: '在榜', value: data.summary ? `${data.summary.weeks_on_chart} 周` : '—' },
                      { label: '走势排名', value: data.summary?.power_rank ? `#${data.summary.power_rank}` : '—' },
                    ]}
                  />
                </div>
              ) : (
                <TrackDetailHero data={data} trackId={trackId ?? ''} onBack={() => navigate(-1)} />
              )}

              {/* Version Group */}
              {data.meta?.version_group && (
                <VersionGroupSection
                  kind="track"
                  data={data.meta.version_group}
                />
              )}

              {isPhone ? (
                <MobileMusicDetailNav
                  activeTab={activeTab}
                  primaryTabs={[
                    { key: 'stats', label: '统计' },
                    { key: 'overview', label: '榜单' },
                    { key: 'lyrics', label: '歌词' },
                  ]}
                  onChange={setActiveTab}
                />
              ) : <div className="mb-6 flex gap-7 border-b border-border">
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
              </div>}

              {activeTab === 'overview' && <TrackOverviewSection data={data} />}
              {activeTab === 'stats' && <EntityStatsPanel kind="track" trackId={trackId} />}
              {activeTab === 'lyrics' && (
                <TrackLyricsSection
                  data={data}
                  enrichment={enrichment}
                  lyrics={lyrics}
                  lyricsLoading={lyricsLoading}
                />
              )}
            </>
          )}
        </>
      )}
    </>
  )
}
