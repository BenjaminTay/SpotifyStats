/** 时间习惯 */

import { Clock } from 'lucide-react'
import type { PlaybackTimePatternRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, TrackCell, ArtistCell, AlbumCell, SectionHeader } from './PlaybackRecordsPrimitives'
import { HourlySegmentsCard } from './HourlySegmentsCard'
import { LateNightTrajectoryCard } from './LateNightTrajectoryCard'

interface Props { data: PlaybackTimePatternRecords }

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

export function TimePatternsSection({ data }: Props) {
  return (
    <div>
      <SectionHeader icon={Clock} title="时间习惯" subtitle="观察一天中的听歌时段、逐月冠军，以及深夜聆听比例如何随时间变化。" />
      <HourlySegmentsCard records={{ track: data.hourly_dominance?.track ?? [], album: data.hourly_dominance?.album ?? [], artist: data.hourly_dominance?.artist ?? [] }} />
      <EntityRecordCard title="月度巅峰 · Monthly Peak" subtitle="逐个自然月列出当月播放次数最高的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.monthly_peak?.track ?? [], album: data.monthly_peak?.album ?? [], artist: data.monthly_peak?.artist ?? [] }}
        columns={(entity) => [
          { header: '月份', width: '84px', render: (row) => <span className="font-sans text-[14px] font-medium">{row.date ?? '—'}</span> },
          entityNameCol(entity),
          { header: '次数', width: '80px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}</span> },
        ]} />
      <LateNightTrajectoryCard trajectory={data.late_night_trajectory} />
    </div>
  )
}
