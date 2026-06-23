/** 时间密码 */

import { Clock } from 'lucide-react'
import { displayName } from '@/lib/chinese'
import type { PlaybackTimePatternRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RecordCard, MiniRankTable, RankNum, TrackCell, ArtistCell, AlbumCell, SectionHeader } from './PlaybackRecordsPrimitives'

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
      <SectionHeader icon={Clock} title="时间密码" subtitle="关于时间维度的峰值和偏好——哪个时段、月份、年份的音乐记忆最特别。" />
      <EntityRecordCard title="时段统治 · Hourly Dominance" subtitle="每个小时段内播放次数最多的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.hourly_dominance?.track ?? [], album: data.hourly_dominance?.album ?? [], artist: data.hourly_dominance?.artist ?? [] }}
        columns={(entity) => [
          { header: '时段', width: '72px', render: (row) => <span className="font-sans text-[14px] font-medium">{row.date ?? '—'}</span> },
          entityNameCol(entity),
          { header: '次数', width: '80px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}</span> },
        ]} />
      <EntityRecordCard title="月度巅峰 · Monthly Peak" subtitle="每月播放次数最高的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.monthly_peak?.track ?? [], album: data.monthly_peak?.album ?? [], artist: data.monthly_peak?.artist ?? [] }}
        columns={(entity) => [
          { header: '月份', width: '84px', render: (row) => <span className="font-sans text-[14px] font-medium">{row.date ?? '—'}</span> },
          entityNameCol(entity),
          { header: '次数', width: '80px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}</span> },
        ]} />
      <EntityRecordCard title="年度巅峰 · Yearly Peak" subtitle="每年播放次数最高的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.yearly_peak?.track ?? [], album: data.yearly_peak?.album ?? [], artist: data.yearly_peak?.artist ?? [] }}
        columns={(entity) => [
          { header: '年份', width: '72px', render: (row) => <span className="font-sans text-[14px] font-medium">{row.date ?? '—'}</span> },
          entityNameCol(entity),
          { header: '次数', width: '80px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}</span> },
        ]} />
      {data.late_night_peak_day && data.late_night_peak_day.length > 0 && (
        <RecordCard title="深夜峰值日 · Late Night Peak Day" subtitle="深夜(0-5点)播放占比最高的日期">
          <MiniRankTable rows={data.late_night_peak_day} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '日期', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: '深夜占比', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          ]} />
        </RecordCard>
      )}
      {data.new_year_eve && data.new_year_eve.length > 0 && (
        <RecordCard title="跨年时刻 · New Year's Eve" subtitle="跨年午夜前后播放的歌曲与艺人">
          <MiniRankTable rows={data.new_year_eve} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '跨年', render: (row) => <span className="font-sans text-[14px] font-medium">{displayName(row.name)}</span> },
            { header: '播放次数', width: '100px', align: 'right', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
            { header: 'Top', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{displayName(row.caption ?? '—')}</span> },
          ]} />
        </RecordCard>
      )}
    </div>
  )
}
