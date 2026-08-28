/** 高光时刻 */

import { useMemo, useState } from 'react'
import { Clock3, Flame, Hash } from 'lucide-react'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { EntityRecordType, PlaybackBehaviorRecords, PlaybackObsessionRecords, PlaybackRecordRow, PlaybackReignRecords } from '@/types/analysis'
import {
  EntityRecordCard,
  EntityRecordToggle,
  RecordCard,
  RankNum,
  TrackCell,
  ArtistCell,
  AlbumCell,
  ValueBar,
  SectionHeader,
  MiniRankTable,
  RecordDateValue,
} from './PlaybackRecordsPrimitives'
import {
  DailyTotalLeaderboard,
  type DailyTotalSortMode,
} from './DailyTotalLeaderboard'
import { PlaybackMilestonesCard } from './BehaviorSection'
import { FastestMilestoneCard } from './ReignsSection'

interface Props {
  data: PlaybackObsessionRecords
  reigns: PlaybackReignRecords
  behavior: PlaybackBehaviorRecords
}

type DailyPeakMode = 'plays' | 'hours'

const DAILY_TOTAL_RECORD_LIMIT = 50

const dailyTotalSortOptions: { value: DailyTotalSortMode; label: string }[] = [
  { value: 'plays', label: '按次数' },
  { value: 'hours', label: '按时长' },
]

function DailyTotalSortToggle({
  value,
  onChange,
}: {
  value: DailyTotalSortMode
  onChange: (value: DailyTotalSortMode) => void
}) {
  return (
    <div className="mobile-record-segmented-toggle mobile-record-compact-segmented-toggle flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
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
          {option.value === 'plays' ? (
            <Hash className="mr-1 inline-block h-3 w-3" aria-hidden="true" />
          ) : (
            <Clock3 className="mr-1 inline-block h-3 w-3" aria-hidden="true" />
          )}
          {option.label}
        </button>
      ))}
    </div>
  )
}

const metricMax = (
  rows: PlaybackRecordRow[],
  getValue: (row: PlaybackRecordRow) => number = (row) => row.value,
) => Math.max(0, ...rows.map(getValue))

function entityCell(entity: EntityRecordType, row: PlaybackRecordRow) {
  if (entity === 'track') {
    return (
      <TrackCell
        trackId={row.entity_id}
        name={row.name}
        artistName={row.artist_name}
        coverUrl={row.cover_url}
      />
    )
  }
  if (entity === 'album') {
    return (
      <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} />
    )
  }
  return <ArtistCell name={row.name} coverUrl={row.cover_url} />
}

function DailyPeakRecordCard({ data }: Pick<Props, 'data'>) {
  const [mode, setMode] = useState<DailyPeakMode>('plays')
  const [entity, setEntity] = useState<EntityRecordType>('track')
  const family = mode === 'plays' ? data.daily_binge : data.daily_duration
  const rows = family?.[entity] ?? []
  const maxValue = metricMax(rows)
  const isPlays = mode === 'plays'
  const nextModeLabel = isPlays ? '听歌时长' : '播放次数'

  return (
    <RecordCard
      title="单日巅峰 · Daily Peak"
      subtitle="单个自然日内播放次数或累计听歌时长最高的歌曲、专辑与艺人"
      toggle={
        <div className="mobile-record-combined-controls flex items-center gap-1">
          <button
            type="button"
            aria-pressed={!isPlays}
            aria-label={`排名口径：${isPlays ? '播放次数' : '听歌时长'}。点击切换为${nextModeLabel}`}
            onClick={() => setMode(isPlays ? 'hours' : 'plays')}
            className="mobile-record-metric-toggle inline-flex items-center gap-1.5 rounded-[6px] border border-border bg-muted/30 px-2.5 py-1 font-sans text-[11px] font-semibold text-foreground transition-colors hover:border-accent-foreground/40 hover:bg-muted/60"
          >
            {isPlays ? (
              <Hash className="h-3 w-3 text-accent-foreground" aria-hidden="true" />
            ) : (
              <Clock3 className="h-3 w-3 text-accent-foreground" aria-hidden="true" />
            )}
            <span className="mobile-record-metric-toggle-label">
              {isPlays ? '次数' : '时长'}
            </span>
          </button>
          <EntityRecordToggle
            value={entity}
            available={['track', 'album', 'artist']}
            onChange={setEntity}
          />
        </div>
      }
    >
      <MiniRankTable
        rows={rows}
        columns={[
          {
            header: '#',
            width: '48px',
            align: 'center',
            render: (_, index) => <RankNum rank={index + 1} />,
          },
          {
            header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人',
            mobileRole: 'entity',
            render: (row) => entityCell(entity, row),
          },
          {
            header: isPlays ? '播放次数' : '听歌时长',
            width: '160px',
            align: 'right',
            mobileRole: 'primary',
            render: (row) => (
              <ValueBar
                value={row.value}
                max={maxValue}
                suffix={displayName(row.unit)}
                label={`${isPlays ? '播放次数' : '听歌时长'}：${displayName(row.name)}`}
              />
            ),
          },
          {
            header: '日期',
            width: '120px',
            align: 'right',
            mobileRole: 'fact',
            render: (row) => <RecordDateValue value={row.date} className="text-[12px]" />,
          },
        ]}
      />
    </RecordCard>
  )
}

