import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import type { TopLists } from '@/types/yearly-review'

interface TopChartsProps {
  topLists: TopLists
}

function CoverImage({ url, alt, rounded }: { url: string; alt: string; rounded?: boolean }) {
  return url ? (
    <img
      src={url}
      alt={alt}
      className={`w-12 h-12 object-cover flex-shrink-0 ${rounded ? 'rounded-full' : 'rounded-md'}`}
      loading="lazy"
    />
  ) : (
    <div className={`w-12 h-12 bg-muted flex items-center justify-center flex-shrink-0 ${rounded ? 'rounded-full' : 'rounded-md'}`}>
      <svg className="w-5 h-5 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
      </svg>
    </div>
  )
}

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

export function TopCharts({ topLists }: TopChartsProps) {
  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">年度最爱</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* 艺人 */}
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 艺人</h3>
          <div className="space-y-3">
            {topLists.artists.map((a) => (
              <Link key={a.rank} to={`/music/artists/${encodeURIComponent(a.name)}`} className="flex items-center gap-3 group">
                <span className="font-sans text-[13px] font-bold tabular-nums text-muted-foreground w-5 text-right">{a.rank}</span>
                <CoverImage url={a.cover_url} alt={a.name} rounded />
                <div className="min-w-0 flex-1">
                  <p className="font-sans text-[14px] font-semibold truncate group-hover:text-accent-foreground transition-colors">{a.name}</p>
                  <p className="font-sans text-[12px] text-muted-foreground tabular-nums">{formatNumber(a.plays)} 次</p>
                  <p className="font-sans text-[12px] text-muted-foreground tabular-nums">{a.hours.toFixed(0)}h</p>
                </div>
              </Link>
            ))}
          </div>
        </GlassCard>

        {/* 曲目 */}
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 曲目</h3>
          <div className="space-y-3">
            {topLists.tracks.map((t) => (
              <div key={t.rank} className="flex items-center gap-3 group">
                <span className="font-sans text-[13px] font-bold tabular-nums text-muted-foreground w-5 text-right">{t.rank}</span>
                <Link to={`/music/tracks/${t.track_id}`}>
                  <CoverImage url={t.cover_url} alt={t.name} />
                </Link>
                <div className="min-w-0 flex-1">
                  <Link to={`/music/tracks/${t.track_id}`} className="font-sans text-[14px] font-semibold truncate transition-colors hover:text-accent-foreground block">
                    {t.name}
                  </Link>
                  <ArtistLinks
                    artistName={t.artist_name}
                    artistNames={t.artist_names}
                    className="block text-[12px] text-muted-foreground truncate"
                  />
                  <p className="font-sans text-[12px] text-muted-foreground tabular-nums">{formatNumber(t.plays)} 次 · {t.hours.toFixed(0)}h</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* 专辑 */}
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 专辑</h3>
          <div className="space-y-3">
            {topLists.albums.map((a) => (
              <div key={a.rank} className="flex items-center gap-3 group">
                <span className="font-sans text-[13px] font-bold tabular-nums text-muted-foreground w-5 text-right">{a.rank}</span>
                <Link to={`/music/albums/${encodeURIComponent(a.name)}?artist=${encodeURIComponent(a.artist_name)}`}>
                  <CoverImage url={a.cover_url} alt={a.name} />
                </Link>
                <div className="min-w-0 flex-1">
                  <Link to={`/music/albums/${encodeURIComponent(a.name)}?artist=${encodeURIComponent(a.artist_name)}`} className="font-sans text-[14px] font-semibold truncate transition-colors hover:text-accent-foreground block">
                    {a.name}
                  </Link>
                  <Link to={`/music/artists/${encodeURIComponent(a.artist_name)}`} className="font-sans text-[12px] text-muted-foreground truncate transition-colors hover:text-accent-foreground block">
                    {a.artist_name}
                  </Link>
                  <p className="font-sans text-[12px] text-muted-foreground tabular-nums">{formatNumber(a.plays)} 次 · {a.hours.toFixed(0)}h</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </section>
  )
}
