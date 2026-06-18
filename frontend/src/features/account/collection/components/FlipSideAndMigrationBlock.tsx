import { useState } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { CollectionInsights } from '@/types/account'

export function FlipSideAndMigrationBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { flip_side, keyword_migration, co_saved_artists } = insights
  useChineseTextVersion()
  const [page, setPage] = useState(0)
  const perPage = 5
  const totalPages = Math.ceil(flip_side.length / perPage)
  const displayed = flip_side.slice(page * perPage, (page + 1) * perPage)

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        另一面 &middot; 品味迁徙
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Flip Side */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            播放最多却没收藏的歌
          </p>

          {displayed.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              没有漏网的鱼
            </p>
          ) : (
            <div className="divide-y divide-border">
              {displayed.map((track) => (
                <div
                  key={`${track.track_name}-${track.artist_name}`}
                  className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                >
                  {track.cover_url && (
                    <img src={track.cover_url} alt={track.track_name}
                      className="h-9 w-9 flex-shrink-0 rounded object-cover"
                      loading="lazy"
                      decoding="async" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-sm font-medium truncate">
                      {displayName(track.track_name)}
                    </p>
                    <p className="font-sans text-xs text-muted-foreground truncate">
                      {displayName(track.artist_name)}
                    </p>
                  </div>
                  <span className="ml-3 shrink-0 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                    {track.play_count} 次
                  </span>
                </div>
              ))}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-3">
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
                  >
                    上一页
                  </button>
                  <span className="font-sans text-[11px] text-muted-foreground tabular-nums">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
                  >
                    下一页
                  </button>
                </div>
              )}
            </div>
          )}
        </GlassCard>

        {/* Right: Taste Migration */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            品味迁徙
          </p>

          {Object.keys(keyword_migration).length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <div className="mb-5 space-y-3">
              {Object.entries(keyword_migration).map(([year, keywords]) => (
                <div key={year} className="flex items-start gap-3">
                  <span className="shrink-0 font-serif text-sm font-bold">
                    {year}
                  </span>
                  <div className="flex flex-wrap gap-1.5 items-center">
                    {keywords.map((item) => (
                      <span
                        key={item.word}
                        className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 font-sans text-[12px] leading-relaxed"
                      >
                        {displayName(item.word)}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {co_saved_artists.length > 0 && (
            <>
              <p className="mb-2 font-sans text-[11px] font-semibold uppercase text-muted-foreground">
                双厨时刻
              </p>
              <div className="space-y-1.5">
                {co_saved_artists.slice(0, 5).map((pair) => (
                  <p
                    key={`${pair.artist_a}-${pair.artist_b}`}
                    className="font-sans text-xs text-muted-foreground"
                  >
                    <span className="font-medium text-foreground">
                      {displayName(pair.artist_a)}
                    </span>{' '}
                    &times;{' '}
                    <span className="font-medium text-foreground">
                      {displayName(pair.artist_b)}
                    </span>
                    ：{pair.count} 首
                  </p>
                ))}
              </div>
            </>
          )}
        </GlassCard>
      </div>
    </section>
  )
}
