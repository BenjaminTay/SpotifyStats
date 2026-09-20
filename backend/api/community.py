"""Community feed API endpoint."""

# ruff: noqa: UP045

from __future__ import annotations

from sqlite3 import Connection
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import BillboardFilters, MergeConfig, get_conn
from backend.services.community_snapshot_service import read as read_community_snapshot

router = APIRouter(prefix="/community", tags=["Community"])


def _community_generation_params(
    filters: BillboardFilters,
    merge_cfg: MergeConfig,
    include_compilations: bool,
) -> dict:
    return {
        "min_ms": filters.min_ms,
        "merge_enabled": filters.merge_enabled,
        "music_only": filters.music_only,
        "bb_top_n": filters.bb_top_n,
        "bb_album_top_n": filters.bb_album_top_n,
        "bb_artist_top_n": filters.bb_artist_top_n,
        "bb_week_start_dow": filters.bb_week_start_dow,
        "bb_week_start_hour": filters.bb_week_start_hour,
        "year_start": filters.year_start,
        "year_end": filters.year_end,
        "dynamic_threshold": filters.dynamic_threshold,
        "max_merge_gap_minutes": filters.max_merge_gap_minutes,
        "merge_level": merge_cfg.merge_level,
        "include_compilations": include_compilations,
    }


class FeedMeta(BaseModel):
    total: int
    total_all: int
    returned: int
    offset: int
    limit: int


class CommunityFeedResponse(BaseModel):
    model_config = {"extra": "allow"}
    snapshot: dict | None = None
    meta: FeedMeta
    posts: list[dict]


class TrendingItem(BaseModel):
    name: str
    count: int
    entity_id: Optional[str | int] = None


class TrendingResponse(BaseModel):
    snapshot: dict | None = None
    artists: list[TrendingItem]
    tracks: list[TrendingItem]
    latest_no1: Optional[dict] = None
    latest_debut: Optional[dict] = None


# ── Post Detail response models ──────────────────────────────────────────────


class PostMetrics(BaseModel):
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0


class PostItem(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    account_handle: str
    posted_at: str
    content: str
    post_type: str
    metrics: PostMetrics
    tags: list[str] = []
    significance: float = 0.0
    attached_list: Optional[list] = None
    linked_entities: Optional[list] = None
    images: Optional[list] = None


class PostDetailResponse(BaseModel):
    snapshot: dict | None = None
    post: PostItem
    replies: list[PostItem]


@router.get("/feed", response_model=CommunityFeedResponse)
def get_community_feed(
    accounts: str | None = Query(default=None, description="Comma-separated handles to filter by"),
    tags: str | None = Query(default=None, description="Comma-separated tags to filter by"),
    highlights_only: bool = Query(
        default=False, description="Show only newsworthy posts (no routine summaries)"
    ),
    significance_min: float = Query(
        default=0.0, ge=0.0, le=1.0, description="Minimum significance threshold"
    ),
    date_from: str | None = Query(default=None, description="ISO date lower bound"),
    date_to: str | None = Query(default=None, description="ISO date upper bound"),
    search: str | None = Query(
        default=None, description="Search post content, handles, and linked entity names"
    ),
    post_types: str | None = Query(
        default=None, description="Comma-separated post type values to filter by"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart"
    ),
    conn: Connection = Depends(get_conn),
):
    """Get the community feed — simulated X-style posts from chart data.

    Posts are generated with historical accuracy: each post only references
    knowledge available at its point in time.

    Filter by accounts, tags, date range, significance threshold, search keywords,
    post types, or use highlights_only for newsworthy posts only.
    """
    return read_community_snapshot(
        conn,
        "feed",
        _community_generation_params(filters, merge_cfg, include_compilations),
        accounts=accounts,
        tags=tags,
        highlights_only=highlights_only,
        significance_min=significance_min,
        date_from=date_from,
        date_to=date_to,
        search=search,
        post_types=post_types,
        limit=limit,
        offset=offset,
    )


@router.get("/trending", response_model=TrendingResponse)
def get_community_trending(
    date_from: str | None = Query(default=None, description="ISO date lower bound"),
    date_to: str | None = Query(default=None, description="ISO date upper bound"),
    artist_limit: int = Query(default=6, ge=1, le=20),
    track_limit: int = Query(default=3, ge=1, le=20),
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart"
    ),
    conn: Connection = Depends(get_conn),
):
    """Get trending entities computed over ALL community posts (not just current page).

    Returns top mentioned artists, tracks, latest #1, and latest debut.
    """
    return read_community_snapshot(
        conn,
        "trending",
        _community_generation_params(filters, merge_cfg, include_compilations),
        date_from=date_from,
        date_to=date_to,
        artist_limit=artist_limit,
        track_limit=track_limit,
    )


@router.get("/post/{post_id}", response_model=PostDetailResponse)
def get_community_post(
    post_id: str,
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(
        default=False, description="Include compilation albums in album chart"
    ),
    conn: Connection = Depends(get_conn),
):
    """Get a single community post by ID, with simulated related replies."""

    return read_community_snapshot(
        conn,
        "post",
        _community_generation_params(filters, merge_cfg, include_compilations),
        post_id=post_id,
    )


@router.post("/refresh")
def refresh_community(
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(default=False),
):
    """Private maintenance only; GET never queues or constructs a publication."""
    from backend.services.community_snapshot_service import enqueue

    return {
        "job_ids": enqueue(_community_generation_params(filters, merge_cfg, include_compilations))
    }
