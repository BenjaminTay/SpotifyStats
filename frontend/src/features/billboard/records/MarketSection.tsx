import { BarChart3 } from 'lucide-react'

import type { BillboardRecords } from '@/types/billboard'
import type { CoverMaps } from './recordsData'
import {
  AlbumCell,
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

export function MarketSection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  return (
    <div>
      <SectionHeader icon={BarChart3} title="每周大盘" subtitle="查看每周总播放、冠亚军差距和新歌入榜情况" />

      <RecordCard title="每周播放量排行 · Weekly Total Plays">
        <MiniRankTable rows={rec.week_total_plays} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '周次', className: 'pl-3', render: (r) => <WeekLink date={r.billboard_week} /> },
          { header: '总播放', width: '165px', align: 'right', render: (r) => <ValueBar value={r.total_plays} max={rec.week_total_plays[0]?.total_plays ?? 1} /> },
          { header: <span className="pl-6">#1 歌曲</span>, render: (r) => r.no1_track ? <div className="pl-6"><TrackCell trackId={r.no1_track_id ?? undefined} trackName={r.no1_track} artistName={r.no1_track_artist ?? undefined} coverUrl={covers.track.get(r.no1_track_id ?? -1)} /></div> : <span className="pl-6 text-muted-foreground">—</span> },
          { header: <span className="pl-6">#1 专辑</span>, render: (r) => r.no1_album ? <div className="pl-6"><AlbumCell albumName={r.no1_album} artistName={r.no1_album_artist ?? ''} coverUrl={covers.album.get(r.no1_album)} /></div> : <span className="pl-6 text-muted-foreground">—</span> },
        ]} />
      </RecordCard>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最激烈竞争 · Closest #1 vs #2" subtitle="冠亚军差距最小的周">
          {rec.closest_no1_vs_no2 && 'week' in rec.closest_no1_vs_no2 ? <FeaturedRecord label="毫厘之差" value={rec.closest_no1_vs_no2.gap_pct.toFixed(2)} unit="%" caption={`#1 ${rec.closest_no1_vs_no2.no1_track} vs #2 ${rec.closest_no1_vs_no2.no2_track} · ${fmtDate(rec.closest_no1_vs_no2.week)}`} /> : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
        </RecordCard>
        <RecordCard title="最悬殊碾压 · Largest #1 vs #2" subtitle="冠亚军差距最大的周">
          {rec.largest_no1_vs_no2 && 'week' in rec.largest_no1_vs_no2 ? <FeaturedRecord label="断层领先" value={rec.largest_no1_vs_no2.gap_pct.toFixed(2)} unit="%" caption={`#1 ${rec.largest_no1_vs_no2.no1_track} vs #2 ${rec.largest_no1_vs_no2.no2_track} · ${fmtDate(rec.largest_no1_vs_no2.week)}`} /> : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
        </RecordCard>
      </div>

      <RecordCard title="新歌活跃度 · New Entry Ratio" subtitle="每周新入榜歌曲占比的变化">
        <MiniRankTable rows={rec.new_entry_ratio} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '周次', className: 'pl-3', render: (r) => <WeekLink date={r.billboard_week} /> },
          { header: '新入榜', width: '80px', align: 'center', mobileRole: 'fact', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r['新入榜歌曲数']}</span> },
          { header: '新歌占比', width: '145px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={Math.round(r['新歌占比'])} max={100} suffix="%" /> },
        ]} />
      </RecordCard>
    </div>
  )
}
