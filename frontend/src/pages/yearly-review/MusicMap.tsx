import { GlassCard } from '@/components/shared/GlassCard'
import type { MusicMap as MusicMapType } from '@/types/yearly-review'

interface MusicMapProps {
  musicMap: MusicMapType | null
}

export function MusicMap({ musicMap }: MusicMapProps) {
  const regions = musicMap?.regions ?? []
  if (!regions.length) {
    return (
      <section className="mb-12">
        <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">音乐版图</h2>
        <GlassCard className="p-8 text-center">
          <p className="font-sans text-[14px] text-muted-foreground">地区分布数据将从你的收听流派中推断。多听听不同地区的音乐！</p>
        </GlassCard>
      </section>
    )
  }

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">音乐版图</h2>
      <GlassCard className="p-5">
        <div className="space-y-3">
          {regions.map((r) => (
            <div key={r.region} className="flex items-center gap-3">
              <span className="text-lg flex-shrink-0 w-7 text-center">{r.flag}</span>
              <span className="font-sans text-[13px] w-16 flex-shrink-0">{r.region}</span>
              <div className="flex-1 h-5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-accent-foreground/50 transition-all duration-700"
                  style={{ width: `${r.play_share}%` }}
                />
              </div>
              <span className="font-sans text-[13px] font-semibold tabular-nums w-12 text-right">{r.play_share}%</span>
            </div>
          ))}
        </div>
        <p className="font-sans text-[11px] text-muted-foreground mt-4">
          地区分布根据你的 Spotify 艺人流派标签推断，可能与实际情况有出入。
        </p>
      </GlassCard>
    </section>
  )
}
