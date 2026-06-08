import { Link } from 'react-router-dom'

import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import {
  AnnualSection,
  NameWithCover,
  No1BarChart,
  PlayCountCell,
  YearSwitcher,
} from './NumberOnesPrimitives'
import { formatWeekStart, type NumberOnesComputed, type YearFilteredNumberOnes } from './numberOnesData'

interface TracksNumberOnesSectionProps {
  computed: NumberOnesComputed
  yearFiltered: YearFilteredNumberOnes
  availableYears: number[]
  selectedYear: number
  onYearChange: (year: number) => void
}

export function TracksNumberOnesSection({
  computed,
  yearFiltered,
  availableYears,
  selectedYear,
  onYearChange,
}: TracksNumberOnesSectionProps) {
  const longestTrack = computed.trackLongest.streak > 0
    ? computed.trackNo1WeeksSorted.find((track) => track.track_name === computed.trackLongest.name)
    : null

  return (
    <>
      <div className="mb-8 grid grid-cols-3 gap-6">
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
            总冠军歌曲数
          </p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.trackNo1WeeksSorted.length} <span className="text-[18px] font-normal">首</span>
          </p>
          {computed.trackNo1List[0] && (
            <NameWithCover
              coverUrl={computed.trackNo1List[0].cover_url}
              name={computed.trackNo1List[0].track_name}
              artistName={computed.trackNo1List[0].artist_name}
              nameLink={billboardDetailLink(`/music/tracks/${computed.trackNo1List[0].track_id}`)}
              artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(computed.trackNo1List[0].artist_name)}`)}
              badge="最新冠军"
            />
          )}
        </GlassCard>
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
            最多冠军周数
          </p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.trackNo1WeeksSorted[0]?.weeks_at_no1 ?? 0}{' '}
            <span className="text-[18px] font-normal">周</span>
          </p>
          {computed.trackNo1WeeksSorted[0] && (
            <NameWithCover
              coverUrl={computed.trackNo1WeeksSorted[0].cover_url}
              name={computed.trackNo1WeeksSorted[0].track_name}
              artistName={computed.trackNo1WeeksSorted[0].artist_name}
              nameLink={billboardDetailLink(`/music/tracks/${computed.trackNo1WeeksSorted[0].track_id}`)}
              artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(computed.trackNo1WeeksSorted[0].artist_name)}`)}
            />
          )}
        </GlassCard>
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
            最长连冠纪录
          </p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.trackLongest.streak} <span className="text-[18px] font-normal">周</span>
          </p>
          {longestTrack && (
            <NameWithCover
              coverUrl={longestTrack.cover_url}
              name={longestTrack.track_name}
              artistName={displayName(longestTrack.artist_name)}
              nameLink={billboardDetailLink(`/music/tracks/${longestTrack.track_id}`)}
              artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(longestTrack.artist_name)}`)}
            />
          )}
        </GlassCard>
      </div>

      <GlassCard className="mb-8 overflow-hidden p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-serif text-[22px] font-bold tracking-[-0.3px]">每周冠军歌曲</h2>
          <YearSwitcher
            availableYears={availableYears}
            selectedYear={selectedYear}
            uniqueCount={yearFiltered.uniqueTrackCount}
            unit="首冠军歌曲"
            onYearChange={onYearChange}
          />
        </div>
        <div className="max-h-[600px] overflow-auto">
          <table className="w-full table-fixed border-collapse">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="sticky top-0 w-[96px] bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">周</th>
                <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠单曲目</th>
                <th className="sticky top-0 w-[132px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">播放次数</th>
                <th className="sticky top-0 w-[64px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Pk Wks</th>
              </tr>
            </thead>
            <tbody>
              {yearFiltered.tracks.map((entry) => (
                <tr key={`${entry.track_id}-${entry.billboard_week}`} className="border-b border-border transition-colors hover:bg-muted/30">
                  <td className="w-[96px] py-3 font-sans text-[13px]">
                    <Link to={`/billboard?week=${entry.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                      {formatWeekStart(entry.billboard_week)}
                    </Link>
                  </td>
                  <td className="py-3">
                    <NameWithCover
                      coverUrl={entry.cover_url}
                      name={entry.track_name}
                      artistName={displayName(entry.artist_name)}
                      nameLink={billboardDetailLink(`/music/tracks/${entry.track_id}`)}
                      artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(entry.artist_name)}`)}
                    />
                  </td>
                  <td className="py-3 text-right">
                    <PlayCountCell value={entry.play_count} max={yearFiltered.trackMaxPlays} />
                  </td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.running_peak_wks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <div className="mb-8 grid grid-cols-2 gap-6">
        <GlassCard className="overflow-hidden p-6">
          <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">冠单周数排行</h2>
          <div className="max-h-[500px] overflow-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">#</th>
                  <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">曲目</th>
                  <th className="sticky top-0 bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠单周数</th>
                </tr>
              </thead>
              <tbody>
                {computed.trackNo1WeeksSorted.slice(0, 20).map((entry, index) => (
                  <tr key={entry.track_id} className="border-b border-border transition-colors hover:bg-muted/30">
                    <td className="py-3 font-serif text-[15px] font-semibold tabular-nums text-muted-foreground">{index + 1}</td>
                    <td className="py-3">
                      <NameWithCover
                        coverUrl={entry.cover_url}
                        name={entry.track_name}
                        artistName={displayName(entry.artist_name)}
                        nameLink={billboardDetailLink(`/music/tracks/${entry.track_id}`)}
                        artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(entry.artist_name)}`)}
                      />
                    </td>
                    <td className="py-3 text-right font-sans text-[13px] font-semibold tabular-nums">{entry.weeks_at_no1}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <GlassCard className="p-6">
          <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">单曲冠军周数 Top 15</h2>
          <No1BarChart
            label="冠单周数"
            data={computed.trackNo1WeeksSorted.slice(0, 15).map((entry) => ({
              name: entry.track_name,
              value: entry.weeks_at_no1,
              subtitle: entry.artist_name,
            }))}
          />
        </GlassCard>
      </div>

      <div className="mb-8">
        <AnnualSection title="每年独特冠单统计" items={computed.trackAnnualNo1} />
      </div>

      <GlassCard className="overflow-hidden p-6">
        <h2 className="mb-1 font-serif text-[22px] font-bold tracking-[-0.3px]">空冠歌曲</h2>
        <p className="mb-5 font-sans text-[13px] text-muted-foreground">
          首次上榜即 #1 · 共 {computed.debutNo1Tracks.length} 首
        </p>
        {computed.debutNo1Tracks.length === 0 ? (
          <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无空冠歌曲</p>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">曲目</th>
                <th className="pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">首次上榜周</th>
                <th className="pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">在榜周数</th>
                <th className="pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠单周数</th>
              </tr>
            </thead>
            <tbody>
              {computed.debutNo1Tracks.map((entry) => (
                <tr key={entry.track_id} className="border-b border-border transition-colors hover:bg-muted/30">
                  <td className="py-3">
                    <NameWithCover
                      coverUrl={entry.cover_url}
                      name={entry.track_name}
                      artistName={displayName(entry.artist_name)}
                      nameLink={billboardDetailLink(`/music/tracks/${entry.track_id}`)}
                      artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(entry.artist_name)}`)}
                    />
                  </td>
                  <td className="py-3 font-sans text-[13px]">
                    <Link to={`/billboard?week=${entry.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                      {formatWeekStart(entry.billboard_week)}
                    </Link>
                  </td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.weeks_on_chart}</td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.weeks_at_no1}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>
    </>
  )
}
