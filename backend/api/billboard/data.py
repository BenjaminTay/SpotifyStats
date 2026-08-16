"""Billboard data endpoints — full data + staged slices.

GET /api/billboard/data        — all data (backward compatible, ~5MB)
GET /api/billboard/weekly      — meta + weekly/weekly_album/weekly_artist (~1.5MB)
GET /api/billboard/records     — records only (~800KB)
GET /api/billboard/power-scores — power_scores + album/artist variants (~200KB)
GET /api/billboard/summaries   — track_summary + artist_summary + counts (~300KB)
GET /api/billboard/all-time    — power-scores + summaries + weekly (~2MB)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import BillboardFilters, MergeConfig
from backend.services.billboard_service import (
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


class BillboardDataResponse(BaseModel):
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


class BillboardWeeklyResponse(BaseModel):
    model_config = {"extra": "allow"}
    meta: BillboardMeta
    weekly: list[dict]
    weekly_album: list[dict]
    weekly_artist: list[dict]


class BillboardRecordsResponse(BaseModel):
    records: dict


class BillboardPowerScoresResponse(BaseModel):
    power_scores: list[TrackPowerScoreRow]
    album_power_scores: list[AlbumPowerScoreRow]
    artist_power_scores: list[ArtistPowerScoreRow]


class BillboardSummariesResponse(BaseModel):
    model_config = {"extra": "allow"}
    track_summary: list[dict]
    artist_summary: list[dict]
    album_track_counts: list[dict]
    artist_track_counts: list[dict]


class BillboardAllTimeResponse(BaseModel):
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


@router.get("/weekly", response_model=BillboardWeeklyResponse)
def get_billboard_weekly(
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Weekly rankings + meta only — used by BillboardPage.

    Returns meta, weekly (tracks), weekly_album, weekly_artist.
    """
    return compute_weekly_data(
        **_billboard_params(filters),
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/records", response_model=BillboardRecordsResponse)
def get_billboard_records(
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart (R14)"
    ),
):
    """Billboard records only — used by RecordsPage.

    Returns all 37 records across 6 sections.
    """
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


@router.get("/all-time", response_model=BillboardAllTimeResponse)
def get_billboard_all_time(
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
    params = _billboard_params(filters)
    ml = merge_cfg.merge_level
    weekly = compute_weekly_data(
        **params,
        merge_level=ml,
        include_compilations=include_compilations,
    )
    power = compute_power_scores_staged(
        **params, merge_level=ml, include_compilations=include_compilations
    )
    summaries = compute_summaries_staged(
        **params, merge_level=ml, include_compilations=include_compilations
    )
    return {**weekly, **power, **summaries}
