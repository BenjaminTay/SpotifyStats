import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Crown } from 'lucide-react'

import { cn } from '@/lib/utils'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import type { BillboardRecords, DecadeBestRecord } from '@/types/billboard'
import type { CoverMaps } from './recordsData'
import {
  AlbumCell,
  ArtistCell,
  ChartWeeksValue,
  CoverImg,
  FeaturedRecord,
  MiniRankTable,
  PeakNum,
  RankNum,
  RecordCard,
  SectionHeader,
  TrackCell,
  ValueBar,
} from './RecordsPrimitives'

function DecadeBestCard({ covers, decadeGroups }: { covers: CoverMaps; decadeGroups: Map<string, DecadeBestRecord[]> }) {
  useChineseTextVersion()
  const decades = useMemo(() => Array.from(decadeGroups.keys()).sort(), [decadeGroups])
  const [activeDecade, setActiveDecade] = useState<string>(decades[decades.length - 1] ?? '')
  const decadeTabsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (decades.length > 0 && !decades.includes(activeDecade)) {
      setActiveDecade(decades[decades.length - 1])
    }
  }, [decades, activeDecade])

  useEffect(() => {
    const container = decadeTabsRef.current
    const selected = container?.querySelector<HTMLElement>('[aria-selected="true"]')
    if (!container || !selected) return
    const left = selected.offsetLeft - (container.clientWidth - selected.offsetWidth) / 2
    container.scrollTo({ left: Math.max(0, left), behavior: 'smooth' })
  }, [activeDecade])

  const tracks = decadeGroups.get(activeDecade) ?? []

  return (
    <RecordCard title="年代之王 · Decade Best" toggle={
      <div ref={decadeTabsRef} role="tablist" aria-label="选择年代" className="mobile-record-decade-toggle flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
        {decades.map((d) => (
          <button key={d} type="button" role="tab" aria-selected={activeDecade === d} onClick={() => setActiveDecade(d)}
            className={cn('rounded-[4px] px-3 py-1 font-sans text-[11px] font-medium transition-colors', activeDecade === d ? 'active bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
            {d}
          </button>
        ))}
      </div>
    }>
      {tracks.length > 0 ? (
        <MiniRankTable rows={tracks} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '走势评分', width: '130px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={tracks[0]?.['走势评分'] ?? 1} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak} /> },
          { header: '在榜', width: '100px', align: 'right', render: (r) => <ChartWeeksValue value={r.weeks_on_chart} /> },
        ]} />
      ) : (
        <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>
      )}
    </RecordCard>
  )
}

export function HallOfFameSection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  useChineseTextVersion()
  const decadeGroups = useMemo(() => {
    const map = new Map<string, typeof rec.decade_best>()
    for (const r of rec.decade_best) { const key = r['年代']; if (!map.has(key)) map.set(key, []); map.get(key)!.push(r) }
    return map
  }, [rec.decade_best])

  const songScoreMax = rec.all_time_greatest[0]?.['走势评分'] ?? 1
  const albumScoreMax = rec.album_power_ranking[0]?.['走势评分'] ?? 1
  const artistScoreMax = rec.artist_power_ranking[0]?.['走势评分'] ?? 1

  return (
    <div>
      <SectionHeader icon={Crown} title="名人堂" subtitle="走势评分最高的歌曲、专辑与艺人——各年代的传奇之作" />

      {/* 歌曲走势总榜 */}
      <RecordCard title="歌曲走势总榜 · All-Time Greatest Songs">
        {rec.all_time_greatest.length > 0 && (
          <div className="mobile-record-podium mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {rec.all_time_greatest.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={r.track_id}
                label={['走势之王', '亚军', '季军'][i]}
                value={r['走势评分'].toFixed(0)}
                unit="走势评分"
                caption={`${r.track_name} — ${r.artist_name}`}
                coverUrl={covers.track.get(r.track_id)}
                linkTo={billboardDetailLink(`/music/tracks/${r.track_id}`)}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={rec.all_time_greatest} mobileSkip={3} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '走势评分', width: '145px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={songScoreMax} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          { header: '在榜', width: '110px', align: 'right', render: (r) => <ChartWeeksValue value={r.weeks_on_chart} /> },
        ]} />
      </RecordCard>

      {/* 专辑走势总榜 */}
      <RecordCard title="专辑走势总榜 · All-Time Greatest Albums">
        {rec.album_power_ranking.length > 0 && (
          <div className="mobile-record-podium mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {rec.album_power_ranking.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={`${r.album_name}-${r.artist_name}`}
                label={['走势之王', '亚军', '季军'][i]}
                value={r['走势评分'].toFixed(0)}
                unit="走势评分"
                caption={`${r.album_name} — ${r.artist_name}`}
                coverUrl={covers.album.get(r.album_name)}
                linkTo={billboardDetailLink(`/music/albums/${encodeURIComponent(r.album_name)}`)}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={rec.album_power_ranking} mobileSkip={3} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
          { header: '走势评分', width: '145px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={albumScoreMax} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          { header: '在榜', width: '110px', align: 'right', render: (r) => <ChartWeeksValue value={r.weeks_on_chart} /> },
        ]} />
      </RecordCard>

      {/* 艺人走势总榜 */}
      <RecordCard title="艺人走势总榜 · All-Time Greatest Artists">
        {rec.artist_power_ranking.length > 0 && (
          <div className="mobile-record-podium mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {rec.artist_power_ranking.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={r.artist_name}
                label={['走势之王', '亚军', '季军'][i]}
                value={r['走势评分'].toFixed(0)}
                unit="走势评分"
                caption={r.artist_name}
                coverUrl={covers.artist.get(r.artist_name)}
                linkTo={billboardDetailLink(`/music/artists/${encodeURIComponent(r.artist_name)}`)}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={rec.artist_power_ranking} mobileSkip={3} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '走势评分', width: '145px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={artistScoreMax} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position as number} /> },
          { header: '在榜', width: '110px', align: 'right', render: (r) => <ChartWeeksValue value={r.weeks_on_chart} /> },
        ]} />
      </RecordCard>

      {/* 年度之歌 */}
      <RecordCard title="年度之歌 · Year-End #1">
        {rec.year_end_no1.length > 0 ? (
          <div className="mobile-record-year-songs grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
            {rec.year_end_no1.map((r) => (
              <Link key={r.year} to={billboardDetailLink(`/music/tracks/${r.track_id}`)} className="mobile-record-year-song group rounded-[10px] border border-border bg-muted/20 p-4 transition-colors hover:bg-muted/40">
                <CoverImg url={covers.track.get(r.track_id)} />
                <p className="mt-2 font-serif text-[28px] font-bold leading-none tracking-[-0.5px]">{r.year}</p>
                <p className="mt-2 truncate font-sans text-[12px] font-semibold group-hover:text-accent-foreground">{displayName(r.track_name)}</p>
                <p className="truncate font-sans text-[11px] italic text-muted-foreground">{displayName(r.artist_name)}</p>
                <p className="mt-1 font-sans text-[11px] text-muted-foreground">Peak #{r.peak} · {r.weeks_on_chart} 周</p>
              </Link>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      {/* 年代之王 */}
      <DecadeBestCard covers={covers} decadeGroups={decadeGroups} />
    </div>
  )
}
