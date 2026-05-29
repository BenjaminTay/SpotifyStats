import { Link } from 'react-router-dom'
import { CoverCell } from '@/components/shared/CoverCell'
import type { AnalysisChartRow, RecentPlayRow } from '@/types/analysis'
import { displayName } from '@/lib/chinese'

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
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse text-left font-sans text-[13px]">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase tracking-[1px] text-muted-foreground">
            <th className="w-14 py-3">#</th>
            <th className="py-3">名称</th>
            <th className="py-3 text-right">播放</th>
            <th className="py-3 text-right">时长</th>
            <th className="py-3 text-right">首次</th>
            <th className="py-3 text-right">最近</th>
            <th className="py-3 text-right">日均</th>
            <th className="py-3 text-right">占比</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const title = entity === 'track' ? row.track_name : entity === 'album' ? row.album_name : row.artist_name
            const sub = entity === 'artist' ? `${row.unique_tracks ?? 0} 首曲目` : row.artist_name
            return (
              <tr key={`${row.rank}-${title}`} className="border-b border-border/70">
                <td className="py-3 font-semibold tabular-nums text-muted-foreground">{row.rank}</td>
                <td className="py-3">
                  <Link to={entityLink(row, entity)} className="flex items-center gap-3 transition-colors hover:text-accent-foreground">
                    <CoverCell index={index} coverUrl={row.cover_url} />
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{displayName(title || '未知')}</span>
                      <span className="block truncate text-[12px] italic text-muted-foreground">{displayName(sub || '')}</span>
                    </span>
                  </Link>
                </td>
                <td className={metric === 'plays' ? 'py-3 text-right font-semibold tabular-nums' : 'py-3 text-right tabular-nums'}>{formatNumber(row.plays)}</td>
                <td className={metric === 'hours' ? 'py-3 text-right font-semibold tabular-nums' : 'py-3 text-right tabular-nums'}>{formatHours(row.hours)}</td>
                <td className="py-3 text-right text-muted-foreground">{dateShort(row.first_played)}</td>
                <td className="py-3 text-right text-muted-foreground">{dateShort(row.last_played)}</td>
                <td className="py-3 text-right tabular-nums">{metric === 'plays' ? row.avg_daily_plays : `${row.avg_daily_hours}h`}</td>
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
      <table className="w-full min-w-[720px] border-collapse text-left font-sans text-[13px]">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase tracking-[1px] text-muted-foreground">
            <th className="py-3">播放时间</th>
            <th className="py-3">歌曲</th>
            <th className="py-3">专辑</th>
            <th className="py-3 text-right">时长</th>
            <th className="py-3 text-right">平台</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.play_id} className="border-b border-border/70">
              <td className="py-3 text-muted-foreground">{row.ts}</td>
              <td className="py-3">
                <Link to={row.track_id ? `/music/tracks/${row.track_id}` : '#'} className="flex items-center gap-3 transition-colors hover:text-accent-foreground">
                  <CoverCell index={index} coverUrl={row.cover_url} />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{displayName(row.track_name)}</span>
                    <span className="block truncate text-[12px] italic text-muted-foreground">{displayName(row.artist_name)}</span>
                  </span>
                </Link>
              </td>
              <td className="py-3 text-muted-foreground">{displayName(row.album_name || '')}</td>
              <td className="py-3 text-right tabular-nums">{formatHours(row.hours)}</td>
              <td className="py-3 text-right text-muted-foreground">{row.platform}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
