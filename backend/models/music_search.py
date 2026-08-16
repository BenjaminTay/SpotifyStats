"""Response models for local music entity search."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.domains.music_search.contracts import parse_music_search_entity_key

MusicSearchKind = Literal["track", "album", "artist"]
MusicSearchSnapshotStatus = Literal["ready", "warming", "unavailable", "stale", "failed"]
MusicSearchMatchField = Literal["label", "artist", "album", "alias"]
MusicSearchMatchQuality = Literal["exact", "prefix", "token", "substring", "fuzzy"]
MusicSearchMatchType = Literal["original", "simplified", "traditional", "fuzzy"]


class MusicSearchChartSummary(BaseModel):
    peak_position: int | None = None
    peak_weeks: int | None = None
    weeks_on_chart: int | None = None
    weeks_at_no1: int | None = None
    power_score: int | None = None
    power_rank: int | None = None
    first_week: str | None = None
    latest_week: str | None = None
    first_peak_week: str | None = None


class MusicSearchResult(BaseModel):
    kind: MusicSearchKind
    label: str
    subtitle: str | None = None
    href: str
    play_events: int = 0
    total_ms: int = 0
    track_id: int | None = None
    artist_id: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None = None
    chart: MusicSearchChartSummary | None = None


class MusicSearchResponse(BaseModel):
    query: str
    limit_per_type: int = Field(ge=1, le=10)
    total: int
    tracks: list[MusicSearchResult] = Field(default_factory=list)
    albums: list[MusicSearchResult] = Field(default_factory=list)
    artists: list[MusicSearchResult] = Field(default_factory=list)


class MusicSearchKindTotals(BaseModel):
    track: int = Field(default=0, ge=0)
    album: int = Field(default=0, ge=0)
    artist: int = Field(default=0, ge=0)


class MusicSearchCandidateResult(BaseModel):
    entity_key: str
    kind: MusicSearchKind
    label: str
    subtitle: str | None = None
    href: str
    track_id: int | None = None
    artist_id: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None = None
    match_field: MusicSearchMatchField
    match_quality: MusicSearchMatchQuality
    match_type: MusicSearchMatchType = "original"

    @model_validator(mode="after")
    def validate_entity_key_kind(self):
        parsed = parse_music_search_entity_key(self.entity_key)
        if parsed.kind == "album_project":
            expected_kind = "album"
        else:
            expected_kind = parsed.kind
        if expected_kind != self.kind:
            raise ValueError("Music-search entity key kind does not match result kind")
        return self


class MusicSearchCandidateResponse(BaseModel):
    response_version: Literal["music_search_v2"] = "music_search_v2"
    query: str
    normalized_query: str
    snapshot_status: MusicSearchSnapshotStatus
    filter_fingerprint: str | None = None
    candidate_index_version: str | None = None
    kind: MusicSearchKind | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=5, ge=1, le=100)
    total: int = Field(default=0, ge=0)
    total_by_kind: MusicSearchKindTotals = Field(default_factory=MusicSearchKindTotals)
    tracks: list[MusicSearchCandidateResult] = Field(default_factory=list)
    albums: list[MusicSearchCandidateResult] = Field(default_factory=list)
    artists: list[MusicSearchCandidateResult] = Field(default_factory=list)


class MusicSearchContextItem(BaseModel):
    play_events: int = Field(ge=0)
    total_ms: int = Field(ge=0)
    chart: MusicSearchChartSummary | None = None


class MusicSearchContextResponse(BaseModel):
    response_version: Literal["music_search_context_v1"] = "music_search_context_v1"
    snapshot_status: MusicSearchSnapshotStatus
    filter_fingerprint: str | None = None
    items: dict[str, MusicSearchContextItem] = Field(default_factory=dict)

    @field_validator("items")
    @classmethod
    def validate_item_keys(
        cls,
        value: dict[str, MusicSearchContextItem],
    ) -> dict[str, MusicSearchContextItem]:
        for entity_key in value:
            parse_music_search_entity_key(entity_key)
        return value
