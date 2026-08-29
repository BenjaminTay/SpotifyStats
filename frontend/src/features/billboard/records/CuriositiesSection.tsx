import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

import { cn } from '@/lib/utils'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import type { ArtistTrackCounts, BillboardRecords, DoubleDebutRecord, TrackSummary, TripleNo1Record } from '@/types/billboard'
import { useViewportMode } from '@/hooks/useViewportMode'
import type { CoverMaps } from './recordsData'
import {
  AlbumCell,
  ArtistCell,
  CoverImg,
  FeaturedRecord,
  fmtNum,
  MiniRankTable,
  PeakNum,
  RankNum,
  RecordCard,
  SectionHeader,
  TrackCell,
  ValueBar,
  WeekLink,
  fmtDate,
} from './RecordsPrimitives'

type DebutSortMode = 'date' | 'market'

function compareTextAsc(a: unknown, b: unknown) {
  return String(a ?? '').localeCompare(String(b ?? ''))
}

function compareIdAsc(a: unknown, b: unknown) {
  return Number(a ?? 0) - Number(b ?? 0)
}

type MobileAchievement = {
  chartLabel: '单曲榜' | '专辑榜' | '艺人榜'
  name: string
  supportingText?: string
  coverUrl?: string | null
  detailLink: string
}

function MobileChartAchievementRow({ achievement }: { achievement: MobileAchievement }) {
  useChineseTextVersion()
  return (
    <Link
      to={achievement.detailLink}
      className="mobile-curiosity-achievement-row"
      aria-label={`${achievement.chartLabel}冠军：${displayName(achievement.name)}`}
    >
      <span className="mobile-curiosity-chart-label">{achievement.chartLabel}</span>
      <CoverImg url={achievement.coverUrl} />
      <span className="mobile-curiosity-entity-copy">
        <strong>{displayName(achievement.name)}</strong>
        <small aria-hidden={!achievement.supportingText}>
          {achievement.supportingText ? displayName(achievement.supportingText) : '\u00A0'}
        </small>
      </span>
      <span className="mobile-curiosity-chart-rank" aria-hidden="true">#1</span>
    </Link>
  )
}

function MobileCuriosityEvent({ week, marketPlays, achievements }: {
  week: string
  marketPlays: number
  achievements: MobileAchievement[]
}) {
  return (
    <article className="mobile-curiosity-event">
      <header className="mobile-curiosity-event-header">
        <WeekLink date={week} />
        <span>当周播放 <strong>{fmtNum(marketPlays)}</strong></span>
      </header>
      <div className="mobile-curiosity-achievements">
        {achievements.map((achievement) => (
          <MobileChartAchievementRow key={achievement.chartLabel} achievement={achievement} />
        ))}
      </div>
    </article>
  )
}

function CuriosityMetricValue({ value, unit }: { value: number; unit?: string }) {
  const isPhone = useViewportMode() === 'phone'
  if (isPhone) {
    return (
      <span className="mobile-record-value">
        {fmtNum(value)}{unit && <small>{unit}</small>}
      </span>
    )
  }
  return (
    <span className="font-sans text-[13px] tabular-nums text-muted-foreground">
      {fmtNum(value)}{unit && ` ${unit}`}
    </span>
  )
}

