"""Playback-volume ranking adapter for Yearly Review V2."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from backend.core.db import load_plays
from backend.domains.yearly_review.entity_links import entity_deep_link
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.analysis_records_service import _build_entity_frames
from backend.services.analysis_stats_service import chart_rows

PLAY_RANKING_LIMITS = {"track": 50, "album": 30, "artist": 30}


def _year_frame(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "ts_year" in frame.columns:
        years = pd.to_numeric(frame["ts_year"], errors="coerce")
        return frame[years == year].copy()
    dates = pd.to_datetime(frame["ts_date"], errors="coerce")
    return frame[dates.dt.year == year].copy()


def _identity_scalar(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
    return str(value)


def _identity_key(entity: str, row: dict[str, Any]) -> str:
    if entity == "track":
        return f"track:{row.get('track_id')}"
    if entity == "album":
        project_id = row.get("album_project_id")
        if project_id is not None:
            return f"album-project:{project_id}"
        return f"album:{row.get('artist_name', '')}\u241f{row.get('album_name', '')}"
    return f"artist:{row.get('artist_name', '')}"


def _deep_link(entity: str, row: dict[str, Any]) -> str | None:
    return entity_deep_link(
        entity,
        entity_id=row.get("track_id") if entity == "track" else row.get("album_project_id"),
        name=row.get(f"{entity}_name"),
        artist_name=row.get("artist_name") if entity != "artist" else None,
    )


def _activity_maps(
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
) -> dict[str, dict[str, dict[str, Any]]]:
    specs = {
        "track": (track_frame, "canonical_track_id"),
        "album": (album_frame, "album_project_id"),
        "artist": (artist_frame, "artist_name"),
    }
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for entity, (frame, column) in specs.items():
        result[entity] = {}
        if frame.empty or column not in frame.columns:
            continue
        work = frame.copy()
        work["_identity"] = work[column].map(_identity_scalar)
        if "ts_month" not in work.columns:
            work["ts_month"] = pd.to_datetime(work["ts_date"], errors="coerce").dt.month
        grouped = work.groupby("_identity", dropna=False).agg(
            active_days=("ts_date", "nunique"),
            active_months=("ts_month", "nunique"),
            first_played=("ts_date", "min"),
            last_played=("ts_date", "max"),
        )
        for identity, row in grouped.iterrows():
            result[entity][str(identity)] = {
                "active_days": int(row["active_days"]),
                "active_months": int(row["active_months"]),
                "first_played": str(row["first_played"]),
                "last_played": str(row["last_played"]),
            }
    return result


def _activity_identity(entity: str, row: dict[str, Any]) -> str:
    if entity == "track":
        return _identity_scalar(row.get("track_id"))
    if entity == "album":
        project_id = row.get("album_project_id")
        return _identity_scalar(project_id if project_id is not None else row.get("album_name", ""))
    return str(row.get("artist_name", ""))


def _enrich_rows(
    entity: str,
    metric: str,
    rows: list[dict[str, Any]],
    activity: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update(activity.get(_activity_identity(entity, item), {}))
        item["identity_key"] = _identity_key(entity, item)
        item["sort_metric"] = metric
        item["deep_link"] = _deep_link(entity, item)
        enriched.append(item)
    return enriched


def build_play_rankings(
    conn: sqlite3.Connection,
    year: int,
    context: YearlyReviewFilterContext,
    *,
    event_frame: pd.DataFrame | None = None,
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Build canonical annual play-count and listening-time rankings."""
    if event_frame is None:
        event_frame = load_plays(
            conn,
            min_ms=context.min_ms,
            music_only=context.music_only,
            merge_enabled=context.merge_enabled,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
        )
    annual_events = _year_frame(event_frame, year)
    if annual_events.empty:
        return {
            "year": year,
            "empty": True,
            "limits": dict(PLAY_RANKING_LIMITS),
            "charts": {
                entity: {"available_count": 0, "by_plays": [], "by_hours": []}
                for entity in PLAY_RANKING_LIMITS
            },
        }

    if entity_frames is None:
        entity_frames = _build_entity_frames(
            annual_events,
            conn,
            context.merge_level,
            context.include_compilations,
            min_ms=context.min_ms,
            music_only=context.music_only,
            merge_enabled=context.merge_enabled,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
        )
    track_frame, album_frame, artist_frame = (_year_frame(frame, year) for frame in entity_frames)
    activity_maps = _activity_maps(track_frame, album_frame, artist_frame)
    source_frames = {
        "track": annual_events,
        "album": annual_events,
        "artist": artist_frame,
    }

    charts: dict[str, Any] = {}
    for entity, limit in PLAY_RANKING_LIMITS.items():
        total, plays_rows = chart_rows(
            conn,
            source_frames[entity],
            entity,
            "plays",
            limit=limit,
            merge_level=context.merge_level,
            include_compilations=context.include_compilations,
        )
        _, hours_rows = chart_rows(
            conn,
            source_frames[entity],
            entity,
            "hours",
            limit=limit,
            merge_level=context.merge_level,
            include_compilations=context.include_compilations,
        )
        charts[entity] = {
            "available_count": total,
            "by_plays": _enrich_rows(entity, "plays", plays_rows, activity_maps[entity]),
            "by_hours": _enrich_rows(entity, "hours", hours_rows, activity_maps[entity]),
        }

    return {
        "year": year,
        "empty": False,
        "limits": dict(PLAY_RANKING_LIMITS),
        "charts": charts,
    }


def build_play_ranking_counts(
    conn: sqlite3.Connection,
    context: YearlyReviewFilterContext,
    *,
    event_frame: pd.DataFrame,
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> dict[str, int]:
    """Count canonical entities without materializing a second set of top lists."""
    if event_frame.empty:
        return {entity: 0 for entity in PLAY_RANKING_LIMITS}
    _, _, artist_frame = entity_frames
    sources = {"track": event_frame, "album": event_frame, "artist": artist_frame}
    counts: dict[str, int] = {}
    for entity, source in sources.items():
        total, _ = chart_rows(
            conn,
            source,
            entity,
            "plays",
            limit=1,
            merge_level=context.merge_level,
            include_compilations=context.include_compilations,
        )
        counts[entity] = int(total)
    return counts
