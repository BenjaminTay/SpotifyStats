/** 狂热时刻 */

import { Flame } from 'lucide-react'
import { displayName } from '@/lib/chinese'
import type { EntityRecordType, PlaybackObsessionRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RecordCard, MiniRankTable, RankNum, TrackCell, ArtistCell, AlbumCell, ValueBar, SectionHeader } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackObsessionRecords }

function marathonCols(entity: EntityRecordType) {
  const nameCol = {
    header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人',
    render: (row: PlaybackRecordRow) => {
      if (entity === 'track') return <TrackCell trackId={row.entity_id} name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
      if (entity === 'album') return <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
      return <ArtistCell name={row.name} coverUrl={row.cover_url} />
    },
  }
  return [
    { header: '#', width: '48px', align: 'center' as const, render: (_: PlaybackRecordRow, i: number) => <RankNum rank={i + 1} /> },
    nameCol,
    { header: '连续次数', width: '120px', align: 'right' as const, render: (row: PlaybackRecordRow) => <ValueBar value={row.value} max={row.value} suffix={displayName(row.unit)} /> },
    { header: '总时长', width: '120px', align: 'right' as const, render: (row: PlaybackRecordRow) => <span className="font-sans text-[14px] tabular-nums text-muted-foreground">{row.secondary_value != null ? `${row.secondary_value} ${displayName(row.secondary_unit ?? '')}` : '—'}</span> },
  ]
}

export function ObsessionSection({ data }: Props) {
  return (
    <div>
      <SectionHeader icon={Flame} title="狂热时刻" subtitle="关于极端播放行为的记录——哪一天听得最疯、哪首歌循环最多。" />
      <EntityRecordCard title="单日爆听 · Daily Binge" subtitle="单个自然日内播放次数最多的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.daily_binge?.track ?? [], album: data.daily_binge?.album ?? [], artist: data.daily_binge?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人', render: (row) => entity === 'track' ? <TrackCell trackId={row.entity_id} name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> : entity === 'album' ? <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> : <ArtistCell name={row.name} coverUrl={row.cover_url} /> },
          { header: '次数', width: '80px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}</span> },
          { header: '日期', width: '120px', align: 'right', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.date ?? '—'}</span> },
        ]} />
      <EntityRecordCard title="单日听歌时长 · Daily Duration" subtitle="单个自然日内累计播放时长最高的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.daily_duration?.track ?? [], album: data.daily_duration?.album ?? [], artist: data.daily_duration?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人', render: (row) => entity === 'track' ? <TrackCell trackId={row.entity_id} name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> : entity === 'album' ? <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> : <ArtistCell name={row.name} coverUrl={row.cover_url} /> },
          { header: '时长', width: '100px', align: 'right', render: (row) => <ValueBar value={row.value} max={row.value} suffix={displayName(row.unit)} /> },
          { header: '日期', width: '120px', align: 'right', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.date ?? '—'}</span> },
        ]} />
      <EntityRecordCard title="连续播放马拉松 · Consecutive Marathon" subtitle="播放序列中连续出现同一实体的最长 run"
        recordsByEntity={{ track: data.consecutive_marathon?.track ?? [], album: data.consecutive_marathon?.album ?? [], artist: data.consecutive_marathon?.artist ?? [] }}
        columns={marathonCols} />
      {data.daily_total_record && data.daily_total_record.length > 0 && (
        <RecordCard title="单日总量纪录 · Daily Total Record" subtitle="总播放次数、总时长、独特歌曲数最高的日期">
          <MiniRankTable rows={data.daily_total_record} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '日期', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: '统计', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{displayName(row.caption ?? `${row.value} ${row.unit}`)}</span> },
          ]} />
        </RecordCard>
      )}
    </div>
  )
}
