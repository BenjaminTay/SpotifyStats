"""Billboard Year-End endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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
    week_start_dow: int
    week_start_hour: int
    score_label: str


class BillboardYearEndRow(BaseModel):
    model_config = {"extra": "allow"}

    year_end_score: int
    year_end_rank: int
    peak_position: int
    weeks_on_chart: int
    weeks_at_peak: int
    weeks_at_no1: int
    weeks_top5: int
    weeks_top10: int
    chart_plays: int
    first_week: str | None
    last_week: str | None
    true_first_week: str | None = None


class BillboardYearEndResponse(BaseModel):
    meta: BillboardYearEndMeta
    tracks: list[BillboardYearEndRow]
    albums: list[BillboardYearEndRow]
    artists: list[BillboardYearEndRow]
    honors: dict[str, Any]


def _params(filters: BillboardFilters) -> dict[str, Any]:
    return {
        "min_ms": filters.min_ms,
        "music_only": filters.music_only,
        "bb_top_n": YEAR_END_TRACK_TOP_N,
        "bb_album_top_n": YEAR_END_ALBUM_TOP_N,
        "bb_artist_top_n": YEAR_END_ARTIST_TOP_N,
        "bb_week_start_dow": filters.bb_week_start_dow,
        "bb_week_start_hour": filters.bb_week_start_hour,
        "dynamic_threshold": filters.dynamic_threshold,
        "max_merge_gap_minutes": filters.max_merge_gap_minutes,
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
