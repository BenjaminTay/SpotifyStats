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

interface AlbumsNumberOnesSectionProps {
  computed: NumberOnesComputed
  yearFiltered: YearFilteredNumberOnes
  availableYears: number[]
  selectedYear: number
  onYearChange: (year: number) => void
}

export function AlbumsNumberOnesSection({
  computed,
  yearFiltered,
  availableYears,
  selectedYear,
  onYearChange,
}: AlbumsNumberOnesSectionProps) {
  const longestAlbum = computed.albumLongest.streak > 0
    ? computed.albumNo1WeeksSorted.find((album) => album.album_name === computed.albumLongest.name)
    : null

  return (
    <>
      <div className="mb-8 grid grid-cols-3 gap-6">
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">总冠军专辑数</p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {new Set(computed.albumNo1WeeksSorted.map((entry) => entry.album_name)).size}{' '}
            <span className="text-[18px] font-normal">张</span>
          </p>
          {computed.albumNo1List[0] && (
            <NameWithCover
              coverUrl={computed.albumNo1List[0].cover_url}
              name={computed.albumNo1List[0].album_name}
              artistName={computed.albumNo1List[0].artist_name}
              nameLink={billboardDetailLink(`/music/albums/${encodeURIComponent(computed.albumNo1List[0].album_name)}`)}
              artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(computed.albumNo1List[0].artist_name)}`)}
              badge="最新冠军"
            />
          )}
        </GlassCard>
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最多冠军周数</p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.albumNo1WeeksSorted[0]?.weeks_at_no1 ?? 0}{' '}
            <span className="text-[18px] font-normal">周</span>
          </p>
          {computed.albumNo1WeeksSorted[0] && (
            <NameWithCover
              coverUrl={computed.albumNo1WeeksSorted[0].cover_url}
              name={computed.albumNo1WeeksSorted[0].album_name}
              artistName={computed.albumNo1WeeksSorted[0].artist_name}
              nameLink={billboardDetailLink(`/music/albums/${encodeURIComponent(computed.albumNo1WeeksSorted[0].album_name)}`)}
              artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(computed.albumNo1WeeksSorted[0].artist_name)}`)}
            />
          )}
        </GlassCard>
        <GlassCard className="p-6">
          <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最长连冠纪录</p>
          <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
            {computed.albumLongest.streak} <span className="text-[18px] font-normal">周</span>
          </p>
          {longestAlbum && (
            <NameWithCover
              coverUrl={longestAlbum.cover_url}
              name={longestAlbum.album_name}
              artistName={displayName(longestAlbum.artist_name)}
              nameLink={billboardDetailLink(`/music/albums/${encodeURIComponent(longestAlbum.album_name)}`)}
              artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(longestAlbum.artist_name)}`)}
            />
          )}
        </GlassCard>
      </div>

      <GlassCard className="mb-8 overflow-hidden p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-serif text-[22px] font-bold tracking-[-0.3px]">每周冠军专辑</h2>
          <YearSwitcher
            availableYears={availableYears}
            selectedYear={selectedYear}
            uniqueCount={yearFiltered.uniqueAlbumCount}
            unit="张冠军专辑"
            onYearChange={onYearChange}
          />
        </div>
        <div className="max-h-[600px] overflow-auto">
          <table className="w-full table-fixed border-collapse">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="sticky top-0 w-[96px] bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">周</th>
                <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军专辑</th>
                <th className="sticky top-0 w-[132px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">总播放</th>
                <th className="sticky top-0 w-[72px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">入榜曲数</th>
                <th className="sticky top-0 w-[64px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Pk Wks</th>
              </tr>
            </thead>
            <tbody>
              {yearFiltered.albums.map((entry) => (
                <tr key={`${entry.album_name}-${entry.artist_name}-${entry.billboard_week}`} className="border-b border-border transition-colors hover:bg-muted/30">
                  <td className="w-[96px] py-3 font-sans text-[13px]">
                    <Link to={`/billboard?week=${entry.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                      {formatWeekStart(entry.billboard_week)}
                    </Link>
                  </td>
                  <td className="py-3">
                    <NameWithCover
                      coverUrl={entry.cover_url}
                      name={entry.album_name}
                      artistName={displayName(entry.artist_name)}
                      nameLink={billboardDetailLink(`/music/albums/${encodeURIComponent(entry.album_name)}`)}
                      artistLink={billboardDetailLink(`/music/artists/${encodeURIComponent(entry.artist_name)}`)}
                    />
                  </td>
                  <td className="py-3 text-right">
                    <PlayCountCell value={entry.play_count} max={yearFiltered.albumMaxPlays} />
                  </td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.tracks_count}</td>
                  <td className="py-3 text-right font-sans text-[13px] tabular-nums">{entry.album_pk_wks}</td>
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
                  <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">专辑</th>
                  <th className="sticky top-0 bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军周数</th>
                </tr>
              </thead>
              <tbody>
                {computed.albumNo1WeeksSorted.slice(0, 20).map((entry, index) => (
                  <tr key={`${entry.album_name}-${entry.artist_name}`} className="border-b border-border transition-colors hover:bg-muted/30">
                    <td className="py-3 font-serif text-[15px] font-semibold tabular-nums text-muted-foreground">{index + 1}</td>
                    <td className="py-3">
                      <NameWithCover
                        coverUrl={entry.cover_url}
                        name={entry.album_name}
                        artistName={displayName(entry.artist_name)}
                        nameLink={billboardDetailLink(`/music/albums/${encodeURIComponent(entry.album_name)}`)}
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
          <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">专辑冠军周数 Top 15</h2>
          {computed.albumNo1WeeksSorted.length === 0 ? (
            <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无专辑冠军数据</p>
          ) : (
            <No1BarChart
              label="冠军周数"
              data={computed.albumNo1WeeksSorted.slice(0, 15).map((entry) => ({
                name: entry.album_name,
                value: entry.weeks_at_no1,
                subtitle: entry.artist_name,
              }))}
            />
          )}
        </GlassCard>
      </div>

      <div className="mb-8">
        <AnnualSection title="每年独特冠军专辑统计" items={computed.albumAnnualNo1} unit="张" />
      </div>

    </>
  )
}
