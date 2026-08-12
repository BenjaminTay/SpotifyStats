export type YearlyReviewStatus = 'complete' | 'year_to_date' | 'observed_range' | 'insufficient' | 'empty'
export type EvidenceGrade = 'A' | 'B' | 'C'
export type EvidenceStatus = 'sufficient' | 'limited' | 'unavailable'

export interface YearlyReviewFilterContext {
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  dynamic_threshold: boolean
  max_merge_gap_minutes: number | null
  merge_level: number
  include_compilations: boolean
  bb_top_n: number
  bb_album_top_n: number
  bb_artist_top_n: number
  bb_week_start_dow: number
  bb_week_start_hour: number
  display_taxonomy_version: string
  artist_metadata_revision: string
  artist_identity_revision: number
  track_credit_revision: number
  track_group_revision: string
  album_project_revision: string
  filter_fingerprint: string
}

export interface YearlyMetric {
  key: string
  label: string
  value: number | string
  unit: string | null
  comparison_value: number | null
  comparison_label: string | null
}

export interface YearlyEntityRef {
  entity_type: 'track' | 'album' | 'artist'
  entity_id: number | string | null
  name: string
  artist_name: string | null
  cover_url: string | null
  deep_link: string | null
}

export interface YearlyHeadline {
  headline_id: string
  title: string
  statement: string
  evidence_grade: EvidenceGrade
  evidence_status: EvidenceStatus
  primary_metric: YearlyMetric | null
  entity_refs: YearlyEntityRef[]
  source_refs: string[]
}

export interface YearlyTasteAxisCoverage {
  known_pct: number
  unknown_hours: number
  level: 'core' | 'secondary' | 'insufficient' | 'unavailable'
  conclusion_allowed: boolean
  caveat_required: boolean
}

export interface YearlyReviewCoverage {
  status: YearlyReviewStatus
  play: {
    status: YearlyReviewStatus
    observed_start: string | null
    observed_end: string | null
    active_days: number
    natural_days_span: number
    import_coverage_status: string
    internal_gap_status: string
    is_calendar_start_observed: boolean
    is_calendar_end_observed: boolean
    latest_data_date: string | null
    reason: string | null
  }
  billboard: {
    status: YearlyReviewStatus
    source_status: string
    observed_weeks: number
    expected_weeks: number
    has_internal_gaps: boolean | null
    first_billboard_week: string | null
    last_billboard_week: string | null
    reason: string | null
  }
  comparison: {
    baseline_year: number | null
    aligned_start: string | null
    aligned_end: string | null
    comparable: boolean
    reason: string | null
  }
  taste: Record<'style' | 'scene' | 'language' | 'release_era', YearlyTasteAxisCoverage>
}

export interface YearlyHonorItem {
  honor_id: string
  title: string
  entity: YearlyEntityRef | null
  metrics: YearlyMetric[]
  evidence_grade: EvidenceGrade
}

export interface YearlyDivergenceStory {
  entity: YearlyEntityRef
  play_rank: number
  billboard_year_end_rank: number
  rank_gap: number
  interpretation: 'season_more_persistent' | 'volume_more_concentrated'
  evidence_grade: EvidenceGrade
}

export interface YearlyFeaturedRecord {
  record_id: string
  category: string
  fact_type: string
  title: string
  statement: string
  evidence_grade: EvidenceGrade
  entity_refs: YearlyEntityRef[]
  metrics: YearlyMetric[]
  source_refs: string[]
  deep_link: string | null
}

export interface YearlyMonthSummary {
  month: number
  plays: number
  hours: number
  active_days: number
  leaders: Record<string, YearlyEntityRef>
  comparisons: YearlyMetric[]
  stage_id: string | null
  event_ids: string[]
}

export interface YearlyReviewResponse {
  schema_version: 'yearly_review_v2'
  year: number
  status: YearlyReviewStatus
  filter_context: YearlyReviewFilterContext
  coverage: YearlyReviewCoverage
  passport: {
    year: number
    label: string
    observed_start: string | null
    observed_end: string | null
    status: YearlyReviewStatus
    metrics: YearlyMetric[]
  } | null
  headlines: YearlyHeadline[]
  honors: {
    play_leaders: Record<string, YearlyHonorItem>
    billboard_leaders: Record<string, YearlyHonorItem>
    divergence_stories: YearlyDivergenceStory[]
    annual_honors: YearlyHonorItem[]
  }
  season: {
    policy_version: string
    stage_status: 'available' | 'no_stable_phase' | 'insufficient'
    stage_note: string | null
    stages: Array<{
      stage_id: string
      label: string
      start_month: number
      end_month: number
      entity_refs: YearlyEntityRef[]
      evidence: YearlyMetric[]
    }>
    turning_points: Array<{
      point_id: string
      month: number
      date: string | null
      event_type: string
      title: string
      statement: string
      evidence_grade: EvidenceGrade
      entity_refs: YearlyEntityRef[]
      metrics: YearlyMetric[]
    }>
    months: YearlyMonthSummary[]
  }
  relationships: Array<{
    story_id: string
    relationship_type: string
    title: string
    statement: string
    entity: YearlyEntityRef
    evidence_grade: 'C'
    evidence_status: EvidenceStatus
    metrics: YearlyMetric[]
    source_refs: string[]
  }>
  listening_life: {
    metrics: YearlyMetric[]
    observations: YearlyHeadline[]
  }
  records: {
    policy_version: string
    featured: YearlyFeaturedRecord[]
    catalog_counts: Record<string, number>
  }
  taste_migration: {
    comparison: {
      mode: 'half_years' | 'completed_quarters' | 'distribution_only'
      status: 'available' | 'insufficient_completed_periods'
      from_slice_key: string | null
      to_slice_key: string | null
      from_label: string | null
      to_label: string | null
      from_start: string | null
      from_end: string | null
      to_start: string | null
      to_end: string | null
    }
    observations: YearlyHeadline[]
    distributions: Record<string, Array<Record<string, unknown>>>
    changes: Record<string, Array<Record<string, unknown>>>
    coverage_notes: Record<string, string>
  }
  epilogue: {
    conclusions: YearlyHeadline[]
    new_history_tops: YearlyEntityRef[]
    next_year_carryovers: YearlyEntityRef[]
  }
  appendix: {
    play_charts: Record<string, Array<Record<string, unknown>>>
    billboard_charts: Record<string, Array<Record<string, unknown>>>
    monthly_champions: Array<Record<string, unknown>>
    record_catalog_counts: Record<string, number>
  }
  methodology: {
    content_version: string
    relationship_policy_version: string
    highlight_policy_version: string
    season_stage_policy_version: string
    metric_definitions: Record<string, string>
    comparison_periods: Record<string, string | null>
    entity_grains: Record<string, string>
    coverage_caveats: string[]
    internal_versions: Record<string, string>
    internal_diagnostics: string[]
    notes: string[]
    limitations: string[]
  }
}

export interface YearlyReviewAvailableYearsResponse {
  years: number[]
  latest_year: number | null
}

export interface YearlyReviewRecordsPage {
  content_version: string
  year: number
  filter_fingerprint: string
  page: number
  page_size: number
  total: number
  total_pages: number
  items: YearlyFeaturedRecord[]
  catalog_counts: Record<string, number>
}
