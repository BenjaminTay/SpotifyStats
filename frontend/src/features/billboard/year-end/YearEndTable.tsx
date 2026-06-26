import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'

import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { CoverCell } from '@/components/shared/CoverCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { PaginationBar } from '@/components/shared/PaginationBar'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink, primaryArtistName } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import type {
  BillboardYearEndAlbumRow,
  BillboardYearEndArtistRow,
  BillboardYearEndTrackRow,
} from '@/types/billboard'
import {
  YEAR_END_COLUMNS,
  entityNameForRow,
  formatYearEndNumber,
  rowKeyForYearEnd,
  subtitleForRow,
  type YearEndRow,
  type YearEndSortDir,
  type YearEndSortKey,
  type YearEndTab,
} from './yearEndData'

const NAME_COLUMN_WIDTH = 260
const RANK_COLUMN_WIDTH = 64
const INSET_BEFORE_PLAYS_KEYS = new Set<YearEndSortKey>([
  'peak_position',
  'weeks_on_chart',
  'weeks_at_no1',
  'weeks_top5',
  'weeks_top10',
])

function SortIcon({ active, dir }: { active: boolean; dir: YearEndSortDir }) {
  if (!active) return <ArrowUpDown className="ml-1 inline h-3 w-3 text-muted-foreground/40" />
  return dir === 'asc'
    ? <ArrowUp className="ml-1 inline h-3 w-3 text-accent-foreground" />
    : <ArrowDown className="ml-1 inline h-3 w-3 text-accent-foreground" />
}

function rankColorClass(rank: number) {
  if (rank === 1) return 'text-accent-foreground'
  if (rank === 2) return 'text-muted-foreground'
  if (rank === 3) return 'text-[#C17A4E] dark:text-[#C97B6B]'
  return 'text-muted-foreground'
}

function formatRankNumber(rank: number) {
  return String(rank).padStart(2, '0')
}

function spacingBeforePlaysClass(key: YearEndSortKey) {
  return INSET_BEFORE_PLAYS_KEYS.has(key) ? 'pr-5' : ''
}

function MetricWithBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <>
      {formatYearEndNumber(value)}
      <span className="ml-2 inline-block h-[3px] w-[70px] rounded-[2px] bg-muted align-middle">
        <span
          className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
          style={{ width: `${pct}%` }}
        />
      </span>
    </>
  )
}

function detailHref(tab: YearEndTab, row: YearEndRow): string {
  if (tab === 'tracks') {
    return billboardDetailLink(`/music/tracks/${(row as BillboardYearEndTrackRow).track_id}`)
  }
  if (tab === 'albums') {
    const album = row as BillboardYearEndAlbumRow
    return billboardDetailLink(
      `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`,
    )
  }
  return billboardDetailLink(`/music/artists/${encodeURIComponent(primaryArtistName(row as BillboardYearEndArtistRow))}`)
}

function EntityCell({ tab, row }: { tab: YearEndTab; row: YearEndRow }) {
  const subtitle = subtitleForRow(tab, row)
  const label = displayName(entityNameForRow(tab, row))
  return (
    <div className="flex min-w-0 items-center gap-3">
      <CoverCell
        index={Math.max(0, row.year_end_rank - 1)}
        coverUrl={row.cover_url}
        label={label}
      />
      <div className="min-w-0">
        <Link
          to={detailHref(tab, row)}
          className="block truncate font-sans text-sm font-semibold text-foreground transition-colors hover:text-accent-foreground"
        >
          {label}
        </Link>
        {tab === 'tracks' ? (
          <ArtistLinks
            artistName={(row as BillboardYearEndTrackRow).artist_name}
            artistNames={(row as BillboardYearEndTrackRow).artist_names}
            className="mt-0.5 block truncate font-sans text-[12px] italic text-muted-foreground"
          />
        ) : (
          <p className="mt-0.5 truncate font-sans text-[12px] italic text-muted-foreground">
            {displayName(subtitle)}
          </p>
        )}
      </div>
    </div>
  )
}

interface YearEndTableProps {
  tab: YearEndTab
  rows: YearEndRow[]
  page: number
  pageSize: number
  sortKey?: YearEndSortKey
  sortDir?: YearEndSortDir
  onSortChange?: (key: YearEndSortKey) => void
  onPageChange: (page: number | ((current: number) => number)) => void
}

