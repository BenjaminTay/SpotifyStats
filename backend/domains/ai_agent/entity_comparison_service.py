"""Batch evidence builder for deterministic entity comparisons."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

import pandas as pd

from backend.core.db import load_plays_for_artists
from backend.domains.ai_agent.entity_resolver import resolve_entities
from backend.domains.billboard.chart_compute import compute_billboard_data
from backend.services.analysis_stats_service import (
    _summary,
    build_duration_frame,
    load_period_plays,
)
from backend.services.entity_stats_service import _filter_entity_rows

EntityType = Literal["track", "album", "artist"]


def _first_candidate(
    conn: sqlite3.Connection,
    *,
    query: str,
    entity_type: EntityType,
) -> dict[str, Any] | None:
    result = resolve_entities(conn, query=query, entity_type=entity_type, limit=1)
    candidates = result.get("candidates")
    if not result.get("found") or not isinstance(candidates, list) or not candidates:
        return None
    candidate = candidates[0]
    return candidate if isinstance(candidate, dict) else None


def _identity_fields(
    requested_name: str,
    entity_type: EntityType,
    candidate: dict[str, Any],
) -> tuple[str, int | None, str | None, str | None]:
    display_name = str(candidate.get("name") or requested_name)
    if entity_type == "track":
        return display_name, int(candidate["track_id"]), None, None
    if entity_type == "album":
        return (
            str(candidate.get("album_name") or display_name),
            None,
            str(candidate.get("album_name") or display_name),
            str(candidate.get("artist_name")) if candidate.get("artist_name") else None,
        )
    return (
        str(candidate.get("artist_name") or display_name),
        None,
        None,
        str(candidate.get("artist_name") or display_name),
    )


def _playback_rows(
    conn: sqlite3.Connection,
    *,
    entity_type: EntityType,
    names: list[str],
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str,
    start_date: str | None,
    end_date: str | None,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    merge_level: int,
) -> list[dict[str, Any]]:
    """Load the effective-play frame once, then slice every requested entity."""
    all_df, current_df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        attach_duration_slices=False,
        _loader=load_plays_for_artists if entity_type == "artist" else None,
    )
    rows: list[dict[str, Any]] = []
    for requested_name in names:
        candidate = _first_candidate(
            conn,
            query=requested_name,
            entity_type=entity_type,
        )
        if candidate is None:
            rows.append(
                {
                    "name": requested_name,
                    "requested_name": requested_name,
                    "entity_type": entity_type,
                    "found": False,
                    "error": f"{entity_type} not found in local listening data",
                }
            )
            continue

        display_name, track_id, album_name, artist_name = _identity_fields(
            requested_name,
            entity_type,
            candidate,
        )
        entity_all = _filter_entity_rows(
            all_df,
            entity_type,
            track_id,
            album_name,
            artist_name,
            conn=conn,
            merge_level=merge_level,
        )
        entity_current = _filter_entity_rows(
            current_df,
            entity_type,
            track_id,
            album_name,
            artist_name,
            conn=conn,
            merge_level=merge_level,
        )
        if entity_all.empty:
            rows.append(
                {
                    "name": display_name,
                    "requested_name": requested_name,
                    "entity_type": entity_type,
                    "found": False,
                    "error": "not found in effective playback evidence",
                }
            )
            continue

        summary = _summary(
            entity_current,
            build_duration_frame(entity_all, resolved),
        )
        row: dict[str, Any] = {
            "name": display_name,
            "requested_name": requested_name,
            "entity_type": entity_type,
            "found": True,
            "plays": summary.get("total_plays"),
            "hours": summary.get("total_hours"),
            "first_play_date": str(entity_all["ts"].min()),
            "latest_play_date": str(entity_all["ts"].max()),
            "period": resolved,
            "_artist_name": artist_name,
        }
        if track_id is not None:
            row["track_id"] = track_id
        rows.append(row)
    return rows


def _ranked_power_row(frame: pd.DataFrame, mask: pd.Series) -> tuple[int | None, int | None]:
    if frame.empty or "power_score" not in frame.columns:
        return None, None
    matches = frame[mask]
    if matches.empty:
        return None, None
    source_index = matches.index[0]
    ranked_indices = list(frame.sort_values("power_score", ascending=False, kind="stable").index)
    return int(matches.iloc[0]["power_score"]), ranked_indices.index(source_index) + 1


def _billboard_metrics(
    data: dict[str, Any],
    *,
    entity_type: EntityType,
    row: dict[str, Any],
) -> dict[str, int | None]:
    if entity_type == "track":
        weekly = pd.DataFrame(data.get("weekly") or [])
        power = pd.DataFrame(data.get("power_scores") or [])
        track_id = row.get("track_id")
        history = weekly[weekly["track_id"] == track_id] if not weekly.empty else weekly
        power_mask = (
            power["track_id"].eq(track_id)
            if not power.empty and "track_id" in power.columns
            else pd.Series(dtype=bool)
        )
    elif entity_type == "album":
        weekly = pd.DataFrame(data.get("weekly_album") or [])
        power = pd.DataFrame(data.get("album_power_scores") or [])
        history = weekly[weekly["album_name"] == row["name"]] if not weekly.empty else weekly
        artist_name = row.get("_artist_name")
        if not history.empty and artist_name and "artist_name" in history.columns:
            history = history[history["artist_name"] == artist_name]
        power_mask = (
            power["album_name"].eq(row["name"])
            if not power.empty and "album_name" in power.columns
            else pd.Series(dtype=bool)
        )
        if not power.empty and artist_name and "artist_name" in power.columns:
            power_mask &= power["artist_name"].eq(artist_name)
    else:
        weekly = pd.DataFrame(data.get("weekly_artist") or [])
        power = pd.DataFrame(data.get("artist_power_scores") or [])
        history = weekly[weekly["artist_name"] == row["name"]] if not weekly.empty else weekly
        power_mask = (
            power["artist_name"].eq(row["name"])
            if not power.empty and "artist_name" in power.columns
            else pd.Series(dtype=bool)
        )

    power_score, power_rank = _ranked_power_row(power, power_mask)
    if history.empty:
        return {
            "power_score": power_score,
            "power_rank": power_rank,
            "no1_weeks": 0,
            "weeks_on_chart": 0,
            "peak_position": None,
        }
    return {
        "power_score": power_score,
        "power_rank": power_rank,
        "no1_weeks": int((history["rank"] == 1).sum()),
        "weeks_on_chart": int(history["billboard_week"].nunique()),
        "peak_position": int(history["rank"].min()),
    }


def build_entity_comparison_rows(
    conn: sqlite3.Connection,
    *,
    entity_type: EntityType,
    names: list[str],
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str,
    start_date: str | None,
    end_date: str | None,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    merge_level: int,
    include_billboard: bool,
) -> list[dict[str, Any]]:
    rows = _playback_rows(
        conn,
        entity_type=entity_type,
        names=names,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_level=merge_level,
    )
    if include_billboard:
        # One shared Billboard build replaces one full detail build per entity.
        billboard = compute_billboard_data(
            min_ms,
            music_only,
            30,
            20,
            20,
            4,
            0,
            None,
            None,
            merge_level=merge_level,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            include_compilations=False,
            merge_enabled=merge_enabled,
        )
        for row in rows:
            if row.get("found"):
                row.update(_billboard_metrics(billboard, entity_type=entity_type, row=row))
    for row in rows:
        row.pop("_artist_name", None)
    return rows
