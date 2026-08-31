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
from backend.domains.ai_agent.entity_comparison_service import build_entity_comparison_rows
from backend.domains.ai_agent.entity_resolver import resolve_entities
from backend.domains.ai_agent.tool_cache import (
    cache_tool_result,
    get_cached_tool_result,
    make_cache_key,
)
from backend.domains.ai_agent.tool_registry import AgentToolDefinition, AgentToolResult
from backend.domains.billboard import details as billboard_details
from backend.domains.community import feed_generator as community_feed_generator
from backend.domains.community.post_types import HIGHLIGHT_POST_TYPES
from backend.domains.metadata.genre_display_taxonomy import build_consumer_taste_profile
from backend.domains.music_search.context import build_music_search_filter_context
from backend.domains.music_search.normalization import normalize_search_text
from backend.domains.music_search.snapshot import get_serving_music_search_snapshot
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
    max_merge_gap_minutes: int | None = Field(default=5, ge=1, le=240)
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
    merge_level: int = Field(default=2, ge=2, le=3)
    include_compilations: bool = False


class TasteProfileParams(AnalysisStatsParams):
    """A bounded taste-only read that avoids building unrelated stats panels."""


class PlaybackRecordsParams(AnalysisStatsParams):
    merge_level: int = Field(default=2, ge=2, le=3)
    include_compilations: bool = False


class WrappedYearlyParams(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=5, ge=1, le=240)
    merge_level: int = Field(default=2, ge=2, le=3)


class EntityStatsParams(AnalysisStatsParams):
    entity: Literal["track", "album", "artist"] = "track"
    track_id: int | None = Field(default=None, ge=1)
    album_name: str | None = Field(default=None, min_length=1, max_length=300)
    artist_name: str | None = Field(default=None, min_length=1, max_length=300)
    merge_level: int = Field(default=2, ge=2, le=3)

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
    max_merge_gap_minutes: int | None = Field(default=5, ge=1, le=240)
    merge_level: int = Field(default=2, ge=2, le=3)

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
    max_merge_gap_minutes: int | None = Field(default=5, ge=1, le=240)


class ResolveEntityParams(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    entity_type: Literal["track", "album", "artist"] = "album"
    limit: int = Field(default=5, ge=1, le=10)


class CompareEntitiesParams(AnalysisStatsParams):
    entity_type: Literal["track", "album", "artist"] = "album"
    names: list[str] = Field(..., min_length=2, max_length=4)
    merge_level: int = Field(default=2, ge=2, le=3)
    include_billboard: bool = True

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
    max_merge_gap_minutes: int | None = Field(default=5, ge=1, le=240)
    merge_level: int = Field(default=2, ge=2, le=3)
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


def _taste_profile_result_summary(data: dict[str, Any]) -> str:
    profile = data.get("taste_profile")
    if not isinstance(profile, dict):
        return "taste profile unavailable"
    styles = profile.get("primary_styles")
    languages = profile.get("language_dist")
    style_buckets = styles.get("buckets") if isinstance(styles, dict) else []
    language_buckets = languages.get("buckets") if isinstance(languages, dict) else []
    return (
        f"styles={len(style_buckets) if isinstance(style_buckets, list) else 0}, "
        f"languages={len(language_buckets) if isinstance(language_buckets, list) else 0}"
    )


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
        cache_key = make_cache_key(conn, tool_name="analysis_stats", params=parsed)
        if cached := get_cached_tool_result(cache_key):
            return cached
        data = analysis_stats_service.get_analysis_stats(conn, **_filter_kwargs(parsed))
    finally:
        conn.close()
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    if int(summary.get("total_plays") or 0) == 0:
        data = {**data, "status": "empty"}
    result = AgentToolResult(
        data=data,
        result_summary=_stats_result_summary(data),
        source_range=_source_range(data),
    )
    cache_tool_result(cache_key, result)
    return result


def taste_profile_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, TasteProfileParams)
        else TasteProfileParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        cache_key = make_cache_key(conn, tool_name="taste_profile", params=parsed)
        if cached := get_cached_tool_result(cache_key):
            return cached
        _, plays, resolved = analysis_stats_service.load_period_plays(
            conn,
            parsed.min_ms,
            parsed.music_only,
            parsed.merge_enabled,
            parsed.period,
            parsed.start_date,
            parsed.end_date,
            dynamic_threshold=parsed.dynamic_threshold,
            max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            attach_duration_slices=False,
        )
        data = {
            "period": resolved,
            "taste_profile": build_consumer_taste_profile(conn, plays),
        }
    finally:
        conn.close()
    result = AgentToolResult(
        data=data,
        result_summary=_taste_profile_result_summary(data),
        source_range=_source_range(data),
    )
    cache_tool_result(cache_key, result)
    return result


