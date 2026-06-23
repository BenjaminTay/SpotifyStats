/** 探索发现 */

import { Compass } from 'lucide-react'
import { displayName } from '@/lib/chinese'
import type { PlaybackDiscoveryRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RecordCard, MiniRankTable, RankNum, TrackCell, ArtistCell, AlbumCell, SectionHeader } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackDiscoveryRecords }

export function DiscoverySection({ data }: Props) {
  const featTrackRows = data.feat_lover?.track ?? []
  const featSummaryRow = featTrackRows.find(
    (row) => row.rank === 0 || row.caption?.includes('合作曲播放'),
  )
  const featTrackRankRows = featSummaryRow
    ? featTrackRows.filter((row) => row !== featSummaryRow)
    : featTrackRows
  const featArtistRows = data.feat_lover?.artist ?? []

  return (
    <div>
      <SectionHeader icon={Compass} title="探索发现" subtitle="关于新发现和多样性——你最博爱的那一天、陪你跨越最远年代的作品。" />
      <EntityRecordCard title="发现日 · Discovery Day" subtitle="单日首次播放的新歌曲/专辑/艺人数量最多的日期"
        recordsByEntity={{ track: data.discovery_day?.track ?? [], album: data.discovery_day?.album ?? [], artist: data.discovery_day?.artist ?? [] }}
        columns={() => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: '日期', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
          { header: '新发现', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
      <EntityRecordCard title="最长不重复序列 · Longest No-Repeat" subtitle="播放序列中连续不重复歌曲/专辑/艺人的最长序列"
        recordsByEntity={{ track: data.longest_no_repeat?.track ?? [], album: data.longest_no_repeat?.album ?? [], artist: data.longest_no_repeat?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
          { header: '序列长度', width: '120px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
      <EntityRecordCard title="专辑完成者 · Album Completionist" subtitle="同一专辑中播放过的不同歌曲占比最高（至少播放3首）"
        recordsByEntity={{ album: data.album_completionist?.album ?? [] }} defaultEntity="album"
        columns={() => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: '专辑', render: (row) => <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> },
          { header: '完成度', width: '120px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
      {featSummaryRow && (
        <RecordCard title="合作曲总体占比 · Collaboration Share" subtitle="所有播放中带 feat/with/& 等合作标记的比例">
          <MiniRankTable rows={[featSummaryRow]} columns={[
            { header: '范围', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: '占比', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
            { header: '播放次数', width: '140px', align: 'right', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.secondary_value}{displayName(row.secondary_unit ?? '')}</span> },
          ]} />
        </RecordCard>
      )}
      {(featTrackRankRows.length > 0 || featArtistRows.length > 0) && (
        <EntityRecordCard title="合作曲排行 · Feat Ranking" subtitle="合作歌曲播放次数与常出现的合作艺人"
          recordsByEntity={{ track: featTrackRankRows, artist: featArtistRows }} defaultEntity="track"
          columns={(entity) => [
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            entity === 'track'
              ? { header: '歌曲', render: (row: PlaybackRecordRow) => <TrackCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> }
              : { header: '艺人', render: (row: PlaybackRecordRow) => <ArtistCell name={row.name} coverUrl={row.cover_url} /> },
            { header: '播放次数', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          ]} />
      )}
      {data.same_name_diff_artist && data.same_name_diff_artist.length > 0 && (
        <RecordCard title="同名异曲 · Same Name, Different Artist" subtitle="播放过相同歌名但不同艺人的歌曲">
          <MiniRankTable rows={data.same_name_diff_artist} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '歌名', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: '不同艺人', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
            { header: '示例', render: (row) => <span className="font-sans text-[12px] text-muted-foreground truncate max-w-[200px] inline-block">{displayName(row.caption ?? '—')}</span> },
          ]} />
        </RecordCard>
      )}
    </div>
  )
}