function SortToggle({ mode, desc, onChange, dateLabel }: { mode: DebutSortMode; desc: boolean; onChange: (m: DebutSortMode) => void; dateLabel?: string }) {
  const items: { key: DebutSortMode; label: string }[] = [
    { key: 'date', label: dateLabel ?? '空降周' },
    { key: 'market', label: '大盘播放' },
  ]
  return (
    <div className="flex items-center gap-1.5">
      <span className="font-sans text-[10px] text-muted-foreground">排序：</span>
      <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
        {items.map((opt) => {
          const active = mode === opt.key
          const arrow = active ? (desc ? ' ↓' : ' ↑') : ''
          return (
            <button key={opt.key} onClick={() => onChange(opt.key)}
              className={cn('rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors', active ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
              {opt.label}{arrow}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function CuriositiesSection({ rec, covers, trackSummary, artistTrackCounts }: {
  rec: BillboardRecords; covers: CoverMaps; trackSummary: TrackSummary[]; artistTrackCounts: ArtistTrackCounts[]
}) {
  useChineseTextVersion()
  const weekPlays = useMemo(() => {
    const map = new Map<string, number>()
    for (const w of rec.week_total_plays) {
      map.set(w.billboard_week, w.total_plays ?? 0)
    }
    return map
  }, [rec.week_total_plays])

  const [debutSort, setDebutSort] = useState<{ mode: DebutSortMode; desc: boolean }>({ mode: 'date', desc: true })

  const handleDebutSort = (mode: DebutSortMode) => {
    setDebutSort(prev => prev.mode === mode ? { mode, desc: !prev.desc } : { mode, desc: true })
  }

  const doubleDebutSorted = useMemo(() => {
    const rows = [...rec.double_debut]
    return rows.sort((a, b) => {
      const cmp = debutSort.mode === 'date'
        ? a.debut_week.localeCompare(b.debut_week)
        : (weekPlays.get(a.debut_week) ?? 0) - (weekPlays.get(b.debut_week) ?? 0)
      if (cmp !== 0) return debutSort.desc ? -cmp : cmp
      const secondary = debutSort.mode === 'date'
        ? (weekPlays.get(b.debut_week) ?? 0) - (weekPlays.get(a.debut_week) ?? 0)
        : b.debut_week.localeCompare(a.debut_week)
      if (secondary !== 0) return secondary
      return compareIdAsc(a.debut_track_id, b.debut_track_id)
        || compareTextAsc(a.debut_artist, b.debut_artist)
        || compareTextAsc(a.debut_album, b.debut_album)
        || compareTextAsc(a.debut_track, b.debut_track)
    })
  }, [rec.double_debut, debutSort, weekPlays])

  const [tripleSort, setTripleSort] = useState<{ mode: DebutSortMode; desc: boolean }>({ mode: 'date', desc: true })

  const handleTripleSort = (mode: DebutSortMode) => {
    setTripleSort(prev => prev.mode === mode ? { mode, desc: !prev.desc } : { mode, desc: true })
  }

  const tripleSorted = useMemo(() => {
    const rows = [...rec.triple_no1]
    return rows.sort((a, b) => {
      const cmp = tripleSort.mode === 'date'
        ? a.billboard_week.localeCompare(b.billboard_week)
        : (weekPlays.get(a.billboard_week) ?? 0) - (weekPlays.get(b.billboard_week) ?? 0)
      if (cmp !== 0) return tripleSort.desc ? -cmp : cmp
      const secondary = tripleSort.mode === 'date'
        ? (weekPlays.get(b.billboard_week) ?? 0) - (weekPlays.get(a.billboard_week) ?? 0)
        : b.billboard_week.localeCompare(a.billboard_week)
      if (secondary !== 0) return secondary
      return compareIdAsc(a.track_id, b.track_id)
        || compareTextAsc(a['艺人'], b['艺人'])
        || compareTextAsc(a['歌曲'], b['歌曲'])
        || compareTextAsc(a['专辑'], b['专辑'])
    })
  }, [rec.triple_no1, tripleSort, weekPlays])

  const oneHitWonders = useMemo(() => artistTrackCounts.filter(a => a.total_tracks === 1 && a.top1 >= 1).sort((a, b) => {
    return b.weeks_at_no1 - a.weeks_at_no1
      || b.total_weeks - a.total_weeks
      || b.top1 - a.top1
      || compareTextAsc(a.artist_name, b.artist_name)
  }), [artistTrackCounts])
  const prolificArtists = useMemo(() => [...artistTrackCounts].sort((a, b) => {
    return b.total_tracks - a.total_tracks
      || b.top1 - a.top1
      || b.total_weeks - a.total_weeks
      || compareTextAsc(a.artist_name, b.artist_name)
  }).slice(0, 20), [artistTrackCounts])
  const sameNameDiffArtist = useMemo(() => {
    const groups = new Map<string, TrackSummary[]>()
    for (const t of trackSummary) { const name = t.track_name.toLowerCase(); if (!groups.has(name)) groups.set(name, []); groups.get(name)!.push(t) }
    return Array.from(groups.values())
      .filter(g => { const artists = new Set(g.map(t => t.artist_name)); return artists.size >= 2 })
      .sort((a, b) => b.length - a.length || compareTextAsc(a[0]?.track_name, b[0]?.track_name))
      .slice(0, 10)
      .map(group => [...group].sort((a, b) => {
        return (a.peak_position ?? Number.POSITIVE_INFINITY) - (b.peak_position ?? Number.POSITIVE_INFINITY)
          || a.first_week.localeCompare(b.first_week)
          || compareTextAsc(a.artist_name, b.artist_name)
          || compareIdAsc(a.track_id, b.track_id)
      }))
  }, [trackSummary])
  const oldestTrack = useMemo(() => [...trackSummary].filter(t => t.first_week).sort((a, b) => a.first_week.localeCompare(b.first_week) || compareIdAsc(a.track_id, b.track_id) || compareTextAsc(a.artist_name, b.artist_name))[0] ?? null, [trackSummary])
  const newestTrack = useMemo(() => [...trackSummary].filter(t => t.first_week).sort((a, b) => b.first_week.localeCompare(a.first_week) || compareIdAsc(a.track_id, b.track_id) || compareTextAsc(a.artist_name, b.artist_name))[0] ?? null, [trackSummary])
  const longestName = useMemo(() => [...trackSummary].sort((a, b) => b.track_name.length - a.track_name.length || compareTextAsc(a.track_name, b.track_name) || compareIdAsc(a.track_id, b.track_id))[0] ?? null, [trackSummary])
  const shortestName = useMemo(() => [...trackSummary].sort((a, b) => a.track_name.length - b.track_name.length || compareTextAsc(a.track_name, b.track_name) || compareIdAsc(a.track_id, b.track_id))[0] ?? null, [trackSummary])

  return (
    <div>
      <SectionHeader icon={Sparkles} title="奇趣纪录" subtitle="那些让人会心一笑的冷知识——数据里的彩蛋" />

      <RecordCard title="双榜空降 · Double Debut" subtitle="同一艺人的歌曲与专辑在同一周分别空降榜首">
        <div className="mb-3 flex justify-end md:block">
          <SortToggle mode={debutSort.mode} desc={debutSort.desc} onChange={handleDebutSort} />
        </div>
        <MiniRankTable<DoubleDebutRecord> rows={doubleDebutSorted} mobileRenderRow={(row) => (
          <MobileCuriosityEvent
            week={row.debut_week}
            marketPlays={weekPlays.get(row.debut_week) ?? 0}
            achievements={[
              {
                chartLabel: '单曲榜',
                name: row.debut_track,
                supportingText: row.debut_artist,
                coverUrl: covers.track.get(row.debut_track_id),
                detailLink: billboardDetailLink(`/music/tracks/${row.debut_track_id}`),
              },
              {
                chartLabel: '专辑榜',
                name: row.debut_album,
                supportingText: row.debut_artist,
                coverUrl: covers.album.get(row.debut_album),
                detailLink: billboardDetailLink(`/music/albums/${encodeURIComponent(row.debut_album)}`),
              },
            ]}
          />
        )} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '空降周', width: '110px', mobileRole: 'primary', render: (r) => <WeekLink date={r.debut_week} /> },
          { header: '歌曲', mobileRole: 'entity', render: (r) => <TrackCell trackId={r.debut_track_id} trackName={r.debut_track} artistName={r.debut_artist} coverUrl={covers.track.get(r.debut_track_id)} /> },
          { header: '专辑', render: (r) => <AlbumCell albumName={r.debut_album} artistName={r.debut_artist} coverUrl={covers.album.get(r.debut_album)} /> },
        ]} />
      </RecordCard>

      <RecordCard title="全榜单制霸 · Triple #1" subtitle="同一周单曲榜、专辑榜、艺人榜三榜 #1 同属一人">
        <div className="mb-3 flex justify-end md:block">
          <SortToggle mode={tripleSort.mode} desc={tripleSort.desc} onChange={handleTripleSort} dateLabel="榜单周" />
        </div>
        <MiniRankTable<TripleNo1Record> rows={tripleSorted} mobileRenderRow={(row) => (
          <MobileCuriosityEvent
            week={row.billboard_week}
            marketPlays={weekPlays.get(row.billboard_week) ?? 0}
            achievements={[
              {
                chartLabel: '单曲榜',
                name: row['歌曲'],
                supportingText: row['艺人'],
                coverUrl: covers.track.get(row.track_id),
                detailLink: billboardDetailLink(`/music/tracks/${row.track_id}`),
              },
              {
                chartLabel: '专辑榜',
                name: row['专辑'],
                supportingText: row['艺人'],
                coverUrl: covers.album.get(row['专辑']),
                detailLink: billboardDetailLink(`/music/albums/${encodeURIComponent(row['专辑'])}`),
              },
              {
                chartLabel: '艺人榜',
                name: row['艺人'],
                coverUrl: covers.artist.get(row['艺人']),
                detailLink: billboardDetailLink(`/music/artists/${encodeURIComponent(row['艺人'])}`),
              },
            ]}
          />
        )} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '榜单周', width: '110px', mobileRole: 'primary', render: (r) => <WeekLink date={r.billboard_week} /> },
          { header: '艺人', mobileRole: 'entity', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} compact /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r['歌曲']} artistName={r['艺人']} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '专辑', render: (r) => <AlbumCell albumName={r['专辑']} artistName={r['艺人']} coverUrl={covers.album.get(r['专辑'])} /> },
        ]} />
      </RecordCard>

      <RecordCard title="一曲成名 · One-Hit Wonder" subtitle="仅一首歌上榜且直接夺冠" mobileSubtitle="仅一首歌上榜且直接夺冠">
        <MiniRankTable rows={oneHitWonders} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '冠军单曲', mobileRole: 'fact', render: (r) => <span className="font-sans text-[12px] font-semibold">{displayName(r.best_peak_track)}</span> },
          { header: '冠军周数', width: '110px', align: 'right', mobileRole: 'primary', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_at_no1} 周</span> },
        ]} />
      </RecordCard>

      <RecordCard title="劳模歌手 · Most Prolific Artists" subtitle="上榜歌曲数最多的艺人">
        <MiniRankTable rows={prolificArtists} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '上榜歌曲', width: '145px', align: 'right', render: (r) => <ValueBar value={r.total_tracks} max={prolificArtists[0]?.total_tracks ?? 1} suffix="首" /> },
          { header: '最佳Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.best_peak as number} /> },
          { header: '冠单数', width: '60px', align: 'center', render: (r) => <CuriosityMetricValue value={r.top1} /> },
          { header: '总周数', width: '110px', align: 'right', render: (r) => <CuriosityMetricValue value={r.total_weeks} unit="周" /> },
        ]} />
      </RecordCard>

      <RecordCard title="同名异曲 · Same Name, Different Song" subtitle="相同歌名、不同艺人的歌曲">
        {sameNameDiffArtist.length > 0 ? (
          <div className="space-y-3">
            {sameNameDiffArtist.slice(0, 5).map((group) => (
              <div key={group[0].track_name} className="rounded-[10px] border border-border bg-muted/20 p-4">
                <p className="mb-2 font-sans text-[14px] font-bold">"{displayName(group[0].track_name)}"</p>
                <div className="flex flex-wrap gap-2">
                  {group.map((t) => (
                    <Link key={t.track_id} to={billboardDetailLink(`/music/tracks/${t.track_id}`)} className="inline-flex items-center gap-1.5 rounded-[6px] bg-background px-2.5 py-1 font-sans text-[12px] transition-colors hover:bg-muted">{displayName(t.artist_name)}<span className="text-[10px] text-muted-foreground">Peak #{t.peak_position}</span></Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      <section className="mobile-curiosity-extremes" aria-label="榜单极值纪录">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-5">
          {oldestTrack && <FeaturedRecord label="最早入榜" value={fmtDate(oldestTrack.first_week)} caption={`${oldestTrack.track_name} — ${oldestTrack.artist_name}`} linkTo={billboardDetailLink(`/music/tracks/${oldestTrack.track_id}`)} />}
          {newestTrack && <FeaturedRecord label="最新入榜" value={fmtDate(newestTrack.first_week)} caption={`${newestTrack.track_name} — ${newestTrack.artist_name}`} linkTo={billboardDetailLink(`/music/tracks/${newestTrack.track_id}`)} />}
          {longestName && <FeaturedRecord label="最长歌名" value={longestName.track_name.length} unit="字" caption={`${longestName.track_name} — ${longestName.artist_name}`} linkTo={billboardDetailLink(`/music/tracks/${longestName.track_id}`)} />}
          {shortestName && <FeaturedRecord label="最短歌名" value={shortestName.track_name.length} unit="字" caption={`${shortestName.track_name} — ${shortestName.artist_name}`} linkTo={billboardDetailLink(`/music/tracks/${shortestName.track_id}`)} />}
        </div>
      </section>
    </div>
  )
}
