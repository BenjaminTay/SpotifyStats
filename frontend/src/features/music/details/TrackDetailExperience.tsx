import { useEffect } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { TrackDetailResponse } from '@/types/billboard'
import { EntityStatsPanel, EntityStatsPrefetch } from '@/components/shared/EntityStatsPanel'
import { getBillboardName } from '@/lib/billboard-name'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, Fingerprint, GitMerge, ListMusic } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'
import { TrackOverviewSection } from './track/TrackOverviewSection'
import { VersionGroupSection } from './VersionGroupSection'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileMusicDetailHero, MobileMusicDetailNav } from '@/features/mobile/music/MobileMusicDetail'
import { TrackDetailHero } from './MusicDetailHeader'
import { displayName } from '@/lib/chinese'
import { CapabilityGate } from '@/components/capabilities/CapabilityGate'

type TabKey = 'stats' | 'overview'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
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
    setSearchParams(next, { replace: true })
  }
  const mergeLevel = normalizeMergeLevel(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams({ ...filters, merge_level: mergeLevel })

  const summaryParams = { ...billboardParams, view: 'summary' }
  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.trackDetail(trackId ?? '', mergeLevel, summaryParams),
    queryFn: () => api.get<TrackDetailResponse>('/billboard/track/canonical/' + trackId!, summaryParams),
    enabled: !!trackId && !filtersLoading,
  })
  const { data: overviewData, isPending: overviewPending } = useQuery({
    queryKey: queryKeys.music.trackDetail(trackId ?? '', mergeLevel, { ...billboardParams, view: 'overview' }),
    queryFn: () => api.get<TrackDetailResponse>('/billboard/track/canonical/' + trackId!, { ...billboardParams, view: 'overview' }),
    enabled: activeTab === 'overview' && !!trackId && !filtersLoading,
  })
  useEffect(() => {
    if (!requestedTab || TABS.some((tab) => tab.key === requestedTab)) return
    const next = new URLSearchParams(searchParams)
    next.delete('tab')
    setSearchParams(next, { replace: true })
  }, [requestedTab, searchParams, setSearchParams])

  return (
    <>
      {activeTab === 'stats' && trackId && <EntityStatsPrefetch kind="track" trackId={trackId} />}
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
                  <CapabilityGate require={['editing', 'metadata_governance']}>
                    <nav className="mt-3 grid grid-cols-3 gap-2" aria-label="管理这首歌">
                      <Link
                        to={`/settings?metadata=merge&merge_type=track&track_id=${encodeURIComponent(trackId ?? '')}&artist=${encodeURIComponent(data.primary_artist_name ?? data.artist_names?.[0] ?? data.artist_name)}&return_to=${encodeURIComponent(`/music/tracks/${trackId}`)}#music-metadata-management`}
                        className="flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-border text-[11px] font-semibold"
                      >
                        <GitMerge className="size-3.5" />归并版本
                      </Link>
                      <Link
                        to={`/settings?metadata=track-credits&track_id=${encodeURIComponent(data.representative_track_id ?? data.track_id)}&return_to=${encodeURIComponent(`/music/tracks/${trackId}`)}#music-metadata-management`}
                        className="flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-border text-[11px] font-semibold"
                      >
                        <ListMusic className="size-3.5" />曲目署名
                      </Link>
                      <Link
                        to={`/settings?metadata=artist-identities&artist=${encodeURIComponent(data.primary_artist_name ?? data.artist_names?.[0] ?? data.artist_name)}&return_to=${encodeURIComponent(`/music/tracks/${trackId}`)}#music-metadata-management`}
                        className="flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-border text-[11px] font-semibold"
                      >
                        <Fingerprint className="size-3.5" />艺人身份
                      </Link>
                    </nav>
                  </CapabilityGate>
                </div>
              ) : (
                <TrackDetailHero data={data} trackId={trackId ?? ''} onBack={() => navigate(-1)} />
              )}

              {isPhone ? (
                <MobileMusicDetailNav
                  activeTab={activeTab}
                  primaryTabs={[
                    { key: 'stats', label: '统计' },
                    { key: 'overview', label: '榜单' },
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

              {activeTab === 'overview' && (
                overviewPending || !overviewData
                  ? <Skeleton className="h-[420px] w-full rounded-[16px]" />
                  : <>
                      {overviewData.meta?.version_group && (
                        <VersionGroupSection kind="track" data={overviewData.meta.version_group} />
                      )}
                      <TrackOverviewSection data={overviewData} />
                    </>
              )}
              {activeTab === 'stats' && <EntityStatsPanel kind="track" trackId={trackId} />}
            </>
          )}
        </>
      )}
    </>
  )
}