def _ready_yearly_chart(
    conn: sqlite3.Connection,
    parsed: AnalysisChartsParams,
) -> dict[str, Any] | None:
    """Reuse an exact ready annual artifact without ever triggering a build."""
    if parsed.period != "custom" or not parsed.start_date or not parsed.end_date:
        return None
    try:
        start = date.fromisoformat(parsed.start_date)
        end = date.fromisoformat(parsed.end_date)
    except ValueError:
        return None
    if start.month != 1 or start.day != 1 or end.month != 12 or end.day != 31:
        return None
    if start.year != end.year:
        return None

    from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository
    from backend.domains.yearly_review.context import build_yearly_review_context
    from backend.services.yearly_review_service import get_cached_yearly_review

    settings = SettingsRepository(conn).load_all()
    context = build_yearly_review_context(
        conn,
        {
            "min_ms": parsed.min_ms,
            "music_only": parsed.music_only,
            "merge_enabled": parsed.merge_enabled,
            "dynamic_threshold": parsed.dynamic_threshold,
            "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
            "merge_level": parsed.merge_level,
            "include_compilations": parsed.include_compilations,
            "bb_top_n": settings.get("bb_top_n", SETTINGS_DEFAULTS["bb_top_n"]),
            "bb_album_top_n": settings.get("bb_album_top_n", SETTINGS_DEFAULTS["bb_album_top_n"]),
            "bb_artist_top_n": settings.get(
                "bb_artist_top_n", SETTINGS_DEFAULTS["bb_artist_top_n"]
            ),
            "bb_week_start_dow": settings.get(
                "bb_week_start_dow", SETTINGS_DEFAULTS["bb_week_start_dow"]
            ),
            "bb_week_start_hour": settings.get(
                "bb_week_start_hour", SETTINGS_DEFAULTS["bb_week_start_hour"]
            ),
        },
    )
    report = get_cached_yearly_review(start.year, context)
    if report is None:
        return None
    key = f"{parsed.entity}_by_{parsed.metric}"
    available_rows = report.appendix.play_charts.get(key) or []
    requested_end = parsed.offset + parsed.limit
    if requested_end > len(available_rows):
        return None
    total = len(available_rows)
    metric_key = {
        "track": "unique_tracks",
        "album": "unique_albums",
        "artist": "unique_artists",
    }[parsed.entity]
    if report.passport is not None:
        metric = next(
            (item for item in report.passport.metrics if item.key == metric_key),
            None,
        )
        if metric is not None and isinstance(metric.value, (int, float)):
            total = int(metric.value)
    return {
        "period": {
            "period": "custom",
            "label": "自定义",
            "start_date": parsed.start_date,
            "end_date": parsed.end_date,
        },
        "entity": parsed.entity,
        "metric": parsed.metric,
        "total": total,
        "limit": parsed.limit,
        "offset": parsed.offset,
        "rows": [dict(row) for row in available_rows[parsed.offset : requested_end]],
        "cache_source": "yearly_review_ready_artifact",
    }


