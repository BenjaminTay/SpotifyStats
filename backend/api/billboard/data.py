"""Billboard data endpoints — full data + staged slices.

GET /api/billboard/data        — all data (backward compatible, ~5MB)
GET /api/billboard/weekly      — meta + weekly/weekly_album/weekly_artist (~1.5MB)
GET /api/billboard/records     — records only (~800KB)
GET /api/billboard/power-scores — power_scores + album/artist variants (~200KB)
GET /api/billboard/summaries   — track_summary + artist_summary + counts (~300KB)
GET /api/billboard/all-time    — power-scores + summaries + weekly (~2MB)
"""

from __future__ import annotations

from typing import Literal, Union

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.api.billboard.projections import (
    all_time_projection,
    number_ones_projection,
    published,
    records_projection,
    weekly_projection,
)
from backend.dependencies import BillboardFilters, MergeConfig
from backend.models.snapshot import SnapshotReadState
from backend.services.billboard_service import (
    compute_all_time_staged,
    compute_billboard_data,
    compute_power_scores_staged,
    compute_records_staged,
    compute_summaries_staged,
    compute_weekly_data,
)

router = APIRouter()


class BillboardMeta(BaseModel):
    total_weeks: int
    total_filtered_records: int
    all_weeks_asc: list[str]
    all_weeks_desc: list[str]
    dow_name: str
    dow_short: str
    top_n: int
    album_top_n: int
    artist_top_n: int
    week_start_dow: int
    week_start_hour: int


class TrackPowerScoreRow(BaseModel):
    model_config = {"extra": "allow"}
    track_id: int
    track_name: str
    artist_name: str
    power_score: int
    peak_position: int
    weeks_on_chart: int
    power_rank: int


class AlbumPowerScoreRow(BaseModel):
    model_config = {"extra": "allow"}
    album_name: str
    artist_name: str
    power_score: int
    peak_position: int
    weeks_on_chart: int
    power_rank: int
    track_power_sum: int = 0
    track_power_rank: int | None = None


class ArtistPowerScoreRow(BaseModel):
    model_config = {"extra": "allow"}
    artist_name: str
    power_score: int
    peak_position: int
    weeks_on_chart: int
    power_rank: int
    track_power_sum: int = 0
    track_power_rank: int | None = None
    album_power_sum: int = 0
    album_power_rank: int | None = None


class BillboardSnapshotResponse(BaseModel):
    snapshot: SnapshotReadState | None = None


class BillboardDataResponse(BillboardSnapshotResponse):
    model_config = {"extra": "allow"}
    meta: BillboardMeta
    weekly: list[dict]
    weekly_album: list[dict]
    weekly_artist: list[dict]
    track_summary: list[dict]
    artist_summary: list[dict]
    artist_track_counts: list[dict]
    album_track_counts: list[dict]
    track_per_album: list[dict]
    records: dict
    power_scores: list[TrackPowerScoreRow]
    album_power_scores: list[AlbumPowerScoreRow]
    artist_power_scores: list[ArtistPowerScoreRow]


class BillboardWeeklyResponse(BillboardSnapshotResponse):
    model_config = {"extra": "allow"}
    meta: BillboardMeta
    weekly: list[dict]
    weekly_album: list[dict]
    weekly_artist: list[dict]


class BillboardRecordsResponse(BillboardSnapshotResponse):
    records: dict


class BillboardPowerScoresResponse(BillboardSnapshotResponse):
    power_scores: list[TrackPowerScoreRow]
    album_power_scores: list[AlbumPowerScoreRow]
    artist_power_scores: list[ArtistPowerScoreRow]


class BillboardSummariesResponse(BillboardSnapshotResponse):
    model_config = {"extra": "allow"}
    track_summary: list[dict]
    artist_summary: list[dict]
    album_track_counts: list[dict]
    artist_track_counts: list[dict]


class BillboardAllTimeResponse(BillboardSnapshotResponse):
    model_config = {"extra": "allow"}
    meta: BillboardMeta
    weekly: list[dict]
    weekly_album: list[dict]
    weekly_artist: list[dict]
    power_scores: list[TrackPowerScoreRow]
    album_power_scores: list[AlbumPowerScoreRow]
    artist_power_scores: list[ArtistPowerScoreRow]
    track_summary: list[dict]
    artist_summary: list[dict]
    album_track_counts: list[dict]
    artist_track_counts: list[dict]


