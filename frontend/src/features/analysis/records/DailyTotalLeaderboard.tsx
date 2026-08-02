import { useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Clock3, ListMusic } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PlaybackRecordRow } from '@/types/analysis'
import { AlbumCell, ArtistCell, TrackCell } from './PlaybackRecordsPrimitives'

export type DailyTotalSortMode = 'plays' | 'hours'

const PAGE_SIZE = 10

const fmtMetric = (value?: number | null, unit = '') =>
  value == null ? '—' : `${new Intl.NumberFormat('zh-CN').format(value)}${unit}`

function DailyEntitySnapshot({
  label,
  type,
  name,
  entityId,
  artistName,
  plays,
  coverUrl,
}: {
  label: string
  type: 'track' | 'album' | 'artist'
  name?: string | null
  entityId?: string | null
  artistName?: string | null
  plays?: number | null
  coverUrl?: string | null
}) {
  return (
    <div className="min-w-0 bg-background/55 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-sans text-[10px] font-bold uppercase tracking-[1.1px] text-muted-foreground">
          {label}
        </span>
        <span className="whitespace-nowrap font-sans text-[11px] font-semibold tabular-nums text-accent-foreground">
          {plays == null ? '—' : `${fmtMetric(plays, '次')}居首`}
        </span>
      </div>
      {!name ? (
        <p className="py-2 font-sans text-[12px] text-muted-foreground">暂无记录</p>
      ) : type === 'track' ? (
        <TrackCell trackId={entityId} name={name} artistName={artistName} coverUrl={coverUrl} />
      ) : type === 'album' ? (
        <AlbumCell name={name} artistName={artistName} coverUrl={coverUrl} />
      ) : (
        <ArtistCell name={name} coverUrl={coverUrl} />
      )}
    </div>
  )
}

function DailyTotalRow({
  row,
  rank,
  sortMode,
  maxValue,
}: {
  row: PlaybackRecordRow
  rank: number
  sortMode: DailyTotalSortMode
  maxValue: number
}) {
  const primaryValue =
    sortMode === 'plays' ? (row.total_plays ?? row.value) : (row.total_hours ?? 0)
  const primaryUnit = sortMode === 'plays' ? '次' : '小时'
  const progress = maxValue > 0 ? Math.min((primaryValue / maxValue) * 100, 100) : 0

  return (
    <li
      aria-label={`第 ${rank} 名，${row.date ?? '未知日期'}`}
      className="group relative overflow-hidden rounded-[14px] border border-border/80 bg-gradient-to-br from-background/80 via-background/55 to-muted/25 p-4 transition-[border-color,transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:border-accent-foreground/35 hover:shadow-md"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-foreground/55 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="mb-3 grid items-center gap-3 sm:grid-cols-[56px_minmax(0,1fr)_auto]">
        <span
          className={cn(
            'font-serif text-[34px] font-bold leading-none tracking-[-1px] tabular-nums',
            rank <= 3 ? 'text-accent-foreground' : 'text-muted-foreground/65',
          )}
        >
          {String(rank).padStart(2, '0')}
        </span>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            <time className="font-serif text-[20px] font-semibold tracking-[-0.25px]">
              {row.date ?? '未知日期'}
            </time>
          </div>
          <div
            role="meter"
            aria-label={`${row.date ?? '该日'}${sortMode === 'plays' ? '播放次数' : '听歌时长'}相对值`}
            aria-valuemin={0}
            aria-valuemax={Math.max(maxValue, 1)}
            aria-valuenow={primaryValue}
            className="mt-2 h-1.5 w-full max-w-[420px] overflow-hidden rounded-full bg-muted"
          >
            <span
              className="block h-full rounded-full bg-accent-foreground transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="text-left sm:text-right">
          <p className="font-sans text-[10px] font-bold uppercase tracking-[1.1px] text-muted-foreground">
            {sortMode === 'plays' ? '当日播放' : '当日时长'}
          </p>
          <p className="font-serif text-[30px] font-bold leading-none tracking-[-0.8px] tabular-nums">
            {fmtMetric(primaryValue)}
            <span className="ml-1 font-sans text-[12px] font-medium text-muted-foreground">
              {primaryUnit}
            </span>
          </p>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-muted/35 px-2.5 py-1 font-sans text-[11px] tabular-nums text-muted-foreground">
          <ListMusic className="h-3 w-3" aria-hidden="true" />
          {fmtMetric(row.total_plays, ' 次播放')}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-muted/35 px-2.5 py-1 font-sans text-[11px] tabular-nums text-muted-foreground">
          <Clock3 className="h-3 w-3" aria-hidden="true" />
          {fmtMetric(row.total_hours, ' 小时')}
        </span>
        <span className="rounded-full border border-border/70 bg-muted/35 px-2.5 py-1 font-sans text-[11px] tabular-nums text-muted-foreground">
          {fmtMetric(row.unique_tracks, ' 首歌曲')}
        </span>
      </div>

      <div className="grid gap-px overflow-hidden rounded-[10px] border border-border/70 bg-border/70 md:grid-cols-3">
        <DailyEntitySnapshot
          label="最高歌曲"
          type="track"
          name={row.top_track_name}
          entityId={row.top_track_entity_id}
          artistName={row.top_track_artist_name}
          plays={row.top_track_plays}
          coverUrl={row.top_track_cover_url}
        />
        <DailyEntitySnapshot
          label="最高专辑"
          type="album"
          name={row.top_album_name}
          artistName={row.top_album_artist_name}
          plays={row.top_album_plays}
          coverUrl={row.top_album_cover_url}
        />
        <DailyEntitySnapshot
          label="最高艺人"
          type="artist"
          name={row.top_artist_name}
          plays={row.top_artist_plays}
          coverUrl={row.top_artist_cover_url}
        />
      </div>
    </li>
  )
}

export function DailyTotalLeaderboard({
  rows,
  sortMode,
}: {
  rows: PlaybackRecordRow[]
  sortMode: DailyTotalSortMode
}) {
  const [page, setPage] = useState(0)
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const start = safePage * PAGE_SIZE
  const pageRows = rows.slice(start, start + PAGE_SIZE)
  const metricValue = (row: PlaybackRecordRow) =>
    sortMode === 'plays' ? (row.total_plays ?? row.value) : (row.total_hours ?? 0)
  const maxValue = Math.max(0, ...rows.map(metricValue))

  return (
    <section aria-label="单日总量记录排行榜">
      <ol className="space-y-3">
        {pageRows.map((row, index) => (
          <DailyTotalRow
            key={`${row.date ?? row.name}-${start + index}`}
            row={row}
            rank={start + index + 1}
            sortMode={sortMode}
            maxValue={maxValue}
          />
        ))}
      </ol>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2 font-sans text-[12px] tabular-nums text-muted-foreground">
          <span>
            {start + 1}—{Math.min(start + PAGE_SIZE, rows.length)} / {rows.length}
          </span>
          <button
            type="button"
            aria-label="上一页"
            disabled={safePage === 0}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
            className="rounded-full border border-border p-1.5 transition-colors hover:bg-muted disabled:opacity-30"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            aria-label="下一页"
            disabled={safePage >= totalPages - 1}
            onClick={() => setPage((current) => Math.min(totalPages - 1, current + 1))}
            className="rounded-full border border-border p-1.5 transition-colors hover:bg-muted disabled:opacity-30"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </section>
  )
}
