import { Link } from 'react-router-dom'

import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import {
  ArtistWithCover,
  No1BarChart,
  PlayCountCell,
  YearSwitcher,
} from './NumberOnesPrimitives'
import { formatWeekStart, type NumberOnesComputed, type YearFilteredNumberOnes } from './numberOnesData'

interface ArtistsNumberOnesSectionProps {
  computed: NumberOnesComputed
  yearFiltered: YearFilteredNumberOnes
  availableYears: number[]
  selectedYear: number
  onYearChange: (year: number) => void
}

export function ArtistsNumberOnesSection({
  computed,
  yearFiltered,
  availableYears,
  selectedYear,
  onYearChange,
}: ArtistsNumberOnesSectionProps) {
  const longestArtist = computed.artistLongest.streak > 0
    ? computed.artistNo1WeeksSorted.find((artist) => artist.artist_name === computed.artistLongest.name)
    : null

  return (
    <>
      <div className="mb-8 grid grid-cols-3 gap-6">
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">总冠军艺人</p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.artistNo1WeeksSorted.length} <span className="text-[18px] font-normal">位</span>
          </p>
          {computed.artistNo1List[0] && (
            <ArtistWithCover
              coverUrl={computed.artistNo1List[0].cover_url}
              artistName={computed.artistNo1List[0].artist_name}
              badge="最新冠军"
            />
          )}
        </GlassCard>
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最多冠军周数</p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.artistNo1WeeksSorted[0]?.weeks_at_no1 ?? 0}{' '}
            <span className="text-[18px] font-normal">周</span>
          </p>
          {computed.artistNo1WeeksSorted[0] && (
            <ArtistWithCover
              coverUrl={computed.artistNo1WeeksSorted[0].cover_url}
              artistName={computed.artistNo1WeeksSorted[0].artist_name}
            />
          )}
        </GlassCard>
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最长连冠纪录</p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.artistLongest.streak} <span className="text-[18px] font-normal">周</span>
          </p>
          {longestArtist && (
            <ArtistWithCover coverUrl={longestArtist.cover_url} artistName={longestArtist.artist_name} />
          )}
        </GlassCard>
      </div>

      <GlassCard className="mb-8 overflow-hidden p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-serif text-[22px] font-bold tracking-[-0.3px]">每周冠军艺人</h2>
          <YearSwitcher
            availableYears={availableYears}
            selectedYear={selectedYear}
            uniqueCount={yearFiltered.uniqueArtistCount}
            unit="位冠军艺人"
            onYearChange={onYearChange}
          />
        </div>
        <div className="max-h-[600px] overflow-auto">
          <table className="w-full table-fixed border-collapse">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="sticky top-0 w-[96px] bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">周</th>
                <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军艺人</th>
                <th className="sticky top-0 w-[132px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">总播放</th>
                <th className="sticky top-0 w-[72px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">入榜曲数</th>
                <th className="sticky top-0 w-[72px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">入榜专辑</th>
                <th className="sticky top-0 w-[64px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Pk Wks</th>
              </tr>
            </thead>
            <tbody>
              {yearFiltered.artists.map((entry) => (
                <tr key={`${entry.artist_name}-${entry.billboard_week}`} className="border-b border-border transition-colors hover:bg-muted/30">
                  <td className="w-[96px] py-3 font-sans text-[13px]">
                    <Link to={`/billboard?week=${entry.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                      {formatWeekStart(entry.billboard_week)}
                    </Link>
                  </td>
                  <td className="py-3">
                    <ArtistWithCover coverUrl={entry.cover_url} artistName={entry.artist_name} />
                  </td>
                  <td className="py-3 text-right">
                    <PlayCountCell value={entry.play_count} max={yearFiltered.artistMaxPlays} />
                  </td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.tracks_count}</td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.albums_count}</td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.artist_pk_wks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <div className="mb-8 grid grid-cols-2 gap-6">
        <GlassCard className="overflow-hidden p-6">
          <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">冠军周数排行</h2>
          <div className="max-h-[500px] overflow-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">#</th>
                  <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">艺人</th>
                  <th className="sticky top-0 bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军周数</th>
                </tr>
              </thead>
              <tbody>
                {computed.artistNo1WeeksSorted.slice(0, 20).map((entry, index) => (
                  <tr key={displayName(entry.artist_name)} className="border-b border-border transition-colors hover:bg-muted/30">
                    <td className="py-3 font-serif text-[15px] font-semibold tabular-nums text-muted-foreground">{index + 1}</td>
                    <td className="py-3">
                      <ArtistWithCover coverUrl={entry.cover_url} artistName={entry.artist_name} />
                    </td>
                    <td className="py-3 text-right font-sans text-[13px] font-semibold tabular-nums">{entry.weeks_at_no1}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <GlassCard className="p-6">
          <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">艺人冠军周数 Top 15</h2>
          {computed.artistNo1WeeksSorted.length === 0 ? (
            <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无艺人冠军数据</p>
          ) : (
            <No1BarChart
              label="冠军周数"
              data={computed.artistNo1WeeksSorted.slice(0, 15).map((entry) => ({
                name: entry.artist_name,
                value: entry.weeks_at_no1,
              }))}
            />
          )}
        </GlassCard>
      </div>
    </>
  )
}
