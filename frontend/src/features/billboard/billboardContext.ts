import type { AnalysisFilters } from '@/types/analysis'

export type BillboardContextParams = Record<string, string | number | boolean>

/** A stable, complete filter fingerprint shared by versus pickers and details. */
export function buildBillboardContextParams(filters: AnalysisFilters): BillboardContextParams {
  const params: BillboardContextParams = {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
    merge_level: filters.merge_level,
    include_compilations: filters.include_compilations,
    bb_top_n: filters.bb_top_n ?? 30,
    bb_album_top_n: filters.bb_album_top_n ?? 20,
    bb_artist_top_n: filters.bb_artist_top_n ?? 20,
    bb_week_start_dow: filters.bb_week_start_dow ?? 4,
    bb_week_start_hour: filters.bb_week_start_hour ?? 0,
  }
  if (filters.max_merge_gap_minutes != null) {
    params.max_merge_gap_minutes = filters.max_merge_gap_minutes
  }
  return params
}

/** Personal stats use the same effective-play settings but have no Billboard Top-N knobs. */
export function buildPersonalStatsParams(filters: AnalysisFilters): BillboardContextParams {
  const params: BillboardContextParams = {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
    merge_level: filters.merge_level,
    include_compilations: filters.include_compilations,
  }
  if (filters.max_merge_gap_minutes != null) {
    params.max_merge_gap_minutes = filters.max_merge_gap_minutes
  }
  return params
}
