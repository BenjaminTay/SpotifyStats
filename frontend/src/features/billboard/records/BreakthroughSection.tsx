import { TrendingDown, TrendingUp, Zap } from 'lucide-react'

import { billboardDetailLink } from '@/lib/navigation'
import type { BillboardRecords } from '@/types/billboard'
import type { CoverMaps } from './recordsData'
import {
  AlbumCell,
  ArtistCell,
  FeaturedRecord,
  MiniRankTable,
  RankNum,
  RecordCard,
  SectionHeader,
  TrackCell,
  ValueBar,
  WeekLink,
  fmtDate,
} from './RecordsPrimitives'

export function BreakthroughSection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  return (
    <div>
      <SectionHeader icon={Zap} title="爆发时刻" subtitle="那些让人瞠目结舌的瞬间——榜单上最极致的爆发力" />

      <RecordCard title="艺人霸榜 · Most Simultaneous Chart Entries" subtitle="单周同一艺人上榜歌曲数最多">
        {rec.artist_simul && (
          <div className="mb-4">
            <FeaturedRecord label="艺人霸榜纪录" value={rec.artist_simul.count} unit="首歌曲同时在榜" caption={`${rec.artist_simul.artist} · ${fmtDate(rec.artist_simul.week)}`} coverUrl={covers.artist.get(rec.artist_simul.artist)} linkTo={billboardDetailLink(`/music/artists/${encodeURIComponent(rec.artist_simul.artist || '')}`)} />
          </div>
        )}
        {rec.artist_simul_list?.length > 0 && (
          <MiniRankTable rows={rec.artist_simul_list} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
            { header: '日期', width: '110px', render: (r) => <WeekLink date={r.billboard_week} /> },
            { header: '上榜数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.track_count} max={rec.artist_simul_list[0]?.track_count ?? 1} suffix="首" /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="专辑霸榜 · Most Simultaneous Album Entries" subtitle="单周同一专辑上榜歌曲数最多">
        {rec.album_simul && (
          <div className="mb-4">
            <FeaturedRecord label="专辑霸榜纪录" value={rec.album_simul.count} unit="首歌曲同时在榜" caption={`${rec.album_simul.album} · ${rec.album_simul.artist} · ${fmtDate(rec.album_simul.week)}`} coverUrl={covers.album.get(rec.album_simul.album)} linkTo={billboardDetailLink(`/music/albums/${encodeURIComponent(rec.album_simul.album || '')}`)} />
          </div>
        )}
        {rec.album_simul_list?.length > 0 && (
          <MiniRankTable rows={rec.album_simul_list} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '日期', width: '110px', render: (r) => <WeekLink date={r.billboard_week} /> },
            { header: '上榜数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.track_count} max={rec.album_simul_list[0]?.track_count ?? 1} suffix="首" /> },
          ]} />
        )}
      </RecordCard>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最大跃升 · Biggest Jump" subtitle="单周排名上升最多">
          <MiniRankTable rows={rec.biggest_jump} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '变化', width: '160px', align: 'right', render: (r) => <span className="inline-flex items-center gap-1 font-sans text-[14px] font-bold tabular-nums text-emerald-600 dark:text-emerald-400"><TrendingUp className="h-3.5 w-3.5" />▲{Math.abs(r['变化'])}</span> },
          ]} />
        </RecordCard>
        <RecordCard title="最大跌幅 · Biggest Drop" subtitle="单周排名下降最多">
          <MiniRankTable rows={rec.biggest_drop} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '变化', width: '160px', align: 'right', render: (r) => <span className="inline-flex items-center gap-1 font-sans text-[14px] font-bold tabular-nums text-red-600 dark:text-red-400"><TrendingDown className="h-3.5 w-3.5" />▼{Math.abs(r['变化'])}</span> },
          ]} />
        </RecordCard>
      </div>

      <RecordCard title="最快出榜 · Fastest Exit After #1" subtitle="夺冠后最快跌出榜单">
        <MiniRankTable rows={rec.fastest_exit_after_no1} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '夺冠日期', width: '110px', render: (r) => <WeekLink date={r.first_peak_week} /> },
          { header: '出榜日期', width: '110px', render: (r) => <WeekLink date={r.last_week} /> },
          { header: '巅后周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['巅峰后周数']} max={rec.fastest_exit_after_no1[0]?.['巅峰后周数'] ?? 1} suffix="周" /> },
        ]} />
      </RecordCard>

    </div>
  )
}
