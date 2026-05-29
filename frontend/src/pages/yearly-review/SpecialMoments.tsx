import { GlassCard } from '@/components/shared/GlassCard'
import type { SpecialMoments as SpecialMomentsType } from '@/types/yearly-review'

interface SpecialMomentsProps {
  specialMoments: SpecialMomentsType
}

function MiniCover({ url, name }: { url: string; name: string }) {
  return url ? (
    <img src={url} alt={name} className="w-10 h-10 object-cover rounded-md flex-shrink-0" loading="lazy" />
  ) : (
    <div className="w-10 h-10 bg-muted rounded-md flex items-center justify-center flex-shrink-0">
      <svg className="w-4 h-4 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" /></svg>
    </div>
  )
}

export function SpecialMoments({ specialMoments }: SpecialMomentsProps) {
  if (!specialMoments.most_active_day && !specialMoments.longest_streak) return null

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">特殊时刻</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 最活跃日 */}
        {specialMoments.most_active_day && (
          <GlassCard className="p-5">
            <p className="font-sans text-[11px] uppercase tracking-[1.2px] text-muted-foreground mb-2">最活跃的一天</p>
            <p className="font-serif text-[24px] font-bold tabular-nums mb-1">{specialMoments.most_active_day.plays} 首</p>
            <p className="font-sans text-[13px] text-muted-foreground mb-3">{specialMoments.most_active_day.date}</p>
            <div className="flex items-center gap-2">
              <MiniCover url={specialMoments.most_active_day.top_track.cover_url} name={specialMoments.most_active_day.top_track.name} />
              <p className="font-sans text-[12px] truncate">{specialMoments.most_active_day.top_track.name}</p>
            </div>
          </GlassCard>
        )}

        {/* 最早听歌 */}
        {specialMoments.earliest_listen && (
          <GlassCard className="p-5">
            <p className="font-sans text-[11px] uppercase tracking-[1.2px] text-muted-foreground mb-2">最早听歌</p>
            <p className="font-serif text-[24px] font-bold tabular-nums mb-1">{specialMoments.earliest_listen.hour}:00</p>
            <p className="font-sans text-[13px] text-muted-foreground mb-3">凌晨</p>
            <div className="flex items-center gap-2">
              <MiniCover url={specialMoments.earliest_listen.track.cover_url} name={specialMoments.earliest_listen.track.name} />
              <p className="font-sans text-[12px] truncate">{specialMoments.earliest_listen.track.name}</p>
            </div>
          </GlassCard>
        )}

        {/* 最晚听歌 */}
        {specialMoments.latest_listen && (
          <GlassCard className="p-5">
            <p className="font-sans text-[11px] uppercase tracking-[1.2px] text-muted-foreground mb-2">最晚听歌</p>
            <p className="font-serif text-[24px] font-bold tabular-nums mb-1">{specialMoments.latest_listen.hour}:00</p>
            <p className="font-sans text-[13px] text-muted-foreground mb-3">深夜</p>
            <div className="flex items-center gap-2">
              <MiniCover url={specialMoments.latest_listen.track.cover_url} name={specialMoments.latest_listen.track.name} />
              <p className="font-sans text-[12px] truncate">{specialMoments.latest_listen.track.name}</p>
            </div>
          </GlassCard>
        )}

        {/* 最长连续 */}
        {specialMoments.longest_streak && (
          <GlassCard className="p-5">
            <p className="font-sans text-[11px] uppercase tracking-[1.2px] text-muted-foreground mb-2">最长连续听歌</p>
            <p className="font-serif text-[24px] font-bold tabular-nums mb-1">{specialMoments.longest_streak.days} 天</p>
            <p className="font-sans text-[12px] text-muted-foreground">
              {specialMoments.longest_streak.start} ~ {specialMoments.longest_streak.end}
            </p>
          </GlassCard>
        )}
      </div>
    </section>
  )
}
