"""Local-first music archive endpoints for the /account page."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_conn
from backend.domains.account_archive.cohorts import get_collection_cohorts
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.discovery import get_archive_discovery
from backend.domains.account_archive.journey import get_collection_journey
from backend.domains.account_archive.library import (
    ALLOWED_SORTS,
    build_archive_library_page,
)
from backend.domains.account_archive.other_media import get_archive_other_media
from backend.domains.account_archive.overview import get_archive_overview
from backend.domains.account_archive.returns import get_archive_returns
from backend.models.account_archive import (
    ArchiveCohortsResponse,
    ArchiveDiscoveryResponse,
    ArchiveJourneyResponse,
    ArchiveLibraryEntityType,
    ArchiveLibraryPageResponse,
    ArchiveLibrarySort,
    ArchiveOtherMediaResponse,
    ArchiveOverviewResponse,
    ArchiveReturnsResponse,
)

router = APIRouter(prefix="/account", tags=["Account"])


class AccountArchiveFilters:
    """Request-scoped relationship filters; music-only is fixed by the domain."""

    def __init__(
        self,
        min_ms: int | None = Query(default=None, ge=0, description="最短有效播放时长"),
        merge_enabled: bool | None = Query(default=None, description="合并连续同曲播放"),
        dynamic_threshold: bool = Query(default=True, description="使用动态有效播放阈值"),
        max_merge_gap_minutes: int | None = Query(
            default=None,
            ge=1,
            le=240,
            description="连续播放最大实际空闲时间；未传时使用设置值（默认 5 分钟）",
        ),
        merge_level: int = Query(default=2, ge=2, le=3, description="曲目版本归并级别（L2/L3）"),
    ):
        self.min_ms = min_ms
        self.merge_enabled = merge_enabled
        self.dynamic_threshold = dynamic_threshold
        self.max_merge_gap_minutes = max_merge_gap_minutes
        self.merge_level = merge_level


@router.get("/archive-overview", response_model=ArchiveOverviewResponse)
def archive_overview(conn: Connection = Depends(get_conn)):
    """返回音乐档案首屏所需的本地事实，不触发 Spotify 在线请求。"""
    return get_archive_overview(conn)


@router.get("/collection-journey", response_model=ArchiveJourneyResponse)
def collection_journey(
    filters: AccountArchiveFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """返回当前收藏快照的增长时间线与准确档案事实。"""
    context = build_archive_filter_context(conn, filters)
    return get_collection_journey(conn, context)


@router.get("/collection-cohorts", response_model=ArchiveCohortsResponse)
def collection_cohorts(
    filters: AccountArchiveFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """返回有完整观察窗的收藏前后关系与固定窗回访。"""
    context = build_archive_filter_context(conn, filters)
    return get_collection_cohorts(conn, context)


@router.get("/returns", response_model=ArchiveReturnsResponse)
def archive_returns(
    filters: AccountArchiveFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """返回至少沉睡 90 天后的回归事件和当前沉睡收藏。"""
    context = build_archive_filter_context(conn, filters)
    return get_archive_returns(conn, context)


@router.get("/discovery", response_model=ArchiveDiscoveryResponse)
def archive_discovery(
    filters: AccountArchiveFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """返回隐私安全的搜索 burst、时段分布和有限曲目发现漏斗。"""
    context = build_archive_filter_context(conn, filters)
    return get_archive_discovery(conn, context)


@router.get("/library/{entity_type}", response_model=ArchiveLibraryPageResponse)
def archive_library(
    entity_type: ArchiveLibraryEntityType,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    search: str = Query(default="", max_length=120),
    sort: ArchiveLibrarySort | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    """返回歌曲、专辑、艺人或歌单的服务端搜索、排序和分页结果。"""
    if sort is not None and sort not in ALLOWED_SORTS[entity_type]:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "type": "value_error",
                    "loc": ["query", "sort"],
                    "msg": f"sort={sort} is not supported for entity_type={entity_type}",
                    "input": sort,
                }
            ],
        )
    return build_archive_library_page(
        conn,
        entity_type=entity_type,
        page=page,
        limit=limit,
        search=search,
        sort=sort,
    )


@router.get("/other-media", response_model=ArchiveOtherMediaResponse)
def archive_other_media(
    filters: AccountArchiveFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """返回播客与视频的最小档案事实和同口径音视频时长。"""
    context = build_archive_filter_context(conn, filters)
    return get_archive_other_media(conn, context)
