"""Models for artist genre metadata review endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtistGenreCoverageResponse(BaseModel):
    known_hours: float
    unknown_hours: float
    known_pct: float
    unknown_pct: float
    source_hours: dict[str, float]
    top_missing: list[dict[str, Any]]
    artist_count: int
    total_hours: float
    excluded_unattributed_hours: float = 0.0


class ArtistGenreAxisGapItem(BaseModel):
    artist_name: str
    hours: float
    axis: str
    raw_genres: list[str] = Field(default_factory=list)
    raw_source: str
    resolved_axes: dict[str, list[str]] = Field(default_factory=dict)
    review_id: int | None = None
    review_status: str | None = None
    pre_review_recommendation: str | None = None


class ArtistGenreAxisGapResponse(BaseModel):
    axis: str
    total: int
    unknown_hours: float
    items: list[ArtistGenreAxisGapItem] = Field(default_factory=list)


class ArtistGenreSourceMixItem(BaseModel):
    source: str
    hours: float
    share_pct: float
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_pct: float = Field(ge=0.0, le=100.0)


class ArtistGenreRiskFlag(BaseModel):
    code: str
    severity: str
    message: str


class ArtistGenreTopArtistItem(BaseModel):
    artist_name: str
    hours: float
    share_pct: float
    source: str
    raw_genres: list[str]


class ArtistGenreCanonicalItem(BaseModel):
    name: str
    axis: str = "style"
    label: str | None = None
    interpretation: str | None = None
    confidence_tier: str = "medium"
    hours: float
    share_pct: float
    overall_share_pct: float
    source_mix: list[ArtistGenreSourceMixItem] = Field(default_factory=list)
    top_artists: list[ArtistGenreTopArtistItem] = Field(default_factory=list)
    dominance_warning: str | None = None
    risk_flags: list[ArtistGenreRiskFlag] = Field(default_factory=list)


class ArtistGenreAxisSummaryItem(BaseModel):
    axis: str
    label: str
    hours: float
    share_pct: float
    coverage_pct: float
    unknown_hours: float
    unknown_pct: float
    canonical_count: int
    interpretation: str


class ArtistGenreRawMappingItem(BaseModel):
    raw_genre: str
    canonical_genres: list[str]
    hours: float
    artist_count: int
    sources: list[str] = Field(default_factory=list)


class ArtistGenrePassthroughItem(BaseModel):
    raw_genre: str
    hours: float


class ArtistGenreTaxonomyResponse(BaseModel):
    raw_genre_count: int
    canonical_genre_count: int
    noncanonical_passthrough_count: int
    unknown_hours: float
    axis_summary: list[ArtistGenreAxisSummaryItem]
    top_canonical_genres: list[ArtistGenreCanonicalItem]
    top_raw_genres: list[ArtistGenreRawMappingItem]
    mapping_examples: list[ArtistGenreRawMappingItem]
    noncanonical_passthrough: list[ArtistGenrePassthroughItem]
    caveat: str


class ArtistGenreReviewItem(BaseModel):
    review_id: int
    artist_name: str
    play_hours: float
    reason: str
    source_id: int
    source: str
    source_key: str
    source_status: str
    genres: list[str]
    primary_genre: str | None = None
    language: str | None = None
    region: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_summary: str | None = None
    evidence_url: str | None = None
    review_status: str
    pre_review_recommendation: str | None = None
    pre_review_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    pre_review_note: str | None = None
    pre_reviewed_by: str | None = None
    pre_reviewed_at: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    resolution_note: str | None = None
    created_at: str
    updated_at: str


class ArtistGenreReviewListResponse(BaseModel):
    items: list[ArtistGenreReviewItem]
    total: int = 0


class ArtistGenreEvidenceUpdateRequest(BaseModel):
    evidence_url: str = Field(min_length=9)
    evidence_summary: str = Field(min_length=1)


class ArtistGenreReviewDecisionRequest(BaseModel):
    resolution_note: str = Field(min_length=1, max_length=500)


class MetadataPreReviewRequest(BaseModel):
    recommendation: Literal[
        "recommend_approve",
        "manual_review",
        "insufficient_evidence",
        "recommend_reject",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    note: str = Field(min_length=1, max_length=1000)


class ArtistGenreReviewDecisionResponse(BaseModel):
    review_id: int
    artist_name: str
    decision: str
    source_id: int
    source_status: str
    review_status: str
