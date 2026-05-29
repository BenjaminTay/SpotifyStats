import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import type { DiscoveryReturns as DiscoveryReturnsType } from '@/types/yearly-review'

interface DiscoveryReturnsProps {
  discovery: DiscoveryReturnsType
}

function CoverImage({ url, alt, size }: { url: string; alt: string; size?: 'sm' | 'md' }) {
  const dims = size === 'sm' ? 'w-10 h-10' : 'w-14 h-14'
  return url ? (
    <img src={url} alt={alt} className={`${dims} object-cover rounded-md flex-shrink-0`} loading="lazy" />
  ) : (
    <div className={`${dims} bg-muted rounded-md flex items-center justify-center flex-shrink-0`}>
      <svg className="w-4 h-4 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" /></svg>
    </div>
  )
}

function formatDate(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts + 'T00:00:00')
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

export function DiscoveryReturns({ discovery }: DiscoveryReturnsProps) {
  // 如果所有子模块都为空，不渲染
  if (!discovery.new_artists.length && !discovery.returning_tracks.length && !discovery.longest_love) {
    return null
  }

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">发现与回归</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* 新发现艺人 */}
        {discovery.new_artists.length > 0 && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">新发现的艺人</h3>
            <div className="space-y-4">
              {discovery.new_artists.map((a) => (
                <Link key={a.name} to={`/music/artists/${encodeURIComponent(a.name)}`} className="flex items-center gap-3 group">
                  <CoverImage url={a.cover_url} alt={a.name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-[14px] font-semibold truncate group-hover:text-accent-foreground transition-colors">{a.name}</p>
                    <p className="font-sans text-[12px] text-muted-foreground">{a.plays} 次播放 · {formatDate(a.first_date)} 首次听到</p>
                  </div>
                </Link>
              ))}
            </div>
          </GlassCard>
        )}

        {/* 老歌回归 */}
        {discovery.returning_tracks.length > 0 && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">老歌回归</h3>
            <div className="space-y-3">
              {discovery.returning_tracks.map((t) => (
                <Link key={t.name + t.artist_name} to={`/music/tracks/${encodeURIComponent(t.name)}`} className="flex items-center gap-3 group">
                  <CoverImage url={t.cover_url} alt={t.name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-[14px] font-semibold truncate group-hover:text-accent-foreground transition-colors">{t.name}</p>
                    <p className="font-sans text-[12px] text-muted-foreground truncate">{t.artist_name}</p>
                    <p className="font-sans text-[12px] text-muted-foreground">
                      {t.plays} 次 · <span className="inline-block px-1.5 py-0.5 rounded bg-muted text-[11px]">{t.release_year}</span>
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </GlassCard>
        )}

        {/* 最长情单曲 */}
        {discovery.longest_love && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">最长情的单曲</h3>
            <Link to={`/music/tracks/${encodeURIComponent(discovery.longest_love.name)}`} className="flex flex-col items-center text-center group pt-2">
              <CoverImage url={discovery.longest_love.cover_url} alt={discovery.longest_love.name} />
              <p className="font-sans text-[16px] font-semibold mt-3 group-hover:text-accent-foreground transition-colors">{discovery.longest_love.name}</p>
              <p className="font-sans text-[13px] text-muted-foreground">{discovery.longest_love.artist_name}</p>
              <p className="font-serif text-[36px] font-bold tabular-nums mt-2">{discovery.longest_love.span_days}<span className="font-sans text-[16px] font-normal text-muted-foreground ml-1">天</span></p>
              <p className="font-sans text-[12px] text-muted-foreground">持续循环</p>
            </Link>
          </GlassCard>
        )}
      </div>
    </section>
  )
}
