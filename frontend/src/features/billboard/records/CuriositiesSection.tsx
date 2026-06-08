import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

import { displayName } from '@/lib/chinese'
import type { ArtistTrackCounts, BillboardRecords, TrackSummary } from '@/types/billboard'
import type { CoverMaps } from './recordsData'
import {
  ArtistCell,
  ArtistCoverImg,
  FeaturedRecord,
  MiniRankTable,
  PeakNum,
  RankNum,
  RecordCard,
  SectionHeader,
  TrackCell,
  ValueBar,
  fmtDate,
} from './RecordsPrimitives'

export function CuriositiesSection({ rec, covers, trackSummary, artistTrackCounts }: {
  rec: BillboardRecords; covers: CoverMaps; trackSummary: TrackSummary[]; artistTrackCounts: ArtistTrackCounts[]
}) {
  const oneHitWonders = useMemo(() => artistTrackCounts.filter(a => a.total_tracks === 1 && a.top1 >= 1).sort((a, b) => b.weeks_at_no1 - a.weeks_at_no1), [artistTrackCounts])
  const prolificArtists = useMemo(() => [...artistTrackCounts].sort((a, b) => b.total_tracks - a.total_tracks).slice(0, 20), [artistTrackCounts])
  const sameNameDiffArtist = useMemo(() => {
    const groups = new Map<string, TrackSummary[]>()
    for (const t of trackSummary) { const name = t.track_name.toLowerCase(); if (!groups.has(name)) groups.set(name, []); groups.get(name)!.push(t) }
    return Array.from(groups.values()).filter(g => { const artists = new Set(g.map(t => t.artist_name)); return artists.size >= 2 }).sort((a, b) => b.length - a.length).slice(0, 10)
  }, [trackSummary])
  const oldestTrack = useMemo(() => [...trackSummary].filter(t => t.first_week).sort((a, b) => a.first_week.localeCompare(b.first_week))[0] ?? null, [trackSummary])
  const newestTrack = useMemo(() => [...trackSummary].filter(t => t.first_week).sort((a, b) => b.first_week.localeCompare(a.first_week))[0] ?? null, [trackSummary])
  const longestName = useMemo(() => [...trackSummary].sort((a, b) => b.track_name.length - a.track_name.length)[0] ?? null, [trackSummary])
  const shortestName = useMemo(() => [...trackSummary].sort((a, b) => a.track_name.length - b.track_name.length)[0] ?? null, [trackSummary])

  return (
    <div>
      <SectionHeader icon={Sparkles} title="奇趣纪录" subtitle="那些让人会心一笑的冷知识——数据里的彩蛋" />

      <RecordCard title="双空冠 · Double Debut" subtitle="同一张专辑有两首歌空降入榜">
        <MiniRankTable rows={rec.double_debut} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.debut_track_id} trackName={r.debut_track} artistName={r.debut_artist} coverUrl={covers.track.get(r.debut_track_id)} /> },
          { header: '空降日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.debut_week)}</span> },
          { header: '所属专辑', render: (r) => <Link to={`/music/albums/${encodeURIComponent(r.debut_album)}`} className="font-sans text-[12px] transition-colors hover:text-accent-foreground">{displayName(r.debut_album)}</Link> },
        ]} />
      </RecordCard>

      <RecordCard title="全榜单制霸 · Triple #1" subtitle="同一周单曲榜、专辑榜、艺人榜三榜 #1 同属一人">
        <MiniRankTable rows={rec.triple_no1} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} /> },
          { header: '日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.billboard_week)}</span> },
        ]} />
      </RecordCard>

      <RecordCard title="一曲成名 · One-Hit Wonder" subtitle="仅一首歌上榜且直接夺冠">
        {oneHitWonders.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
            {oneHitWonders.slice(0, 9).map((a) => (
              <Link key={a.artist_name} to={`/music/artists/${encodeURIComponent(a.artist_name)}`} className="flex items-center gap-3 rounded-[10px] border border-border bg-muted/20 p-3 transition-colors hover:bg-muted/40">
                <ArtistCoverImg url={covers.artist.get(a.artist_name)} />
                <div className="min-w-0">
                  <p className="truncate font-sans text-[13px] font-semibold">{displayName(a.artist_name)}</p>
                  <p className="font-sans text-[11px] text-muted-foreground">{a.best_peak_track} · 冠周 {a.weeks_at_no1}</p>
                </div>
              </Link>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      <RecordCard title="劳模歌手 · Most Prolific Artists" subtitle="上榜歌曲数最多的艺人">
        <MiniRankTable rows={prolificArtists} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '上榜歌曲', width: '145px', align: 'right', render: (r) => <ValueBar value={r.total_tracks} max={prolificArtists[0]?.total_tracks ?? 1} suffix="首" /> },
          { header: '最佳Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.best_peak as number} /> },
          { header: '冠单数', width: '60px', align: 'center', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.top1}</span> },
          { header: '总周数', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.total_weeks} 周</span> },
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
                    <Link key={t.track_id} to={`/music/tracks/${t.track_id}`} className="inline-flex items-center gap-1.5 rounded-[6px] bg-background px-2.5 py-1 font-sans text-[12px] transition-colors hover:bg-muted">{displayName(t.artist_name)}<span className="text-[10px] text-muted-foreground">Peak #{t.peak_position}</span></Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最早上榜 · Oldest Chart Entry">
          {oldestTrack && <FeaturedRecord label="最早入榜" value={fmtDate(oldestTrack.first_week)} caption={`${oldestTrack.track_name} — ${oldestTrack.artist_name}`} linkTo={`/music/tracks/${oldestTrack.track_id}`} />}
        </RecordCard>
        <RecordCard title="最新上榜 · Newest Chart Entry">
          {newestTrack && <FeaturedRecord label="最新入榜" value={fmtDate(newestTrack.first_week)} caption={`${newestTrack.track_name} — ${newestTrack.artist_name}`} linkTo={`/music/tracks/${newestTrack.track_id}`} />}
        </RecordCard>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最长歌名 · Longest Track Name">
          {longestName && <FeaturedRecord label="最长歌名" value={longestName.track_name.length} unit="字" caption={`${longestName.track_name} — ${longestName.artist_name}`} linkTo={`/music/tracks/${longestName.track_id}`} />}
        </RecordCard>
        <RecordCard title="最短歌名 · Shortest Track Name">
          {shortestName && <FeaturedRecord label="最短歌名" value={shortestName.track_name.length} unit="字" caption={`${shortestName.track_name} — ${shortestName.artist_name}`} linkTo={`/music/tracks/${shortestName.track_id}`} />}
        </RecordCard>
      </div>
    </div>
  )
}
