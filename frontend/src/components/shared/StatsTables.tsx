import { Link } from 'react-router-dom'
import { CoverCell } from '@/components/shared/CoverCell'
import type { AnalysisChartRow, RecentPlayRow } from '@/types/analysis'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatHours(n: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n)}h`
}

function formatTs(value: string): { date: string; time: string } {
  const tIdx = value.indexOf('T')
  if (tIdx === -1) return { date: value.slice(0, 10), time: '' }
  return { date: value.slice(0, tIdx), time: value.slice(tIdx + 1, tIdx + 6) }
}

function formatMinutes(n: number): string {
  const totalSec = Math.round(n * 3600)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return `${m}m${s}s`
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
          {rows.map((row, index) => {
            const title = entity === 'track' ? row.track_name : entity === 'album' ? row.album_name : row.artist_name
            const sub = entity === 'artist' ? `${row.unique_tracks ?? 0} 首曲目` : row.artist_name
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
                  <Link to={entityLink(row, entity)} className="flex items-center gap-3 min-w-0 transition-colors hover:text-accent-foreground">
                    <CoverCell index={index} coverUrl={row.cover_url} />
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{displayName(title || '未知')}</span>
                      <span className="block truncate text-[12px] italic text-muted-foreground">{displayName(sub || '')}</span>
                    </span>
                  </Link>
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
    </div>
  )
}

export function RecentPlaysTable({ rows }: { rows: RecentPlayRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[660px] table-fixed border-collapse text-left font-sans text-[13px]">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase tracking-[1px] text-muted-foreground">
            <th className="w-[110px] py-3">播放时间</th>
            <th className="w-[240px] py-3">歌曲</th>
            <th className="w-[220px] py-3">专辑</th>
            <th className="w-[60px] py-3 text-right">时长</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const { date, time } = formatTs(row.ts)
            return (
              <tr key={row.play_id} className="border-b border-border/70">
                <td className="py-3">
                  <span className="block tabular-nums font-semibold text-muted-foreground">{date}</span>
                  <span className="block text-[12px] text-muted-foreground/60">{time}</span>
                </td>
                <td className="py-3 pr-3">
                  <span className="flex items-center gap-3 min-w-0">
                    <Link to={row.track_id ? `/music/tracks/${row.track_id}` : '#'} className="shrink-0">
                      <CoverCell index={index} coverUrl={row.cover_url} />
                    </Link>
                    <span className="min-w-0">
                      <Link to={row.track_id ? `/music/tracks/${row.track_id}` : '#'} className="block truncate font-semibold transition-colors hover:text-accent-foreground">
                        {displayName(row.track_name)}
                      </Link>
                      <Link to={row.artist_name ? `/music/artists/${encodeURIComponent(row.artist_name)}` : '#'} className="block truncate text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground">
                        {displayName(row.artist_name)}
                      </Link>
                    </span>
                  </span>
                </td>
                <td className="py-3 pr-3">
                  <span className="flex items-center gap-3 min-w-0">
                    <CoverCell index={index} coverUrl={row.cover_url} />
                    <span className="min-w-0">
                      <Link to={row.album_name ? `/music/albums/${encodeURIComponent(row.album_name)}${row.artist_name ? `?artist=${encodeURIComponent(row.artist_name)}` : ''}` : '#'} className="block truncate font-semibold text-muted-foreground transition-colors hover:text-accent-foreground">
                        {displayName(row.album_name || '—')}
                      </Link>
                      <Link to={row.artist_name ? `/music/artists/${encodeURIComponent(row.artist_name)}` : '#'} className="block truncate text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground">
                        {displayName(row.artist_name)}
                      </Link>
                    </span>
                  </span>
                </td>
                <td className="py-3 text-right tabular-nums font-semibold">{formatMinutes(row.hours)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

