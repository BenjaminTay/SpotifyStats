/** 狂热时刻 */

import { useMemo, useState } from 'react'
import { Flame } from 'lucide-react'
import { displayName } from '@/lib/chinese'
import type { EntityRecordType, PlaybackObsessionRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RecordCard, MiniRankTable, RankNum, TrackCell, ArtistCell, AlbumCell, ValueBar, SectionHeader } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackObsessionRecords }

type DailyTotalSortMode = 'plays' | 'hours'

const DAILY_TOTAL_RECORD_LIMIT = 50

const dailyTotalSortOptions: { value: DailyTotalSortMode; label: string }[] = [
  { value: 'plays', label: '播放次数纪录' },
  { value: 'hours', label: '总时长纪录' },
]

function DailyTotalSortToggle({
  value,
  onChange,
}: {
  value: DailyTotalSortMode
  onChange: (value: DailyTotalSortMode) => void
}) {
  return (
    <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
      {dailyTotalSortOptions.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors ${
            value === option.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

const fmtMetric = (value?: number | null, unit = '') =>
  value == null ? '—' : `${new Intl.NumberFormat('zh-CN').format(value)}${unit}`

function DailyTopEntityCell({
  type,
  name,
  artistName,
  plays,
  coverUrl,
}: {
  type: 'track' | 'album' | 'artist'
  name?: string | null
  artistName?: string | null
  plays?: number | null
  coverUrl?: string | null
}) {
  if (!name) {
    return <span className="font-sans text-[12px] text-muted-foreground">—</span>
  }

  const metric = typeof plays === 'number' ? `${fmtMetric(plays, '次')}居首` : '当日最高'

  return (
    <div className="min-w-[160px] space-y-1">
      {type === 'track' && (
        <TrackCell name={name} artistName={artistName} coverUrl={coverUrl} />
      )}
      {type === 'album' && (
        <AlbumCell name={name} artistName={artistName} coverUrl={coverUrl} />
      )}
      {type === 'artist' && <ArtistCell name={name} coverUrl={coverUrl} />}
      <p className="pl-[50px] font-sans text-[11px] text-muted-foreground">{metric}</p>
    </div>
  )
}

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
  const [dailyTotalSort, setDailyTotalSort] = useState<DailyTotalSortMode>('plays')
  const dailyTotalRows = useMemo(() => {
    const rows = [...(data.daily_total_record ?? [])]
    const valueFor = (row: PlaybackRecordRow) =>
      dailyTotalSort === 'plays' ? row.total_plays ?? row.value : row.total_hours ?? 0
    return rows
      .sort((a, b) => {
        const diff = valueFor(b) - valueFor(a)
        if (diff !== 0) return diff
        return String(b.date ?? '').localeCompare(String(a.date ?? ''))
      })
      .slice(0, DAILY_TOTAL_RECORD_LIMIT)
  }, [data.daily_total_record, dailyTotalSort])

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
      {dailyTotalRows.length > 0 && (
        <RecordCard
          title="单日总量纪录 · Daily Total Record"
          subtitle="按单日播放次数或总时长排序，并列出当天播放最高歌曲/专辑/艺人"
          toggle={<DailyTotalSortToggle value={dailyTotalSort} onChange={setDailyTotalSort} />}
        >
          <MiniRankTable rows={dailyTotalRows} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            { header: '日期', width: '110px', render: (row) => <span className="font-sans text-[14px] font-medium">{row.date ?? '—'}</span> },
            { header: '当日播放次数', width: '110px', align: 'right', render: (row) => <span className="whitespace-nowrap font-serif text-[20px] font-semibold tabular-nums">{fmtMetric(row.total_plays, '次')}</span> },
            { header: '当日播放时长', width: '110px', align: 'right', render: (row) => <span className="whitespace-nowrap font-serif text-[20px] font-semibold tabular-nums">{fmtMetric(row.total_hours, '小时')}</span> },
            { header: '当日播放歌曲', width: '110px', align: 'right', render: (row) => <span className="whitespace-nowrap font-serif text-[20px] font-semibold tabular-nums">{fmtMetric(row.unique_tracks, '首')}</span> },
            { header: '最高歌曲', width: '190px', render: (row) => <DailyTopEntityCell type="track" name={row.top_track_name} artistName={row.top_track_artist_name} plays={row.top_track_plays} coverUrl={row.top_track_cover_url} /> },
            { header: '最高专辑', width: '190px', render: (row) => <DailyTopEntityCell type="album" name={row.top_album_name} artistName={row.top_album_artist_name} plays={row.top_album_plays} coverUrl={row.top_album_cover_url} /> },
            { header: '最高艺人', width: '170px', render: (row) => <DailyTopEntityCell type="artist" name={row.top_artist_name} plays={row.top_artist_plays} coverUrl={row.top_artist_cover_url} /> },
          ]} />
        </RecordCard>
      )}
    </div>
  )
}
