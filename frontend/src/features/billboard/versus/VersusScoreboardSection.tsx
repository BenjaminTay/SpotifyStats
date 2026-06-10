import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import { GlassCard } from '@/components/shared/GlassCard'
import type { VersusEntityData, EntityListItem } from '@/types/billboard'
import type { EntityStatsResponse } from '@/types/analysis'
import { METRIC_DEFS, METRIC_GROUPS, bestIndex, ENTITY_COLORS, type VersusKind, type MetricGroup } from './versusData'

interface VersusScoreboardSectionProps {
  entities: VersusEntityData[] | null
  kind: VersusKind
  queue: EntityListItem[]
  buildDetailLink: (item: EntityListItem) => string | null
}

function personalPath(kind: VersusKind, id: string): string {
  switch (kind) {
    case 'track': return `/music/tracks/${id}/stats`
    case 'album': return `/music/albums/${encodeURIComponent(id)}/stats`
    default: return `/music/artists/${encodeURIComponent(id)}/stats`
  }
}

function personalId(kind: VersusKind, item: EntityListItem): string {
  switch (kind) {
    case 'track': return String(item.track_id ?? '')
    case 'album': return item.album_name ?? ''
    case 'artist': return item.artist_name ?? ''
  }
}

export function VersusScoreboardSection({
  entities,
  kind,
  queue,
  buildDetailLink,
}: VersusScoreboardSectionProps) {
  if (!entities || entities.length < 2) return null

  const n = entities.length

  // ── Personal stats (useQueries, only when versus data is ready) ──
  const personalResults = useQueries({
    queries: queue.map((q) => ({
      queryKey: queryKeys.music.entityStats(kind, personalId(kind, q), kind === 'album' ? { artist: q.artist_name ?? '' } : {}),
      queryFn: () => api.get<EntityStatsResponse>(
        personalPath(kind, personalId(kind, q)),
        kind === 'album' ? { artist: q.artist_name ?? '' } : undefined,
      ),
      enabled: !!personalId(kind, q),
      staleTime: 1000 * 60 * 5,
    })),
  })

  // ── Chart metrics ──
  const allMetrics = entities.map((e) => {
    const m = { ...(e.metrics ?? {}) }
    if (e.popularity != null) m.popularity = e.popularity
    return m
  })

  const defs = METRIC_DEFS.filter((d) => {
    if (!d.only) return true
    if (Array.isArray(d.only)) return d.only.includes(kind)
    return d.only === kind
  })

  // Compute chart week max plays from rank_history (shown in 个人播放 as 单周最多播放)
  const chartWeekMaxes = entities.map((e) => {
    const rh = e.rank_history
    if (!rh || rh.length === 0) return null
    let max = 0
    for (const p of rh) {
      if (p.play_count > max) max = p.play_count
    }
    return max > 0 ? max : null
  })

  // ── Win tracking ──
  const wins = new Array(n).fill(0)
  for (const def of defs) {
    const values = allMetrics.map((m) => m[def.key])
    const best = bestIndex(values, def.higherIsBetter)
    if (best >= 0) wins[best]++
  }

  // ── Personal play metric definitions ──
  interface PersonalMetricRow {
    label: string
    higherIsBetter: boolean
    values: (unknown)[]
    best: number
    fmt: (v: unknown) => string
  }

  function makePersonalRows(): PersonalMetricRow[] {
    const rows: PersonalMetricRow[] = []
    const define = (
      label: string,
      higherIsBetter: boolean,
      get: (s: EntityStatsResponse) => unknown,
      fmt: (v: unknown) => string,
    ) => {
      const values = personalResults.map((r) => r.data ? get(r.data) : null)
      const best = bestIndex(values, higherIsBetter)
      if (best >= 0) wins[best]++
      rows.push({ label, higherIsBetter, values, best, fmt })
    }

    define('个人总播放', true, (s) => s.summary?.total_plays, (v) => v != null ? String(v) : '—')
    define('总时长 (小时)', true, (s) => s.summary?.total_hours, (v) => v != null ? Number(v).toFixed(1) : '—')
    define('日均播放', true, (s) => s.daily_metrics?.avg_daily_plays, (v) => v != null ? Number(v).toFixed(1) : '—')
    define('日均时长 (小时)', true, (s) => s.daily_metrics?.avg_daily_hours, (v) => v != null ? Number(v).toFixed(2) : '—')
    define('单天最多播放', true, (s) => {
      const trend = s.daily_trend
      if (!trend || trend.length === 0) return null
      let max = 0
      for (const d of trend) { if (d.plays > max) max = d.plays }
      return max > 0 ? max : null
    }, (v) => v != null ? String(v) : '—')

    // 单周最多播放 (from chart rank_history)
    if (chartWeekMaxes.some((v) => v != null)) {
      const best = bestIndex(chartWeekMaxes, true)
      if (best >= 0) wins[best]++
      rows.push({ label: '单周最多播放', higherIsBetter: true, values: [...chartWeekMaxes], best, fmt: (v) => v != null ? String(v) : '—' })
    }

    define('活跃天数', true, (s) => s.summary?.active_days, (v) => v != null ? String(v) : '—')
    define('全时段排名', false, (s) => s.ranks?.lifetime, (v) => v != null ? `#${v}` : '—')
    define('近6个月排名', false, (s) => s.ranks?.last_6_months, (v) => v != null ? `#${v}` : '—')
    define('近4周排名', false, (s) => s.ranks?.last_4_weeks, (v) => v != null ? `#${v}` : '—')
    return rows
  }

  const personalRows = makePersonalRows()

  const grouped = new Map<MetricGroup, typeof defs>()
  for (const g of METRIC_GROUPS) {
    const items = defs.filter((d) => d.group === g)
    if (items.length > 0) grouped.set(g, items)
  }
  // Add personal-play group if any personal data loaded
  const hasPersonal = personalResults.some((r) => r.data)

  const detailLinks = queue.map((q) => buildDetailLink(q))

  return (
    <div>
      <h3 className="mb-4 font-serif text-xl font-semibold">对决记分牌</h3>

      <GlassCard className="overflow-x-auto p-0">
        <table className="w-full border-collapse min-w-[300px]">
          <thead>
            <tr className="border-b border-border">
              <th className="w-[140px] py-2.5 pl-4 text-left text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground sticky left-0 bg-card">
                指标
              </th>
              {entities.map((e, i) => (
                <th
                  key={i}
                  className="py-3 pr-4 text-center align-top"
                  style={{ color: ENTITY_COLORS[i % ENTITY_COLORS.length] }}
                >
                  {e.cover_url && (
                    <img src={e.cover_url} alt="" className="h-10 w-10 mx-auto rounded-lg object-cover mb-1.5" />
                  )}
                  {detailLinks[i] ? (
                    <Link
                      to={detailLinks[i]}
                      className="block truncate text-[13px] font-serif font-semibold transition-colors hover:underline"
                      title={e.name ?? undefined}
                    >
                      {e.name}
                    </Link>
                  ) : (
                    <span className="block truncate text-[13px] font-serif font-semibold" title={e.name ?? undefined}>
                      {e.name}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from(grouped.entries()).map(([group, items], gi) => (
              <Fragment key={group}>
                <tr>
                  <td
                    colSpan={n + 1}
                    className="py-1.5 pl-4 text-[10px] font-bold uppercase tracking-[1.4px] text-muted-foreground bg-muted/30 border-b border-border/30"
                  >
                    {group}
                  </td>
                </tr>
                {items.map((def) => {
                  const values = allMetrics.map((m) => m[def.key])
                  const best = bestIndex(values, def.higherIsBetter)
                  return (
                    <tr key={def.key} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                      <td className="py-2.5 pl-4 text-[13px] text-muted-foreground sticky left-0 bg-card w-[140px]">
                        {def.label}
                      </td>
                      {values.map((v, i) => {
                        const isBest = best >= 0 && i === best
                        return (
                          <td
                            key={i}
                            className="py-2.5 pr-4 text-right text-[14px] font-semibold tabular-nums"
                            style={isBest ? { color: ENTITY_COLORS[i % ENTITY_COLORS.length], backgroundColor: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}14` } : undefined}
                          >
                            {def.format(v, allMetrics[i])}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
                {gi < grouped.size - 1 && (
                  <tr><td colSpan={n + 1} className="h-1.5" /></tr>
                )}
              </Fragment>
            ))}

            {/* ── Personal Play section ── */}
            {hasPersonal && (
              <>
                <tr><td colSpan={n + 1} className="h-1.5" /></tr>
                <tr>
                  <td
                    colSpan={n + 1}
                    className="py-1.5 pl-4 text-[10px] font-bold uppercase tracking-[1.4px] text-muted-foreground bg-muted/30 border-b border-border/30"
                  >
                    个人播放
                  </td>
                </tr>
                {personalRows.map((row) => (
                  <tr key={row.label} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                    <td className="py-2.5 pl-4 text-[13px] text-muted-foreground sticky left-0 bg-card w-[140px]">
                      {row.label}
                    </td>
                    {row.values.map((v, i) => {
                      const isBest = row.best >= 0 && i === row.best
                      return (
                        <td
                          key={i}
                          className="py-2.5 pr-4 text-right text-[14px] font-semibold tabular-nums"
                          style={isBest ? { color: ENTITY_COLORS[i % ENTITY_COLORS.length], backgroundColor: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}14` } : undefined}
                        >
                          {row.fmt(v)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
                {personalResults.some((r) => r.isLoading) && (
                  <tr>
                    <td colSpan={n + 1} className="px-4 py-2 text-center text-[12px] text-muted-foreground">
                      个人数据加载中...
                    </td>
                  </tr>
                )}
              </>
            )}

            {/* ── Total Score row ── */}
            <tr><td colSpan={n + 1} className="h-1.5" /></tr>
            <tr>
              <td
                colSpan={n + 1}
                className="py-1.5 pl-4 text-[10px] font-bold uppercase tracking-[1.4px] text-muted-foreground bg-muted/30 border-b border-border/30"
              >
                总分 (胜出指标数)
              </td>
            </tr>
            <tr className="border-b border-border/40">
              <td className="py-2.5 pl-4 text-[13px] font-semibold sticky left-0 bg-card">
                胜出次数
              </td>
              {wins.map((w, i) => {
                const maxWins = Math.max(...wins)
                const isBest = maxWins > 0 && w === maxWins
                return (
                  <td
                    key={i}
                    className="py-2.5 pr-4 text-right text-[15px] font-bold tabular-nums"
                    style={isBest ? { color: ENTITY_COLORS[i % ENTITY_COLORS.length], backgroundColor: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}14` } : undefined}
                  >
                    {w}
                  </td>
                )
              })}
            </tr>
          </tbody>
        </table>
      </GlassCard>
    </div>
  )
}
