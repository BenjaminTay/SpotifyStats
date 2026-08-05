import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { api } from '@/lib/api'
import { MobileEntityRow, MobilePagination } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'

interface SavedTrackRow {
  track_uri: string
  track_name: string
  artist_name: string
  album_name: string
  added_date: string | null
  cover_url?: string | null
}

interface SavedTracksPage {
  page: number
  limit: number
  total: number
  total_pages: number
  tracks: SavedTrackRow[]
}

export function SavedTracksBrowser() {
  const isPhone = useViewportMode() === 'phone'
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [data, setData] = useState<SavedTracksPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search])

  const fetchPage = useCallback(async (p: number, q: string) => {
    setLoading(true)
    setError('')
    try {
      const result = await api.get<SavedTracksPage>(
        `/library/saved-tracks?page=${p}&limit=20&search=${encodeURIComponent(q)}`
      )
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPage(page, debouncedSearch)
  }, [page, debouncedSearch, fetchPage])

  const totalPages = data?.total_pages || 0
  const hasNext = page < totalPages
  const hasPrev = page > 1

  return (
    <GlassCard className="p-4">
      <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
        收藏曲目
      </p>
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <svg
            className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索曲目或艺人..."
            className="w-full rounded-lg border border-border bg-background py-1.5 pl-9 pr-3 font-sans text-[13px] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent-foreground"
          />
        </div>
        {data && (
          <span className="font-sans text-[12px] text-muted-foreground">
            {data.total} 首
          </span>
        )}
      </div>

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

      {!loading && !error && data && (
        <>
          {data.tracks.length === 0 ? (
            <div className="py-8 text-center text-[13px] text-muted-foreground">
              {debouncedSearch ? '没有匹配的曲目' : '暂无收藏曲目'}
            </div>
          ) : (
            isPhone ? (
              <div className="mobile-rank-list" aria-label="收藏曲目列表">
                {data.tracks.map((track) => (
                  <MobileEntityRow
                    key={track.track_uri}
                    entityType="track"
                    title={displayName(track.track_name)}
                    subtitle={displayName(track.artist_name)}
                    coverUrl={track.cover_url}
                    metric={track.added_date ? new Date(track.added_date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : '—'}
                    metricLabel="收藏"
                    facts={track.album_name ? [{ label: '专辑', value: displayName(track.album_name) }] : []}
                    to={`/music/tracks/${track.track_uri.replace('spotify:track:', '')}`}
                  />
                ))}
              </div>
            ) : (
            <div className="overflow-x-auto">
              <table className="w-full font-sans text-[13px]">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                    <th className="pb-2 pr-4 w-8"></th>
                    <th className="pb-2 pr-4">曲目</th>
                    <th className="pb-2 pr-4">艺人</th>
                    <th className="pb-2 pr-4 hidden md:table-cell">专辑</th>
                    <th className="pb-2 text-right">收藏日期</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tracks.map((t) => (
                    <tr key={t.track_uri} className="border-b border-border/50 last:border-b-0">
                      <td className="py-2 pr-1">
                        {t.cover_url ? (
                          <img src={t.cover_url} alt={t.track_name}
                            className="h-8 w-8 rounded object-cover"
                            loading="lazy"
                            decoding="async" />
                        ) : (
                          <div className="h-8 w-8 rounded bg-muted" />
                        )}
                      </td>
                      <td className="py-2 pr-4 font-medium">
                        <Link
                          to={`/music/tracks/${t.track_uri.replace('spotify:track:', '')}`}
                          className="hover:text-accent-foreground hover:underline transition-colors"
                        >
                          {displayName(t.track_name)}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">{displayName(t.artist_name)}</td>
                      <td className="py-2 pr-4 text-muted-foreground hidden md:table-cell">
                        {displayName(t.album_name)}
                      </td>
                      <td className="py-2 text-right text-muted-foreground whitespace-nowrap">
                        {t.added_date
                          ? new Date(t.added_date).toLocaleDateString('zh-CN')
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )
          )}

          {totalPages > 1 && (
            isPhone ? (
              <MobilePagination page={page} pageCount={totalPages} totalLabel={`${data.total} 首`} loading={loading} onPageChange={setPage} />
            ) : (
            <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={!hasPrev}
                className="rounded-md px-3 py-1 font-sans text-[12px] text-muted-foreground transition hover:text-foreground disabled:opacity-30"
              >
                上一页
              </button>
              <span className="font-sans text-[12px] text-muted-foreground">
                第 {page} / {totalPages} 页
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={!hasNext}
                className="rounded-md px-3 py-1 font-sans text-[12px] text-muted-foreground transition hover:text-foreground disabled:opacity-30"
              >
                下一页
              </button>
            </div>
            )
          )}
        </>
      )}
    </GlassCard>
  )
}
