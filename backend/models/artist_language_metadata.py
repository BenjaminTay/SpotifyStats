"""Models for artist language metadata review endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LanguageClassification = Literal["single_language", "multilingual", "instrumental"]
LanguageOrigin = Literal["manual", "curated_seed", "legacy_import"]
EvidenceKind = Literal[
    "artist_profile",
    "artist_repertoire",
    "editorial_source",
    "track_credit",
    "track_language",
]
PerformerAttribution = Literal[
    "artist_vocal_confirmed",
    "artist_instrumental_confirmed",
    "track_language_only",
    "not_applicable",
]
SourceStatus = Literal["suggested", "approved", "rejected", "superseded"]
ReviewStatus = Literal["open", "approved", "rejected", "insufficient_evidence"]
ReviewAction = Literal["approve", "reject", "insufficient_evidence"]
LanguageBucketClassification = Literal[
    "single_language",
    "multilingual",
    "instrumental",
    "unknown",
]


class ArtistLanguageEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_track_id: int | None = None
    claimed_language_code: str | None = None
    claimed_language_variant: str | None = None
    evidence_kind: EvidenceKind
    performer_attribution: PerformerAttribution
    evidence_url: str
    evidence_title: str
    evidence_summary: str


class ArtistLanguageSourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: LanguageClassification
    primary_language_code: str | None = None
    language_variant: str | None = None
    raw_language: str | None = None
    evidence: list[ArtistLanguageEvidenceInput] = Field(default_factory=list)


class ArtistLanguageReviewCreateRequest(BaseModel):
    artist_id: int
    reason: str = "manual_research"


class ArtistLanguageReviewDecisionRequest(BaseModel):
    action: ReviewAction
    resolution_note: str


class ArtistLanguageBucket(BaseModel):
    key: str
    label: str
    classification: LanguageBucketClassification
    hours: float
    share_pct: float
    artist_count: int


class ArtistLanguageMissingItem(BaseModel):
    artist_id: int
    artist_name: str
    hours: float


class ArtistLanguageCoverageResponse(BaseModel):
    eligible_hours: float
    excluded_unattributed_hours: float
    classified_hours: float
    unknown_hours: float
    classified_pct: float
    unknown_pct: float
    buckets: list[ArtistLanguageBucket] = Field(default_factory=list)
    source_hours: dict[str, float] = Field(default_factory=dict)
    top_missing: list[ArtistLanguageMissingItem] = Field(default_factory=list)
    caveat: str


class ArtistLanguageEvidenceItem(BaseModel):
    evidence_id: int
    source_id: int
    local_track_id: int | None = None
    claimed_language_code: str | None = None
    claimed_language_variant: str | None = None
    evidence_kind: EvidenceKind
    performer_attribution: PerformerAttribution
    evidence_url: str
    evidence_title: str
    evidence_accessed_at: str
    evidence_summary: str
    created_at: str


class ArtistLanguageSourceItem(BaseModel):
    source_id: int
    artist_id: int
    classification: LanguageClassification
    primary_language_code: str | None = None
    language_variant: str | None = None
    raw_language: str | None = None
    origin: LanguageOrigin
    source_key: str
    status: SourceStatus
    replaces_source_id: int | None = None
    created_at: str
    updated_at: str
    evidence: list[ArtistLanguageEvidenceItem] = Field(default_factory=list)


class ArtistLanguageReviewItem(BaseModel):
    review_id: int
    artist_id: int
    artist_name: str
    suggested_source_id: int | None = None
    play_hours_snapshot: float
    reason: str
    status: ReviewStatus
    resolution_note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str
    updated_at: str
    source: ArtistLanguageSourceItem | None = None


class ArtistLanguageReviewListResponse(BaseModel):
    items: list[ArtistLanguageReviewItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


class ArtistLanguageReviewMutationResponse(BaseModel):
    review_id: int
    review_status: ReviewStatus
    source_id: int | None = None
    source_status: SourceStatus | None = None
