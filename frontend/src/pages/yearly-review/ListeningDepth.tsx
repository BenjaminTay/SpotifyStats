import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import type { ListeningDepth as ListeningDepthType } from '@/types/yearly-review'

interface ListeningDepthProps {
  listeningDepth: ListeningDepthType
}

function CoverImage({ url, alt }: { url: string; alt: string }) {
  return url ? (
    <img src={url} alt={alt} className="w-14 h-14 object-cover rounded-md flex-shrink-0" loading="lazy" />
  ) : (
    <div className="w-14 h-14 bg-muted rounded-md flex items-center justify-center flex-shrink-0">
      <svg className="w-5 h-5 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" /></svg>
    </div>
  )
}

export function ListeningDepth({ listeningDepth }: ListeningDepthProps) {
  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">收听深度</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* 收听年龄 */}
        {listeningDepth.listening_age && (
          <GlassCard className="p-5 flex flex-col items-center text-center">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">收听年龄</h3>
            <div className="flex items-baseline gap-1 mb-3">
              <span className="font-serif text-[56px] font-bold tabular-nums leading-none">{listeningDepth.listening_age.age}</span>
              <span className="font-sans text-[18px] text-muted-foreground">岁</span>
            </div>
            <p className="font-sans text-[13px] text-muted-foreground leading-relaxed">{listeningDepth.listening_age.description}</p>
          </GlassCard>
        )}

        {/* 深度聆听率 */}
        <GlassCard className="p-5 flex flex-col items-center text-center">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">深度聆听率</h3>
          <div className="relative w-28 h-28 mb-3">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted" />
              <circle
                cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="6"
                strokeLinecap="round"
                className="text-accent-foreground"
                strokeDasharray={`${listeningDepth.deep_listen_ratio * 2.64} 264`}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center font-serif text-[28px] font-bold tabular-nums">
              {listeningDepth.deep_listen_ratio}%
            </span>
          </div>
          <p className="font-sans text-[13px] text-muted-foreground leading-relaxed">
            完整听完 ≤3 分钟的歌曲不算，听到 90% 以上才算
          </p>
        </GlassCard>

        {/* 专辑完整度 */}
        <div className="space-y-4">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">完整听完的专辑</h3>
          {listeningDepth.album_completion.length === 0 ? (
            <GlassCard className="p-5">
              <p className="font-sans text-[13px] text-muted-foreground">还没有完整听完的专辑。试试从头到尾听完一张吧！</p>
            </GlassCard>
          ) : (
            listeningDepth.album_completion.map((album) => (
              <Link key={album.name + album.artist_name} to={`/music/albums/${encodeURIComponent(album.name)}?artist=${encodeURIComponent(album.artist_name)}`}>
                <GlassCard className="p-4 flex items-center gap-3 group hover:border-accent-foreground/20 transition-colors">
                  <CoverImage url={album.cover_url} alt={album.name} />
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-[14px] font-semibold truncate group-hover:text-accent-foreground transition-colors">{album.name}</p>
                    <Link to={`/music/artists/${encodeURIComponent(album.artist_name)}`} className="font-sans text-[12px] text-muted-foreground truncate transition-colors hover:text-accent-foreground block">
                      {album.artist_name}
                    </Link>
                    <div className="mt-1.5 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-green-500 dark:bg-green-400 transition-all duration-700"
                        style={{ width: `${album.completion_pct}%` }}
                      />
                    </div>
                    <span className="font-sans text-[11px] text-muted-foreground tabular-nums">{album.completion_pct}% 完成</span>
                  </div>
                </GlassCard>
              </Link>
            ))
          )}
        </div>
      </div>
    </section>
  )
}
