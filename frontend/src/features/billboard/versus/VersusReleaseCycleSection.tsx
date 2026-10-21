import { useReleaseCycleCompare } from '@/hooks/useBillboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { Button } from '@/components/ui/button'
import type { ReleaseCycleCompareItem, ReleaseCycleCompareResult } from '@/types/billboard'
import { ENTITY_COLORS, bestIndices } from './versusData'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface AlbumSlot {
  albumName: string
  artistName: string
  name: string
}

interface VersusReleaseCycleSectionProps {
  albums: AlbumSlot[]
  billboardParams: Record<string, string | number | boolean>
  enabled?: boolean
}

const unavailableMessages: Record<string, string> = {
  release_day_unconfirmed: '缺少已确认的发行日，需补充发行证据。',
  release_date_coarse: '来源日期仅精确到年或月，无法按发行日对齐。',
  release_date_invalid: '发行日期无效，需核对来源。',
  release_date_conflict: '发行日期存在冲突，需核对目标版本。',
  artist_identity_unconfirmed: '专辑艺人身份尚未确认。',
  entity_not_found: '未找到对应的专辑项目或发行版本。',
  release_ambiguous: '无法唯一确定发行版本，需核对版本关联。',
  missing_result: '本次响应缺少此专辑的结果，请重新加载。',
}

const metricMessages: Record<string, string> = {
  no_chart_entry: '窗口内未上榜',
  no_plays_in_window: '窗口内无播放',
  no_artist_baseline: '无艺人基准播放',
  no_market_baseline: '无大盘基准播放',
  no_playback: '无播放',
}

function readyComparison(result: ReleaseCycleCompareResult | undefined): ReleaseCycleCompareItem | null {
  return result && result.status !== 'unavailable' ? result : null
}

export function VersusReleaseCycleSection({ albums, billboardParams, enabled = true }: VersusReleaseCycleSectionProps) {
  useChineseTextVersion()
  const { results, loading, fetching, error, refetch } = useReleaseCycleCompare(
    albums.map((a) => ({ artist_name: a.artistName, album_name: a.albumName })),
    billboardParams,
    enabled,
  )

  if (albums.length < 2) return null
  const comparisons = albums.map((_, index) => readyComparison(results[index]))

  type MetricRow = {
    key: string
    label: string
    higherIsBetter: boolean
    getRaw: (c: ReleaseCycleCompareItem) => unknown
    fmt: (v: unknown) => string
  }

  const metricRows: MetricRow[] = [
    { key: 'debut_rank', label: '首发排名', higherIsBetter: false, getRaw: (c) => c.metrics?.debut_rank, fmt: (v) => v != null ? `#${v}` : '窗口内未上榜' },
    { key: 'peak_rank', label: '最高排名', higherIsBetter: false, getRaw: (c) => c.metrics?.peak_rank, fmt: (v) => v != null ? `#${v}` : '窗口内未上榜' },
    { key: 'release_week_plays', label: '发行周播放', higherIsBetter: true, getRaw: (c) => c.metrics?.release_week_plays, fmt: (v) => v != null ? String(v) : '暂无可用指标' },
    { key: 'artist_impact', label: '艺人影响力', higherIsBetter: true, getRaw: (c) => c.metrics?.artist_impact, fmt: (v) => v != null ? `${Number(v).toFixed(1)}x` : '暂无可用指标' },
    { key: 'market_impact', label: '大盘影响力', higherIsBetter: true, getRaw: (c) => c.metrics?.market_impact, fmt: (v) => v != null ? `${Number(v).toFixed(1)}x` : '暂无可用指标' },
    { key: 'half_life', label: '半数播放距 (周)', higherIsBetter: true, getRaw: (c) => c.metrics?.half_life, fmt: (v) => v != null ? String(v) : '暂无可用指标' },
  ]

  return (
    <div>
      <h3 className="mb-4 font-serif text-xl font-semibold">发行周期对比</h3>
      {error && (
        <div role="alert" className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-4 py-3 text-sm">
          <span>发行周期读取失败：{error}</span>
          <Button variant="outline" className="min-h-11 min-w-11" disabled={fetching} onClick={refetch}>
            {fetching ? '正在重试…' : '重新加载'}
          </Button>
        </div>
      )}
      <GlassCard className="p-0">
        <div role="region" aria-label="发行周期对比表格，可横向滚动" tabIndex={0} className="overflow-x-auto rounded-[inherit] focus-visible:outline-2 focus-visible:outline-ring">
          <table aria-label="发行周期对比" aria-busy={!enabled || loading} className="w-full border-collapse" style={{ minWidth: 136 + albums.length * 180 }}>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="min-w-[136px] py-2.5 pl-4 pr-3 text-left text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground sticky left-0 bg-card">
                  指标
                </th>
                {albums.map((a, i) => (
                  <th
                    key={JSON.stringify([a.artistName, a.albumName])}
                    scope="col"
                    className="min-w-[180px] py-2.5 pl-3 pr-4 text-right text-[10px] font-bold uppercase tracking-[1.2px]"
                    style={{ color: ENTITY_COLORS[i % ENTITY_COLORS.length] }}
                  >
                    {displayName(a.name)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <th scope="row" className="sticky left-0 bg-card py-3 pl-4 pr-3 text-left text-[13px] font-normal text-muted-foreground">计算状态</th>
                {albums.map((album, index) => {
                  const result = results[index]
                  const comparison = comparisons[index]
                  const status = !enabled ? '等待当前对决数据就绪…' : loading ? '正在加载…'
                    : result?.status === 'unavailable' ? unavailableMessages[result.reason] ?? '发行证据暂不可用，需核对来源。'
                      : comparison ? `可计算${comparison.release_date ? ` · ${comparison.release_date}` : ''}`
                        : error ? '请求失败，尚未取得结果' : '等待榜单数据就绪'
                  return <td key={JSON.stringify([album.artistName, album.albumName])} className="px-4 py-3 text-right align-top text-xs leading-relaxed text-muted-foreground">{status}</td>
                })}
              </tr>
              {metricRows.map((row) => {
                const values = comparisons.map((c) => c ? row.getRaw(c) : undefined)
                const winners = bestIndices(values, row.higherIsBetter)

                return (
                  <tr key={row.key} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                    <th scope="row" className="py-2 pl-4 pr-3 text-left text-[13px] font-normal text-muted-foreground sticky left-0 bg-card">{row.label}</th>
                    {values.map((v, i) => {
                      const isBest = winners.includes(i)
                      const reason = comparisons[i]?.metric_reasons?.[row.key]
                      const text = !enabled ? '等待数据' : loading ? '加载中…'
                        : !comparisons[i] ? results[i]?.status === 'unavailable' ? '不可计算' : error ? '请求失败' : '等待数据'
                          : v == null && reason ? metricMessages[reason] ?? '暂无可用指标'
                            : row.fmt(v)
                      return (
                        <td
                          key={i}
                          className="py-2 pr-4 text-right text-[14px] font-semibold tabular-nums"
                          style={isBest ? { color: ENTITY_COLORS[i % ENTITY_COLORS.length], backgroundColor: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}14` } : undefined}
                        >
                          {text}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {(!enabled || loading) && (
          <div role="status" className="px-4 py-3 text-center text-[12px] text-muted-foreground">{enabled ? '正在加载发行周期…' : '等待当前对决数据就绪…'}</div>
        )}
      </GlassCard>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">按各专辑已确认的发行日对齐；0 表示真实零值。缺少证据的专辑不参与指标比较。</p>
    </div>
  )
}
