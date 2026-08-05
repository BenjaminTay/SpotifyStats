import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import type { CollectionInsights } from '@/types/account'
import { MobileEntityRow } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'

export function LeaderboardBlock({ insights }: { insights: CollectionInsights }) {
  const { top_saved_artists, top_saved_albums } = insights
  const isPhone = useViewportMode() === 'phone'

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        排行榜
      </h2>

      <div className="grid grid-cols-1 gap-6">
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏曲目最多的艺人
          </p>

          {top_saved_artists.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : isPhone ? (
            <div className="mobile-rank-list" aria-label="收藏艺人榜">
              {top_saved_artists.slice(0, 10).map((artist, index) => (
                <MobileEntityRow
                  key={artist.artist_name}
                  entityType="artist"
                  rank={index + 1}
                  title={displayName(artist.artist_name)}
                  coverUrl={artist.cover_url}
                  metric={String(artist.saved_count)}
                  metricLabel="收藏"
                  facts={[{ label: '播放', value: artist.total_plays.toLocaleString('zh-CN') }]}
                  to={`/music/artists/${encodeURIComponent(artist.artist_name)}`}
                />
              ))}
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    #
                  </th>
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    艺人
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    收藏
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    播放
                  </th>
                </tr>
              </thead>
              <tbody>
                {top_saved_artists.slice(0, 10).map((artist, idx) => (
                  <tr
                    key={artist.artist_name}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-2.5 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="py-2.5 flex items-center gap-2.5 min-w-0">
                      {artist.cover_url && (
                        <img src={artist.cover_url} alt={artist.artist_name}
                          className="h-8 w-8 flex-shrink-0 rounded-full object-cover"
                          loading="lazy"
                          decoding="async" />
                      )}
                      <span className="font-sans text-sm font-medium truncate">{displayName(artist.artist_name)}</span>
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums">
                      {artist.saved_count}
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums text-muted-foreground">
                      {artist.total_plays.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>

        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏曲目最多的专辑
          </p>

          {top_saved_albums.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : isPhone ? (
            <div className="mobile-rank-list" aria-label="收藏专辑榜">
              {top_saved_albums.slice(0, 10).map((album, index) => (
                <MobileEntityRow
                  key={`${album.album_name}-${album.artist_name}`}
                  entityType="album"
                  rank={index + 1}
                  title={displayName(album.album_name)}
                  subtitle={displayName(album.artist_name)}
                  coverUrl={album.cover_url}
                  metric={String(album.saved_count)}
                  metricLabel="收藏"
                  facts={[{ label: '播放', value: album.total_plays.toLocaleString('zh-CN') }]}
                  to={`/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`}
                />
              ))}
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    #
                  </th>
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    专辑
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    收藏
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    播放
                  </th>
                </tr>
              </thead>
              <tbody>
                {top_saved_albums.slice(0, 10).map((album, idx) => (
                  <tr key={`${album.album_name}-${album.artist_name}`}
                    className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="py-2.5 flex items-center gap-2.5 min-w-0">
                      {album.cover_url && (
                        <img src={album.cover_url} alt={album.album_name}
                          className="h-8 w-8 flex-shrink-0 rounded object-cover"
                          loading="lazy"
                          decoding="async" />
                      )}
                      <div className="min-w-0">
                        <span className="font-sans text-sm font-medium">{displayName(album.album_name)}</span>
                        <span className="font-sans text-[11px] text-muted-foreground block">{displayName(album.artist_name)}</span>
                      </div>
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums">
                      {album.saved_count}
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums text-muted-foreground">
                      {album.total_plays.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>
      </div>
    </section>
  )
}
