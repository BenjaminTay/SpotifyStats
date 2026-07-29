"""Billboard Year-End endpoint."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.dependencies import BillboardFilters, MergeConfig
from backend.domains.billboard.year_end import (
    YEAR_END_ALBUM_TOP_N,
    YEAR_END_ARTIST_TOP_N,
    YEAR_END_TRACK_TOP_N,
)
from backend.services.billboard_service import compute_year_end_staged

router = APIRouter()


class BillboardYearEndMeta(BaseModel):
    year: int | None
    available_years: list[int]
    total_weeks: int
    top_n: int
    album_top_n: int
    artist_top_n: int
    year_end_top_n: int
    year_end_album_top_n: int
    year_end_artist_top_n: int
    weekly_top_n: int
    weekly_album_top_n: int
    weekly_artist_top_n: int
    week_start_dow: int
    week_start_hour: int
    score_label: str
    semantics_version: str
    coverage_status: Literal[
        "empty",
        "complete",
        "incomplete",
        "partial_start",
        "year_to_date",
        "partial_range",
    ]
    is_complete_year: bool
    period_start: str | None
    period_end: str | None
    first_billboard_week: str | None
    last_billboard_week: str | None
    observed_weeks: int
    expected_weeks: int
    has_internal_gaps: bool


class BillboardYearEndRow(BaseModel):
    year_end_score: int
    year_end_rank: int
    peak_position: int
    weeks_on_chart: int
    weeks_at_peak: int
    weeks_at_no1: int
    weeks_top5: int
    weeks_top10: int
    chart_plays: int
    annual_plays: int
    first_week: str | None
    last_week: str | None
    true_first_week: str | None = None
    cover_url: str | None = None


class BillboardYearEndTrackRow(BillboardYearEndRow):
    track_id: int
    track_name: str
    artist_name: str
    artist_names: list[str] = Field(default_factory=list)
    album_name: str | None = None
    is_true_debut_no1: bool


class BillboardYearEndAlbumRow(BillboardYearEndRow):
    album_name: str
    artist_name: str
    release_date: str | None = None
    album_type: str | None = None
    is_new_entry: bool = False


class BillboardYearEndArtistRow(BillboardYearEndRow):
    artist_name: str
    is_new_entry: bool = False


class BillboardYearEndHonors(BaseModel):
    year_end_no1_track: BillboardYearEndTrackRow | None = None
    year_end_no1_album: BillboardYearEndAlbumRow | None = None
    year_end_no1_artist: BillboardYearEndArtistRow | None = None
    longest_charting_track: BillboardYearEndTrackRow | None = None
    longest_charting_album: BillboardYearEndAlbumRow | None = None
    longest_charting_artist: BillboardYearEndArtistRow | None = None
    biggest_no1_run_track: BillboardYearEndTrackRow | None = None
    biggest_no1_run_album: BillboardYearEndAlbumRow | None = None
    biggest_no1_run_artist: BillboardYearEndArtistRow | None = None
    top_new_entry_track: BillboardYearEndTrackRow | None = None
    breakthrough_artist: BillboardYearEndArtistRow | None = None
    album_era_of_the_year: BillboardYearEndAlbumRow | None = None


class BillboardYearEndResponse(BaseModel):
    meta: BillboardYearEndMeta
    tracks: list[BillboardYearEndTrackRow]
    albums: list[BillboardYearEndAlbumRow]
    artists: list[BillboardYearEndArtistRow]
    honors: BillboardYearEndHonors


def _params(filters: BillboardFilters) -> dict[str, Any]:
    return {
        "min_ms": filters.min_ms,
        "music_only": filters.music_only,
        "bb_top_n": filters.bb_top_n,
        "bb_album_top_n": filters.bb_album_top_n,
        "bb_artist_top_n": filters.bb_artist_top_n,
        "bb_week_start_dow": filters.bb_week_start_dow,
        "bb_week_start_hour": filters.bb_week_start_hour,
        "dynamic_threshold": filters.dynamic_threshold,
        "max_merge_gap_minutes": filters.max_merge_gap_minutes,
        "year_end_top_n": YEAR_END_TRACK_TOP_N,
        "year_end_album_top_n": YEAR_END_ALBUM_TOP_N,
        "year_end_artist_top_n": YEAR_END_ARTIST_TOP_N,
    }


@router.get("/year-end", response_model=BillboardYearEndResponse)
def get_billboard_year_end(
    year: int | None = Query(default=None, description="Billboard Year-End 年份"),
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False,
        description="Include compilation albums in album chart",
    ),
):
    try:
        return compute_year_end_staged(
            **_params(filters),
            year=year,
            merge_level=merge_cfg.merge_level,
            include_compilations=include_compilations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
