import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react'

import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { cn } from '@/lib/utils'
import { billboardDetailLink, primaryArtistName } from '@/lib/navigation'
import type {
  AllTimeRow,
  ColumnDef,
  EntityTab,
  MergedAlbumRow,
  MergedArtistRow,
  MergedTrackRow,
} from './allTimeData'
import { formatNumber, rankColorClass } from './allTimeData'

const COLUMN_WIDTH_DEFAULTS: Record<string, number> = {
  _name_tracks: 200,
  _name_albums: 200,
  _name_artists: 200,
  peak_position: 72,
  weeks_at_peak: 72,
  weeks_on_chart: 72,
  weeks_top5: 72,
  weeks_top10: 72,
  power_score: 80,
  power_rank: 88,
  track_power_sum: 116,
  track_power_rank: 108,
  album_power_sum: 116,
  album_power_rank: 108,
  total_chart_plays: 110,
  total_plays: 110,
  total_tracks: 72,
  top1_tracks: 80,
  top5_tracks: 72,
  top10_tracks: 72,
  num_no1_albums: 80,
  top5_albums: 80,
  top10_albums: 80,
}

const COL_WIDTHS_KEY = 'billboard-alltime-col-widths'

function loadColumnWidths(): Record<string, number> {
  try {
    const saved = localStorage.getItem(COL_WIDTHS_KEY)
    if (saved) return JSON.parse(saved)
  } catch {
    // ignore invalid persisted UI state
  }
  return {}
}

function saveColumnWidths(widths: Record<string, number>) {
  try {
    localStorage.setItem(COL_WIDTHS_KEY, JSON.stringify(widths))
  } catch {
    // ignore localStorage failures
  }
}

function CoverImg({ url }: { url?: string | null }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)

  if (url && failedUrl !== url) {
    return (
      <img
        src={url}
        alt=""
        className="h-10 w-10 shrink-0 rounded-[8px] object-cover"
        onError={() => setFailedUrl(url)}
        loading="lazy"
      />
    )
  }

  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] bg-muted text-base">
      🎵
    </div>
  )
}

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  if (!active) return <ArrowUpDown className="ml-1 inline h-3 w-3 text-muted-foreground/40" />
  return dir === 'asc'
    ? <ArrowUp className="ml-1 inline h-3 w-3 text-accent-foreground" />
    : <ArrowDown className="ml-1 inline h-3 w-3 text-accent-foreground" />
}

function renderTrackName(row: MergedTrackRow) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={row.cover_url} />
      <div className="min-w-0">
        <Link
          to={billboardDetailLink(`/music/tracks/${row.track_id}`)}
          className="block truncate font-sans text-[14px] font-semibold text-foreground transition-colors hover:text-accent-foreground"
        >
          {displayName(row.track_name)}
        </Link>
        <ArtistLinks
          artistName={row.artist_name}
          artistNames={row.artist_names}
          className="block truncate font-sans text-[12px] text-muted-foreground"
        />
      </div>
    </div>
  )
}

function renderAlbumName(row: MergedAlbumRow) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={row.cover_url} />
      <div className="min-w-0">
        <Link
          to={billboardDetailLink(`/music/albums/${encodeURIComponent(row.album_name)}?artist=${encodeURIComponent(row.artist_name)}`)}
          className="block truncate font-sans text-[14px] font-semibold text-foreground transition-colors hover:text-accent-foreground"
        >
          {displayName(row.album_name)}
        </Link>
        <Link
          to={billboardDetailLink(`/music/artists/${encodeURIComponent(primaryArtistName(row))}`)}
          className="block truncate font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
        >
          {displayName(row.artist_name)}
        </Link>
      </div>
    </div>
  )
}

function renderArtistName(row: MergedArtistRow) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={row.cover_url} />
      <Link
        to={billboardDetailLink(`/music/artists/${encodeURIComponent(row.artist_name)}`)}
        className="font-sans text-[14px] font-semibold text-foreground transition-colors hover:text-accent-foreground"
      >
        {displayName(row.artist_name)}
      </Link>
    </div>
  )
}

function isTotalPlaysCol(key: string) {
  return key === 'total_chart_plays' || key === 'total_plays'
}

function rowKey(activeTab: EntityTab, row: AllTimeRow) {
  if (activeTab === 'tracks') return (row as MergedTrackRow).track_id
  if (activeTab === 'albums') {
    const album = row as MergedAlbumRow
    return `${album.album_name}||${album.artist_name}`
  }
  return (row as MergedArtistRow).artist_name
}

