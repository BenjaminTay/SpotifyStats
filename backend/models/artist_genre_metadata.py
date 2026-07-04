"""Models for artist genre metadata review endpoints."""

from __future__ import annotations

from typing import Any

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


class ArtistGenreSourceMixItem(BaseModel):
    source: str
    hours: float
    share_pct: float


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
    source_mix: list[ArtistGenreSourceMixItem] = Field(default_factory=list)
    top_artists: list[ArtistGenreTopArtistItem] = Field(default_factory=list)
    dominance_warning: str | None = None
    risk_flags: list[ArtistGenreRiskFlag] = Field(default_factory=list)


class ArtistGenreAxisSummaryItem(BaseModel):
    axis: str
    label: str
    hours: float
    share_pct: float
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


class ArtistGenreReviewListResponse(BaseModel):
    items: list[ArtistGenreReviewItem]


class ArtistGenreReviewDecisionResponse(BaseModel):
    review_id: int
    artist_name: str
    decision: str
    source_id: int
    source_status: str
    review_status: str
