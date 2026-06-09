import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { CoverCell } from '@/components/shared/CoverCell'
import type { AnalysisChartRow } from '@/types/analysis'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'

const PAGE_SIZE = 50

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatHours(n: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n)}h`
}

function dateShort(value: string): string {
  return value ? value.slice(0, 10) : '—'
}

export function entityLink(row: Pick<AnalysisChartRow, 'track_id' | 'track_name' | 'album_name' | 'artist_name'>, entity: 'track' | 'album' | 'artist'): string {
  if (entity === 'track' && row.track_id != null) return `/music/tracks/${row.track_id}`
  if (entity === 'album' && row.album_name) {
    return `/music/albums/${encodeURIComponent(row.album_name)}${row.artist_name ? `?artist=${encodeURIComponent(row.artist_name)}` : ''}`
  }
  if (entity === 'artist' && row.artist_name) return `/music/artists/${encodeURIComponent(row.artist_name)}`
  return '#'
}

export function PersonalRankTable({ rows, entity, metric }: { rows: AnalysisChartRow[]; entity: 'track' | 'album' | 'artist'; metric: 'plays' | 'hours' }) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)

  useEffect(() => { setPage(1) }, [rows])

  const paged = rows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
  const maxPlays = Math.max(1, ...rows.map((r) => r.plays))
  const maxHours = Math.max(1, ...rows.map((r) => r.hours))

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
                <td className="py-3 font-semibold tabular-nums text-muted-foreground">{row.rank}</td>
                <td className="py-3 pr-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <Link to={entityLink(row, entity)}>
                      <CoverCell index={index} coverUrl={row.cover_url} />
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
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between">
          <span className="font-sans text-[12px] text-muted-foreground tabular-nums">
            显示 {(safePage - 1) * PAGE_SIZE + 1}-{Math.min(safePage * PAGE_SIZE, rows.length)} / 总数 {rows.length} 条
          </span>
          <div className="flex items-center gap-1">
            <span className="mr-2 font-sans text-[12px] text-muted-foreground tabular-nums">
              {safePage} / {totalPages}
            </span>
            <button
              onClick={() => setPage(1)}
              disabled={safePage <= 1}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
            >
              <ChevronsLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage(totalPages)}
              disabled={safePage >= totalPages}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
            >
              <ChevronsRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}