def analysis_charts_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, AnalysisChartsParams)
        else AnalysisChartsParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        cache_key = make_cache_key(conn, tool_name="analysis_charts", params=parsed)
        if cached := get_cached_tool_result(cache_key):
            return cached
        if parsed.entity == "album" and parsed.merge_level > 1 and not _album_projects_ready(conn):
            return _album_projects_unavailable("analysis_charts")
        data = _ready_yearly_chart(conn, parsed)
        if data is None:
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
    if not data.get("rows"):
        data = {**data, "status": "empty"}
    result = AgentToolResult(
        data=data,
        result_summary=_charts_result_summary(data),
        source_range=_source_range(data),
    )
    cache_tool_result(cache_key, result)
    return result


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
    if data.get("empty") is True:
        data = {**data, "status": "empty"}
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
        cache_key = make_cache_key(conn, tool_name="entity_stats", params=parsed)
        if cached := get_cached_tool_result(cache_key):
            return cached
        if parsed.entity == "album" and not _album_projects_ready(conn):
            return _album_projects_unavailable("entity_stats")
        if parsed.entity == "track":
            data = entity_stats_service.get_track_stats(
                conn,
                track_id=int(parsed.track_id or 0),
                **_filter_kwargs(parsed),
                merge_level=parsed.merge_level,
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
    result = AgentToolResult(
        data=data,
        result_summary=_entity_result_summary(data),
        source_range=_source_range(data),
    )
    cache_tool_result(cache_key, result)
    return result


def billboard_entity_detail_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, BillboardEntityDetailParams)
        else BillboardEntityDetailParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        cache_key = make_cache_key(
            conn,
            tool_name="billboard_entity_detail",
            params=parsed,
            include_billboard=True,
        )
        if cached := get_cached_tool_result(cache_key):
            return cached
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
    result = AgentToolResult(
        data=data,
        result_summary=_billboard_detail_result_summary(data),
        source_range=_year_bounds_source_range(parsed.year_start, parsed.year_end),
    )
    cache_tool_result(cache_key, result)
    return result


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
        "period": parsed.period,
        "start_date": parsed.start_date,
        "end_date": parsed.end_date,
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
        "period": playback.get("period"),
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
    billboard = (
        billboard_entity_detail_handler(
            BillboardEntityDetailParams.model_validate(billboard_params)
        ).data
        if parsed.include_billboard
        else {}
    )
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
    billboard = (
        billboard_entity_detail_handler(
            BillboardEntityDetailParams.model_validate(
                {
                    "entity": "track",
                    "track_id": int(track_id),
                    **_compare_billboard_kwargs(parsed),
                }
            )
        ).data
        if parsed.include_billboard
        else {}
    )
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
    conn = get_db(readonly=True)
    try:
        cache_key = make_cache_key(
            conn,
            tool_name="compare_entities",
            params=parsed,
            include_billboard=parsed.include_billboard,
        )
        if cached := get_cached_tool_result(cache_key):
            return cached
        if parsed.entity_type == "album" and not _album_projects_ready(conn):
            return _album_projects_unavailable("compare_entities")
        rows = build_entity_comparison_rows(
            conn,
            entity_type=parsed.entity_type,
            names=parsed.names,
            min_ms=parsed.min_ms,
            music_only=parsed.music_only,
            merge_enabled=parsed.merge_enabled,
            period=parsed.period,
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            dynamic_threshold=parsed.dynamic_threshold,
            max_merge_gap_minutes=parsed.max_merge_gap_minutes,
            merge_level=parsed.merge_level,
            include_billboard=parsed.include_billboard,
        )
    finally:
        conn.close()
    data = summarize_entity_comparison(entity_type=parsed.entity_type, entities=rows)
    data["period"] = {
        "period": parsed.period,
        "start_date": parsed.start_date,
        "end_date": parsed.end_date,
    }
    data["includes_personal_billboard"] = parsed.include_billboard
    source_range = (
        f"{parsed.start_date or ''}..{parsed.end_date or ''}"
        if parsed.period == "custom"
        else parsed.period
    )
    result = AgentToolResult(
        data=data,
        result_summary=_comparison_result_summary(data),
        source_range=source_range,
    )
    cache_tool_result(cache_key, result)
    return result


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


