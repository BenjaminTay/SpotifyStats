import { GlassCard } from '@/components/shared/GlassCard'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import { Megaphone } from 'lucide-react'
import { fmtInt } from './habitsPrimitives'
import type { MarqueeData } from '@/types/account'

interface Props {
  marquee: MarqueeData
}

export function MarqueeSection({ marquee }: Props) {
  return (
    <GlassCard className="p-6">
      <div className="space-y-5">
        <div className="flex items-center gap-2.5">
          <Megaphone className="h-5 w-5 text-violet-500" />
          <h2 className="mb-5 font-serif text-lg font-semibold">推广转化</h2>
        </div>

        <p className="font-sans text-xs leading-relaxed text-muted-foreground">
          Spotify Marquee
          是全屏推荐广告，以下为你看到推广后转化为实际收听的艺人排行（按转化率降序）。
        </p>

        <div className="space-y-3">
          {marquee.conversions.slice(0, 5).map((c) => {
            const rate = c.conversion_rate * 100
            return (
              <div
                key={`${c.artist_name}-${c.segment}`}
                className="flex items-center gap-3 rounded-lg border border-border bg-muted/20 p-3"
              >
                {c.cover_url ? (
                  <img
                    src={c.cover_url}
                    alt={c.artist_name}
                    className="h-11 w-11 shrink-0 rounded-full border border-border object-cover"
                  />
                ) : (
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Megaphone className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-serif text-sm font-semibold">
                    {displayName(c.artist_name)}
                  </p>
                  <p className="font-sans text-[10px] text-muted-foreground">
                    展示 {fmtInt(c.impressions)} 次 · 转化{' '}
                    {fmtInt(c.actual_plays)} 次
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p
                    className={cn(
                      'font-serif text-lg font-bold',
                      rate > 5
                        ? 'text-emerald-500'
                        : rate > 2
                          ? 'text-amber-500'
                          : 'text-muted-foreground',
                    )}
                  >
                    {rate.toFixed(1)}%
                  </p>
                  <p className="font-sans text-[9px] uppercase tracking-[0.5px] text-muted-foreground">
                    转化率
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </GlassCard>
  )
}
