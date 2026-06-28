"""Read-only AI agent tool handlers backed by local analysis services."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.db import get_db
from backend.domains.ai_agent.entity_resolver import resolve_entities
from backend.domains.ai_agent.tool_registry import AgentToolDefinition, AgentToolResult
from backend.domains.billboard import details as billboard_details
from backend.services import (
    analysis_records_service,
    analysis_stats_service,
    entity_stats_service,
    play_service,
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
        count = len(items)
    else:
        count = 0
    return f"view={data.get('view')}, items={count}"


def _resolve_entity_result_summary(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    count = len(candidates) if isinstance(candidates, list) else 0
    return f"found={str(bool(data.get('found'))).lower()}, candidates={count}"


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