def _community_posts(
    conn: sqlite3.Connection,
    parsed: CommunityFeedSearchParams,
) -> list[Any]:
    return community_feed_generator.generate_all_posts(
        conn=conn,
        **_community_generation_kwargs(parsed),
        include_cover_images=False,
        include_engagement_metrics=False,
    )


def _community_snapshot_search(
    conn: sqlite3.Connection,
    parsed: CommunityFeedSearchParams,
) -> dict[str, Any] | None:
    """Build scoped community activity cards from a ready search snapshot.

    The public community feed replays every historical chart week because it
    must derive global records and milestones.  A text search does not need
    that full history.  Reuse the exact/LKG music-search chart ledger instead,
    while keeping the response honest about snapshot freshness.
    """

    if not parsed.search:
        return None
    normalized = normalize_search_text(parsed.search)
    if not normalized or normalized.startswith("@"):
        return None
    context = build_music_search_filter_context(conn, parsed)
    serving = get_serving_music_search_snapshot(
        conn,
        filter_fingerprint=context.filter_fingerprint,
        merge_level=parsed.merge_level,
        dynamic_threshold=parsed.dynamic_threshold,
    )
    snapshot_key = serving.get("snapshot_key")
    if not isinstance(snapshot_key, str) or not snapshot_key:
        return None
    generation = conn.execute(
        "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
    ).fetchone()
    if generation is None or not generation[0]:
        return None

    conditions = [
        "d.generation_id=?",
        "w.snapshot_key=?",
        "(d.kind='artist' OR d.merge_level=?)",
        "(instr(d.normalized_label, ?) > 0 "
        "OR instr(d.normalized_secondary, ?) > 0 "
        "OR instr(d.normalized_alias, ?) > 0)",
        "w.family=CASE d.kind WHEN 'album_project' THEN 'album' ELSE d.kind END",
    ]
    values: list[Any] = [
        str(generation[0]),
        snapshot_key,
        parsed.merge_level,
        normalized,
        normalized,
        normalized,
    ]
    if parsed.date_from:
        conditions.append("w.week>=?")
        values.append(parsed.date_from[:10])
    if parsed.date_to:
        conditions.append("w.week<=?")
        values.append(parsed.date_to[:10])
    if parsed.year_start is not None:
        conditions.append("w.week>=?")
        values.append(f"{parsed.year_start:04d}-01-01")
    if parsed.year_end is not None:
        conditions.append("w.week<=?")
        values.append(f"{parsed.year_end:04d}-12-31")
    if parsed.highlights_only:
        conditions.append("w.rank=1")

    query = f"""
        SELECT d.entity_key, d.kind, d.label, d.secondary,
               d.artist_name, d.album_name,
               w.week, w.rank, w.play_count, w.total_ms
          FROM music_search_documents d
          JOIN music_search_weekly_chart_context w
            ON w.entity_key=d.entity_key
         WHERE {" AND ".join(conditions)}
         ORDER BY w.week DESC, w.rank ASC,
                  CASE d.kind WHEN 'artist' THEN 0 WHEN 'album_project' THEN 1 ELSE 2 END,
                  d.entity_key
         LIMIT ?
    """
    values.append(parsed.limit + 1)
    rows = conn.execute(query, values).fetchall()
    if not rows:
        return {
            "status": "empty",
            "retrieval_mode": "scoped_chart_snapshot",
            "snapshot": serving,
            "meta": {"total": 0, "total_all": 0, "returned": 0, "limit": parsed.limit},
            "highlights_only": parsed.highlights_only,
            "posts": [],
        }

    posts: list[dict[str, Any]] = []
    for row in rows[: parsed.limit]:
        kind = str(row[1])
        family = "album" if kind == "album_project" else kind
        label = str(row[2])
        artist_name = str(row[4] or "")
        if family == "artist":
            subject = label
        elif artist_name:
            subject = f"{label} — {artist_name}"
        else:
            subject = label
        family_label = {"artist": "艺人", "album": "专辑", "track": "单曲"}.get(family, "音乐")
        posts.append(
            {
                "id": f"snapshot:{snapshot_key[:12]}:{family}:{row[0]}:{row[6]}",
                "account_handle": "@spotifydata",
                "posted_at": str(row[6]),
                "content": (
                    f"本周个人{family_label}榜：{subject} 排名第 {int(row[7])}，"
                    f"播放 {int(row[8])} 次。"
                ),
                "post_type": "scoped_chart_activity",
                "tags": ["weekly", "chart", "scoped_search"],
                "significance": 1.0 if int(row[7]) == 1 else 0.55,
                "linked_entities": [
                    {
                        "type": family,
                        "name": label,
                        "id": str(row[0]).split(":", 1)[-1],
                    },
                    *(
                        [{"type": "artist", "name": artist_name}]
                        if artist_name and family != "artist"
                        else []
                    ),
                ],
                "metrics": {"likes": 0, "retweets": 0, "replies": 0, "views": 0},
                "chart": {
                    "family": family,
                    "week": str(row[6]),
                    "rank": int(row[7]),
                    "play_count": int(row[8]),
                    "total_ms": int(row[9]),
                },
            }
        )
    return {
        "retrieval_mode": "scoped_chart_snapshot",
        "snapshot": serving,
        "meta": {
            "total": len(rows),
            "total_all": len(rows),
            "returned": len(posts),
            "limit": parsed.limit,
            "has_more": len(rows) > parsed.limit,
        },
        "highlights_only": parsed.highlights_only,
        "posts": posts,
        "limitations": [
            "文本窄查询返回确定性周榜活动卡片；全历史纪录与里程碑帖子仍由完整社区 Feed 生成。"
        ],
    }


