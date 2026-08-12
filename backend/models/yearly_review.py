"""Typed response contract for the deterministic Yearly Review V2 report."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

YearlyReportStatus = Literal[
    "complete",
    "year_to_date",
    "observed_range",
    "insufficient",
    "empty",
]
ImportCoverageStatus = Literal["verified_complete", "verified_partial", "unknown"]
InternalGapStatus = Literal["verified_complete", "verified_gaps", "unknown"]
TasteCoverageLevel = Literal["core", "secondary", "insufficient", "unavailable"]
EvidenceGrade = Literal["A", "B", "C"]
EvidenceDisplayStatus = Literal["sufficient", "limited", "unavailable"]
HighlightCandidateSource = Literal["playback_records", "billboard_records"]
TasteComparisonMode = Literal["half_years", "completed_quarters", "distribution_only"]
TasteComparisonStatus = Literal["available", "insufficient_completed_periods"]


class YearlyReviewFilterContext(BaseModel):
    """Every semantic input and revision shared by all report builders."""

    min_ms: int = Field(ge=0)
    music_only: bool
    merge_enabled: bool
    dynamic_threshold: bool
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(ge=1, le=3)
    include_compilations: bool
    bb_top_n: int = Field(ge=5, le=100)
    bb_album_top_n: int = Field(ge=5, le=100)
    bb_artist_top_n: int = Field(ge=5, le=100)
    bb_week_start_dow: int = Field(ge=0, le=6)
    bb_week_start_hour: int = Field(ge=0, le=23)
    display_taxonomy_version: str
    artist_metadata_revision: str
    artist_identity_revision: int = Field(ge=0)
    track_credit_revision: int = Field(ge=0)
    track_group_revision: str
    album_project_revision: str
    filter_fingerprint: str


class YearlyPlayCoverage(BaseModel):
    status: YearlyReportStatus
    observed_start: str | None = None
    observed_end: str | None = None
    active_days: int = Field(default=0, ge=0)
    natural_days_span: int = Field(default=0, ge=0)
    import_coverage_status: ImportCoverageStatus = "unknown"
    internal_gap_status: InternalGapStatus = "unknown"
    is_calendar_start_observed: bool = False
    is_calendar_end_observed: bool = False
    latest_data_date: str | None = None
    reason: str | None = None


class YearlyBillboardCoverage(BaseModel):
    status: YearlyReportStatus
    source_status: str
    observed_weeks: int = Field(default=0, ge=0)
    expected_weeks: int = Field(default=0, ge=0)
    has_internal_gaps: bool | None = None
    first_billboard_week: str | None = None
    last_billboard_week: str | None = None
    reason: str | None = None


class YearlyComparisonCoverage(BaseModel):
    baseline_year: int | None = None
    aligned_start: str | None = None
    aligned_end: str | None = None
    comparable: bool = False
    reason: str | None = None


class YearlyTasteAxisCoverage(BaseModel):
    known_pct: float = Field(default=0, ge=0, le=100)
    unknown_hours: float = Field(default=0, ge=0)
    level: TasteCoverageLevel = "unavailable"
    conclusion_allowed: bool = False
    caveat_required: bool = True


class YearlyTasteCoverage(BaseModel):
    style: YearlyTasteAxisCoverage = Field(default_factory=YearlyTasteAxisCoverage)
    scene: YearlyTasteAxisCoverage = Field(default_factory=YearlyTasteAxisCoverage)
    language: YearlyTasteAxisCoverage = Field(default_factory=YearlyTasteAxisCoverage)
    release_era: YearlyTasteAxisCoverage = Field(default_factory=YearlyTasteAxisCoverage)


class YearlyReviewCoverage(BaseModel):
    status: YearlyReportStatus
    play: YearlyPlayCoverage
    billboard: YearlyBillboardCoverage
    comparison: YearlyComparisonCoverage
    taste: YearlyTasteCoverage


class YearlyEntityRef(BaseModel):
    entity_type: Literal["track", "album", "artist"]
    entity_id: str | int | None = None
    name: str
    artist_name: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None


class YearlyMetric(BaseModel):
    key: str
    label: str
    value: int | float | str
    unit: str | None = None
    comparison_value: int | float | None = None
    comparison_label: str | None = None


class YearlyReportPassport(BaseModel):
    year: int
    label: str
    observed_start: str | None = None
    observed_end: str | None = None
    status: YearlyReportStatus
    metrics: list[YearlyMetric] = Field(default_factory=list)


class YearlyHeadline(BaseModel):
    headline_id: str
    title: str
    statement: str
    evidence_grade: EvidenceGrade
    evidence_status: EvidenceDisplayStatus = "sufficient"
    primary_metric: YearlyMetric | None = None
    entity_refs: list[YearlyEntityRef] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class YearlyHonorItem(BaseModel):
    honor_id: str
    title: str
    entity: YearlyEntityRef | None = None
    metrics: list[YearlyMetric] = Field(default_factory=list)
    evidence_grade: EvidenceGrade = "A"


class YearlyDivergenceStory(BaseModel):
    entity: YearlyEntityRef
    play_rank: int = Field(ge=1)
    billboard_year_end_rank: int = Field(ge=1)
    rank_gap: int
    interpretation: Literal["season_more_persistent", "volume_more_concentrated"]
    evidence_grade: EvidenceGrade = "B"


class YearlyHonorsChapter(BaseModel):
    play_leaders: dict[str, YearlyHonorItem] = Field(default_factory=dict)
    billboard_leaders: dict[str, YearlyHonorItem] = Field(default_factory=dict)
    divergence_stories: list[YearlyDivergenceStory] = Field(default_factory=list)
    annual_honors: list[YearlyHonorItem] = Field(default_factory=list)


class YearlySeasonStage(BaseModel):
    stage_id: str
    label: str
    start_month: int = Field(ge=1, le=12)
    end_month: int = Field(ge=1, le=12)
    entity_refs: list[YearlyEntityRef] = Field(default_factory=list)
    evidence: list[YearlyMetric] = Field(default_factory=list)


class YearlyTurningPoint(BaseModel):
    point_id: str
    month: int = Field(ge=1, le=12)
    date: str | None = None
    event_type: str
    title: str
    statement: str
    evidence_grade: EvidenceGrade
    entity_refs: list[YearlyEntityRef] = Field(default_factory=list)
    metrics: list[YearlyMetric] = Field(default_factory=list)


class YearlyMonthSummary(BaseModel):
    month: int = Field(ge=1, le=12)
    plays: int = Field(default=0, ge=0)
    hours: float = Field(default=0, ge=0)
    active_days: int = Field(default=0, ge=0)
    leaders: dict[str, YearlyEntityRef] = Field(default_factory=dict)
    comparisons: list[YearlyMetric] = Field(default_factory=list)
    stage_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)


class YearlySeasonChapter(BaseModel):
    policy_version: str = "season_stage_v1"
    stage_status: Literal["available", "no_stable_phase", "insufficient"] = "insufficient"
    stage_note: str | None = None
    stages: list[YearlySeasonStage] = Field(default_factory=list)
    turning_points: list[YearlyTurningPoint] = Field(default_factory=list)
    months: list[YearlyMonthSummary] = Field(default_factory=list)


class YearlyRelationshipStory(BaseModel):
    story_id: str
    relationship_type: str
    title: str
    statement: str
    entity: YearlyEntityRef
    evidence_grade: Literal["C"] = "C"
    evidence_status: EvidenceDisplayStatus = "sufficient"
    metrics: list[YearlyMetric] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class YearlyListeningLifeChapter(BaseModel):
    metrics: list[YearlyMetric] = Field(default_factory=list)
    observations: list[YearlyHeadline] = Field(default_factory=list)


class YearlyFeaturedRecord(BaseModel):
    record_id: str
    category: str
    fact_type: str
    title: str
    statement: str
    evidence_grade: EvidenceGrade
    entity_refs: list[YearlyEntityRef] = Field(default_factory=list)
    metrics: list[YearlyMetric] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    deep_link: str | None = None


class YearlyHighlightCandidate(BaseModel):
    """Internal normalized record fact consumed by the M3 highlight selector.

    The adapter keeps the original record values for deterministic selection,
    while the public report only receives the small selected subset as
    ``YearlyFeaturedRecord`` items.
    """

    candidate_id: str
    source: HighlightCandidateSource
    source_family: str
    record_key: str
    category: str
    fact_type: str
    entity_refs: list[YearlyEntityRef] = Field(default_factory=list)
    primary_metric: YearlyMetric | None = None
    secondary_metrics: list[YearlyMetric] = Field(default_factory=list)
    period: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    raw_values: dict[str, Any] = Field(default_factory=dict)
    eligible: bool = True
    eligibility_reasons: list[str] = Field(default_factory=list)
    evidence_grade: EvidenceGrade = "A"
    coverage_status: EvidenceDisplayStatus = "sufficient"
    noteworthiness_components: dict[str, float] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    deep_link: str | None = None


class YearlyRecordsChapter(BaseModel):
    policy_version: str = "highlight_policy_v2"
    featured: list[YearlyFeaturedRecord] = Field(default_factory=list)
    catalog_counts: dict[str, int] = Field(default_factory=dict)


class YearlyTasteComparison(BaseModel):
    mode: TasteComparisonMode = "distribution_only"
    status: TasteComparisonStatus = "insufficient_completed_periods"
    from_slice_key: str | None = None
    to_slice_key: str | None = None
    from_label: str | None = None
    to_label: str | None = None
    from_start: str | None = None
    from_end: str | None = None
    to_start: str | None = None
    to_end: str | None = None


class YearlyTasteMigrationChapter(BaseModel):
    comparison: YearlyTasteComparison = Field(default_factory=YearlyTasteComparison)
    observations: list[YearlyHeadline] = Field(default_factory=list)
    distributions: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    changes: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    coverage_notes: dict[str, str] = Field(default_factory=dict)


class YearlyEpilogue(BaseModel):
    conclusions: list[YearlyHeadline] = Field(default_factory=list)
    new_history_tops: list[YearlyEntityRef] = Field(default_factory=list)
    next_year_carryovers: list[YearlyEntityRef] = Field(default_factory=list)


class YearlyAppendix(BaseModel):
    play_charts: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    billboard_charts: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    monthly_champions: list[dict[str, Any]] = Field(default_factory=list)
    record_catalog_counts: dict[str, int] = Field(default_factory=dict)


class YearlyMethodology(BaseModel):
    content_version: str = "yearly_review_v2_12"
    relationship_policy_version: str = "relationship_policy_v2"
    highlight_policy_version: str = "highlight_policy_v2"
    season_stage_policy_version: str = "season_stage_v1"
    metric_definitions: dict[str, str] = Field(default_factory=dict)
    comparison_periods: dict[str, str | None] = Field(default_factory=dict)
    entity_grains: dict[str, str] = Field(default_factory=dict)
    coverage_caveats: list[str] = Field(default_factory=list)
    internal_versions: dict[str, str] = Field(default_factory=dict)
    internal_diagnostics: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class YearlyReviewResponse(BaseModel):
    schema_version: Literal["yearly_review_v2"] = "yearly_review_v2"
    year: int = Field(ge=2000)
    status: YearlyReportStatus
    filter_context: YearlyReviewFilterContext
    coverage: YearlyReviewCoverage
    passport: YearlyReportPassport | None = None
    headlines: list[YearlyHeadline] = Field(default_factory=list)
    honors: YearlyHonorsChapter = Field(default_factory=YearlyHonorsChapter)
    season: YearlySeasonChapter = Field(default_factory=YearlySeasonChapter)
    relationships: list[YearlyRelationshipStory] = Field(default_factory=list)
    listening_life: YearlyListeningLifeChapter = Field(default_factory=YearlyListeningLifeChapter)
    records: YearlyRecordsChapter = Field(default_factory=YearlyRecordsChapter)
    taste_migration: YearlyTasteMigrationChapter = Field(
        default_factory=YearlyTasteMigrationChapter
    )
    epilogue: YearlyEpilogue = Field(default_factory=YearlyEpilogue)
    appendix: YearlyAppendix = Field(default_factory=YearlyAppendix)
    methodology: YearlyMethodology = Field(default_factory=YearlyMethodology)


class YearlyReviewAvailableYearsResponse(BaseModel):
    years: list[int] = Field(default_factory=list)
    latest_year: int | None = None


YearlyReviewGenerationState = Literal["queued", "running", "ready", "failed"]


class YearlyReviewGenerationTask(BaseModel):
    year: int = Field(ge=2000, le=2100)
    state: YearlyReviewGenerationState
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class YearlyReviewPrewarmRequest(BaseModel):
    years: list[Annotated[int, Field(ge=2000, le=2100)]] = Field(min_length=1, max_length=20)
    foreground_year: int | None = Field(default=None, ge=2000, le=2100)


class YearlyReviewGenerationResponse(BaseModel):
    protocol_version: Literal["yearly_review_generation_v1"] = "yearly_review_generation_v1"
    tasks: list[YearlyReviewGenerationTask] = Field(default_factory=list)


class YearlyReviewRecordsPage(BaseModel):
    content_version: str = "yearly_review_v2_12"
    year: int = Field(ge=2000)
    filter_fingerprint: str
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    items: list[YearlyFeaturedRecord] = Field(default_factory=list)
    catalog_counts: dict[str, int] = Field(default_factory=dict)
