import { useMemo } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import { Heart } from 'lucide-react'
import { fmtInt, fmtHours, medalBorder, medalBadge, medalIcon } from './habitsPrimitives'
import type { ArtistTiersData } from '@/types/account'

function safeDiv(a: number, b: number): number {
  return b === 0 ? 0 : a / b
}

interface Props {
  tiers: ArtistTiersData
}

export function FanTiersSection({ tiers }: Props) {
  const tierEntries = useMemo(() => {
    if (!tiers.available || tiers.empty) return []
    return Object.entries(tiers.tier_counts)
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
  }, [tiers])

  const tierTotal = useMemo(
    () => tierEntries.reduce((s, t) => s + t.count, 0),
    [tierEntries],
  )

  const superFans = useMemo(() => {
    if (!tiers.available || tiers.empty) return []
    return tiers.artists
      .filter((a) => a.tier === '超级粉丝 (Top 5)')
      .slice(0, 3)
  }, [tiers])

  const conicGradient = useMemo(() => {
    if (tierEntries.length === 0) return 'conic-gradient(#e5e7eb 0% 100%)'
    const palette = ['#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#6b7280']
    let cumulative = 0
    const segments = tierEntries.map((t, i) => {
      const pct = safeDiv(t.count, tierTotal) * 100
      const start = cumulative
      cumulative += pct
      return `${palette[i % palette.length]} ${start}% ${cumulative}%`
    })
    return `conic-gradient(${segments.join(', ')})`
  }, [tierEntries, tierTotal])

  return (
    <GlassCard className="p-6">
      <div className="space-y-6">
        <div className="flex items-center gap-2.5">
          <Heart className="h-5 w-5 text-rose-500" />
          <h2 className="mb-5 font-serif text-xl font-semibold">粉丝层级</h2>
        </div>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          {/* left: donut chart */}
          <div className="flex flex-col items-center justify-center gap-4">
            <div className="relative h-48 w-48">
              <div
                className="h-full w-full rounded-full"
                style={{ background: conicGradient }}
              />
              <div className="absolute inset-[28%] flex flex-col items-center justify-center rounded-full bg-card">
                <p className="font-serif text-2xl font-bold">
                  {fmtInt(tiers.total_artists)}
                </p>
                <p className="font-sans text-[10px] uppercase tracking-[1px] text-muted-foreground">
                  总艺人
                </p>
              </div>
            </div>

            {/* legend */}
            <div className="flex flex-wrap justify-center gap-x-5 gap-y-1.5">
              {tierEntries.map((t, i) => {
                const palette = [
                  '#f59e0b',
                  '#3b82f6',
                  '#8b5cf6',
                  '#10b981',
                  '#6b7280',
                ]
                return (
                  <span
                    key={t.label}
                    className="flex items-center gap-1.5 font-sans text-xs text-muted-foreground"
                  >
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{
                        backgroundColor: palette[i % palette.length],
                      }}
                    />
                    {t.label}（{t.count}）
                  </span>
                )
              })}
            </div>
          </div>

          {/* right: super fan cards */}
          <div className="space-y-4">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
              超级粉丝档案
            </p>
            {superFans.length === 0 ? (
              <p className="font-sans text-sm text-muted-foreground">
                暂无超级粉丝数据
              </p>
            ) : (
              superFans.map((fan, idx) => (
                <div
                  key={fan.artist_name}
                  className={cn(
                    'rounded-xl border bg-muted/20 p-4 transition-all',
                    medalBorder[idx + 1] ?? 'border-border',
                  )}
                >
                  <div className="flex items-start gap-3">
                    {fan.cover_url ? (
                      <img
                        src={fan.cover_url}
                        alt={fan.artist_name}
                        className="h-12 w-12 shrink-0 rounded-full border border-border object-cover"
                      />
                    ) : (
                      <div
                        className={cn(
                          'flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
                          medalBadge[idx + 1] ?? 'bg-muted',
                        )}
                      >
                        {medalIcon[idx + 1] ?? idx + 1}
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-serif text-base font-semibold">
                        {displayName(fan.artist_name)}
                      </p>
                      <div className="mt-2 flex gap-5 font-sans text-xs text-muted-foreground">
                        <span>
                          播放{' '}
                          <strong className="text-foreground">
                            {fmtInt(fan.play_count)}
                          </strong>{' '}
                          次
                        </span>
                        <span>
                          收听{' '}
                          <strong className="text-foreground">
                            {fmtHours(fan.hours)}
                          </strong>
                        </span>
                        <span className="text-amber-500">#{fan.rank}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  )
}