def community_feed_search_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, CommunityFeedSearchParams)
        else CommunityFeedSearchParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        cache_key = make_cache_key(
            conn,
            tool_name="community_feed_search",
            params=parsed,
            include_billboard=True,
        )
        if cached := get_cached_tool_result(cache_key):
            return cached
        scoped = _community_snapshot_search(conn, parsed)
        if scoped is not None:
            result = AgentToolResult(
                data=scoped,
                result_summary=_community_feed_result_summary(scoped),
                source_range="community_feed:scoped_chart_snapshot",
            )
            cache_tool_result(cache_key, result)
            return result
        posts = _community_posts(conn, parsed)
    finally:
        conn.close()
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
    result = AgentToolResult(
        data=data,
        result_summary=_community_feed_result_summary(data),
        source_range="community_feed",
    )
    cache_tool_result(cache_key, result)
    return result


def community_trending_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, CommunityTrendingParams)
        else CommunityTrendingParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        cache_key = make_cache_key(
            conn,
            tool_name="community_trending",
            params=parsed,
            include_billboard=True,
        )
        if cached := get_cached_tool_result(cache_key):
            return cached
        posts = _community_posts(conn, parsed)
    finally:
        conn.close()
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
    result = AgentToolResult(
        data=data,
        result_summary=_community_trending_result_summary(data),
        source_range="community_trending",
    )
    cache_tool_result(cache_key, result)
    return result


ANALYSIS_STATS_TOOL = AgentToolDefinition(
    name="analysis_stats",
    description="Read compact listening statistics for a bounded period.",
    read_only=True,
    params_model=AnalysisStatsParams,
    handler=analysis_stats_handler,
    cost="medium",
    timeout_seconds=45,
    cacheability="revision",
    best_for=("周期概览", "播放习惯摘要", "轻量统计核对"),
    covers=("cumulative", "period", "behavior"),
    cold_build_risk="low",
    avoid_when=("需要实体排行明细", "需要单个实体详情"),
    fallback=("analysis_charts",),
)