function renderNameCell(activeTab: EntityTab, row: AllTimeRow) {
  if (activeTab === 'tracks') return renderTrackName(row as MergedTrackRow)
  if (activeTab === 'albums') return renderAlbumName(row as MergedAlbumRow)
  return renderArtistName(row as MergedArtistRow)
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number
  totalPages: number
  onPageChange: (page: number | ((current: number) => number)) => void
}) {
  return (
    <nav aria-label="总榜分页" className="flex items-center gap-1">
      <span className="mr-2 font-sans text-[12px] text-muted-foreground tabular-nums">
        {page} / {totalPages}
      </span>
      <button
        onClick={() => onPageChange(1)}
        disabled={page <= 1}
        aria-label="第一页"
        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
      >
        <ChevronsLeft className="h-4 w-4" />
      </button>
      <button
        onClick={() => onPageChange((current) => Math.max(1, current - 1))}
        disabled={page <= 1}
        aria-label="上一页"
        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <button
        onClick={() => onPageChange((current) => Math.min(totalPages, current + 1))}
        disabled={page >= totalPages}
        aria-label="下一页"
        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
      <button
        onClick={() => onPageChange(totalPages)}
        disabled={page >= totalPages}
        aria-label="最后一页"
        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
      >
        <ChevronsRight className="h-4 w-4" />
      </button>
    </nav>
  )
}

interface AllTimeTableProps {
  activeTab: EntityTab
  rows: AllTimeRow[]
  columns: ColumnDef<AllTimeRow>[]
  total: number
  sortKey: string
  sortDir: 'asc' | 'desc'
  page: number
  pageSize: number
  maxBarValue: number
  emptyMessage?: string
  onColumnClick: (column: ColumnDef<AllTimeRow>) => void
  onPageChange: (page: number | ((current: number) => number)) => void
}

