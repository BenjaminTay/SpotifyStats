"""Global music entity API endpoints."""

from __future__ import annotations

import logging
from sqlite3 import Connection
from typing import Literal, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel

from backend.core.access_surface import is_public_readonly
from backend.dependencies import BillboardFilters, MergeConfig, PlayFilters, get_conn
from backend.domains.music_search.context import build_music_search_filter_context
from backend.domains.music_search.contracts import parse_music_search_entity_key
from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.music_search.snapshot import (
    get_music_search_snapshot_status,
    get_ready_music_search_snapshot_key,
    lookup_music_search_context,
)
from backend.domains.music_search.timing import MusicSearchTiming
from backend.domains.settings.repository import SettingsRepository
from backend.models.music_search import (
    MusicSearchCandidateResponse,
    MusicSearchContextResponse,
    MusicSearchResponse,
)
from backend.services.entity_stats_service import (
    get_album_personal_ranking,
    get_album_stats,
    get_artist_personal_ranking,
    get_artist_stats,
    get_entity_play_dates,
    get_entity_plays,
    get_track_stats,
)
from backend.services.music_search_candidate_service import search_music_candidates
from backend.services.music_search_service import search_music_entities

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/music", tags=["Music"])


def _search_filter_context(
    conn: Connection,
    filters: PlayFilters,
    merge_cfg: MergeConfig,
):
    settings = SettingsRepository(conn).load_all()
    return build_music_search_filter_context(
        conn,
        {
            # Candidate V2 supports exactly the six maintained
            # merge-level/dynamic variants.  Every other semantic value comes
            # from the server settings snapshot used by the builder.
            "min_ms": settings.get("min_ms", 30000),
            "music_only": settings.get("music_only", True),
            "merge_enabled": settings.get("merge_enabled", True),
            "dynamic_threshold": filters.dynamic_threshold,
            "max_merge_gap_minutes": settings.get("max_merge_gap_minutes", 5),
            "merge_level": merge_cfg.merge_level,
            "include_compilations": bool(settings.get("include_compilations", False)),
            "bb_top_n": settings.get("bb_top_n", 30),
            "bb_album_top_n": settings.get("bb_album_top_n", 20),
            "bb_artist_top_n": settings.get("bb_artist_top_n", 20),
            "bb_week_start_dow": settings.get("bb_week_start_dow", 4),
            "bb_week_start_hour": settings.get("bb_week_start_hour", 0),
            "year_start": None,
            "year_end": None,
        },
    )


_CANDIDATE_BASE_FILTERS = {
    "min_ms",
    "music_only",
    "merge_enabled",
    "max_merge_gap_minutes",
    "bb_top_n",
    "bb_album_top_n",
    "bb_artist_top_n",
    "bb_week_start_dow",
    "bb_week_start_hour",
}


def _reject_unsupported_candidate_filters(
    request: Request,
    *,
    conn: Connection,
    filters: PlayFilters,
    billboard_filters: BillboardFilters,
) -> None:
    """Reject semantic combinations that the six-variant builder never creates."""

    settings = SettingsRepository(conn).load_all()
    resolved = {
        "min_ms": filters.min_ms,
        "music_only": filters.music_only,
        "merge_enabled": filters.merge_enabled,
        "max_merge_gap_minutes": filters.max_merge_gap_minutes,
        "bb_top_n": billboard_filters.bb_top_n,
        "bb_album_top_n": billboard_filters.bb_album_top_n,
        "bb_artist_top_n": billboard_filters.bb_artist_top_n,
        "bb_week_start_dow": billboard_filters.bb_week_start_dow,
        "bb_week_start_hour": billboard_filters.bb_week_start_hour,
    }
    unsupported = [
        name
        for name in sorted(_CANDIDATE_BASE_FILTERS)
        if name in request.query_params and resolved[name] != settings.get(name)
    ]
    unsupported.extend(name for name in ("year_start", "year_end") if name in request.query_params)
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": "unsupported_candidate_filter",
                "parameters": unsupported,
            },
        )


class EntityStatsResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool | None = None
    period: dict | None = None
    entity: dict | None = None
    first_played: str | None = None
    last_played: str | None = None
    ranks: dict | None = None
    recent_plays: list[dict] | None = None
    summary: dict | None = None
    daily_metrics: dict | None = None
    hourly_distribution: list | None = None
    daily_trend: list | None = None
    cumulative_trend: list | None = None
    weekday_distribution: list | None = None
    month_distribution: list | None = None
    year_distribution: list | None = None
    top250_counts: dict | None = None
    track_breakdown: list[dict] | None = None
    top_tracks: list[dict] | None = None
    top_albums: list[dict] | None = None
    recent_50_count: int | None = None


class EntityPlaysResponse(BaseModel):
    total: int
    limit: int
    offset: int
    rows: list[dict]


class PlayDateEntry(BaseModel):
    date: str
    count: int


class ArtistPersonalRankingResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    artist_name: str | None = None
    entity: Literal["track", "album"]
    metric: Literal["plays", "hours"] = "plays"
    total: int
    limit: int
    offset: int
    rows: list[dict]


class AlbumPersonalRankingResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    album_name: str | None = None
    artist_name: str | None = None
    entity: Literal["track"] = "track"
    metric: Literal["plays", "hours"] = "plays"
    total: int
    limit: int
    offset: int
    rows: list[dict]


@router.get(
    "/search",
    response_model=Union[MusicSearchResponse, MusicSearchCandidateResponse],
)
def music_search(
    request: Request,
    response: Response,
    q: str = Query(default="", max_length=120, description="Local track, album, or artist query"),
    kind: Literal["track", "album", "artist"] | None = Query(
        default=None,
        description="Optional entity kind filter",
    ),
    limit_per_type: int = Query(default=5, ge=1, le=10),
    include_chart: bool = Query(
        default=False, description="Include personal Billboard chart summary"
    ),
    response_mode: Literal["legacy", "candidates"] = Query(default="legacy"),
    eligibility: Literal["current", "any_local"] = Query(default="current"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=100),
    filters: PlayFilters = Depends(),
    billboard_filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    conn: Connection = Depends(get_conn),
):
    timing = MusicSearchTiming()
    result: Union[MusicSearchResponse, MusicSearchCandidateResponse]
    with timing.measure("total"):
        if response_mode == "candidates":
            _reject_unsupported_candidate_filters(
                request,
                conn=conn,
                filters=filters,
                billboard_filters=billboard_filters,
            )
            if eligibility == "any_local" and is_public_readonly(request):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="public-readonly 仅允许 current 搜索资格",
                )
            with timing.measure("fingerprint"):
                search_context = _search_filter_context(
                    conn,
                    filters,
                    merge_cfg,
                )
                snapshot_status = get_music_search_snapshot_status(
                    conn,
                    search_context.filter_fingerprint,
                )
                snapshot_key = get_ready_music_search_snapshot_key(
                    conn,
                    search_context.filter_fingerprint,
                )
            result = search_music_candidates(
                conn,
                query=q,
                kinds=(kind,) if kind else None,
                page=page,
                page_size=page_size,
                eligibility=eligibility,
                filter_fingerprint=search_context.filter_fingerprint,
                snapshot_status=snapshot_status,
                merge_level=merge_cfg.merge_level,
                snapshot_key=snapshot_key,
                timing=timing,
            )
        else:
            result = search_music_entities(
                conn,
                query=q,
                kinds=(kind,) if kind else None,
                limit_per_type=limit_per_type,
                min_ms=filters.min_ms,
                music_only=filters.music_only,
                merge_enabled=filters.merge_enabled,
                dynamic_threshold=filters.dynamic_threshold,
                max_merge_gap_minutes=filters.max_merge_gap_minutes,
                merge_level=merge_cfg.merge_level,
                include_chart=include_chart,
                bb_top_n=billboard_filters.bb_top_n,
                bb_album_top_n=billboard_filters.bb_album_top_n,
                bb_artist_top_n=billboard_filters.bb_artist_top_n,
                bb_week_start_dow=billboard_filters.bb_week_start_dow,
                bb_week_start_hour=billboard_filters.bb_week_start_hour,
                year_start=billboard_filters.year_start,
                year_end=billboard_filters.year_end,
                include_compilations=bool(
                    SettingsRepository(conn).load_all().get("include_compilations", False)
                ),
                timing=timing,
            )
    response.headers["Server-Timing"] = timing.server_timing_header()
    search_snapshot_status = getattr(result, "snapshot_status", "legacy")
    generation_id = (
        get_music_search_index_state(conn).get("active_generation_id")
        if response_mode == "candidates"
        else None
    )
    logger.info(
        "Music search completed: mode=%s query_length=%d kind=%s results=%d "
        "include_chart=%s snapshot_status=%s index_generation=%s timing_ms=%s",
        response_mode,
        len(q.strip()),
        kind or "all",
        result.total,
        include_chart if response_mode == "legacy" else False,
        search_snapshot_status,
        str(generation_id)[:12] if generation_id else "none",
        timing.as_dict(),
    )
    return result


@router.get("/search/context", response_model=MusicSearchContextResponse)
def music_search_context(
    request: Request,
    response: Response,
    entity_key: list[str] = Query(default=[]),
    filters: PlayFilters = Depends(),
    billboard_filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    conn: Connection = Depends(get_conn),
) -> MusicSearchContextResponse:
    """Read the exact derived context without queuing or rebuilding work."""

    _reject_unsupported_candidate_filters(
        request,
        conn=conn,
        filters=filters,
        billboard_filters=billboard_filters,
    )
    if len(entity_key) > 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_key 最多 30 个",
        )
    try:
        for value in dict.fromkeys(entity_key):
            parse_music_search_entity_key(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_key 格式无效",
        ) from exc
    timing = MusicSearchTiming()
    with timing.measure("total"):
        with timing.measure("fingerprint"):
            search_context = _search_filter_context(
                conn,
                filters,
                merge_cfg,
            )
        with timing.measure("snapshot_lookup"):
            result = lookup_music_search_context(
                conn,
                filter_fingerprint=search_context.filter_fingerprint,
                entity_keys=entity_key,
            )
        with timing.measure("serialize"):
            result.model_dump(mode="json")
    response.headers["Server-Timing"] = timing.server_timing_header()
    logger.info(
        "Music search context completed: requested_keys=%d returned_items=%d "
        "snapshot_status=%s timing_ms=%s",
        len(dict.fromkeys(entity_key)),
        len(result.items),
        result.snapshot_status,
        timing.as_dict(),
    )
    return result