ANALYSIS_CHARTS_TOOL = AgentToolDefinition(
    name="analysis_charts",
    description="Read ranked track, album, or artist charts for a bounded period.",
    read_only=True,
    params_model=AnalysisChartsParams,
    handler=analysis_charts_handler,
    cost="high",
    timeout_seconds=60,
    cacheability="revision",
    best_for=("Top N 排行", "周期排行", "排行趋势核对"),
    covers=("ranking", "cumulative", "recency", "period", "trend"),
    cold_build_risk="medium",
    avoid_when=("比较 2-4 个已知实体", "只需要轻量总览"),
    fallback=("analysis_stats",),
)

TASTE_PROFILE_TOOL = AgentToolDefinition(
    name="taste_profile",
    description=(
        "Read structured style, regional-pop, and language distributions for a bounded period."
    ),
    read_only=True,
    params_model=TasteProfileParams,
    handler=taste_profile_handler,
    cost="medium",
    timeout_seconds=45,
    cacheability="revision",
    best_for=("曲风与类型分布", "语种分布", "地区流行偏好"),
    covers=("taste", "period"),
    cold_build_risk="low",
    avoid_when=("只需要歌曲、专辑或艺人排行",),
    fallback=("analysis_stats",),
)

PLAYBACK_RECORDS_TOOL = AgentToolDefinition(
    name="playback_records",
    description="Read listening record highlights such as champions, streaks, and milestones.",
    read_only=True,
    params_model=PlaybackRecordsParams,
    handler=playback_records_handler,
    best_for=("冠军记录", "连续播放纪录", "播放里程碑"),
    covers=("consistency", "peak", "behavior"),
    cold_build_risk="low",
    avoid_when=("普通排行", "实体间比较"),
    fallback=("analysis_stats",),
)

WRAPPED_YEARLY_TOOL = AgentToolDefinition(
    name="wrapped_yearly",
    description="Read the full yearly Wrapped-style listening summary for one year.",
    read_only=True,
    params_model=WrappedYearlyParams,
    handler=wrapped_yearly_handler,
    cost="medium",
    cacheability="revision",
    best_for=("单个完整年份总结", "年度排行与习惯"),
    covers=("cumulative", "ranking", "period", "behavior"),
    cold_build_risk="medium",
    avoid_when=("非完整自然年窗口", "实体间比较"),
    fallback=("analysis_stats", "analysis_charts"),
)

ENTITY_STATS_TOOL = AgentToolDefinition(
    name="entity_stats",
    description="Read track, album, or artist detail statistics from local listening history.",
    read_only=True,
    params_model=EntityStatsParams,
    handler=entity_stats_handler,
    cost="high",
    timeout_seconds=60,
    cacheability="revision",
    best_for=("单个歌曲专辑或艺人详情", "实体内部歌曲或专辑排行", "单实体趋势"),
    covers=("scope", "detail", "cumulative", "recency", "intensity", "ranking", "trend"),
    cold_build_risk="medium",
    avoid_when=("比较 2-4 个已知同类实体",),
    fallback=("resolve_entity", "analysis_charts"),
)

BILLBOARD_ENTITY_DETAIL_TOOL = AgentToolDefinition(
    name="billboard_entity_detail",
    description="Read Billboard-style chart detail for a known track, album, or artist.",
    read_only=True,
    params_model=BillboardEntityDetailParams,
    handler=billboard_entity_detail_handler,
    cost="high",
    timeout_seconds=120,
    cacheability="revision",
    best_for=("明确询问个人 Billboard", "Power Score", "峰值与在榜周"),
    covers=("personal_billboard", "consistency", "peak", "detail"),
    cold_build_risk="high",
    avoid_when=("用户未明确询问个人 Billboard", "只比较本地播放次数或时长"),
    fallback=("entity_stats",),
)

LISTENING_HOURS_TOOL = AgentToolDefinition(
    name="listening_hours",
    description="Read listening-hour heatmaps and time-of-day breakdowns.",
    read_only=True,
    params_model=ListeningHoursParams,
    handler=listening_hours_handler,
    cost="medium",
    cacheability="revision",
    best_for=("时段热力图", "深夜或小时偏好", "工作日与周末时段"),
    covers=("time_of_day", "behavior", "ranking"),
    cold_build_risk="low",
    avoid_when=("不涉及收听时段",),
    fallback=("analysis_stats",),
)

