import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import { GlassCard } from '@/components/shared/GlassCard'
import type { VersusEntityData, EntityListItem } from '@/types/billboard'
import type { EntityStatsResponse } from '@/types/analysis'
import { METRIC_DEFS, METRIC_GROUPS, bestIndices, ENTITY_COLORS, type VersusKind, type MetricGroup } from './versusData'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileVersusScoreboard, type MobileVersusMetricGroup } from '@/features/mobile/billboard/MobileVersusScoreboard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface VersusScoreboardSectionProps {
  entities: VersusEntityData[] | null
  kind: VersusKind
  queue: EntityListItem[]
  buildDetailLink: (item: EntityListItem) => string | null
  personalStatsParams: Record<string, string | number | boolean>
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
  personalStatsParams,
}: VersusScoreboardSectionProps) {
  useChineseTextVersion()
  const isPhone = useViewportMode() === 'phone'
  // ── Personal stats (useQueries, only when versus data is ready) ──
  const personalResults = useQueries({
    queries: queue.map((q) => ({
      queryKey: queryKeys.music.entityStats(kind, personalId(kind, q), {
        ...personalStatsParams,
        ...(kind === 'album' ? { artist: q.artist_name ?? '' } : {}),
      }),
      queryFn: () => api.get<EntityStatsResponse>(
        personalPath(kind, personalId(kind, q)),
        {
          ...personalStatsParams,
          ...(kind === 'album' ? { artist: q.artist_name ?? '' } : {}),
        },
      ),
      enabled: !!personalId(kind, q),
      staleTime: 1000 * 60 * 5,
    })),
  })

  if (!entities || entities.length < 2) return null

  const n = entities.length

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
    const winners = bestIndices(values, def.higherIsBetter)
    if (winners.length === 1) wins[winners[0]]++
  }

  // ── Personal play metric definitions ──
  interface PersonalMetricRow {
    label: string
    higherIsBetter: boolean
    values: (unknown)[]
    winners: number[]
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
      const w = bestIndices(values, higherIsBetter)
      if (w.length === 1) wins[w[0]]++
      rows.push({ label, higherIsBetter, values, winners: w, fmt })
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

    // Highest play count among weeks where this entity entered the chart.
    if (chartWeekMaxes.some((v) => v != null)) {
      const w = bestIndices(chartWeekMaxes, true)
      if (w.length === 1) wins[w[0]]++
      rows.push({ label: '入榜周最高播放', higherIsBetter: true, values: [...chartWeekMaxes], winners: w, fmt: (v) => v != null ? String(v) : '—' })
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

  if (isPhone) {
    const mobileGroups: MobileVersusMetricGroup[] = Array.from(grouped.entries()).map(([group, items]) => ({
      label: group,
      metrics: items.map((def) => {
        const values = allMetrics.map((metrics) => metrics[def.key])
        return {
          label: def.label,
          description: def.description,
          values: values.map((value, index) => def.format(value, allMetrics[index])),
          winners: bestIndices(values, def.higherIsBetter),
        }
      }),
    }))
    return (
      <MobileVersusScoreboard
        entities={entities}
        detailLinks={detailLinks}
        groups={mobileGroups}
        personalMetrics={personalRows.map((row) => ({
          label: row.label,
          values: row.values.map(row.fmt),
          winners: row.winners,
        }))}
        wins={wins}
        personalLoading={personalResults.some((result) => result.isLoading)}
      />
    )
  }

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
              {entities.map((e, i) => {
                // Split "Song — Artist" into parts for two-line display
                const raw = e.name ?? ''
                const sepIdx = raw.indexOf(' — ')
                const titleName = sepIdx >= 0 ? raw.slice(0, sepIdx) : raw
                const subtitle = sepIdx >= 0 ? raw.slice(sepIdx + 3) : null
                const renderedTitleName = displayName(titleName)
                const renderedSubtitle = subtitle ? displayName(subtitle) : null

                return (
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
                        title={renderedTitleName}
                      >
                        {renderedTitleName}
                      </Link>
                    ) : (
                      <span className="block truncate text-[13px] font-serif font-semibold" title={renderedTitleName}>
                        {renderedTitleName}
                      </span>
                    )}
                    {renderedSubtitle && (
                      <span className="mt-0.5 block font-sans text-[12px] italic">
                        {renderedSubtitle}
                      </span>
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {Array.from(grouped.entries()).map(([group, items], gi) => (
              <Fragment key={group}>
                <tr>
                  <td
                    colSpan={n + 1}
                    className="py-2 pl-4 text-[11px] font-bold uppercase tracking-[1.4px] text-accent-foreground bg-accent/12 border-b border-border"
                  >
                    {group}
                  </td>
                </tr>
                {items.map((def) => {
                  const values = allMetrics.map((m) => m[def.key])
                  const winners = bestIndices(values, def.higherIsBetter)
                  return (
                    <tr key={def.key} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                      <td className="py-2.5 pl-4 text-[13px] text-muted-foreground sticky left-0 bg-card w-[140px]">
                        <span title={def.description}>{def.label}</span>
                      </td>
                      {values.map((v, i) => {
                        const isBest = winners.includes(i)
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
                    className="py-2 pl-4 text-[11px] font-bold uppercase tracking-[1.4px] text-accent-foreground bg-accent/12 border-b border-border"
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
                      const isBest = row.winners.includes(i)
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

            {/* ── Total Score row ──*/}
            <tr><td colSpan={n + 1} className="h-1.5" /></tr>
            <tr>
              <td
                colSpan={n + 1}
                className="py-2 pl-4 text-[11px] font-bold uppercase tracking-[1.4px] text-accent-foreground bg-accent/12 border-b border-border"
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
