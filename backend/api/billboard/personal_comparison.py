"""Bounded read-only personal metrics and published ranks for comparisons."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Annotated, Literal, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from backend.dependencies import MergeConfig, PlayFilters, get_conn
from backend.domains.music_search.timing import MusicSearchTiming
from backend.models.snapshot import SnapshotUnavailableResponse
from backend.services.versus_personal_stats_service import build_personal_stats
from backend.services.versus_rank_context_service import read_personal_ranks

router = APIRouter()
Kind = Literal["track", "album", "artist"]
EntityStatus = Literal["found", "empty", "unavailable"]
Name = Annotated[str, Field(min_length=1, max_length=500)]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrackRequest(StrictBody):
    track_ids: list[Annotated[StrictInt, Field(gt=0)]] = Field(min_length=2, max_length=4)


class AlbumSelection(StrictBody):
    album_name: Name
    artist_name: Name


class AlbumRequest(StrictBody):
    albums: list[AlbumSelection] = Field(min_length=2, max_length=4)


class ArtistRequest(StrictBody):
    artist_names: list[Name] = Field(min_length=2, max_length=4)


RequestBody = Union[TrackRequest, AlbumRequest, ArtistRequest]


class PersonalPeriod(BaseModel):
    period: str
    label: str
    start_date: str | None
    end_date: str | None


class PersonalContext(BaseModel):
    filter_fingerprint: str
    source_revision: str
    statistics_contract_version: str


class PersonalMetrics(BaseModel):
    total_plays: int
    total_hours: float
    active_days: int
    avg_daily_plays: float
    avg_daily_hours: float
    max_daily_plays: int | None


class PersonalStatsEntity(BaseModel):
    requested_key: str
    entity_key: str
    found: bool
    status: EntityStatus
    metrics: PersonalMetrics | None = None


class PersonalStatsResponse(PersonalContext):
    period: PersonalPeriod
    entities: list[PersonalStatsEntity]


class PersonalRanks(BaseModel):
    lifetime: int | None
    last_6_months: int | None
    last_4_weeks: int | None


class PersonalRanksEntity(BaseModel):
    requested_key: str
    entity_key: str
    found: bool
    status: EntityStatus
    ranks: PersonalRanks | None = None


class RankPublication(BaseModel):
    status: Literal["ready"]
    freshness: Literal["current"]
    source_revision: str
    target_revision: str
    builder_version: str
    request_key: str


class PersonalRanksResponse(PersonalContext):
    periods: dict[str, PersonalPeriod]
    snapshot: RankPublication
    entities: list[PersonalRanksEntity]


def _items(kind: Kind, body: RequestBody) -> list:
    if kind == "track" and isinstance(body, TrackRequest):
        return body.track_ids
    if kind == "album" and isinstance(body, AlbumRequest):
        return [item.model_dump() for item in body.albums]
    if kind == "artist" and isinstance(body, ArtistRequest):
        return body.artist_names
    raise HTTPException(422, "对象类型与请求内容不一致")


def _filters(filters: PlayFilters, merge: MergeConfig, include_compilations: bool) -> dict:
    return {
        "min_ms": filters.min_ms,
        "music_only": filters.music_only,
        "merge_enabled": filters.merge_enabled,
        "dynamic_threshold": filters.dynamic_threshold,
        "max_merge_gap_minutes": filters.max_merge_gap_minutes,
        "merge_level": merge.merge_level,
        "include_compilations": include_compilations,
    }


@router.post(
    "/versus/{kind}/personal-stats",
    response_model=PersonalStatsResponse,
    responses={503: {"model": SnapshotUnavailableResponse}},
)
def personal_stats(
    kind: Kind,
    body: RequestBody,
    response: Response,
    filters: PlayFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
    conn: Connection = Depends(get_conn),
):
    timing = MusicSearchTiming()
    try:
        with timing.measure("personal_stats"):
            result = build_personal_stats(
                conn,
                kind,
                _items(kind, body),
                _filters(filters, merge, include_compilations),
                timings=timing.durations_ms,
            )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    response.headers["Server-Timing"] = timing.server_timing_header()
    return result


@router.post(
    "/versus/{kind}/personal-ranks",
    response_model=PersonalRanksResponse,
    responses={503: {"model": SnapshotUnavailableResponse}},
)
def personal_ranks(
    kind: Kind,
    body: RequestBody,
    response: Response,
    filters: PlayFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
    conn: Connection = Depends(get_conn),
):
    timing = MusicSearchTiming()
    try:
        with timing.measure("personal_ranks"):
            result = read_personal_ranks(
                conn, kind, _items(kind, body), _filters(filters, merge, include_compilations)
            )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    response.headers["Server-Timing"] = timing.server_timing_header()
    return result
