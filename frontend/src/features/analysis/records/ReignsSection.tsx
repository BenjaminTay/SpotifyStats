/** 个人王朝 */

import { Crown } from 'lucide-react'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { PlaybackReignRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RankNum, TrackCell, ArtistCell, AlbumCell, RecordDateValue, SectionHeader } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackReignRecords }

function entityNameCol(entity: string) {
  return {
    header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人',
    mobileRole: 'entity' as const,
    render: (row: PlaybackRecordRow) => {
      if (entity === 'track') return <TrackCell trackId={row.entity_id} name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
      if (entity === 'album') return <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
      return <ArtistCell name={row.name} coverUrl={row.cover_url} />
    },
  }
}

export function ReignsSection({ data }: Props) {
  useChineseTextVersion()
  return (
    <div>
      <SectionHeader icon={Crown} title="个人王朝" />
      <EntityRecordCard title="每日冠军次数 · Daily Champion"
        recordsByEntity={{ track: data.daily_champion?.track ?? [], album: data.daily_champion?.album ?? [], artist: data.daily_champion?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '冠军天数', width: '120px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
      <EntityRecordCard title="月度统治 · Monthly Reign" subtitle="获得月冠军次数最多的歌曲、专辑与艺人"
        recordsByEntity={{ track: data.monthly_reign?.track ?? [], album: data.monthly_reign?.album ?? [], artist: data.monthly_reign?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '月冠军', width: '120px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
      <EntityRecordCard title="年度统治 · Yearly Reign" subtitle="每一年播放次数最高的歌曲、专辑与艺人"
        recordsByEntity={{ track: data.yearly_reign?.track ?? [], album: data.yearly_reign?.album ?? [], artist: data.yearly_reign?.artist ?? [] }}
        columns={(entity) => [
          { header: '年份', width: '72px', mobileRole: 'fact', render: (row) => <RecordDateValue value={row.date} /> },
          entityNameCol(entity),
          { header: '播放次数', width: '120px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">次</span></span> },
        ]} />
      <EntityRecordCard title="连续冠军天数 · Consecutive Champion Days"
        recordsByEntity={{ track: data.consecutive_champion_days?.track ?? [], album: data.consecutive_champion_days?.album ?? [], artist: data.consecutive_champion_days?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '连续天数', width: '120px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
    </div>
  )
}

export function FastestMilestoneCard({ data }: Props) {
  useChineseTextVersion()
  return (
    <EntityRecordCard title="最快里程碑 · Fastest Milestone" subtitle="从第一次听到达到播放门槛，用时最短的歌曲、专辑与艺人"
      recordsByEntity={{ track: data.fastest_milestone?.track ?? [], album: data.fastest_milestone?.album ?? [], artist: data.fastest_milestone?.artist ?? [] }}
      columns={(entity) => [
        { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
        entityNameCol(entity),
        { header: '天数', width: '120px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
      ]} />
  )
}
