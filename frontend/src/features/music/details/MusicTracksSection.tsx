import { Link } from 'react-router-dom'
import { CoverCell } from '@/components/shared/CoverCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import {
  KpiStrip,
  PlaysCell,
  formatDateShort,
  formatNumber,
} from './MusicDetailPrimitives'

type TrackInfo = {
  total_tracks: number
  top1: number
  top5: number
  top10: number
  weeks_at_no1: number
}

type TrackEntry = {
  track_id: number
  track_name: string
  cover_url: string | null
  peak_position: number
  weeks_on_chart: number
  weeks_at_peak: number
  first_week: string
  first_peak_week: string
  last_week: string
  total_chart_plays: number
  power_score: number
  power_rank: number | null
}

export function MusicTracksSection({
  artistName,
  info,
  tracks,
}: {
  artistName: string
  info: TrackInfo
  tracks: TrackEntry[]
}) {
  return (
    <div className="mb-8">
      <KpiStrip
        items={[
          { label: '入榜曲目', value: formatNumber(info.total_tracks) },
          { label: '#1 曲目', value: formatNumber(info.top1), accent: info.top1 > 0 },
          { label: 'Top 5', value: formatNumber(info.top5) },
          { label: 'Top 10', value: formatNumber(info.top10) },
          {
            label: '冠军周数',
            value: formatNumber(info.weeks_at_no1),
            accent: info.weeks_at_no1 > 0,
          },
        ]}
      />

      <GlassCard className="overflow-hidden p-0">
        <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
          <thead>
            <tr>
              <th className="w-[44px] pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground" />
              <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                曲目
              </th>
              <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                峰值
              </th>
              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                峰位周
              </th>
              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                在榜
              </th>
              <th className="w-28 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                上榜播放
              </th>
              <th className="w-[72px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                走势点数
              </th>
              <th className="w-[60px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                走势排名
              </th>
              <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                首周
              </th>
              <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                首次达峰
              </th>
              <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                末周
              </th>
            </tr>
          </thead>
          <tbody>
            {(() => {
              const maxPlays = Math.max(...tracks.map((track) => track.total_chart_plays), 1)
              return tracks.map((track, index) => (
                <tr key={track.track_id} className="transition-colors hover:bg-muted/50">
                  <td className="py-3.5 pr-2">
                    <CoverCell index={index} coverUrl={track.cover_url} />
                  </td>
                  <td className="py-3.5 pl-1">
                    <Link
                      to={`/music/tracks/${track.track_id}`}
                      className="font-sans text-sm font-semibold leading-snug transition-colors hover:text-accent-foreground"
                    >
                      {displayName(track.track_name)}
                    </Link>
                    <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                      {displayName(artistName)}
                    </div>
                  </td>
                  <td
                    className="py-3.5 text-right font-serif text-[22px] font-bold italic"
                    style={{
                      color: track.peak_position === 1 ? 'var(--accent-foreground)' : undefined,
                    }}
                  >
                    {track.peak_position}
                  </td>
                  <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                    {track.weeks_at_peak}
                  </td>
                  <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                    {track.weeks_on_chart}
                  </td>
                  <td className="py-3.5 text-right">
                    <PlaysCell plays={track.total_chart_plays} maxPlays={maxPlays} />
                  </td>
                  <td className="py-3.5 text-right font-sans text-[13px] tabular-nums">
                    {track.power_score > 0 ? formatNumber(track.power_score) : '—'}
                  </td>
                  <td className="py-3.5 text-right font-serif text-[22px] italic text-muted-foreground">
                    {track.power_rank ?? '—'}
                  </td>
                  <td className="py-3.5 text-right">
                    <Link
                      to={`/billboard?week=${track.first_week}`}
                      className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                    >
                      {formatDateShort(track.first_week)}
                    </Link>
                  </td>
                  <td className="py-3.5 text-right">
                    <Link
                      to={`/billboard?week=${track.first_peak_week}`}
                      className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                    >
                      {formatDateShort(track.first_peak_week)}
                    </Link>
                  </td>
                  <td className="py-3.5 text-right">
                    <Link
                      to={`/billboard?week=${track.last_week}`}
                      className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                    >
                      {formatDateShort(track.last_week)}
                    </Link>
                  </td>
                </tr>
              ))
            })()}
          </tbody>
        </table>
      </GlassCard>
    </div>
  )
}