export function AllTimeTable({
  activeTab,
  rows,
  columns,
  total,
  sortKey,
  sortDir,
  page,
  pageSize,
  maxBarValue,
  emptyMessage = '暂无数据',
  onColumnClick,
}: AllTimeTableProps) {
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(loadColumnWidths)
  const columnWidthsRef = useRef(columnWidths)
  useEffect(() => { columnWidthsRef.current = columnWidths }, [columnWidths])
  const didResizeRef = useRef(false)
  const [resizing, setResizing] = useState<{ key: string; startX: number; startWidth: number } | null>(null)

  const getColWidth = (key: string, fallback?: number) => columnWidths[key] ?? COLUMN_WIDTH_DEFAULTS[key] ?? fallback ?? 80

  useEffect(() => {
    if (!resizing) return
    const handleMouseMove = (event: MouseEvent) => {
      const diff = event.clientX - resizing.startX
      const newWidth = Math.max(48, resizing.startWidth + diff)
      setColumnWidths((prev) => ({ ...prev, [resizing.key]: newWidth }))
    }
    const handleMouseUp = () => {
      saveColumnWidths(columnWidthsRef.current)
      didResizeRef.current = true
      setResizing(null)
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [resizing])

  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const paginatedRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize)

  function handleHeaderClick(column: ColumnDef<AllTimeRow>) {
    if (didResizeRef.current) {
      didResizeRef.current = false
      return
    }
    onColumnClick(column)
  }

  function resizeColumnByKeyboard(key: string, delta: number) {
    setColumnWidths((current) => {
      const width = current[key] ?? COLUMN_WIDTH_DEFAULTS[key] ?? 80
      const next = { ...current, [key]: Math.max(48, width + delta) }
      saveColumnWidths(next)
      return next
    })
  }

  function renderTableCell(row: AllTimeRow, column: ColumnDef<AllTimeRow>) {
    const rawValue = column.getValue(row)
    const isSortCol = column.key === sortKey
    const isRankCol = column.rankStyle && typeof rawValue === 'number' && Number.isFinite(rawValue)
    const showBar = isTotalPlaysCol(column.key) && typeof rawValue === 'number'
    const pinTrackPlayValueRight = column.key === 'total_chart_plays'

    return (
      <td
        key={column.key}
        data-column-key={column.key}
        className={cn(
          'whitespace-nowrap px-3 py-2.5 tabular-nums',
          pinTrackPlayValueRight && 'relative',
          isRankCol ? 'font-serif text-[17px] font-semibold' : 'font-sans text-[13px]',
          column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left',
          isRankCol ? rankColorClass(rawValue) : isSortCol ? 'font-semibold text-accent-foreground' : 'text-foreground/80',
        )}
      >
        <span className={cn(pinTrackPlayValueRight && 'relative z-[1] inline-block text-right')}>
          {isRankCol ? String(rawValue).padStart(2, '0') : column.format(row)}
        </span>
        {showBar && (
          <span className={cn(
            'h-[3px] w-[70px] rounded-[2px] bg-muted',
            pinTrackPlayValueRight
              ? 'absolute bottom-1.5 right-3'
              : 'ml-2 inline-block align-middle',
          )}>
            <span
              className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
              style={{ width: `${Math.round((rawValue / maxBarValue) * 100)}%` }}
            />
          </span>
        )}
      </td>
    )
  }

  return (
    <>
      <GlassCard className="overflow-x-auto p-0">
        <table
          className="table-fixed border-collapse"
          style={{ width: 44 + getColWidth(`_name_${activeTab}`) + columns.reduce((sum, column) => sum + getColWidth(column.key, column.minWidth), 0) }}
        >
          <thead>
            <tr className="border-b border-border">
              <th style={{ width: 44 }} className="sticky left-0 top-0 z-30 bg-card px-2 py-3 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                #
              </th>
              <th
                style={{ width: getColWidth(`_name_${activeTab}`) }}
                className="relative sticky left-[44px] top-0 z-20 bg-card px-3 py-3 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground"
              >
                名称
                <div
                  role="separator"
                  aria-label="调整名称列宽"
                  aria-orientation="vertical"
                  tabIndex={0}
                  className="absolute bottom-0 right-0 top-0 w-[6px] cursor-col-resize transition-colors hover:bg-accent-foreground/25"
                  onMouseDown={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    const key = `_name_${activeTab}`
                    setResizing({ key, startX: event.clientX, startWidth: getColWidth(key) })
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
                    event.preventDefault()
                    resizeColumnByKeyboard(`_name_${activeTab}`, event.key === 'ArrowLeft' ? -8 : 8)
                  }}
                />
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  data-column-key={column.key}
                  onClick={() => handleHeaderClick(column)}
                  style={{ width: getColWidth(column.key, column.minWidth) }}
                  title={column.description}
                  className={cn(
                    'relative sticky top-0 z-10 cursor-pointer select-none whitespace-nowrap bg-card px-2 py-3 font-sans text-[10px] font-bold uppercase tracking-[1.2px] transition-colors hover:text-foreground',
                    column.align === 'right' ? 'text-right' : 'text-left',
                    column.key === sortKey ? 'text-accent-foreground' : 'text-muted-foreground',
                  )}
                >
                  {column.label}
                  <SortIcon active={column.key === sortKey} dir={column.key === sortKey ? sortDir : 'desc'} />
                  <div
                    role="separator"
                    aria-label={`调整${column.label}列宽`}
                    aria-orientation="vertical"
                    tabIndex={0}
                    className="absolute bottom-0 right-0 top-0 w-[6px] cursor-col-resize transition-colors hover:bg-accent-foreground/25"
                    onMouseDown={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      setResizing({ key: column.key, startX: event.clientX, startWidth: getColWidth(column.key) })
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
                      event.preventDefault()
                      event.stopPropagation()
                      resizeColumnByKeyboard(column.key, event.key === 'ArrowLeft' ? -8 : 8)
                    }}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.map((row) => {
              return (
                <tr key={rowKey(activeTab, row)} className="border-b border-border/50 transition-colors hover:bg-muted/50">
                  <td
                    className={cn(
                      'sticky left-0 z-20 bg-card px-2 py-2.5 text-right font-serif text-[17px] font-semibold tabular-nums',
                      rankColorClass(row.power_rank),
                    )}
                    title="当前完整总榜走势排名；搜索、分页和字段隐藏不会重算"
                  >
                    {String(row.power_rank).padStart(2, '0')}
                  </td>
                  <td className="sticky left-[44px] z-10 bg-card px-3 py-2.5" style={{ maxWidth: getColWidth(`_name_${activeTab}`) }}>
                    {renderNameCell(activeTab, row)}
                  </td>
                  {columns.map((column) => renderTableCell(row, column))}
                </tr>
              )
            })}
            {paginatedRows.length === 0 && (
              <tr>
                <td colSpan={2 + columns.length} className="px-3 py-16 text-center font-sans text-[14px] text-muted-foreground">
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </GlassCard>

      <p className="mb-5 font-sans text-[12px] text-muted-foreground">
        显示 {rows.length === 0 ? 0 : (safePage - 1) * pageSize + 1}-{Math.min(safePage * pageSize, rows.length)} / 总数 {formatNumber(rows.length)} 条
        {rows.length !== total && <>（共 {formatNumber(total)} 条）</>}
      </p>
    </>
  )
}
