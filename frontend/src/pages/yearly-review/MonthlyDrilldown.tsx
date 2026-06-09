import { useState } from 'react'
import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { displayName } from '@/lib/chinese'
import type { MonthlyDrillItem } from '@/types/yearly-review'

interface MonthlyDrilldownProps {
  monthlyDrilldown: MonthlyDrillItem[]
}

const MONTH_NAMES = ['', '一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']

function MiniCover({ url, name }: { url: string; name: string }) {
  return url ? (
    <img src={url} alt={name} className="w-10 h-10 object-cover rounded-md flex-shrink-0" loading="lazy" />
  ) : (
    <div className="w-10 h-10 bg-muted rounded-md flex items-center justify-center flex-shrink-0">
      <svg className="w-4 h-4 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" /></svg>
    </div>
  )
}

export function MonthlyDrilldown({ monthlyDrilldown }: MonthlyDrilldownProps) {
  // 找到峰值月，默认展开
  const peakMonth = monthlyDrilldown.reduce(
    (max, m) => (m.total_hours > (max?.total_hours ?? 0) ? m : max),
    monthlyDrilldown[0]
  )
  const [expandedMonth, setExpandedMonth] = useState<number | null>(peakMonth?.month ?? null)

  if (!monthlyDrilldown.length) return null

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">月度回顾</h2>
      <div className="space-y-3">
        {monthlyDrilldown.map((m) => {
          const isExpanded = expandedMonth === m.month
          return (
            <GlassCard key={m.month} className="overflow-hidden">
              <button
                onClick={() => setExpandedMonth(isExpanded ? null : m.month)}
                className="w-full p-4 flex items-center gap-4 text-left hover:bg-muted/30 transition-colors"
              >
                <span className="font-sans text-[13px] font-semibold text-muted-foreground w-12 flex-shrink-0">
                  {MONTH_NAMES[m.month]}
                </span>
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent-foreground/40"
                    style={{ width: `${Math.min(m.total_hours / (peakMonth?.total_hours ?? 1) * 100, 100)}%` }}
                  />
                </div>
                <span className="font-sans text-[13px] font-semibold tabular-nums w-16 text-right">{m.total_hours.toFixed(0)}h</span>
                <svg
                  className={`w-4 h-4 text-muted-foreground transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isExpanded && (
                <div className="px-4 pb-4 border-t border-border">
                  {/* Top 3 曲目 */}
                  {m.top_tracks.length > 0 && (
                    <div className="mt-3">
                      <p className="font-sans text-[11px] uppercase tracking-[1px] text-muted-foreground mb-2">最爱曲目</p>
                      <div className="space-y-2">
                        {m.top_tracks.map((t, i) => (
                          <div key={t.name + t.artist_name} className="flex items-center gap-3 group">
                            <span className="font-sans text-[11px] font-bold text-muted-foreground w-4">{i + 1}</span>
                            <Link to={`/music/tracks/${t.track_id}`}>
                              <MiniCover url={t.cover_url} name={t.name} />
                            </Link>
                            <div className="min-w-0 flex-1">
                              <Link to={`/music/tracks/${t.track_id}`} className="font-sans text-[13px] font-semibold truncate transition-colors hover:text-accent-foreground block">
                                {displayName(t.name)}
                              </Link>
                              <ArtistLinks
                                artistName={t.artist_name}
                                artistNames={t.artist_names}
                                className="block text-[11px] text-muted-foreground truncate"
                              />
                            </div>
                            <span className="font-sans text-[12px] text-muted-foreground tabular-nums">{t.plays} 次</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Top 艺人 */}
                  {m.top_artist?.name && (
                    <Link to={`/music/artists/${encodeURIComponent(m.top_artist.name)}`} className="flex items-center gap-3 mt-3 pt-3 border-t border-border group">
                      <span className="font-sans text-[11px] uppercase tracking-[1px] text-muted-foreground">本月艺人</span>
                      <MiniCover url={m.top_artist.cover_url} name={m.top_artist.name} />
                      <span className="font-sans text-[14px] font-semibold group-hover:text-accent-foreground transition-colors">{displayName(m.top_artist.name)}</span>
                    </Link>
                  )}
                </div>
              )}
            </GlassCard>
          )
        })}
      </div>
    </section>
  )
}
