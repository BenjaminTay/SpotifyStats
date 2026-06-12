import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { Mic } from 'lucide-react'
import { fmtInt, fmtHours } from './habitsPrimitives'
import type { PodcastData } from '@/types/account'

interface Props {
  podcast: PodcastData
}

export function PodcastSection({ podcast }: Props) {
  return (
    <GlassCard className="p-6">
      <div className="space-y-5">
        <div className="flex items-center gap-2.5">
          <Mic className="h-5 w-5 text-emerald-500" />
          <h2 className="mb-5 font-serif text-lg font-semibold">播客聆听</h2>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="font-serif text-xl font-bold">
              {fmtInt(podcast.total_plays)}
            </p>
            <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
              总播放
            </p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="font-serif text-xl font-bold">
              {fmtHours(podcast.total_hours)}
            </p>
            <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
              总时长
            </p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="font-serif text-xl font-bold">
              {fmtInt(podcast.unique_shows)}
            </p>
            <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
              独特节目
            </p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="font-serif text-xl font-bold">
              {fmtInt(podcast.saved_shows)}
            </p>
            <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
              已收藏
            </p>
          </div>
        </div>

        {/* top shows */}
        <div className="space-y-2">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
            最爱节目 Top 5
          </p>
          {podcast.top_shows.slice(0, 5).map((s, idx) => (
            <div
              key={s.show_name}
              className="flex items-center gap-3 rounded-lg px-3 py-1.5 transition-colors hover:bg-muted/30"
            >
              <span className="w-5 text-right font-sans text-xs tabular-nums text-muted-foreground">
                {idx + 1}
              </span>
              <span className="flex-1 truncate font-sans text-sm">
                {displayName(s.show_name)}
              </span>
              <span className="shrink-0 font-sans text-xs tabular-nums text-muted-foreground">
                {fmtHours(s.hours)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  )
}
