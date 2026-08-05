import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { api } from '@/lib/api'
import { formatDate } from '@/features/account/collection/utils/formatDate'
import { MobileEntityRow } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'

interface PlaylistRow {
  id: number
  name: string
  last_modified: string
  track_count: number
}

interface PlaylistTrackRow {
  track_uri: string
  track_name: string
  artist_name: string
  album_name: string
  added_date: string
  cover_url?: string | null
}

export function PlaylistsBrowser() {
  const isPhone = useViewportMode() === 'phone'
  const [playlists, setPlaylists] = useState<PlaylistRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [tracks, setTracks] = useState<PlaylistTrackRow[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)
  const [plPage, setPlPage] = useState(0)
  const PL_PER_PAGE = 10
  const plTotalPages = Math.ceil(playlists.length / PL_PER_PAGE)
  const pagedPlaylists = playlists.slice(plPage * PL_PER_PAGE, (plPage + 1) * PL_PER_PAGE)

  useEffect(() => {
    setLoading(true)
    api.get<PlaylistRow[]>('/library/playlists')
      .then((data) => { setPlaylists(data); setPlPage(0); setLoading(false) })
      .catch((e: unknown) => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [])

  const loadTracks = useCallback(async (id: number) => {
    if (expanded === id) {
      setExpanded(null)
      return
    }
    setExpanded(id)
    setTracksLoading(true)
    try {
      const data = await api.get<PlaylistTrackRow[]>(`/library/playlists/${id}/tracks`)
      setTracks(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setTracksLoading(false)
    }
  }, [expanded])

  return (
    <GlassCard className="p-4">
      <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
        播放列表
      </p>

      {loading && (
        <div className="space-y-2 py-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-muted" />
          ))}
        </div>
      )}

      {error && (
        <div className="py-8 text-center text-[13px] text-red-500">{error}</div>
      )}

      {!loading && !error && playlists.length === 0 && (
        <div className="py-8 text-center text-[13px] text-muted-foreground">
          暂无播放列表
        </div>
      )}

      {!loading && !error && playlists.length > 0 && (
        <>
        <div className="space-y-1">
          {pagedPlaylists.map((pl) => (
            <div key={pl.id}>
              <button
                onClick={() => loadTracks(pl.id)}
                className="w-full flex items-center justify-between rounded-md px-3 py-2 text-left transition hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-sans text-[13px] font-medium truncate">{displayName(pl.name)}</p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    {pl.track_count} 首{pl.last_modified ? ` · ${formatDate(pl.last_modified)}` : ''}
                  </p>
                </div>
                <span className="ml-2 font-sans text-[11px] text-muted-foreground shrink-0">
                  {expanded === pl.id ? '收起' : '展开'}
                </span>
              </button>

              {expanded === pl.id && (
                <div className="ml-3 border-l-2 border-border pl-4 mt-1 mb-2">
                  {tracksLoading ? (
                    <div className="space-y-1 py-2">
                      {[1, 2, 3].map((i) => (
                        <div key={i} className="h-6 animate-pulse rounded bg-muted" />
                      ))}
                    </div>
                  ) : tracks.length === 0 ? (
                    <p className="py-3 text-center font-sans text-[12px] text-muted-foreground">
                      该列表暂无曲目
                    </p>
                  ) : isPhone ? (
                    <div className="mobile-rank-list max-h-[360px] overflow-y-auto">
                      {tracks.map((track) => (
                        <MobileEntityRow
                          key={track.track_uri}
                          entityType="track"
                          title={displayName(track.track_name)}
                          subtitle={displayName(track.artist_name)}
                          coverUrl={track.cover_url}
                          metric={track.added_date ? formatDate(track.added_date) : '—'}
                          metricLabel="加入"
                          facts={track.album_name ? [{ label: '专辑', value: displayName(track.album_name) }] : []}
                          to={`/music/tracks/${track.track_uri.replace('spotify:track:', '')}`}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="max-h-[360px] overflow-y-auto">
                      <table className="w-full font-sans text-[12px]">
                        <thead>
                          <tr className="border-b border-border/50 text-left text-[10px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                            <th className="pb-1.5 pr-2 w-7"></th>
                            <th className="pb-1.5 pr-2">曲目</th>
                            <th className="pb-1.5 pr-2">艺人</th>
                            <th className="pb-1.5 pr-2 hidden md:table-cell">专辑</th>
                            <th className="pb-1.5 text-right">加入日期</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tracks.map((t) => (
                            <tr key={t.track_uri} className="border-b border-border/30 last:border-b-0">
                              <td className="py-1 pr-1">
                                {t.cover_url ? (
                                  <img src={t.cover_url} alt={t.track_name}
                                    className="h-7 w-7 rounded object-cover"
                                    loading="lazy"
                                    decoding="async" />
                                ) : (
                                  <div className="h-7 w-7 rounded bg-muted" />
                                )}
                              </td>
                              <td className="py-1 pr-2 font-medium">
                                <Link
                                  to={`/music/tracks/${t.track_uri.replace('spotify:track:', '')}`}
                                  className="hover:text-accent-foreground hover:underline transition-colors"
                                >
                                  {displayName(t.track_name)}
                                </Link>
                              </td>
                              <td className="py-1 pr-2 text-muted-foreground">{displayName(t.artist_name)}</td>
                              <td className="py-1 pr-2 text-muted-foreground hidden md:table-cell">
                                {displayName(t.album_name)}
                              </td>
                              <td className="py-1 text-right text-muted-foreground whitespace-nowrap">
                                {t.added_date
                                  ? formatDate(t.added_date)
                                  : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
        {plTotalPages > 1 && (
          <div className="flex items-center justify-between pt-3 mt-3 border-t border-border/50">
            <button
              onClick={() => setPlPage(p => Math.max(0, p - 1))}
              disabled={plPage === 0}
              className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
            >
              上一页
            </button>
            <span className="font-sans text-[11px] text-muted-foreground tabular-nums">
              {plPage + 1} / {plTotalPages}
            </span>
            <button
              onClick={() => setPlPage(p => Math.min(plTotalPages - 1, p + 1))}
              disabled={plPage >= plTotalPages - 1}
              className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
            >
              下一页
            </button>
          </div>
        )}
        </>
      )}
    </GlassCard>
  )
}