@router.get("/tracks/{track_id}/stats", response_model=EntityStatsResponse)
def track_stats(
    track_id: int,
    response: Response,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    include_rank_context: bool = Query(default=True),
    conn: Connection = Depends(get_conn),
):
    timing = MusicSearchTiming()
    with timing.measure("entity_stats"):
        result = get_track_stats(
            conn,
            track_id,
            filters.min_ms,
            filters.music_only,
            filters.merge_enabled,
            period,
            start_date,
            end_date,
            filters.dynamic_threshold,
            filters.max_merge_gap_minutes,
            include_rank_context,
        )
    response.headers["Server-Timing"] = timing.server_timing_header()
    return result


@router.get("/albums/{album_name}/stats", response_model=EntityStatsResponse)
def album_stats(
    album_name: str,
    response: Response,
    artist: str | None = Query(default=None),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(
        default=2,
        ge=1,
        le=3,
        description="Album project merge level (1=none, 2=recording, 3=composition)",
    ),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    include_rank_context: bool = Query(default=True),
    conn: Connection = Depends(get_conn),
):
    timing = MusicSearchTiming()
    with timing.measure("entity_stats"):
        result = get_album_stats(
            conn,
            album_name,
            artist,
            filters.min_ms,
            filters.music_only,
            filters.merge_enabled,
            period,
            start_date,
            end_date,
            filters.dynamic_threshold,
            filters.max_merge_gap_minutes,
            merge_level=merge_level,
            include_rank_context=include_rank_context,
        )
    response.headers["Server-Timing"] = timing.server_timing_header()
    return result


@router.get("/artists/{artist_name}/stats", response_model=EntityStatsResponse)
def artist_stats(
    artist_name: str,
    response: Response,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    include_rank_context: bool = Query(default=True),
    conn: Connection = Depends(get_conn),
):
    timing = MusicSearchTiming()
    with timing.measure("entity_stats"):
        result = get_artist_stats(
            conn,
            artist_name,
            filters.min_ms,
            filters.music_only,
            filters.merge_enabled,
            period,
            start_date,
            end_date,
            filters.dynamic_threshold,
            filters.max_merge_gap_minutes,
            include_rank_context,
        )
    response.headers["Server-Timing"] = timing.server_timing_header()
    return result


@router.get(
    "/albums/{album_name}/rankings",
    response_model=AlbumPersonalRankingResponse,
)
def album_personal_rankings(
    album_name: str,
    artist: str | None = Query(default=None),
    metric: Literal["plays", "hours"] = Query(default="plays"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(default=2, ge=1, le=3),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_album_personal_ranking(
        conn,
        album_name,
        artist,
        metric,
        limit,
        offset,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
        merge_level,
    )


@router.get(
    "/artists/{artist_name}/rankings",
    response_model=ArtistPersonalRankingResponse,
)
def artist_personal_rankings(
    artist_name: str,
    entity: Literal["track", "album"] = Query(default="track"),
    metric: Literal["plays", "hours"] = Query(default="plays"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_artist_personal_ranking(
        conn,
        artist_name,
        entity,
        metric,
        limit,
        offset,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/tracks/{track_id}/plays", response_model=EntityPlaysResponse)
def track_plays(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_entity_plays(
        conn,
        entity="track",
        track_id=track_id,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/albums/{album_name}/plays", response_model=EntityPlaysResponse)
def album_plays(
    album_name: str,
    artist: str | None = Query(default=None),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(default=2, ge=1, le=3),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_entity_plays(
        conn,
        entity="album",
        album_name=album_name,
        artist_name=artist,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        merge_level=merge_level,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/artists/{artist_name}/plays", response_model=EntityPlaysResponse)
def artist_plays(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_entity_plays(
        conn,
        entity="artist",
        artist_name=artist_name,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/tracks/{track_id}/play-dates", response_model=list[PlayDateEntry])
def track_play_dates(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_entity_play_dates(
        conn,
        entity="track",
        track_id=track_id,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )


@router.get("/albums/{album_name}/play-dates", response_model=list[PlayDateEntry])
def album_play_dates(
    album_name: str,
    artist: str | None = Query(default=None),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(default=2, ge=1, le=3),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_entity_play_dates(
        conn,
        entity="album",
        album_name=album_name,
        artist_name=artist,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        merge_level=merge_level,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )


@router.get("/artists/{artist_name}/play-dates", response_model=list[PlayDateEntry])
def artist_play_dates(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_entity_play_dates(
        conn,
        entity="artist",
        artist_name=artist_name,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
