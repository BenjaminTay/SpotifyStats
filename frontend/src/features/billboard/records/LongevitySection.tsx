import { useState } from 'react'

import { Clock } from 'lucide-react'

import type {
  BillboardRecords,
  LongestChartingAlbumRecord,
  LongestChartingArtistRecord,
  LongestChartingRecord,
  LongestNoTop5AlbumRecord,
  LongestNoTop5ArtistRecord,
  LongestNoTop5Record,
  LongestSameRankAlbumRecord,
  LongestSameRankArtistRecord,
  LongestSameRankRecord,
  LongestStreakAlbumRecord,
  LongestStreakArtistRecord,
  LongestStreakRecord,
  MostReentriesAlbumRecord,
  MostReentriesArtistRecord,
  MostReentriesRecord,
  MostWeeksNo2AlbumRecord,
  MostWeeksNo2ArtistRecord,
  MostWeeksNo2Record,
} from '@/types/billboard'
import type { CoverMaps } from './recordsData'
import {
  AlbumCell,
  ArtistCell,
  ChartWeeksValue,
  MiniRankTable,
  PeakNum,
  RankNum,
  RecordCard,
  SectionHeader,
  TrackAlbumToggle,
  TrackCell,
  ValueBar,
  WeekLink,
  type EntityType,
} from './RecordsPrimitives'

