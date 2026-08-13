"""Read-only AI agent tool handlers backed by local analysis services."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.db import get_db
from backend.domains.account_archive.cohorts import get_collection_cohorts
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.discovery import get_archive_discovery
from backend.domains.account_archive.journey import get_collection_journey
from backend.domains.account_archive.overview import get_archive_overview
from backend.domains.account_archive.returns import get_archive_returns
from backend.domains.ai_agent.comparison import summarize_entity_comparison
from backend.domains.ai_agent.entity_resolver import resolve_entities
from backend.domains.ai_agent.tool_registry import AgentToolDefinition, AgentToolResult
from backend.domains.billboard import details as billboard_details
from backend.domains.community import feed_generator as community_feed_generator
from backend.domains.community.post_types import HIGHLIGHT_POST_TYPES
from backend.services import (
    analysis_records_service,
    analysis_stats_service,
    entity_stats_service,
    play_service,
    search_service,
    wrapped_service,
)

PeriodName = Literal[
    "lifetime",
    "today",
    "this_week",
    "this_year",
    "last_4_weeks",
    "last_6_months",
    "custom",
]

ALBUM_PROJECT_TABLES = (
    "album_projects",
    "album_project_albums",
    "album_project_tracks",
)


class AnalysisStatsParams(BaseModel):
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    period: PeriodName = "lifetime"
    start_date: str | None = None
    end_date: str | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def validate_custom_range(self) -> AnalysisStatsParams:
        if self.period == "custom" and self.start_date and self.end_date:
            if date.fromisoformat(self.start_date) > date.fromisoformat(self.end_date):
                raise ValueError("start_date must be before or equal to end_date")
        return self


class AnalysisChartsParams(AnalysisStatsParams):
    entity: Literal["track", "album", "artist"] = "track"
    metric: Literal["plays", "hours"] = "plays"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    merge_level: int = Field(default=2, ge=1, le=3)
    include_compilations: bool = False


class PlaybackRecordsParams(AnalysisStatsParams):
    merge_level: int = Field(default=2, ge=1, le=3)
    include_compilations: bool = False


class WrappedYearlyParams(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=1, ge=1, le=3)


class EntityStatsParams(AnalysisStatsParams):
    entity: Literal["track", "album", "artist"] = "track"
    track_id: int | None = Field(default=None, ge=1)
    album_name: str | None = Field(default=None, min_length=1, max_length=300)
    artist_name: str | None = Field(default=None, min_length=1, max_length=300)
    merge_level: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def validate_entity_identifier(self) -> EntityStatsParams:
        if self.entity == "track" and self.track_id is None:
            raise ValueError("track_id is required for track entity stats")
        if self.entity == "album" and not self.album_name:
            raise ValueError("album_name is required for album entity stats")
        if self.entity == "artist" and not self.artist_name:
            raise ValueError("artist_name is required for artist entity stats")
        return self


class BillboardEntityDetailParams(BaseModel):
    entity: Literal["track", "album", "artist"] = "track"
    track_id: int | None = Field(default=None, ge=1)
    album_name: str | None = Field(default=None, min_length=1, max_length=300)
    artist_name: str | None = Field(default=None, min_length=1, max_length=300)
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    bb_top_n: int = Field(default=30, ge=1, le=500)
    bb_album_top_n: int = Field(default=20, ge=1, le=500)
    bb_artist_top_n: int = Field(default=20, ge=1, le=500)
    bb_week_start_dow: int = Field(default=4, ge=0, le=6)
    bb_week_start_hour: int = Field(default=0, ge=0, le=23)
    year_start: int | None = Field(default=None, ge=2000, le=2100)
    year_end: int | None = Field(default=None, ge=2000, le=2100)
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def validate_entity_identifier(self) -> BillboardEntityDetailParams:
        if self.year_start is not None and self.year_end is not None:
            if self.year_start > self.year_end:
                raise ValueError("year_start must be before or equal to year_end")
        if self.entity == "track" and self.track_id is None:
            raise ValueError("track_id is required for track billboard detail")
        if self.entity == "album" and not self.album_name:
            raise ValueError("album_name is required for album billboard detail")
        if self.entity == "artist" and not self.artist_name:
            raise ValueError("artist_name is required for artist billboard detail")
        return self


class ListeningHoursParams(BaseModel):
    view: Literal[
        "heatmap",
        "yearly_heatmaps",
        "late_night_ratio",
        "late_night_tracks",
        "weekday_weekend",
        "platform_hourly",
    ] = "heatmap"
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)


class ResolveEntityParams(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    entity_type: Literal["track", "album", "artist"] = "album"
    limit: int = Field(default=5, ge=1, le=10)


class CompareEntitiesParams(BaseModel):
    entity_type: Literal["track", "album", "artist"] = "album"
    names: list[str] = Field(..., min_length=2, max_length=4)
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=2, ge=1, le=3)

    @field_validator("names")
    @classmethod
    def validate_names(cls, value: list[str]) -> list[str]:
        cleaned = [name.strip() for name in value if name.strip()]
        if len(cleaned) != len(value):
            raise ValueError("names must not contain empty values")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("names must be unique")
        return cleaned


class AccountSummaryParams(BaseModel):
    include_collection: bool = True
    include_search: bool = True


class AccountCollectionInsightsParams(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class SearchHistoryParams(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=120)
    limit: int = Field(default=10, ge=1, le=30)


class CommunityFeedSearchParams(BaseModel):
    search: str | None = Field(default=None, min_length=1, max_length=120)
    highlights_only: bool = False
    limit: int = Field(default=10, ge=1, le=50)
    date_from: str | None = None
    date_to: str | None = None
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    bb_top_n: int = Field(default=30, ge=5, le=100)
    bb_album_top_n: int = Field(default=20, ge=5, le=100)
    bb_artist_top_n: int = Field(default=20, ge=5, le=100)
    bb_week_start_dow: int = Field(default=4, ge=0, le=6)
    bb_week_start_hour: int = Field(default=0, ge=0, le=23)
    year_start: int | None = Field(default=None, ge=2000, le=2100)
    year_end: int | None = Field(default=None, ge=2000, le=2100)
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=2, ge=1, le=3)
    include_compilations: bool = False

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        date.fromisoformat(value[:10])
        return value

    @model_validator(mode="after")
    def validate_year_bounds(self) -> CommunityFeedSearchParams:
        if self.year_start is not None and self.year_end is not None:
            if self.year_start > self.year_end:
                raise ValueError("year_start must be before or equal to year_end")
        return self


class CommunityTrendingParams(CommunityFeedSearchParams):
    artist_limit: int = Field(default=6, ge=1, le=20)
    track_limit: int = Field(default=3, ge=1, le=20)


def _source_range(data: dict[str, Any]) -> str:
    period = data.get("period")
    if not isinstance(period, dict):
        return ""
    start = period.get("start_date")
    end = period.get("end_date")
    if start and end:
        return f"{start}..{end}"
    if start:
        return f"{start}.."
    if end:
        return f"..{end}"
    return str(period.get("period") or "")


def _year_source_range(year: int) -> str:
    return str(year)


def _year_bounds_source_range(year_start: int | None, year_end: int | None) -> str:
    if year_start is not None and year_end is not None:
        return f"{year_start}..{year_end}"
    if year_start is not None:
        return f"{year_start}.."
    if year_end is not None:
        return f"..{year_end}"
    return "all_years"


def _album_projects_ready(conn) -> bool:
    rows = conn.execute(
        """SELECT name FROM sqlite_master
           WHERE type = 'table' AND name IN (?, ?, ?)""",
        ALBUM_PROJECT_TABLES,
    ).fetchall()
    found = {
        row["name"]
        if isinstance(row, sqlite3.Row)
        else row.get("name")
        if isinstance(row, dict)
        else row[0]
        for row in rows
    }
    if not set(ALBUM_PROJECT_TABLES).issubset(found):
        return False
    row = conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()
    count = row[0] if row is not None else 0
    return int(count or 0) > 0


def _album_projects_unavailable(context: str) -> AgentToolResult:
    return AgentToolResult(
        data={
            "found": False,
            "error": (
                "album project data is not initialized; run the import maintenance "
                "refresh before using this read-only Agent tool for album-project analysis"
            ),
            "context": context,
        },
        result_summary="album_project_data_unavailable",
        source_range="album_projects:not_ready",
    )


def _stats_result_summary(data: dict[str, Any]) -> str:
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return "summary unavailable"
    return (
        f"plays={int(summary.get('total_plays') or 0)}, "
        f"hours={float(summary.get('total_hours') or 0):g}, "
        f"tracks={int(summary.get('unique_tracks') or 0)}, "
        f"artists={int(summary.get('unique_artists') or 0)}"
    )


def _charts_result_summary(data: dict[str, Any]) -> str:
    rows = data.get("rows")
    row_count = len(rows) if isinstance(rows, list) else 0
    total = int(data.get("total") or 0)
    entity = data.get("entity") or "track"
    metric = data.get("metric") or "plays"
    return f"{entity} {metric} rows={row_count}/{total}"


def _records_result_summary(data: dict[str, Any]) -> str:
    meta = data.get("meta") if isinstance(data, dict) else {}
    records = data.get("records") if isinstance(data, dict) else {}
    record_count = len(records) if isinstance(records, dict) else 0
    total_plays = int(meta.get("total_plays") or 0) if isinstance(meta, dict) else 0
    total_hours = float(meta.get("total_hours") or 0) if isinstance(meta, dict) else 0.0
    return f"plays={total_plays}, hours={total_hours:g}, records={record_count}"


def _wrapped_yearly_result_summary(data: dict[str, Any]) -> str:
    hero = data.get("hero") if isinstance(data.get("hero"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    source = hero or summary
    if not source:
        return f"year={data.get('year', 'unknown')}, empty={bool(data.get('empty'))}"
    plays = int(source.get("total_plays") or 0)
    minutes = float(source.get("total_minutes") or 0)
    tracks = int(source.get("unique_tracks") or 0)
    artists = int(source.get("unique_artists") or 0)
    return f"plays={plays}, minutes={minutes:g}, tracks={tracks}, artists={artists}"


def _entity_result_summary(data: dict[str, Any]) -> str:
    found = bool(data.get("found"))
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    plays = int(summary.get("total_plays") or 0)
    hours = float(summary.get("total_hours") or 0)
    return f"found={str(found).lower()}, plays={plays}, hours={hours:g}"


def _billboard_detail_result_summary(data: dict[str, Any]) -> str:
    found = bool(data.get("found"))
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    chart_summary = data.get("chart_summary") if isinstance(data.get("chart_summary"), dict) else {}
    metric_source = chart_summary or summary
    history = (
        data.get("history") or data.get("album_weekly_history") or data.get("rank_history") or []
    )
    history_weeks = len(history) if isinstance(history, list) else 0
    weeks = int(metric_source.get("weeks_on_chart") or history_weeks)
    peak = metric_source.get("peak_position")

    parts = [f"found={str(found).lower()}"]
    entity_name = (
        data.get("album_name")
        or data.get("track_name")
        or data.get("artist_name")
        or metric_source.get("name")
    )
    if entity_name:
        parts.append(f"album={entity_name}")
    parts.extend([f"weeks={weeks}", f"peak={peak or 'n/a'}"])
    if metric_source.get("no1_weeks") is not None:
        parts.append(f"no1_weeks={int(metric_source.get('no1_weeks') or 0)}")
    if metric_source.get("power_score") is not None:
        parts.append(f"power_score={int(metric_source.get('power_score') or 0)}")
    if metric_source.get("power_rank") is not None:
        parts.append(f"power_rank={int(metric_source.get('power_rank') or 0)}")
    return ", ".join(parts)


def _listening_hours_result_summary(data: dict[str, Any]) -> str:
    items = data.get("items")
    if isinstance(items, list):
        count = len(items)
    elif isinstance(items, dict):
        tracks = items.get("tracks")
        count = len(tracks) if isinstance(tracks, list) else len(items)
    else:
        count = 0
    return f"view={data.get('view')}, items={count}"


def _resolve_entity_result_summary(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    count = len(candidates) if isinstance(candidates, list) else 0
    return f"found={str(bool(data.get('found'))).lower()}, candidates={count}"


def _comparison_result_summary(data: dict[str, Any]) -> str:
    entities = data.get("entities")
    count = len(entities) if isinstance(entities, list) else 0
    return (
        f"entities={count}, "
        f"winner_by_plays={data.get('winner_by_cumulative_plays') or 'n/a'}, "
        f"winner_by_intensity={data.get('winner_by_intensity') or 'n/a'}"
    )


def _account_summary_result_summary(data: dict[str, Any]) -> str:
    counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
    coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}
    return (
        f"status={data.get('status') or 'empty'}, "
        f"saved_tracks={int(counts.get('saved_tracks') or 0)}, "
        f"linked_pct={float(coverage.get('saved_tracks_linked_to_history_pct') or 0):.1f}, "
        f"dated_pct={float(coverage.get('saved_tracks_with_date_pct') or 0):.1f}"
    )


def _collection_result_summary(data: dict[str, Any]) -> str:
    counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
    returns = data.get("returns") if isinstance(data.get("returns"), dict) else {}
    returns_summary = returns.get("summary") if isinstance(returns.get("summary"), dict) else {}
    return (
        f"status={data.get('status') or 'empty'}, "
        f"saved_tracks={int(counts.get('saved_tracks') or 0)}, "
        f"saved_albums={int(counts.get('saved_albums') or 0)}, "
        f"sleeping={int(returns_summary.get('current_sleeping_entities') or 0)}"
    )


def _search_result_summary(data: dict[str, Any]) -> str:
    top_queries = data.get("top_queries")
    top_count = len(top_queries) if isinstance(top_queries, list) else 0
    return (
        f"available={str(bool(data.get('available'))).lower()}, "
        f"total_searches={int(data.get('total_searches') or 0)}, "
        f"top_queries={top_count}"
    )


def _community_feed_result_summary(data: dict[str, Any]) -> str:
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    return (
        f"posts={int(meta.get('returned') or 0)}/{int(meta.get('total') or 0)}, "
        f"highlights_only={str(bool(data.get('highlights_only'))).lower()}"
    )


def _community_trending_result_summary(data: dict[str, Any]) -> str:
    artists = data.get("artists")
    tracks = data.get("tracks")
    return (
        f"artists={len(artists) if isinstance(artists, list) else 0}, "
        f"tracks={len(tracks) if isinstance(tracks, list) else 0}"
    )


def _compact_archive_summary(
    overview: dict[str, Any],
    parsed: AccountSummaryParams,
    *,
    cohorts: dict[str, Any] | None = None,
    discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "schema_version": "account_agent_summary_v2",
        "status": overview.get("status"),
        "counts": overview.get("counts", {}),
        "coverage": overview.get("coverage", {}),
        "period": overview.get("period", {}),
        "capabilities": overview.get("capabilities", {}),
    }
    if parsed.include_collection and cohorts:
        relationship = cohorts.get("relationship_matrix")
        compact["collection"] = {
            "status": cohorts.get("status"),
            "coverage": cohorts.get("coverage", {}),
            "return_windows": cohorts.get("return_windows", []),
            "vitality_metrics": cohorts.get("vitality_metrics", []),
            "relationship_counts": relationship.get("counts", {})
            if isinstance(relationship, dict)
            else {},
        }
    if parsed.include_search and discovery:
        compact["discovery"] = {
            "status": discovery.get("status"),
            "period": discovery.get("period", {}),
            "coverage": discovery.get("coverage", {}),
            "funnel": discovery.get("funnel", {}),
        }
    return compact


def _compact_archive_collection(
    overview: dict[str, Any],
    journey: dict[str, Any],
    cohorts: dict[str, Any],
    returns: dict[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    relationship = cohorts.get("relationship_matrix")
    return {
        "schema_version": "account_agent_collection_v2",
        "status": overview.get("status"),
        "counts": overview.get("counts", {}),
        "coverage": overview.get("coverage", {}),
        "period": overview.get("period", {}),
        "journey": {
            "status": journey.get("status"),
            "coverage": journey.get("coverage", {}),
            "duration": journey.get("duration", {}),
            "annual_growth": journey.get("annual_growth", []),
            "milestones": journey.get("milestones", [])[:limit],
        },
        "relationship": {
            "status": cohorts.get("status"),
            "coverage": cohorts.get("coverage", {}),
            "encounter_to_save": cohorts.get("encounter_to_save", {}),
            "symmetric_30_day_window": cohorts.get("symmetric_30_day_window", {}),
            "return_windows": cohorts.get("return_windows", []),
            "vitality_metrics": cohorts.get("vitality_metrics", []),
            "counts": relationship.get("counts", {}) if isinstance(relationship, dict) else {},
        },
        "returns": {
            "status": returns.get("status"),
            "coverage": returns.get("coverage", {}),
            "summary": returns.get("summary", {}),
            "latest_returns": returns.get("latest_returns", [])[:limit],
            "longest_returns": returns.get("longest_returns", [])[:limit],
            "sleeping_recommendations": returns.get("sleeping_recommendations", [])[:limit],
        },
    }


def _compact_search_stats(
    data: dict[str, Any], *, limit: int, query: str | None = None
) -> dict[str, Any]:
    query_lower = query.casefold() if query else None
    top_queries = data.get("top_queries")
    if isinstance(top_queries, list):
        rows = [
            row
            for row in top_queries
            if isinstance(row, dict)
            and (not query_lower or query_lower in str(row.get("query") or "").casefold())
        ][:limit]
    else:
        rows = []
    intent_dist = data.get("intent_dist")
    return {
        "available": data.get("available"),
        "empty": data.get("empty"),
        "total_searches": data.get("total_searches"),
        "top_queries": rows,
        "intent_dist": intent_dist[:limit] if isinstance(intent_dist, list) else [],
    }


def _post_to_dict(post: Any) -> dict[str, Any]:
    metrics = getattr(post, "metrics", None)
    return {
        "id": getattr(post, "id", None),
        "account_handle": getattr(post, "account_handle", None),
        "posted_at": getattr(post, "posted_at", None),
        "content": getattr(post, "content", None),
        "post_type": getattr(post, "post_type", None),
        "tags": list(getattr(post, "tags", []) or [])[:6],
        "significance": getattr(post, "significance", None),
        "linked_entities": list(getattr(post, "linked_entities", []) or [])[:6],
        "metrics": {
            "likes": getattr(metrics, "likes", 0) if metrics else 0,
            "retweets": getattr(metrics, "retweets", 0) if metrics else 0,
            "replies": getattr(metrics, "replies", 0) if metrics else 0,
            "views": getattr(metrics, "views", 0) if metrics else 0,
        },
    }


def _community_generation_kwargs(parsed: CommunityFeedSearchParams) -> dict[str, Any]:
    return {
        "min_ms": parsed.min_ms,
        "music_only": parsed.music_only,
        "bb_top_n": parsed.bb_top_n,
        "bb_album_top_n": parsed.bb_album_top_n,
        "bb_artist_top_n": parsed.bb_artist_top_n,
        "bb_week_start_dow": parsed.bb_week_start_dow,
        "bb_week_start_hour": parsed.bb_week_start_hour,
        "year_start": parsed.year_start,
        "year_end": parsed.year_end,
        "dynamic_threshold": parsed.dynamic_threshold,
        "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
        "merge_level": parsed.merge_level,
        "include_compilations": parsed.include_compilations,
    }


def _filter_kwargs(parsed: AnalysisStatsParams) -> dict[str, Any]:
    return {
        "min_ms": parsed.min_ms,
        "music_only": parsed.music_only,
        "merge_enabled": parsed.merge_enabled,
        "period": parsed.period,
        "start_date": parsed.start_date,
        "end_date": parsed.end_date,
        "dynamic_threshold": parsed.dynamic_threshold,
        "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
    }


def analysis_stats_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, AnalysisStatsParams)
        else AnalysisStatsParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        data = analysis_stats_service.get_analysis_stats(conn, **_filter_kwargs(parsed))
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_stats_result_summary(data),
        source_range=_source_range(data),
    )


def analysis_charts_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, AnalysisChartsParams)
        else AnalysisChartsParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        if parsed.entity == "album" and parsed.merge_level > 1 and not _album_projects_ready(conn):
            return _album_projects_unavailable("analysis_charts")
        data = analysis_stats_service.get_analysis_charts(
            conn,
            min_ms=parsed.min_ms,
            music_only=parsed.music_only,
            merge_enabled=parsed.merge_enabled,
            period=parsed.period,
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            entity=parsed.entity,
            metric=parsed.metric,
            limit=parsed.limit,
            offset=parsed.offset,
            merge_level=parsed.merge_level,
            dynamic_threshold=parsed.dynamic_threshold,
            max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            include_compilations=parsed.include_compilations,
        )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_charts_result_summary(data),
        source_range=_source_range(data),
    )


def playback_records_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, PlaybackRecordsParams)
        else PlaybackRecordsParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        if parsed.merge_level > 1 and not _album_projects_ready(conn):
            return _album_projects_unavailable("playback_records")
        data = analysis_records_service.get_analysis_records(
            conn,
            **_filter_kwargs(parsed),
            merge_level=parsed.merge_level,
            include_compilations=parsed.include_compilations,
        )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_records_result_summary(data),
        source_range=_source_range(data),
    )


def wrapped_yearly_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, WrappedYearlyParams)
        else WrappedYearlyParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        if parsed.merge_level > 1 and not _album_projects_ready(conn):
            return _album_projects_unavailable("wrapped_yearly")
        data = wrapped_service._build_wrapped_full(
            conn,
            parsed.min_ms,
            parsed.music_only,
            parsed.merge_enabled,
            parsed.year,
            dynamic_threshold=parsed.dynamic_threshold,
            max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            merge_level=parsed.merge_level,
        )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_wrapped_yearly_result_summary(data),
        source_range=_year_source_range(parsed.year),
    )


def entity_stats_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, EntityStatsParams)
        else EntityStatsParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        if parsed.entity == "album" and not _album_projects_ready(conn):
            return _album_projects_unavailable("entity_stats")
        if parsed.entity == "track":
            data = entity_stats_service.get_track_stats(
                conn,
                track_id=int(parsed.track_id or 0),
                **_filter_kwargs(parsed),
            )
        elif parsed.entity == "album":
            data = entity_stats_service.get_album_stats(
                conn,
                album_name=parsed.album_name or "",
                artist=parsed.artist_name,
                **_filter_kwargs(parsed),
                merge_level=parsed.merge_level,
            )
        else:
            data = entity_stats_service.get_artist_stats(
                conn,
                artist_name=parsed.artist_name or "",
                **_filter_kwargs(parsed),
            )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_entity_result_summary(data),
        source_range=_source_range(data),
    )


def billboard_entity_detail_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, BillboardEntityDetailParams)
        else BillboardEntityDetailParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        if parsed.entity == "album" and parsed.merge_level > 1 and not _album_projects_ready(conn):
            return _album_projects_unavailable("billboard_entity_detail")
        if parsed.entity == "track":
            data = billboard_details.get_track_history(
                int(parsed.track_id or 0),
                parsed.min_ms,
                parsed.music_only,
                parsed.bb_top_n,
                parsed.bb_album_top_n,
                parsed.bb_artist_top_n,
                parsed.bb_week_start_dow,
                parsed.bb_week_start_hour,
                parsed.year_start,
                parsed.year_end,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
                merge_level=parsed.merge_level,
            )
        elif parsed.entity == "album":
            data = billboard_details.get_album_chart_detail(
                parsed.album_name or "",
                parsed.artist_name,
                parsed.min_ms,
                parsed.music_only,
                parsed.bb_top_n,
                parsed.bb_album_top_n,
                parsed.bb_artist_top_n,
                parsed.bb_week_start_dow,
                parsed.bb_week_start_hour,
                parsed.year_start,
                parsed.year_end,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
                merge_level=parsed.merge_level,
            )
        else:
            data = billboard_details.get_artist_chart_detail(
                parsed.artist_name or "",
                parsed.min_ms,
                parsed.music_only,
                parsed.bb_top_n,
                parsed.bb_album_top_n,
                parsed.bb_artist_top_n,
                parsed.bb_week_start_dow,
                parsed.bb_week_start_hour,
                parsed.year_start,
                parsed.year_end,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_billboard_detail_result_summary(data),
        source_range=_year_bounds_source_range(parsed.year_start, parsed.year_end),
    )


def listening_hours_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, ListeningHoursParams)
        else ListeningHoursParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        items: Any
        if parsed.view == "heatmap":
            items = play_service.get_listening_heatmap(
                conn,
                min_ms=parsed.min_ms,
                music_only=parsed.music_only,
                merge_enabled=parsed.merge_enabled,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
        elif parsed.view == "yearly_heatmaps":
            items = play_service.get_yearly_heatmaps(
                conn,
                min_ms=parsed.min_ms,
                music_only=parsed.music_only,
                merge_enabled=parsed.merge_enabled,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
        elif parsed.view == "late_night_ratio":
            items = play_service.get_late_night_ratio(
                conn,
                min_ms=parsed.min_ms,
                music_only=parsed.music_only,
                merge_enabled=parsed.merge_enabled,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
        elif parsed.view == "late_night_tracks":
            items = play_service.get_late_night_top_tracks(
                conn,
                min_ms=parsed.min_ms,
                music_only=parsed.music_only,
                merge_enabled=parsed.merge_enabled,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
        elif parsed.view == "weekday_weekend":
            items = play_service.get_weekday_weekend_comparison(
                conn,
                min_ms=parsed.min_ms,
                music_only=parsed.music_only,
                merge_enabled=parsed.merge_enabled,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
        else:
            items = play_service.get_platform_hourly_listening(
                conn,
                min_ms=parsed.min_ms,
                music_only=parsed.music_only,
                merge_enabled=parsed.merge_enabled,
                dynamic_threshold=parsed.dynamic_threshold,
                max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            )
    finally:
        conn.close()

    data = {"view": parsed.view, "items": items}
    return AgentToolResult(
        data=data,
        result_summary=_listening_hours_result_summary(data),
        source_range=parsed.view,
    )


def resolve_entity_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, ResolveEntityParams)
        else ResolveEntityParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        data = resolve_entities(
            conn,
            query=parsed.query,
            entity_type=parsed.entity_type,
            limit=parsed.limit,
        )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=_resolve_entity_result_summary(data),
        source_range="local_tracks",
    )


def _compare_filter_kwargs(parsed: CompareEntitiesParams) -> dict[str, Any]:
    return {
        "min_ms": parsed.min_ms,
        "music_only": parsed.music_only,
        "merge_enabled": parsed.merge_enabled,
        "dynamic_threshold": parsed.dynamic_threshold,
        "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
        "merge_level": parsed.merge_level,
    }


def _compare_billboard_kwargs(parsed: CompareEntitiesParams) -> dict[str, Any]:
    return {
        "min_ms": parsed.min_ms,
        "music_only": parsed.music_only,
        "dynamic_threshold": parsed.dynamic_threshold,
        "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
        "merge_level": parsed.merge_level,
    }


def _track_candidate(name: str) -> dict[str, Any] | None:
    result = resolve_entity_handler(
        ResolveEntityParams(query=name, entity_type="track", limit=1)
    ).data
    candidates = result.get("candidates")
    if not result.get("found") or not isinstance(candidates, list) or not candidates:
        return None
    candidate = candidates[0]
    return candidate if isinstance(candidate, dict) else None


def _metric_source(data: dict[str, Any], entity_type: str) -> dict[str, Any]:
    chart_summary = data.get("chart_summary")
    if isinstance(chart_summary, dict):
        return chart_summary
    summary = data.get("summary")
    if entity_type == "track" and isinstance(summary, dict):
        return summary
    return {}


def _entity_found(*payloads: dict[str, Any]) -> bool:
    explicit_flags = [payload.get("found") for payload in payloads if "found" in payload]
    if explicit_flags:
        return any(bool(flag) for flag in explicit_flags)
    return any(bool(payload.get("summary") or payload.get("chart_summary")) for payload in payloads)


def _entity_errors(*payloads: dict[str, Any]) -> str | None:
    errors: list[str] = []
    for payload in payloads:
        error = payload.get("error")
        if error and str(error) not in errors:
            errors.append(str(error))
    return "; ".join(errors) if errors else None


def _nested_entity_value(payload: dict[str, Any], key: str) -> Any:
    entity = payload.get("entity")
    if isinstance(entity, dict):
        return entity.get(key)
    return None


def _comparison_display_name(
    *,
    requested_name: str,
    entity_type: str,
    playback: dict[str, Any],
    billboard: dict[str, Any],
) -> str:
    if entity_type == "track":
        name = (
            playback.get("track_name")
            or _nested_entity_value(playback, "track_name")
            or billboard.get("track_name")
        )
    elif entity_type == "album":
        name = (
            playback.get("album_name")
            or _nested_entity_value(playback, "album_name")
            or billboard.get("album_name")
        )
    else:
        name = (
            playback.get("artist_name")
            or _nested_entity_value(playback, "artist_name")
            or billboard.get("artist_name")
        )
    return str(name or requested_name)


def _comparison_row(
    *,
    requested_name: str,
    entity_type: str,
    playback: dict[str, Any],
    billboard: dict[str, Any],
    track_id: int | None = None,
) -> dict[str, Any]:
    summary = playback.get("summary") if isinstance(playback.get("summary"), dict) else {}
    metric_source = _metric_source(billboard, entity_type)
    row: dict[str, Any] = {
        "name": _comparison_display_name(
            requested_name=requested_name,
            entity_type=entity_type,
            playback=playback,
            billboard=billboard,
        ),
        "requested_name": requested_name,
        "entity_type": entity_type,
        "found": _entity_found(playback, billboard),
        "plays": summary.get("total_plays"),
        "hours": summary.get("total_hours"),
        "first_play_date": playback.get("first_played")
        or playback.get("first_play_date")
        or summary.get("first_play_date")
        or summary.get("first_played"),
        "latest_play_date": playback.get("last_played")
        or playback.get("latest_play_date")
        or summary.get("latest_play_date")
        or summary.get("last_played"),
        "power_score": metric_source.get("power_score"),
        "power_rank": metric_source.get("power_rank"),
        "no1_weeks": metric_source.get("no1_weeks")
        if metric_source.get("no1_weeks") is not None
        else metric_source.get("weeks_at_no1"),
        "weeks_on_chart": metric_source.get("weeks_on_chart"),
        "peak_position": metric_source.get("peak_position"),
    }
    if track_id is not None:
        row["track_id"] = track_id
    if error := _entity_errors(playback, billboard):
        row["error"] = error
    elif row["found"] is False:
        row["error"] = "not found in local evidence"
    return row


def _missing_comparison_row(
    *,
    requested_name: str,
    entity_type: str,
    error: str,
) -> dict[str, Any]:
    return {
        "name": requested_name,
        "requested_name": requested_name,
        "entity_type": entity_type,
        "found": False,
        "error": error,
    }


def _compare_album_or_artist_row(parsed: CompareEntitiesParams, name: str) -> dict[str, Any]:
    base_params: dict[str, Any] = {
        "entity": parsed.entity_type,
        **_compare_filter_kwargs(parsed),
    }
    billboard_params: dict[str, Any] = {
        "entity": parsed.entity_type,
        **_compare_billboard_kwargs(parsed),
    }
    if parsed.entity_type == "album":
        base_params["album_name"] = name
        billboard_params["album_name"] = name
    else:
        base_params["artist_name"] = name
        billboard_params["artist_name"] = name

    playback = entity_stats_handler(EntityStatsParams.model_validate(base_params)).data
    billboard = billboard_entity_detail_handler(
        BillboardEntityDetailParams.model_validate(billboard_params)
    ).data
    return _comparison_row(
        requested_name=name,
        entity_type=parsed.entity_type,
        playback=playback,
        billboard=billboard,
    )


def _compare_track_row(parsed: CompareEntitiesParams, name: str) -> dict[str, Any]:
    candidate = _track_candidate(name)
    if candidate is None:
        return _missing_comparison_row(
            requested_name=name,
            entity_type="track",
            error="track not found in local listening data",
        )
    track_id = candidate.get("track_id")
    if track_id is None:
        return _missing_comparison_row(
            requested_name=name,
            entity_type="track",
            error="resolved track candidate has no track_id",
        )

    playback = entity_stats_handler(
        EntityStatsParams.model_validate(
            {
                "entity": "track",
                "track_id": int(track_id),
                **_compare_filter_kwargs(parsed),
            }
        )
    ).data
    billboard = billboard_entity_detail_handler(
        BillboardEntityDetailParams.model_validate(
            {
                "entity": "track",
                "track_id": int(track_id),
                **_compare_billboard_kwargs(parsed),
            }
        )
    ).data
    return _comparison_row(
        requested_name=name,
        entity_type="track",
        playback={**playback, "track_name": playback.get("track_name") or candidate.get("name")},
        billboard=billboard,
        track_id=int(track_id),
    )


def compare_entities_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, CompareEntitiesParams)
        else CompareEntitiesParams.model_validate(params)
    )
    rows = [
        _compare_track_row(parsed, name)
        if parsed.entity_type == "track"
        else _compare_album_or_artist_row(parsed, name)
        for name in parsed.names
    ]
    data = summarize_entity_comparison(entity_type=parsed.entity_type, entities=rows)
    return AgentToolResult(
        data=data,
        result_summary=_comparison_result_summary(data),
        source_range="comparison",
    )


def account_summary_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, AccountSummaryParams)
        else AccountSummaryParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        overview = get_archive_overview(conn)
        context = build_archive_filter_context(conn, {})
        cohorts = get_collection_cohorts(conn, context) if parsed.include_collection else None
        discovery = get_archive_discovery(conn, context) if parsed.include_search else None
    finally:
        conn.close()
    data = _compact_archive_summary(
        overview,
        parsed,
        cohorts=cohorts,
        discovery=discovery,
    )
    return AgentToolResult(
        data=data,
        result_summary=_account_summary_result_summary(data),
        source_range="account",
    )


def account_collection_insights_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, AccountCollectionInsightsParams)
        else AccountCollectionInsightsParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        overview = get_archive_overview(conn)
        context = build_archive_filter_context(conn, {})
        journey = get_collection_journey(conn, context)
        cohorts = get_collection_cohorts(conn, context)
        returns = get_archive_returns(conn, context)
    finally:
        conn.close()
    data = _compact_archive_collection(
        overview,
        journey,
        cohorts,
        returns,
        limit=parsed.limit,
    )
    return AgentToolResult(
        data=data,
        result_summary=_collection_result_summary(data),
        source_range="account_collection",
    )


def search_history_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, SearchHistoryParams)
        else SearchHistoryParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        raw_data = search_service.get_search_stats(conn)
    finally:
        conn.close()
    data = _compact_search_stats(raw_data, limit=parsed.limit, query=parsed.query)
    return AgentToolResult(
        data=data,
        result_summary=_search_result_summary(data),
        source_range="search_history",
    )


def _community_posts(parsed: CommunityFeedSearchParams) -> list[Any]:
    conn = get_db(readonly=True)
    try:
        return community_feed_generator.generate_all_posts(
            conn=conn,
            **_community_generation_kwargs(parsed),
        )
    finally:
        conn.close()


def community_feed_search_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, CommunityFeedSearchParams)
        else CommunityFeedSearchParams.model_validate(params)
    )
    posts = _community_posts(parsed)
    search_lower = parsed.search.casefold() if parsed.search else None
    filtered = []
    total_all = 0
    for post in posts:
        posted_at = str(getattr(post, "posted_at", "") or "")
        if parsed.date_from and posted_at < parsed.date_from:
            continue
        if parsed.date_to and posted_at > parsed.date_to:
            continue
        if search_lower:
            linked_entities = getattr(post, "linked_entities", []) or []
            content_match = search_lower in str(getattr(post, "content", "") or "").casefold()
            handle_match = search_lower in str(getattr(post, "account_handle", "") or "").casefold()
            entity_match = any(
                search_lower in str(entity.get("name", "")).casefold()
                for entity in linked_entities
                if isinstance(entity, dict)
            )
            if not (content_match or handle_match or entity_match):
                continue
        total_all += 1
        if not parsed.highlights_only or getattr(post, "post_type", "") in HIGHLIGHT_POST_TYPES:
            filtered.append(post)
    page = filtered[: parsed.limit]
    data = {
        "meta": {
            "total": len(filtered),
            "total_all": total_all,
            "returned": len(page),
            "limit": parsed.limit,
        },
        "highlights_only": parsed.highlights_only,
        "posts": [_post_to_dict(post) for post in page],
    }
    return AgentToolResult(
        data=data,
        result_summary=_community_feed_result_summary(data),
        source_range="community_feed",
    )


def community_trending_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, CommunityTrendingParams)
        else CommunityTrendingParams.model_validate(params)
    )
    posts = _community_posts(parsed)
    artist_counts: dict[str, int] = {}
    track_counts: dict[str, int] = {}
    track_to_id: dict[str, str | int] = {}
    latest_no1_post: Any | None = None
    latest_debut_post: Any | None = None

    for post in posts:
        posted_at = str(getattr(post, "posted_at", "") or "")
        if parsed.date_from and posted_at < parsed.date_from:
            continue
        if parsed.date_to and posted_at > parsed.date_to:
            continue
        post_type = getattr(post, "post_type", "")
        if latest_no1_post is None and post_type == "no1_announcement":
            latest_no1_post = post
        if latest_debut_post is None and post_type == "debut":
            latest_debut_post = post
        for entity in getattr(post, "linked_entities", []) or []:
            if not isinstance(entity, dict):
                continue
            name = str(entity.get("name") or "")
            if not name:
                continue
            if entity.get("type") == "artist":
                artist_counts[name] = artist_counts.get(name, 0) + 1
            elif entity.get("type") == "track":
                track_counts[name] = track_counts.get(name, 0) + 1
                if entity.get("id") is not None and name not in track_to_id:
                    track_to_id[name] = entity["id"]

    def linked_entity(post: Any | None, entity_type: str) -> dict[str, Any] | None:
        if post is None:
            return None
        for entity in getattr(post, "linked_entities", []) or []:
            if isinstance(entity, dict) and entity.get("type") == entity_type:
                return entity
        return None

    no1_track = linked_entity(latest_no1_post, "track")
    no1_artist = linked_entity(latest_no1_post, "artist")
    debut_track = linked_entity(latest_debut_post, "track")
    debut_artist = linked_entity(latest_debut_post, "artist")
    top_artists = sorted(artist_counts.items(), key=lambda item: item[1], reverse=True)[
        : parsed.artist_limit
    ]
    top_tracks = sorted(track_counts.items(), key=lambda item: item[1], reverse=True)[
        : parsed.track_limit
    ]
    data = {
        "artists": [{"name": name, "count": count} for name, count in top_artists],
        "tracks": [
            {"name": name, "count": count, "entity_id": track_to_id.get(name)}
            for name, count in top_tracks
        ],
        "latest_no1": {
            "track": no1_track.get("name") if no1_track else None,
            "artist": no1_artist.get("name") if no1_artist else None,
            "post_id": getattr(latest_no1_post, "id", None) if latest_no1_post else None,
        }
        if latest_no1_post
        else None,
        "latest_debut": {
            "track": debut_track.get("name") if debut_track else None,
            "artist": debut_artist.get("name") if debut_artist else None,
            "post_id": getattr(latest_debut_post, "id", None) if latest_debut_post else None,
        }
        if latest_debut_post
        else None,
    }
    return AgentToolResult(
        data=data,
        result_summary=_community_trending_result_summary(data),
        source_range="community_trending",
    )


ANALYSIS_STATS_TOOL = AgentToolDefinition(
    name="analysis_stats",
    description="Read compact listening statistics for a bounded period.",
    read_only=True,
    params_model=AnalysisStatsParams,
    handler=analysis_stats_handler,
)

ANALYSIS_CHARTS_TOOL = AgentToolDefinition(
    name="analysis_charts",
    description="Read ranked track, album, or artist charts for a bounded period.",
    read_only=True,
    params_model=AnalysisChartsParams,
    handler=analysis_charts_handler,
)

PLAYBACK_RECORDS_TOOL = AgentToolDefinition(
    name="playback_records",
    description="Read listening record highlights such as champions, streaks, and milestones.",
    read_only=True,
    params_model=PlaybackRecordsParams,
    handler=playback_records_handler,
)

WRAPPED_YEARLY_TOOL = AgentToolDefinition(
    name="wrapped_yearly",
    description="Read the full yearly Wrapped-style listening summary for one year.",
    read_only=True,
    params_model=WrappedYearlyParams,
    handler=wrapped_yearly_handler,
)

ENTITY_STATS_TOOL = AgentToolDefinition(
    name="entity_stats",
    description="Read track, album, or artist detail statistics from local listening history.",
    read_only=True,
    params_model=EntityStatsParams,
    handler=entity_stats_handler,
)

BILLBOARD_ENTITY_DETAIL_TOOL = AgentToolDefinition(
    name="billboard_entity_detail",
    description="Read Billboard-style chart detail for a known track, album, or artist.",
    read_only=True,
    params_model=BillboardEntityDetailParams,
    handler=billboard_entity_detail_handler,
)

LISTENING_HOURS_TOOL = AgentToolDefinition(
    name="listening_hours",
    description="Read listening-hour heatmaps and time-of-day breakdowns.",
    read_only=True,
    params_model=ListeningHoursParams,
    handler=listening_hours_handler,
)

RESOLVE_ENTITY_TOOL = AgentToolDefinition(
    name="resolve_entity",
    description="Resolve a user-provided album, artist, or track name against local listening data.",
    read_only=True,
    params_model=ResolveEntityParams,
    handler=resolve_entity_handler,
)

COMPARE_ENTITIES_TOOL = AgentToolDefinition(
    name="compare_entities",
    description=(
        "Compare two to four known tracks, albums, or artists using local playback "
        "statistics and personal Billboard evidence."
    ),
    read_only=True,
    params_model=CompareEntitiesParams,
    handler=compare_entities_handler,
)

ACCOUNT_SUMMARY_TOOL = AgentToolDefinition(
    name="account_summary",
    description=(
        "Read a compact privacy-whitelisted music archive overview with library counts, "
        "coverage, relationship windows, and aggregate discovery signals."
    ),
    read_only=True,
    params_model=AccountSummaryParams,
    handler=account_summary_handler,
)

ACCOUNT_COLLECTION_INSIGHTS_TOOL = AgentToolDefinition(
    name="account_collection_insights",
    description=(
        "Read evidence-backed saved-library journey, fixed-window playback relationships, "
        "returns, and sleeping collection facts."
    ),
    read_only=True,
    params_model=AccountCollectionInsightsParams,
    handler=account_collection_insights_handler,
)

SEARCH_HISTORY_TOOL = AgentToolDefinition(
    name="search_history",
    description="Read compact Spotify search-history statistics and top queries.",
    read_only=True,
    params_model=SearchHistoryParams,
    handler=search_history_handler,
)

COMMUNITY_FEED_SEARCH_TOOL = AgentToolDefinition(
    name="community_feed_search",
    description="Read generated community feed posts filtered by search text or date range.",
    read_only=True,
    params_model=CommunityFeedSearchParams,
    handler=community_feed_search_handler,
)

COMMUNITY_TRENDING_TOOL = AgentToolDefinition(
    name="community_trending",
    description="Read trending artists, tracks, latest #1, and debut signals from community posts.",
    read_only=True,
    params_model=CommunityTrendingParams,
    handler=community_trending_handler,
)
