/** Bounded read-only comparison contracts; no detail response fields. */
export interface VersusPersonalContext {
  filter_fingerprint: string
  source_revision: string
  statistics_contract_version: string
}
export interface VersusPersonalPeriod {
  period: string
  label: string
  start_date: string | null
  end_date: string | null
}
export interface VersusPersonalEntity {
  requested_key: string
  entity_key: string | null
  found: boolean
  status: 'found' | 'empty' | 'unavailable'
}
export interface VersusPersonalMetrics {
  total_plays: number
  total_hours: number
  active_days: number
  avg_daily_plays: number
  avg_daily_hours: number
  max_daily_plays: number | null
}
export interface VersusPersonalStats extends VersusPersonalContext {
  period: VersusPersonalPeriod
  entities: (VersusPersonalEntity & { metrics: VersusPersonalMetrics | null })[]
}
export interface VersusRankPublication {
  status: 'ready'
  freshness: 'current'
  source_revision: string
  target_revision: string
  builder_version: string
  request_key: string
}
export interface VersusPersonalRanks extends VersusPersonalContext {
  snapshot: VersusRankPublication
  periods: Record<'lifetime' | 'last_6_months' | 'last_4_weeks', VersusPersonalPeriod>
  entities: (VersusPersonalEntity & { ranks: Record<'lifetime' | 'last_6_months' | 'last_4_weeks', number | null> | null })[]
}