export function YearEndTable({
  tab,
  rows,
  page,
  pageSize,
  sortKey = 'year_end_score',
  sortDir = 'desc',
  onSortChange,
  onPageChange,
}: YearEndTableProps) {
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const pageRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize)
  const maxScore = rows.reduce((max, row) => Math.max(max, row.year_end_score), 0)
  const maxChartPlays = rows.reduce((max, row) => Math.max(max, row.chart_plays), 0)
  const tableWidth =
    RANK_COLUMN_WIDTH +
    NAME_COLUMN_WIDTH +
    YEAR_END_COLUMNS.reduce((sum, column) => sum + column.width, 0)

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table
          className="mx-7 my-0 w-[calc(100%-56px)] table-fixed border-collapse"
          style={{ minWidth: tableWidth }}
        >
          <thead>
            <tr>
              <th
                style={{ width: RANK_COLUMN_WIDTH }}
                className="pb-3.5 pt-4 text-center font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground"
              >
                #
              </th>
              <th
                style={{ width: NAME_COLUMN_WIDTH }}
                className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground"
              >
                名称
              </th>
              {YEAR_END_COLUMNS.map((column) => (
                <th
                  key={column.key}
                  style={{ width: column.width }}
                  className={cn(
                    'pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground',
                    column.align === 'right' && 'text-right',
                    column.align === 'center' && 'text-center',
                    column.align === 'left' && 'text-left',
                    spacingBeforePlaysClass(column.key),
                  )}
                >
                  <button
                    type="button"
                    disabled={!column.sortable || !onSortChange}
                    aria-label={`按${column.label}排序`}
                    onClick={() => onSortChange?.(column.key)}
                    className={cn(
                      'inline-flex items-center border-none bg-transparent p-0 text-inherit transition-colors',
                      column.align === 'right' && 'justify-end',
                      column.align === 'center' && 'justify-center',
                      column.align === 'left' && 'justify-start',
                      column.sortable && onSortChange ? 'hover:text-foreground' : 'cursor-default',
                      sortKey === column.key ? 'text-accent-foreground' : '',
                    )}
                  >
                    {column.label}
                    {column.sortable && <SortIcon active={sortKey === column.key} dir={sortDir} />}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr
                key={`${rowKeyForYearEnd(tab, row)}-${row.year_end_rank}`}
                className="transition-colors hover:bg-muted/50"
              >
                <td
                  className={cn(
                    'pb-3.5 pt-3.5 text-center font-serif text-[22px] font-semibold tabular-nums',
                    rankColorClass(row.year_end_rank),
                  )}
                >
                  {formatRankNumber(row.year_end_rank)}
                </td>
                <td className="pb-3.5 pt-3.5">
                  <EntityCell tab={tab} row={row} />
                </td>
                {YEAR_END_COLUMNS.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      'whitespace-nowrap pb-3.5 pt-3.5 tabular-nums',
                      !column.rankStyle && 'font-sans text-[13px]',
                      !column.rankStyle && column.align === 'right' && 'text-right',
                      !column.rankStyle && column.align === 'center' && 'text-center',
                      !column.rankStyle && column.align === 'left' && 'text-left',
                      column.rankStyle &&
                        'text-center font-serif text-[22px] font-semibold',
                      spacingBeforePlaysClass(column.key),
                      column.rankStyle
                        ? rankColorClass(Number(row[column.key] ?? 0))
                        : sortKey === column.key
                          ? 'font-semibold text-accent-foreground'
                          : 'text-foreground/80',
                    )}
                  >
                    {column.key === 'peak_position' && formatRankNumber(row[column.key])}
                    {column.key === 'year_end_score' && (
                      <MetricWithBar value={row.year_end_score} max={maxScore} />
                    )}
                    {column.key === 'chart_plays' && (
                      <MetricWithBar value={row.chart_plays} max={maxChartPlays} />
                    )}
                    {column.key !== 'peak_position' &&
                      column.key !== 'year_end_score' &&
                      column.key !== 'chart_plays' &&
                      formatYearEndNumber(row[column.key])}
                  </td>
                ))}
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={2 + YEAR_END_COLUMNS.length}
                  className="px-3 py-16 text-center font-sans text-[14px] text-muted-foreground"
                >
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <PaginationBar
        page={safePage}
        totalPages={totalPages}
        totalEntries={rows.length}
        pageSize={pageSize}
        onPageChange={(nextPage) => onPageChange(nextPage)}
      />
    </GlassCard>
  )
}
