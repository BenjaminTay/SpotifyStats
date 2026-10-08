import type { EntityListItem, VersusEntityData } from '@/types/billboard'
import type { VersusPersonalMetrics } from '@/types/versus-personal'
import { METRIC_DEFS, METRIC_GROUPS, bestIndices, type VersusKind } from './versusData'
import { personalRequestedKey, type VersusPersonalState } from './useVersusPersonal'

export interface ScoreboardRow {
  label: string
  description?: string
  values: string[]
  winners: number[]
  complete: boolean
}
export interface ScoreboardGroup { label: string; metrics: ScoreboardRow[] }

export function buildScoreboard(kind: VersusKind, queue: EntityListItem[], charts: VersusEntityData[] | null, personal: VersusPersonalState, chartUnavailable = false) {
  const entities = queue.map((item, index) => charts?.[index] ?? {
    name: item.display, cover_url: item.cover_url ?? null, popularity: null, metrics: null, rank_history: null,
  })
  const allMetrics = entities.map((entity) => ({ ...entity.metrics, ...(entity.popularity != null ? { popularity: entity.popularity } : {}) }))
  const wins = queue.map(() => 0)
  const scoredRows: ScoreboardRow[] = []
  function row(label: string, values: unknown[], higher: boolean, format: (value: unknown, index: number) => string, description?: string): ScoreboardRow {
    const complete = values.every((value) => value != null && typeof value === 'number' && Number.isFinite(value))
    const winners = complete ? bestIndices(values, higher) : []
    if (winners.length === 1) wins[winners[0]]++
    const result = { label, values: values.map(format), winners, description, complete }
    scoredRows.push(result)
    return result
  }
  const chartDefinitions = METRIC_DEFS.filter((def) => !def.only || (Array.isArray(def.only) ? def.only.includes(kind) : def.only === kind))
  const groups: ScoreboardGroup[] = METRIC_GROUPS.map((group) => ({
    label: group,
    metrics: chartDefinitions.filter((def) => def.group === group).map((def) => row(
      def.label, allMetrics.map((metrics) => metrics[def.key as keyof typeof metrics]), def.higherIsBetter,
      (value, index) => charts ? def.format(value, allMetrics[index]) : chartUnavailable ? '暂不可用' : '加载中…', def.description,
    )),
  })).filter((group) => group.metrics.length > 0)
  const statsEntities = queue.map((item) => personal.statsData?.entities.find((entity) => entity.requested_key === personalRequestedKey(kind, item)))
  const rankEntities = queue.map((item) => personal.ranksData?.entities.find((entity) => entity.requested_key === personalRequestedKey(kind, item)))
  function stateText(group: 'stats' | 'ranks', index: number) {
    const query = personal[group]
    if (query.isError) return '暂不可用'
    if (group === 'ranks' && personal.mismatched) return query.isFetching || personal.stats.isFetching ? '更新中…' : '待更新'
    if (!(group === 'stats' ? personal.statsData : personal.ranksData)) return '加载中…'
    if ((group === 'stats' ? statsEntities : rankEntities)[index]?.status === 'unavailable') return '暂不可用'
    return '—'
  }
  const personalRows: ScoreboardRow[] = []
  function statsRow(label: string, metric: keyof VersusPersonalMetrics, digits?: number) {
    const values = statsEntities.map((entity) => entity?.status !== 'unavailable' ? entity?.metrics?.[metric] : null)
    personalRows.push(row(label, values, true, (value, index) => value == null ? stateText('stats', index) : digits == null ? String(value) : Number(value).toFixed(digits)))
  }
  statsRow('个人总播放', 'total_plays')
  statsRow('总时长 (小时)', 'total_hours', 1)
  statsRow('日均播放', 'avg_daily_plays', 1)
  statsRow('日均时长 (小时)', 'avg_daily_hours', 2)
  statsRow('单天最多播放', 'max_daily_plays')
  const weekMax = entities.map((entity) => entity.rank_history?.length ? Math.max(...entity.rank_history.map((point) => point.play_count)) : null)
  personalRows.push(row('入榜周最高播放', weekMax, true, (value) => value == null ? charts ? '—' : chartUnavailable ? '暂不可用' : '加载中…' : String(value)))
  statsRow('活跃天数', 'active_days')
  for (const [label, period] of [['全时段排名', 'lifetime'], ['近6个月排名', 'last_6_months'], ['近4周排名', 'last_4_weeks']] as const) {
    const values = rankEntities.map((entity) => entity?.status !== 'unavailable' ? entity?.ranks?.[period] : null)
    personalRows.push(row(label, values, false, (value, index) => value == null ? stateText('ranks', index) : `#${value}`))
  }
  return { entities, groups, personalRows, wins, scoreComplete: !!charts && scoredRows.every((item) => item.complete) }
}
