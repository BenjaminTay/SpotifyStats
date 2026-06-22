import { useState } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { TrackDetailResponse, LyricsData, TrackEnrichmentResponse } from '@/types/billboard'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { displayName } from '@/lib/chinese'
import { getBillboardName } from '@/lib/billboard-name'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { TrackOverviewSection } from './track/TrackOverviewSection'
import { TrackLyricsSection } from './track/TrackLyricsSection'
import { VersionGroupSection } from './VersionGroupSection'

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

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
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabKey>(
    (searchParams.get('tab') as TabKey | null) ?? 'stats',
  )
  const mergeLevel = Number(searchParams.get('merge_level') ?? getDefaultMergeLevel())

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.trackDetail(trackId ?? '', mergeLevel),
    queryFn: () => api.get<TrackDetailResponse>('/billboard/track/' + trackId!, { merge_level: mergeLevel }),
    enabled: !!trackId,
  })
  const { data: enrichment = null } = useQuery({
    queryKey: queryKeys.music.trackEnrichment(data?.track_name ?? '', data?.artist_name ?? ''),
    queryFn: () =>
      api.get<TrackEnrichmentResponse>(
        '/billboard/enrichment/track/' + encodeURIComponent(data!.track_name),
        { artist_name: data!.artist_name },
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
                      {(data.artist_names && data.artist_names.length > 1
                        ? data.artist_names
                        : [data.artist_name]
                      ).map((name, idx, arr) => (
                        <span key={name}>
                          <Link
                            to={`/music/artists/${encodeURIComponent(name)}`}
                            className="transition-colors hover:text-accent-foreground"
                          >
                            {displayName(name)}
                          </Link>
                          {idx < arr.length - 1 && (
                            <span className="text-muted-foreground/40">{' · '}</span>
                          )}
                        </span>
                      ))}
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

              {/* Version Group */}
              {data.meta?.version_group && (
                <VersionGroupSection
                  kind="track"
                  data={data.meta.version_group}
                />
              )}

              {/* Tabs */}
              <div className="mb-6 flex gap-7 border-b border-border">
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
              </div>

              {/* Tab: 榜单表现 */}
              {activeTab === 'overview' && <TrackOverviewSection data={data} />}

              {/* Tab: 播放统计 */}
              {activeTab === 'stats' && <EntityStatsPanel kind="track" trackId={trackId} />}

              {/* Tab: 歌词 */}
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
