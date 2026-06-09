import type { AlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { MiniStat } from './AlbumDetailPrimitives'
import { formatDateShort, formatNumber } from './MusicDetailPrimitives'

type AlbumPersonalStorySectionProps = {
  data: AlbumDetailResponse
}

export function AlbumPersonalStorySection({ data }: AlbumPersonalStorySectionProps) {
  const firstWeek = data.album_weekly_history[0]

  return (
    <div className="mb-8">
      <h3 className="mb-4 font-serif text-xl font-semibold">你的收听故事</h3>
      <GlassCard className="p-5">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
          <MiniStat
            label="首次收听"
            value={firstWeek ? formatDateShort(firstWeek.week) : '—'}
          />
          <MiniStat
            label="总播放次数"
            value={formatNumber(
              data.album_weekly_history.reduce((sum, e) => sum + e.play_count, 0)
            )}
          />
          <MiniStat
            label="在榜周数"
            value={formatNumber(data.chart_summary.weeks_on_chart)}
          />
          <MiniStat
            label="最高排名"
            value={`#${data.chart_summary.peak_position}`}
            accent={data.chart_summary.peak_position === 1}
          />
        </div>
      </GlassCard>
    </div>
  )
}
