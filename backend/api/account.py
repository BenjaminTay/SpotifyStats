"""Account center API — aggregated endpoints for the /account page."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import get_conn
from backend.domains.account_archive.cohorts import get_collection_cohorts
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.journey import get_collection_journey
from backend.domains.account_archive.overview import get_archive_overview
from backend.domains.account_archive.returns import get_archive_returns
from backend.domains.metadata.artist_identity import canonicalize_artist_payload
from backend.models.account_archive import (
    ArchiveCohortsResponse,
    ArchiveJourneyResponse,
    ArchiveOverviewResponse,
    ArchiveReturnsResponse,
)
from backend.services.account_service import get_account_summary, get_collection_insights

router = APIRouter(prefix="/account", tags=["Account"])


class AccountArchiveFilters:
    """Request-scoped relationship filters; music-only is fixed by the domain."""

    def __init__(
        self,
        min_ms: int | None = Query(default=None, ge=0, description="最短有效播放时长"),
        merge_enabled: bool | None = Query(default=None, description="合并连续同曲播放"),
        dynamic_threshold: bool = Query(default=True, description="使用动态有效播放阈值"),
        max_merge_gap_minutes: int | None = Query(
            default=None, ge=1, le=240, description="连续播放最大合并间隔"
        ),
        merge_level: int = Query(default=2, ge=1, le=3, description="曲目版本归并级别"),
    ):
        self.min_ms = min_ms
        self.merge_enabled = merge_enabled
        self.dynamic_threshold = dynamic_threshold
        self.max_merge_gap_minutes = max_merge_gap_minutes
        self.merge_level = merge_level


class AccountSummaryResponse(BaseModel):
    model_config = {"extra": "allow"}
    has_account_data: bool | None = None


class CollectionInsightsResponse(BaseModel):
    model_config = {"extra": "allow"}
    available: bool | None = None
    empty: bool | None = None


@router.get("", response_model=AccountSummaryResponse)
def account_summary(conn: Connection = Depends(get_conn)):
    """聚合账号中心所有数据（library + search + insights + podcast + video + profile + collection insights）。"""
    return canonicalize_artist_payload(get_account_summary(conn), conn)


@router.get("/collection-insights", response_model=CollectionInsightsResponse)
def collection_insights(conn: Connection = Depends(get_conn)):
    """收藏×播放交叉分析洞察。"""
    return canonicalize_artist_payload(get_collection_insights(conn), conn)


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