function marathonCols(entity: EntityRecordType, rows: PlaybackRecordRow[]) {
  const maxRuns = metricMax(rows)
  const maxHours = metricMax(rows, (row) => row.secondary_value ?? 0)
  const nameCol = {
    header: entity === 'track' ? '歌曲' : entity === 'album' ? '专辑' : '艺人',
    mobileRole: 'entity' as const,
    render: (row: PlaybackRecordRow) => entityCell(entity, row),
  }
  return [
    { header: '#', width: '48px', align: 'center' as const, render: (_: PlaybackRecordRow, i: number) => <RankNum rank={i + 1} /> },
    nameCol,
    { header: '连续次数', mobileHeader: null, width: '180px', align: 'right' as const, mobileRole: 'primary' as const, render: (row: PlaybackRecordRow) => <ValueBar value={row.value} max={maxRuns} suffix={displayName(row.unit)} label={`连续次数：${displayName(row.name)}`} /> },
    { header: '总时长', width: '160px', align: 'right' as const, mobileRole: 'secondary' as const, render: (row: PlaybackRecordRow) => row.secondary_value != null ? <ValueBar value={row.secondary_value} max={maxHours} suffix={displayName(row.secondary_unit ?? '')} label={`马拉松时长：${displayName(row.name)}`} /> : <span className="font-sans text-[12px] text-muted-foreground">—</span> },
  ]
}

export function ObsessionSection({ data, reigns, behavior }: Props) {
  useChineseTextVersion()
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
      <SectionHeader icon={Flame} title="高光时刻" subtitle="把最强烈的一天、关键里程碑与最快达成纪录放在同一条个人音乐时间线上。" />
      <DailyPeakRecordCard data={data} />
      <RecordCard
        title="单日总量记录 · Daily Total"
        subtitle="把一天的播放强度、曲目广度与最高歌曲、专辑、艺人放在同一张日历切片中"
        toggle={<DailyTotalSortToggle value={dailyTotalSort} onChange={setDailyTotalSort} />}
      >
        {dailyTotalRows.length > 0 ? (
          <DailyTotalLeaderboard
            key={dailyTotalSort}
            rows={dailyTotalRows}
            sortMode={dailyTotalSort}
          />
        ) : <p className="py-6 text-center font-sans text-[12px] text-muted-foreground">暂无单日总量记录</p>}
      </RecordCard>
      <PlaybackMilestonesCard data={behavior} />
      <FastestMilestoneCard data={reigns} />
      <EntityRecordCard title="连续播放马拉松 · Consecutive Marathon" subtitle="播放序列中连续出现同一实体的最长 run"
        recordsByEntity={{ track: data.consecutive_marathon?.track ?? [], album: data.consecutive_marathon?.album ?? [], artist: data.consecutive_marathon?.artist ?? [] }}
        columns={(entity) => marathonCols(entity, data.consecutive_marathon?.[entity] ?? [])} />
    </div>
  )
}