RESOLVE_ENTITY_TOOL = AgentToolDefinition(
    name="resolve_entity",
    description="Resolve a user-provided album, artist, or track name against local listening data.",
    read_only=True,
    params_model=ResolveEntityParams,
    handler=resolve_entity_handler,
    best_for=("实体名称模糊", "需要稳定实体标识", "同名消歧"),
    covers=("entity_resolution", "scope"),
    cold_build_risk="none",
    avoid_when=("实体名称已明确且下游工具可直接解析",),
    fallback=("entity_stats",),
)

COMPARE_ENTITIES_TOOL = AgentToolDefinition(
    name="compare_entities",
    description=(
        "Compare two to four known tracks, albums, or artists in one requested period "
        "using local playback statistics. Set include_billboard=true only when the user "
        "explicitly asks about their personal Billboard, Power Score, ranks, or chart weeks."
    ),
    read_only=True,
    params_model=CompareEntitiesParams,
    handler=compare_entities_handler,
    cost="high",
    timeout_seconds=120,
    cacheability="revision",
    best_for=("比较 2-4 个同类实体", "一次获取比较所需播放次数时长与强度", "公平性比较"),
    covers=(
        "cumulative",
        "recency",
        "intensity",
        "fairness",
        "ranking",
        "personal_billboard",
    ),
    cold_build_risk="medium",
    avoid_when=("只查询单个实体", "比较不同实体类型"),
    fallback=("entity_stats", "resolve_entity"),
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
    best_for=("音乐档案概览", "收藏规模与覆盖范围"),
    covers=("collection", "behavior", "cumulative"),
    cold_build_risk="none",
    avoid_when=("需要单项收藏旅程明细",),
    fallback=("account_collection_insights",),
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
    cost="medium",
    best_for=("收藏旅程", "收藏后播放关系", "回访与沉睡收藏"),
    covers=("collection", "behavior", "recency", "detail"),
    cold_build_risk="low",
    avoid_when=("只需要账户收藏计数概览",),
    fallback=("account_summary",),
)

SEARCH_HISTORY_TOOL = AgentToolDefinition(
    name="search_history",
    description="Read compact Spotify search-history statistics and top queries.",
    read_only=True,
    params_model=SearchHistoryParams,
    handler=search_history_handler,
    best_for=("搜索历史", "高频搜索词", "搜索行为"),
    covers=("search", "behavior", "ranking"),
    cold_build_risk="none",
    avoid_when=("播放排行或播放趋势",),
    fallback=(),
)

COMMUNITY_FEED_SEARCH_TOOL = AgentToolDefinition(
    name="community_feed_search",
    description="Read generated community feed posts filtered by search text or date range.",
    read_only=True,
    params_model=CommunityFeedSearchParams,
    handler=community_feed_search_handler,
    best_for=("按文本或日期查社区动态", "社区帖子详情"),
    covers=("community", "detail", "period"),
    cost="high",
    timeout_seconds=75,
    cacheability="revision",
    cold_build_risk="high",
    avoid_when=("只需要社区趋势排行",),
    fallback=("community_trending",),
)

COMMUNITY_TRENDING_TOOL = AgentToolDefinition(
    name="community_trending",
    description="Read trending artists, tracks, latest #1, and debut signals from community posts.",
    read_only=True,
    params_model=CommunityTrendingParams,
    handler=community_trending_handler,
    best_for=("社区趋势", "社区热门艺人与歌曲", "最新冠军或空降信号"),
    covers=("community", "ranking", "peak"),
    cost="high",
    timeout_seconds=75,
    cacheability="revision",
    cold_build_risk="high",
    avoid_when=("按关键词查找特定帖子",),
    fallback=("community_feed_search",),
)
