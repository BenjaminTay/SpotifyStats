import { useQueries } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import { GlassCard } from '@/components/shared/GlassCard'
import type { ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { ENTITY_COLORS } from './versusData'

interface AlbumSlot {
  albumName: string
  artistName: string
  name: string
}

interface VersusReleaseCycleSectionProps {
  albums: AlbumSlot[]
}

export function VersusReleaseCycleSection({ albums }: VersusReleaseCycleSectionProps) {
  const results = useQueries({
    queries: albums.map((a) => ({
      queryKey: queryKeys.music.albumReleaseCycle(a.albumName, a.artistName, { weeks_before: 12, weeks_after: 24 }),
      queryFn: () =>
        api.get<ReleaseCycleAlbumDetailResponse>(
          `/billboard/release-cycle/artist/${encodeURIComponent(a.artistName)}/album/${encodeURIComponent(a.albumName)}`,
          { weeks_before: 12, weeks_after: 24 },
        ),
      enabled: !!a.albumName,
    })),
  })

  const allEmpty = results.every((r) => !r.data && !r.isLoading)
  if (allEmpty) return null

  const isLoading = results.some((r) => r.isLoading)

  type MetricRow = { label: string; getValue: (s: ReleaseCycleAlbumDetailResponse) => unknown }
  const metricRows: MetricRow[] = [
    { label: '首发排名', getValue: (s) => s.metrics?.debut_rank != null ? `#${s.metrics.debut_rank}` : null },
    { label: '最高排名', getValue: (s) => s.metrics?.peak_rank != null ? `#${s.metrics.peak_rank}` : null },
    { label: '到达峰值周数', getValue: (s) => s.metrics?.weeks_to_peak },
    { label: '在榜周数', getValue: (s) => s.metrics?.weeks_on_chart },
    { label: '发行周播放', getValue: (s) => s.metrics?.release_week_plays },
    { label: '发行前周均播放', getValue: (s) => s.metrics?.pre_release_avg },
    { label: '艺人影响力', getValue: (s) => s.metrics?.artist_impact != null ? `${Number(s.metrics.artist_impact).toFixed(1)}x` : null },
    { label: '大盘影响力', getValue: (s) => s.metrics?.market_impact != null ? `${Number(s.metrics.market_impact).toFixed(1)}x` : null },
    { label: '半衰期 (周)', getValue: (s) => s.metrics?.half_life },
  ]

  return (
    <div>
      <h3 className="mb-4 font-serif text-xl font-semibold">发行周期对比</h3>
      <GlassCard className="overflow-x-auto p-0">
        <table className="w-full border-collapse min-w-[300px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-2.5 pl-4 text-left text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground sticky left-0 bg-card">
                指标
              </th>
              {albums.map((a, i) => (
                <th
                  key={i}
                  className="py-2.5 pr-4 text-right text-[10px] font-bold uppercase tracking-[1.2px]"
                  style={{ color: ENTITY_COLORS[i % ENTITY_COLORS.length] }}
                >
                  {a.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((row) => (
              <tr key={row.label} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                <td className="py-2 pl-4 text-[13px] text-muted-foreground sticky left-0 bg-card">{row.label}</td>
                {results.map((r, i) => (
                  <td key={i} className="py-2 pr-4 text-right text-[14px] font-semibold tabular-nums">
                    {r.data ? (row.getValue(r.data) != null ? String(row.getValue(r.data)) : '—') : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {isLoading && (
          <div className="px-4 py-3 text-center text-[12px] text-muted-foreground">加载中...</div>
        )}
      </GlassCard>
    </div>
  )
}
