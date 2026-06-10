import { useReleaseCycleCompare } from '@/hooks/useBillboard'
import { GlassCard } from '@/components/shared/GlassCard'
import type { ReleaseCycleCompareItem } from '@/types/billboard'
import { ENTITY_COLORS, bestIndices } from './versusData'

interface AlbumSlot {
  albumName: string
  artistName: string
  name: string
}

interface VersusReleaseCycleSectionProps {
  albums: AlbumSlot[]
}

export function VersusReleaseCycleSection({ albums }: VersusReleaseCycleSectionProps) {
  const { data, loading } = useReleaseCycleCompare(
    albums.map((a) => ({ artist_name: a.artistName, album_name: a.albumName })),
  )

  const comparisons: ReleaseCycleCompareItem[] = data?.comparisons ?? []
  if (!loading && comparisons.length === 0) return null

  type MetricRow = {
    key: string
    label: string
    higherIsBetter: boolean
    getRaw: (c: ReleaseCycleCompareItem) => unknown
    fmt: (v: unknown) => string
  }

  const metricRows: MetricRow[] = [
    { key: 'debut', label: '首发排名', higherIsBetter: false, getRaw: (c) => c.metrics?.debut_rank, fmt: (v) => v != null ? `#${v}` : '—' },
    { key: 'peak', label: '最高排名', higherIsBetter: false, getRaw: (c) => c.metrics?.peak_rank, fmt: (v) => v != null ? `#${v}` : '—' },
    { key: 'weeks_to_peak', label: '到达峰值周数', higherIsBetter: false, getRaw: (c) => c.metrics?.weeks_to_peak, fmt: (v) => v != null ? String(v) : '—' },
    { key: 'weeks_on_chart', label: '在榜周数', higherIsBetter: true, getRaw: (c) => c.metrics?.weeks_on_chart, fmt: (v) => v != null ? String(v) : '—' },
    { key: 'release_week_plays', label: '发行周播放', higherIsBetter: true, getRaw: (c) => c.metrics?.release_week_plays, fmt: (v) => v != null ? String(v) : '—' },
    { key: 'artist_impact', label: '艺人影响力', higherIsBetter: true, getRaw: (c) => c.metrics?.artist_impact, fmt: (v) => v != null ? `${Number(v).toFixed(1)}x` : '—' },
    { key: 'market_impact', label: '大盘影响力', higherIsBetter: true, getRaw: (c) => c.metrics?.market_impact, fmt: (v) => v != null ? `${Number(v).toFixed(1)}x` : '—' },
    { key: 'half_life', label: '半数播放距 (周)', higherIsBetter: true, getRaw: (c) => c.metrics?.half_life, fmt: (v) => v != null ? String(v) : '—' },
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
            {metricRows.map((row) => {
              const values = comparisons.map((c) => row.getRaw(c))
              const winners = bestIndices(values, row.higherIsBetter)

              return (
                <tr key={row.key} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                  <td className="py-2 pl-4 text-[13px] text-muted-foreground sticky left-0 bg-card">{row.label}</td>
                  {values.map((v, i) => {
                    const isBest = winners.includes(i)
                    return (
                      <td
                        key={i}
                        className="py-2 pr-4 text-right text-[14px] font-semibold tabular-nums"
                        style={isBest ? { color: ENTITY_COLORS[i % ENTITY_COLORS.length], backgroundColor: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}14` } : undefined}
                      >
                        {row.fmt(v)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
        {loading && (
          <div className="px-4 py-3 text-center text-[12px] text-muted-foreground">加载中...</div>
        )}
      </GlassCard>
    </div>
  )
}