export function LongevitySection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  const [chartingType, setChartingType] = useState<EntityType>('track')
  const [streakType, setStreakType] = useState<EntityType>('track')
  const [noTop5Type, setNoTop5Type] = useState<EntityType>('track')
  const [no2Type, setNo2Type] = useState<EntityType>('track')
  const [reentryType, setReentryType] = useState<EntityType>('track')
  const [sameRankType, setSameRankType] = useState<EntityType>('track')

  return (
    <div>
      <SectionHeader icon={Clock} title="持久传奇" subtitle="时间是最严苛的裁判——那些经得起岁月考验的纪录" />

      <RecordCard title="最长在榜 · Longest Charting" subtitle="在榜周数最多" toggle={<TrackAlbumToggle value={chartingType} onChange={setChartingType} showArtist />}>
        {chartingType === 'track' ? (
          <MiniRankTable rows={rec.longest_charting as LongestChartingRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_charting as LongestChartingRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
            { header: '冠周', width: '110px', align: 'right', render: (r) => r.weeks_at_no1 > 0 ? <ChartWeeksValue value={r.weeks_at_no1} /> : <span className="text-muted-foreground">—</span> },
          ]} />
        ) : chartingType === 'album' ? (
          <MiniRankTable rows={rec.longest_charting_album as LongestChartingAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_charting_album as LongestChartingAlbumRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
            { header: '冠周', width: '110px', align: 'right', render: (r) => r.weeks_at_no1 > 0 ? <ChartWeeksValue value={r.weeks_at_no1} /> : <span className="text-muted-foreground">—</span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_charting_artist as LongestChartingArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_charting_artist as LongestChartingArtistRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
            { header: '冠周', width: '110px', align: 'right', render: (r) => r.weeks_at_no1 > 0 ? <ChartWeeksValue value={r.weeks_at_no1} /> : <span className="text-muted-foreground">—</span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="最长连续在榜 · Longest Consecutive Streak" subtitle="无断档连续在榜纪录" toggle={<TrackAlbumToggle value={streakType} onChange={setStreakType} showArtist />}>
        {streakType === 'track' ? (
          <MiniRankTable rows={rec.longest_streak as LongestStreakRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_streak as LongestStreakRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['起始周']} /><span className="text-muted-foreground">—</span><WeekLink date={r['结束周']} /></span> },
          ]} />
        ) : streakType === 'album' ? (
          <MiniRankTable rows={rec.longest_streak_album as LongestStreakAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_streak_album as LongestStreakAlbumRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['起始周']} /><span className="text-muted-foreground">—</span><WeekLink date={r['结束周']} /></span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_streak_artist as LongestStreakArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_streak_artist as LongestStreakArtistRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['起始周']} /><span className="text-muted-foreground">—</span><WeekLink date={r['结束周']} /></span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="隐形冠军 · Longest Without Top 5" subtitle="在榜最久但从未来到 Top 5" mobileSubtitle="在榜最久但从未进入 Top 5" toggle={<TrackAlbumToggle value={noTop5Type} onChange={setNoTop5Type} showArtist />}>
        {noTop5Type === 'track' ? (
          <MiniRankTable rows={rec.longest_no_top5 as LongestNoTop5Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_no_top5 as LongestNoTop5Record[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          ]} />
        ) : noTop5Type === 'album' ? (
          <MiniRankTable rows={rec.longest_no_top5_album as LongestNoTop5AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_no_top5_album as LongestNoTop5AlbumRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_no_top5_artist as LongestNoTop5ArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_no_top5_artist as LongestNoTop5ArtistRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="万年老二 · Most Weeks at #2 Without #1" subtitle="在 #2 停留最久但从未夺冠" mobileSubtitle="在第 2 名停留最久但从未夺冠" toggle={<TrackAlbumToggle value={no2Type} onChange={setNo2Type} showArtist />}>
        {no2Type === 'track' ? (
          <MiniRankTable rows={rec.most_weeks_no2_no_no1 as MostWeeksNo2Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '#2 周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_at_no2} max={(rec.most_weeks_no2_no_no1 as MostWeeksNo2Record[])[0]?.weeks_at_no2 ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: () => <PeakNum rank={2} /> },
          ]} />
        ) : no2Type === 'album' ? (
          <MiniRankTable rows={rec.most_weeks_no2_no_no1_album as MostWeeksNo2AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '#2 周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_at_no2} max={(rec.most_weeks_no2_no_no1_album as MostWeeksNo2AlbumRecord[])[0]?.weeks_at_no2 ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: () => <PeakNum rank={2} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.most_weeks_no2_no_no1_artist as MostWeeksNo2ArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '#2 周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_at_no2} max={(rec.most_weeks_no2_no_no1_artist as MostWeeksNo2ArtistRecord[])[0]?.weeks_at_no2 ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: () => <PeakNum rank={2} /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="回榜王 · Most Re-entries" subtitle="出榜后重新入榜次数最多" toggle={<TrackAlbumToggle value={reentryType} onChange={setReentryType} showArtist />}>
        {reentryType === 'track' ? (
          <MiniRankTable rows={rec.most_reentries as MostReentriesRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '回榜次数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['回榜次数']} max={(rec.most_reentries as MostReentriesRecord[])[0]?.['回榜次数'] ?? 1} suffix="次" /> },
            { header: '在榜周数', width: '110px', align: 'right', render: (r) => <ChartWeeksValue value={r['在榜周数']} /> },
          ]} />
        ) : reentryType === 'album' ? (
          <MiniRankTable rows={rec.most_reentries_album as MostReentriesAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '回榜次数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['回榜次数']} max={(rec.most_reentries_album as MostReentriesAlbumRecord[])[0]?.['回榜次数'] ?? 1} suffix="次" /> },
            { header: '在榜周数', width: '110px', align: 'right', render: (r) => <ChartWeeksValue value={r['在榜周数']} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.most_reentries_artist as MostReentriesArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '回榜次数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['回榜次数']} max={(rec.most_reentries_artist as MostReentriesArtistRecord[])[0]?.['回榜次数'] ?? 1} suffix="次" /> },
            { header: '在榜周数', width: '110px', align: 'right', render: (r) => <ChartWeeksValue value={r['在榜周数']} /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="稳如磐石 · Longest Consecutive Same Rank" subtitle="在同一排名连续停留最久" toggle={<TrackAlbumToggle value={sameRankType} onChange={setSameRankType} showArtist />}>
        {sameRankType === 'track' ? (
          <MiniRankTable rows={rec.longest_consecutive_same_rank as LongestSameRankRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '排名', width: '55px', align: 'center', render: (r) => <PeakNum rank={r['停留排名']} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_consecutive_same_rank as LongestSameRankRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['起始周']} /><span className="text-muted-foreground">—</span><WeekLink date={r['结束周']} /></span> },
          ]} />
        ) : sameRankType === 'album' ? (
          <MiniRankTable rows={rec.longest_consecutive_same_rank_album as LongestSameRankAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '排名', width: '55px', align: 'center', render: (r) => <PeakNum rank={r['停留排名']} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_consecutive_same_rank_album as LongestSameRankAlbumRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['起始周']} /><span className="text-muted-foreground">—</span><WeekLink date={r['结束周']} /></span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_consecutive_same_rank_artist as LongestSameRankArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '排名', width: '55px', align: 'center', render: (r) => <PeakNum rank={r['停留排名']} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_consecutive_same_rank_artist as LongestSameRankArtistRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['起始周']} /><span className="text-muted-foreground">—</span><WeekLink date={r['结束周']} /></span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="最长艺人生涯 · Longest Artist Chart Span" subtitle="首次上榜到最近上榜跨度最大">
        <MiniRankTable rows={rec.longest_artist_span} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '生涯跨度', width: '145px', align: 'right', render: (r) => <ValueBar value={r['跨度天数']} max={rec.longest_artist_span[0]?.['跨度天数'] ?? 1} suffix="天" /> },
          { header: '时间区间', width: '190px', render: (r) => <span className="inline-flex items-center gap-1"><WeekLink date={r['首次上榜']} /><span className="text-muted-foreground">—</span><WeekLink date={r['最近上榜']} /></span> },
          { header: '歌曲数', width: '60px', align: 'center', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r['上榜歌曲数']}</span> },
        ]} />
      </RecordCard>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// Sections 3-6 (no toggle needed, keep as-is but with new structure)
// ══════════════════════════════════════════════════════════════
