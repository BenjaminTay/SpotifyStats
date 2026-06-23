/** 行为奇观 */

import { Zap } from 'lucide-react'
import { displayName } from '@/lib/chinese'
import type { PlaybackBehaviorRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RecordCard, MiniRankTable, RankNum, TrackCell, ArtistCell, AlbumCell, SectionHeader } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackBehaviorRecords }

function entityNameCol(entity: string) {
  return {
    header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人',
    render: (row: PlaybackRecordRow) => {
      if (entity === 'track') return <TrackCell trackId={row.entity_id} name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
      if (entity === 'album') return <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
      return <ArtistCell name={row.name} coverUrl={row.cover_url} />
    },
  }
}

export function BehaviorSection({ data }: Props) {
  return (
    <div>
      <SectionHeader icon={Zap} title="行为奇观" subtitle="关于播放行为的有趣发现——快进率、Shuffle 习惯、平台偏好和里程碑。" />
      <EntityRecordCard title="快进风暴 · Forward Storm" subtitle="快进率（reason_end=fwdbtn）最高的歌曲/专辑/艺人（至少播放10次）"
        recordsByEntity={{ track: data.skip_storm?.track ?? [], album: data.skip_storm?.album ?? [], artist: data.skip_storm?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '快进率', width: '120px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          { header: '总播放', width: '80px', align: 'right', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.secondary_value}{displayName(row.secondary_unit ?? '')}</span> },
        ]} />
      {data.shuffle_peak && data.shuffle_peak.length > 0 && (
        <RecordCard title="Shuffle 高峰 · Shuffle Peak" subtitle="Shuffle 播放比例最高的日期">
          <MiniRankTable rows={data.shuffle_peak} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '日期', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: 'Shuffle 率', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          ]} />
        </RecordCard>
      )}
      {data.platform_switch_day && data.platform_switch_day.length > 0 && (
        <RecordCard title="平台切换日 · Platform Switch Day" subtitle="同一天内切换平台次数最多的日期">
          <MiniRankTable rows={data.platform_switch_day} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '日期', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: '切换次数', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          ]} />
        </RecordCard>
      )}
      {data.playback_milestones && data.playback_milestones.length > 0 && (
        <RecordCard title="播放里程碑 · Playback Milestones" subtitle="第 1000/5000/10000/50000 次有效播放的时刻">
          <MiniRankTable rows={data.playback_milestones} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '里程碑', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.caption ?? `${row.value} ${row.unit}`)}</span> },
            { header: '歌曲', render: (row) => <span className="font-sans text-[14px]">{displayName(row.name || '—')}</span> },
            { header: '日期', width: '120px', align: 'right', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.date ?? '—'}</span> },
          ]} />
        </RecordCard>
      )}
    </div>
  )
}
