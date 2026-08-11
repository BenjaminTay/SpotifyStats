import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { CoverCell } from '@/components/shared/CoverCell'
import { RankNumber } from '@/components/shared/RankNumber'
import type { AnalysisChartRow } from '@/types/analysis'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import { MobileRankList } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'

const PAGE_SIZE = 20

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatHours(n: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n)}h`
}

function dateShort(value: string): string {
  return value ? value.slice(0, 10) : '—'
}

function entityLink(row: Pick<AnalysisChartRow, 'track_id' | 'track_name' | 'album_name' | 'artist_name'>, entity: 'track' | 'album' | 'artist'): string {
  if (entity === 'track' && row.track_id != null) return `/music/tracks/${row.track_id}`
  if (entity === 'album' && row.album_name) {
    return `/music/albums/${encodeURIComponent(row.album_name)}${row.artist_name ? `?artist=${encodeURIComponent(row.artist_name)}` : ''}`
  }
  if (entity === 'artist' && row.artist_name) return `/music/artists/${encodeURIComponent(row.artist_name)}`
  return '#'
}

export function PersonalRankPagination({
  total,
  pageSize,
  page,
  totalPages,
  onPageChange,
  compact = false,
  className,
}: {
  total: number
  pageSize: number
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  compact?: boolean
  className?: string
}) {
  if (compact) {
    return (
      <div className={cn('flex items-center justify-end', className)}>
        <div className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
          <button
            type="button"
            aria-label="上一页"
            disabled={page <= 1}
            onClick={() => onPageChange(Math.max(1, page - 1))}
            className="rounded-lg border border-border px-2.5 py-1.5 disabled:opacity-30"
          >
            上一页
          </button>
          <span className="min-w-14 text-center tabular-nums">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            aria-label="下一页"
            disabled={page >= totalPages}
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            className="rounded-lg border border-border px-2.5 py-1.5 disabled:opacity-30"
          >
            下一页
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('flex items-center justify-between', className)}>
      <span className="font-sans text-[12px] text-muted-foreground tabular-nums">
        显示 {total === 0 ? 0 : (page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} / 总数 {total} 条
      </span>
      <div className="flex items-center gap-1">
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
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="上一页"
          className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
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
      </div>
    </div>
  )
}

function matchesPersonalRankSearch(
  row: AnalysisChartRow,
  entity: 'track' | 'album' | 'artist',
  query: string,
): boolean {
  const normalized = query.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim()
  if (!normalized) return true
  const fields = entity === 'track'
    ? [row.track_name, row.artist_name, ...(row.artist_names ?? []), row.album_name]
    : entity === 'album'
      ? [row.album_name, row.artist_name]
      : [row.artist_name]
  return fields.some((field) => field && [field, displayName(field)].some((candidate) =>
    candidate.normalize('NFKC').toLocaleLowerCase().includes(normalized),
  ))
}

export function PersonalRankTable({ rows, entity, metric, pagination, searchQuery = '' }: { rows: AnalysisChartRow[]; entity: 'track' | 'album' | 'artist'; metric: 'plays' | 'hours'; pagination?: { total: number; page: number; pageSize: number; onPageChange: (page: number) => void }; searchQuery?: string }) {
  const isPhone = useViewportMode() === 'phone'
  const [internalPageState, setInternalPageState] = useState({ rows, entity, searchQuery, page: 1 })
  const internalPage = internalPageState.rows === rows
    && internalPageState.entity === entity
    && internalPageState.searchQuery === searchQuery
    ? internalPageState.page
    : 1
  const filteredRows = searchQuery
    ? rows.filter((row) => matchesPersonalRankSearch(row, entity, searchQuery))
    : rows
  const total = pagination?.total ?? filteredRows.length
  const pageSize = pagination?.pageSize ?? PAGE_SIZE
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(pagination?.page ?? internalPage, totalPages)
  const goToPage = (next: number) => {
    if (pagination) pagination.onPageChange(next)
    else setInternalPageState({ rows, entity, searchQuery, page: next })
  }

  const paged = pagination ? rows : filteredRows.slice((safePage - 1) * pageSize, safePage * pageSize)
  const maxPlays = Math.max(1, ...rows.map((r) => r.plays))
  const maxHours = Math.max(1, ...rows.map((r) => r.hours))

  if (isPhone) {
    return (
      <MobileRankList
        rows={paged.map((row) => {
          const title = entity === 'track' ? row.track_name : entity === 'album' ? row.album_name : row.artist_name
          const subtitle = entity === 'artist'
            ? `${row.unique_tracks ?? 0} 首曲目`
            : displayName(row.artist_name || '')
          return {
            entityType: entity,
            title: displayName(title || '未知'),
            subtitle,
            rank: row.rank,
            coverUrl: row.cover_url,
            metric: metric === 'plays' ? formatNumber(row.plays) : formatHours(row.hours),
            metricLabel: metric === 'plays' ? '播放次数' : '播放时长',
            facts: [
              { label: '首次', value: dateShort(row.first_played) },
              { label: '最近', value: dateShort(row.last_played) },
            ],
            badges: [`占比 ${row.share_pct}%`],
            to: entityLink(row, entity),
          }
        })}
        page={safePage}
        pageCount={totalPages}
        onPageChange={totalPages > 1 ? goToPage : undefined}
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[784px] table-fixed border-collapse text-left font-sans text-[13px]">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase tracking-[1px] text-muted-foreground">
            <th className="w-12 py-3">#</th>
            <th className="py-3">名称</th>
            <th className="w-[200px] py-3 text-right">播放</th>
            <th className="w-[200px] py-3 text-right">时长</th>
            <th className="w-[100px] py-3 text-right">首次</th>
            <th className="w-[100px] py-3 text-right">最近</th>
            <th className="w-16 py-3 text-right">日均</th>
            <th className="w-[72px] py-3 text-right">占比</th>
          </tr>
        </thead>
        <tbody>
          {paged.map((row, index) => {
            const title = entity === 'track' ? row.track_name : entity === 'album' ? row.album_name : row.artist_name
            const isTrack = entity === 'track'
            const playsPct = (row.plays / maxPlays) * 100
            const hoursPct = (row.hours / maxHours) * 100
            const dailyText = metric === 'plays'
              ? row.avg_daily_plays.toFixed(2)
              : row.avg_daily_hours * 60 < 1
                ? `${Math.round(row.avg_daily_hours * 3600)}s`
                : `${Math.round(row.avg_daily_hours * 60)}m`
            return (
              <tr key={`${row.rank}-${title}`} className="border-b border-border/70">
                <td className="py-3">
                  <RankNumber rank={row.rank} className="text-[20px]" />
                </td>
                <td className="py-3 pr-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <Link to={entityLink(row, entity)}>
                      <CoverCell index={index} coverUrl={row.cover_url} label={displayName(title || '未知')} />
                    </Link>
                    <span className="min-w-0">
                      <Link to={entityLink(row, entity)} className="block truncate font-semibold transition-colors hover:text-accent-foreground">
                        {displayName(title || '未知')}
                      </Link>
                      {entity === 'artist' ? (
                        <span className="block truncate text-[12px] italic text-muted-foreground">{row.unique_tracks ?? 0} 首曲目</span>
                      ) : isTrack && row.artist_name ? (
                        <ArtistLinks
                          artistName={row.artist_name}
                          artistNames={row.artist_names}
                          className="block truncate text-[12px] italic text-muted-foreground"
                        />
                      ) : (
                        <span className="block truncate text-[12px] italic text-muted-foreground">{displayName(row.artist_name || '')}</span>
                      )}
                    </span>
                  </div>
                </td>
                <td className="py-3 text-right tabular-nums">
                  <span className="inline-flex items-center gap-2 justify-end">
                    <span className={cn(metric === 'plays' && 'font-semibold')}>{formatNumber(row.plays)}</span>
                    <span className="inline-block h-[3px] w-[60px] rounded-[2px] bg-muted align-middle">
                      <span className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300" style={{ width: `${Math.round(playsPct)}%` }} />
                    </span>
                  </span>
                </td>
                <td className="py-3 text-right tabular-nums">
                  <span className="inline-flex items-center gap-2 justify-end">
                    <span className={cn(metric === 'hours' && 'font-semibold')}>{formatHours(row.hours)}</span>
                    <span className="inline-block h-[3px] w-[60px] rounded-[2px] bg-muted align-middle">
                      <span className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300" style={{ width: `${Math.round(hoursPct)}%` }} />
                    </span>
                  </span>
                </td>
                <td className="py-3 text-right text-muted-foreground">{dateShort(row.first_played)}</td>
                <td className="py-3 text-right text-muted-foreground">{dateShort(row.last_played)}</td>
                <td className="py-3 text-right tabular-nums">{dailyText}</td>
                <td className="py-3 text-right tabular-nums">{row.share_pct}%</td>
              </tr>
            )
          })}
          {paged.length === 0 && (
            <tr>
              <td colSpan={8} className="py-16 text-center text-sm text-muted-foreground">
                没有匹配的结果
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {totalPages > 1 && (
        <PersonalRankPagination
          total={total}
          pageSize={pageSize}
          page={safePage}
          totalPages={totalPages}
          onPageChange={goToPage}
          className="mt-3"
        />
      )}
    </div>
  )
}
