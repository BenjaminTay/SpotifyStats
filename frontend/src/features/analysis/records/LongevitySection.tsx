/** 长线陪伴 */

import { Heart } from 'lucide-react'
import { displayName } from '@/lib/chinese'
import type { PlaybackLongevityRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RankNum, TrackCell, ArtistCell, AlbumCell, ValueBar, SectionHeader } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackLongevityRecords }

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

export function LongevitySection({ data }: Props) {
  return (
    <div>
      <SectionHeader icon={Heart} title="长线陪伴" subtitle="关于长期关系——哪首歌陪你最久、谁在离开后再次回来。" />
      <EntityRecordCard title="最长连续播放天数 · Longest Streak" subtitle="连续多少个自然日每天至少播放一次的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.longest_streak_days?.track ?? [], album: data.longest_streak_days?.album ?? [], artist: data.longest_streak_days?.artist ?? [] }}
        columns={(entity) => {
          const maxStreak = Math.max(
            0,
            ...(data.longest_streak_days?.[entity] ?? []).map((item) => item.value),
          )
          return [
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            entityNameCol(entity),
            { header: '连续天数', width: '170px', align: 'right', mobileRole: 'primary', render: (row) => <ValueBar value={row.value} max={maxStreak} suffix={displayName(row.unit)} label={`连续天数：${displayName(row.name)}`} /> },
            { header: '总时长', width: '100px', align: 'right', mobileRole: 'fact', render: (row) => <span className="mobile-playback-record-secondary-fact font-sans text-[14px] tabular-nums text-muted-foreground">{row.secondary_value != null ? `${row.secondary_value} ${displayName(row.secondary_unit ?? '')}` : '—'}</span> },
          ]
        }} />
      <EntityRecordCard title="最长陪伴跨度 · Longest Span" subtitle="首次播放到最近一次播放日期跨度最长的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.longest_span?.track ?? [], album: data.longest_span?.album ?? [], artist: data.longest_span?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '跨度', width: '140px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          { header: '起止', width: '200px', align: 'right', mobileRole: 'fact', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.start_date ?? '?'} → {row.end_date ?? '?'}</span> },
        ]} />
      <EntityRecordCard title="沉睡后回归 · Comeback After Sleep" subtitle="同一实体两次出现之间间隔最长，并在后一次重新出现"
        recordsByEntity={{ track: data.comeback_after_sleep?.track ?? [], album: data.comeback_after_sleep?.album ?? [], artist: data.comeback_after_sleep?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '间隔', width: '140px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          { header: '沉睡→唤醒', width: '200px', align: 'right', mobileRole: 'fact', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.start_date ?? '?'} → {row.end_date ?? '?'}</span> },
        ]} />
      <EntityRecordCard title="最活跃月份 · Most Active Months" subtitle="活跃月份（有播放的月数）最多的歌曲/专辑/艺人"
        recordsByEntity={{ track: data.most_active_months?.track ?? [], album: data.most_active_months?.album ?? [], artist: data.most_active_months?.artist ?? [] }}
        columns={(entity) => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          entityNameCol(entity),
          { header: '活跃月数', width: '120px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
        ]} />
    </div>
  )
}