class WeeklyProjectionResponse(BillboardSnapshotResponse):
    meta: BillboardMeta
    selected_week: str
    entity: Literal["tracks", "albums", "artists"]
    current: list[dict]
    previous: list[dict]
    historical: list[dict]


class RecordsProjectionResponse(BillboardSnapshotResponse):
    records: dict
    covers: dict
    curiosity_tracks: list[dict]
    artist_track_counts: list[dict]


class AllTimeProjectionResponse(BillboardSnapshotResponse):
    entity: Literal["tracks", "albums", "artists"]
    rows: list[dict]


class NumberOnesProjectionResponse(BillboardSnapshotResponse):
    weekly: list[dict]
    weekly_album: list[dict]
    weekly_artist: list[dict]
    power_scores: list[dict]
    album_power_scores: list[dict]
    artist_power_scores: list[dict]


def _billboard_params(filters: BillboardFilters):
    """Extract Billboard computation params from filters."""
    return dict(
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        bb_top_n=filters.bb_top_n,
        bb_album_top_n=filters.bb_album_top_n,
        bb_artist_top_n=filters.bb_artist_top_n,
        bb_week_start_dow=filters.bb_week_start_dow,
        bb_week_start_hour=filters.bb_week_start_hour,
        year_start=filters.year_start,
        year_end=filters.year_end,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )


@router.get("/data", response_model=BillboardDataResponse)
def get_billboard_data(
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Compute all Billboard chart data in a single request.

    Returns weekly rankings, track/artist/album summaries, records,
    and power scores. Kept for backward compatibility.
    """
    return compute_billboard_data(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/weekly", response_model=Union[BillboardWeeklyResponse, WeeklyProjectionResponse])
def get_billboard_weekly(
    projection: Literal["page"] | None = None,
    week: str | None = None,
    entity: Literal["tracks", "albums", "artists"] = "tracks",
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Weekly rankings + meta only — used by BillboardPage.

    Returns meta, weekly (tracks), weekly_album, weekly_artist.
    """
    if projection:
        params = {
            **_billboard_params(filters),
            "merge_level": merge_cfg.merge_level,
            "include_compilations": include_compilations,
        }
        return weekly_projection(published(("weekly",), params)[0], week, entity)
    return compute_weekly_data(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/records", response_model=Union[BillboardRecordsResponse, RecordsProjectionResponse])
def get_billboard_records(
    projection: Literal["page"] | None = None,
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Billboard records only — used by RecordsPage.

    Returns all 37 records across 6 sections.
    """
    if projection:
        params = {
            **_billboard_params(filters),
            "merge_level": merge_cfg.merge_level,
            "include_compilations": include_compilations,
        }
        return records_projection(*published(("records", "summaries", "weekly"), params))
    return compute_records_staged(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/power-scores", response_model=BillboardPowerScoresResponse)
def get_billboard_power_scores(
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Power scores for tracks, albums, and artists.

    Returns power_scores, album_power_scores, artist_power_scores
    each with power_rank, weeks_top5, weeks_top10.
    """
    return compute_power_scores_staged(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/summaries", response_model=BillboardSummariesResponse)
def get_billboard_summaries(
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Track/artist/album summaries and counts.

    Returns track_summary, artist_summary, album_track_counts,
    artist_track_counts.
    """
    return compute_summaries_staged(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )


@router.get(
    "/all-time",
    response_model=Union[
        BillboardAllTimeResponse, AllTimeProjectionResponse, NumberOnesProjectionResponse
    ],
)
def get_billboard_all_time(
    projection: Literal["entity", "number-ones"] | None = None,
    entity: Literal["tracks", "albums", "artists"] = "tracks",
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Combined data for all-time charts pages.

    Returns power-scores + summaries + weekly data.
    Used by NumberOnesPage and AllTimeChartsPage.
    """
    if projection:
        params = {
            **_billboard_params(filters),
            "merge_level": merge_cfg.merge_level,
            "include_compilations": include_compilations,
        }
        data = published(("all_time",), params)[0]
        return (
            number_ones_projection(data)
            if projection == "number-ones"
            else all_time_projection(data, entity)
        )
    return compute_all_time_staged(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )
