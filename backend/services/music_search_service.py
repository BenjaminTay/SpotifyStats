"""Local read-only music entity search service."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any, cast
from urllib.parse import quote

import pandas as pd

from backend.core.db import load_plays_for_artists
from backend.domains.ai_agent.entity_resolver import EntityType, resolve_entities
from backend.domains.music_search.timing import MusicSearchTiming, measure_search_phase
from backend.models.music_search import (
    MusicSearchChartSummary,
    MusicSearchResponse,
    MusicSearchResult,
)
from backend.services.analysis_stats_service import load_period_plays
from backend.services.billboard_service import (
    compute_power_scores_staged,
    compute_summaries_staged,
    compute_weekly_data,
)
from backend.services.entity_stats_service import _filter_entity_rows

_ALL_KINDS: tuple[EntityType, ...] = ("track", "album", "artist")
_EMPTY_CHART_LOOKUP: dict[str, dict[Any, MusicSearchChartSummary]] = {
    "track": {},
    "album": {},
    "artist": {},
}


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 10))


def _valid_kinds(kinds: Iterable[str] | None) -> tuple[EntityType, ...]:
    if kinds is None:
        return _ALL_KINDS
    selected = tuple(cast(EntityType, kind) for kind in kinds if kind in _ALL_KINDS)
    return selected or _ALL_KINDS


def _plays_text(play_events: int) -> str:
    return f"{play_events} 次播放"


def _cover_url(kind: str, entity_id: Any) -> str | None:
    if entity_id is None:
        return None
    try:
        resolved_id = int(entity_id)
    except (TypeError, ValueError):
        return None
    return f"/covers/{kind}/{resolved_id}.jpg"


def _candidate_metric(candidate: dict[str, Any], key: str, metrics: tuple[int, int] | None) -> int:
    if metrics is not None:
        return metrics[0] if key == "play_events" else metrics[1]
    return int(candidate.get(key) or 0)


def _track_result(
    candidate: dict[str, Any],
    metrics: tuple[int, int] | None = None,
    chart: MusicSearchChartSummary | None = None,
) -> MusicSearchResult | None:
    track_id = candidate.get("track_id")
    label = candidate.get("track_name") or candidate.get("name")
    if track_id is None or not label:
        return None
    artist_name = candidate.get("artist_name")
    album_name = candidate.get("album_name")
    subtitle_parts = [part for part in (artist_name, album_name) if part]
    return MusicSearchResult(
        kind="track",
        label=str(label),
        subtitle=" · ".join(str(part) for part in subtitle_parts) or None,
        href=f"/music/tracks/{track_id}",
        play_events=_candidate_metric(candidate, "play_events", metrics),
        total_ms=_candidate_metric(candidate, "total_ms", metrics),
        track_id=int(track_id),
        album_name=str(album_name) if album_name else None,
        artist_name=str(artist_name) if artist_name else None,
        cover_url=_cover_url("albums", candidate.get("album_id")),
        chart=chart,
    )


def _album_result(
    candidate: dict[str, Any],
    metrics: tuple[int, int] | None = None,
    chart: MusicSearchChartSummary | None = None,
) -> MusicSearchResult | None:
    album_name = candidate.get("album_name") or candidate.get("name")
    if not album_name:
        return None
    artist_name = candidate.get("artist_name")
    href = f"/music/albums/{quote(str(album_name), safe='')}"
    if artist_name:
        href = f"{href}?artist={quote(str(artist_name), safe='')}"
    return MusicSearchResult(
        kind="album",
        label=str(album_name),
        subtitle=str(artist_name) if artist_name else None,
        href=href,
        play_events=_candidate_metric(candidate, "play_events", metrics),
        total_ms=_candidate_metric(candidate, "total_ms", metrics),
        album_name=str(album_name),
        artist_name=str(artist_name) if artist_name else None,
        cover_url=_cover_url("albums", candidate.get("album_id")),
        chart=chart,
    )


def _artist_result(
    candidate: dict[str, Any],
    metrics: tuple[int, int] | None = None,
    chart: MusicSearchChartSummary | None = None,
) -> MusicSearchResult | None:
    artist_name = candidate.get("artist_name") or candidate.get("name")
    if not artist_name:
        return None
    play_events = _candidate_metric(candidate, "play_events", metrics)
    return MusicSearchResult(
        kind="artist",
        label=str(artist_name),
        subtitle=_plays_text(play_events),
        href=f"/music/artists/{quote(str(artist_name), safe='')}",
        play_events=play_events,
        total_ms=_candidate_metric(candidate, "total_ms", metrics),
        artist_id=int(candidate["artist_id"]) if candidate.get("artist_id") is not None else None,
        artist_name=str(artist_name),
        cover_url=_cover_url("artists", candidate.get("artist_id")),
        chart=chart,
    )


def _convert(
    kind: EntityType,
    candidate: dict[str, Any],
    metrics: tuple[int, int] | None = None,
    chart: MusicSearchChartSummary | None = None,
) -> MusicSearchResult | None:
    if kind == "track":
        return _track_result(candidate, metrics, chart)
    if kind == "album":
        return _album_result(candidate, metrics, chart)
    return _artist_result(candidate, metrics, chart)


def _metrics_from_frame(frame: pd.DataFrame) -> tuple[int, int]:
    if frame.empty:
        return 0, 0
    return int(len(frame)), int(frame["ms_played"].sum())


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _has_album_project_inputs(conn: sqlite3.Connection) -> bool:
    return all(
        _table_exists(conn, table_name)
        for table_name in (
            "release_groups",
            "album_projects",
            "album_project_albums",
            "album_project_tracks",
        )
    )


def _direct_album_metrics(
    plays_df: pd.DataFrame,
    album_name: str,
    artist_name: str | None,
) -> tuple[int, int]:
    frame = plays_df[plays_df["album_name"] == album_name]
    if artist_name is not None:
        frame = frame[frame["artist_name"] == artist_name]
    return _metrics_from_frame(frame)


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value)
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _sorted_power_frame(data: dict[str, Any], key: str) -> pd.DataFrame:
    frame = pd.DataFrame(data.get(key) or [])
    if frame.empty or "power_score" not in frame.columns:
        return frame
    frame = frame.sort_values("power_score", ascending=False).reset_index(drop=True)
    frame["_detail_power_rank"] = frame.index + 1
    return frame


def _power_row_by_track(power_scores: pd.DataFrame, track_id: int) -> dict[str, Any]:
    if power_scores.empty or "track_id" not in power_scores.columns:
        return {}
    match = power_scores[power_scores["track_id"] == track_id]
    return match.iloc[0].to_dict() if not match.empty else {}


def _power_row_by_album(
    album_power_scores: pd.DataFrame, album_name: str, artist_name: str
) -> dict[str, Any]:
    if album_power_scores.empty:
        return {}
    match = album_power_scores[
        (album_power_scores["album_name"] == album_name)
        & (album_power_scores["artist_name"] == artist_name)
    ]
    return match.iloc[0].to_dict() if not match.empty else {}


def _power_row_by_artist(artist_power_scores: pd.DataFrame, artist_name: str) -> dict[str, Any]:
    if artist_power_scores.empty or "artist_name" not in artist_power_scores.columns:
        return {}
    match = artist_power_scores[artist_power_scores["artist_name"] == artist_name]
    return match.iloc[0].to_dict() if not match.empty else {}


def _track_chart_map(data: dict[str, Any]) -> dict[int, MusicSearchChartSummary]:
    track_summary = pd.DataFrame(data.get("track_summary") or [])
    if track_summary.empty or "track_id" not in track_summary.columns:
        return {}
    power_scores = _sorted_power_frame(data, "power_scores")
    charts: dict[int, MusicSearchChartSummary] = {}
    for row in track_summary.to_dict("records"):
        track_id = _int_or_none(row.get("track_id"))
        if track_id is None:
            continue
        power = _power_row_by_track(power_scores, track_id)
        charts[track_id] = MusicSearchChartSummary(
            peak_position=_int_or_none(row.get("peak_position")),
            peak_weeks=_int_or_none(row.get("weeks_at_peak")),
            weeks_on_chart=_int_or_none(row.get("weeks_on_chart")),
            weeks_at_no1=_int_or_none(row.get("weeks_at_no1")),
            power_score=_int_or_none(power.get("power_score")) or 0,
            power_rank=_int_or_none(power.get("_detail_power_rank")),
            first_week=_clean_str(row.get("first_week")),
            latest_week=_clean_str(row.get("last_week")),
            first_peak_week=_clean_str(row.get("first_peak_week")),
        )
    return charts


def _ranked_group_chart(
    group: pd.DataFrame,
    *,
    power: dict[str, Any],
) -> MusicSearchChartSummary:
    peak = _int_or_none(group["rank"].min())
    if peak is None:
        return MusicSearchChartSummary()
    peak_rows = group[group["rank"] == peak]
    return MusicSearchChartSummary(
        peak_position=peak,
        peak_weeks=int((group["rank"] == peak).sum()),
        weeks_on_chart=int(group["billboard_week"].nunique()),
        weeks_at_no1=int((group["rank"] == 1).sum()),
        power_score=_int_or_none(power.get("power_score")) or 0,
        power_rank=_int_or_none(power.get("_detail_power_rank")),
        first_week=_clean_str(group["billboard_week"].min()),
        latest_week=_clean_str(group["billboard_week"].max()),
        first_peak_week=_clean_str(peak_rows["billboard_week"].min())
        if not peak_rows.empty
        else None,
    )


def _album_chart_map(data: dict[str, Any]) -> dict[tuple[str, str], MusicSearchChartSummary]:
    weekly_album = pd.DataFrame(data.get("weekly_album") or [])
    if weekly_album.empty:
        return {}
    album_power_scores = _sorted_power_frame(data, "album_power_scores")
    charts: dict[tuple[str, str], MusicSearchChartSummary] = {}
    for (album_name, artist_name), group in weekly_album.groupby(["album_name", "artist_name"]):
        album = str(album_name)
        artist = str(artist_name)
        charts[(album, artist)] = _ranked_group_chart(
            group,
            power=_power_row_by_album(album_power_scores, album, artist),
        )
    return charts


def _artist_chart_map(data: dict[str, Any]) -> dict[str, MusicSearchChartSummary]:
    weekly_artist = pd.DataFrame(data.get("weekly_artist") or [])
    if weekly_artist.empty:
        return {}
    artist_power_scores = _sorted_power_frame(data, "artist_power_scores")
    charts: dict[str, MusicSearchChartSummary] = {}
    for artist_name, group in weekly_artist.groupby("artist_name"):
        artist = str(artist_name)
        charts[artist] = _ranked_group_chart(
            group,
            power=_power_row_by_artist(artist_power_scores, artist),
        )
    return charts


def _build_chart_lookup(
    *,
    min_ms: int,
    music_only: bool,
    bb_top_n: int,
    bb_album_top_n: int,
    bb_artist_top_n: int,
    bb_week_start_dow: int,
    bb_week_start_hour: int,
    year_start: int | None,
    year_end: int | None,
    merge_level: int,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    merge_enabled: bool,
    include_compilations: bool,
) -> dict[str, dict[Any, MusicSearchChartSummary]]:
    try:
        common = dict(
            min_ms=min_ms,
            music_only=music_only,
            bb_top_n=bb_top_n,
            bb_album_top_n=bb_album_top_n,
            bb_artist_top_n=bb_artist_top_n,
            bb_week_start_dow=bb_week_start_dow,
            bb_week_start_hour=bb_week_start_hour,
            year_start=year_start,
            year_end=year_end,
            merge_level=merge_level,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            merge_enabled=merge_enabled,
            include_compilations=include_compilations,
        )
        # Search context consumes weekly ranks, summaries, and power scores.
        # Building the full Billboard payload also computes records and other
        # unused slices, multiplying post-import work across six variants.
        data = {
            **compute_weekly_data(**common),
            **compute_summaries_staged(**common),
            **compute_power_scores_staged(**common),
        }
    except sqlite3.OperationalError as exc:
        if "no such" in str(exc).lower():
            return {key: value.copy() for key, value in _EMPTY_CHART_LOOKUP.items()}
        raise
    return {
        "track": _track_chart_map(data),
        "album": _album_chart_map(data),
        "artist": _artist_chart_map(data),
    }


def _chart_for_candidate(
    kind: EntityType,
    candidate: dict[str, Any],
    chart_lookup: dict[str, dict[Any, MusicSearchChartSummary]],
) -> MusicSearchChartSummary | None:
    if kind == "track":
        track_id = candidate.get("track_id")
        if track_id is None:
            return None
        return chart_lookup["track"].get(int(track_id))
    if kind == "album":
        album_name = candidate.get("album_name") or candidate.get("name")
        artist_name = candidate.get("artist_name")
        if not album_name or not artist_name:
            return None
        return chart_lookup["album"].get((str(album_name), str(artist_name)))
    artist_name = candidate.get("artist_name") or candidate.get("name")
    return chart_lookup["artist"].get(str(artist_name)) if artist_name else None


def _filtered_metrics(
    conn: sqlite3.Connection,
    kind: EntityType,
    candidate: dict[str, Any],
    *,
    plays_df: pd.DataFrame | None,
    artist_plays_df: pd.DataFrame | None,
    merge_level: int,
) -> tuple[int, int]:
    if kind == "track":
        track_id = candidate.get("track_id")
        if track_id is None or plays_df is None:
            return 0, 0
        return _metrics_from_frame(
            _filter_entity_rows(plays_df, "track", int(track_id), None, None)
        )
    if kind == "album":
        album_name = candidate.get("album_name") or candidate.get("name")
        artist_name = candidate.get("artist_name")
        if not album_name or plays_df is None:
            return 0, 0
        if not _has_album_project_inputs(conn):
            return _direct_album_metrics(
                plays_df,
                str(album_name),
                str(artist_name) if artist_name else None,
            )
        return _metrics_from_frame(
            _filter_entity_rows(
                plays_df,
                "album",
                None,
                str(album_name),
                str(artist_name) if artist_name else None,
                conn=conn,
                merge_level=merge_level,
            )
        )
    artist_name = candidate.get("artist_name") or candidate.get("name")
    if not artist_name or artist_plays_df is None:
        return 0, 0
    return _metrics_from_frame(
        _filter_entity_rows(artist_plays_df, "artist", None, None, str(artist_name))
    )


def _load_filtered_search_frames(
    conn: sqlite3.Connection,
    selected_kinds: tuple[EntityType, ...],
    *,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    plays_df: pd.DataFrame | None = None
    artist_plays_df: pd.DataFrame | None = None
    if any(kind in selected_kinds for kind in ("track", "album")):
        _, plays_df, _ = load_period_plays(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            "lifetime",
            None,
            None,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
    if "artist" in selected_kinds:
        _, artist_plays_df, _ = load_period_plays(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            "lifetime",
            None,
            None,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            _loader=load_plays_for_artists,
        )
    return plays_df, artist_plays_df


def search_music_entities(
    conn: sqlite3.Connection,
    *,
    query: str,
    kinds: Iterable[str] | None = None,
    limit_per_type: int = 5,
    min_ms: int = 30000,
    music_only: bool = True,
    merge_enabled: bool = True,
    dynamic_threshold: bool = True,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    use_filtered_counts: bool = True,
    include_chart: bool = False,
    bb_top_n: int = 30,
    bb_album_top_n: int = 20,
    bb_artist_top_n: int = 20,
    bb_week_start_dow: int = 4,
    bb_week_start_hour: int = 0,
    year_start: int | None = None,
    year_end: int | None = None,
    include_compilations: bool = False,
    timing: MusicSearchTiming | None = None,
) -> MusicSearchResponse:
    bounded_limit = _bounded_limit(limit_per_type)
    selected_kinds = _valid_kinds(kinds)

    grouped: dict[EntityType, list[MusicSearchResult]] = {
        "track": [],
        "album": [],
        "artist": [],
    }
    if not query.strip():
        return MusicSearchResponse(
            query=query,
            limit_per_type=bounded_limit,
            total=0,
            tracks=[],
            albums=[],
            artists=[],
        )

    plays_df = None
    artist_plays_df = None
    if use_filtered_counts:
        with measure_search_phase(timing, "filtered_frames"):
            plays_df, artist_plays_df = _load_filtered_search_frames(
                conn,
                selected_kinds,
                min_ms=min_ms,
                music_only=music_only,
                merge_enabled=merge_enabled,
                dynamic_threshold=dynamic_threshold,
                max_merge_gap_minutes=max_merge_gap_minutes,
            )

    with measure_search_phase(timing, "chart_lookup"):
        chart_lookup = (
            _build_chart_lookup(
                min_ms=min_ms,
                music_only=music_only,
                bb_top_n=bb_top_n,
                bb_album_top_n=bb_album_top_n,
                bb_artist_top_n=bb_artist_top_n,
                bb_week_start_dow=bb_week_start_dow,
                bb_week_start_hour=bb_week_start_hour,
                year_start=year_start,
                year_end=year_end,
                merge_level=merge_level,
                dynamic_threshold=dynamic_threshold,
                max_merge_gap_minutes=max_merge_gap_minutes,
                merge_enabled=merge_enabled,
                include_compilations=include_compilations,
            )
            if include_chart
            else {key: value.copy() for key, value in _EMPTY_CHART_LOOKUP.items()}
        )

    for kind in selected_kinds:
        with measure_search_phase(timing, f"resolve_{kind}"):
            resolved = resolve_entities(
                conn,
                query=query,
                entity_type=kind,
                limit=bounded_limit,
            )
        rows = []
        with measure_search_phase(timing, f"assemble_{kind}"):
            for candidate in resolved.get("candidates", []):
                metrics = (
                    _filtered_metrics(
                        conn,
                        kind,
                        candidate,
                        plays_df=plays_df,
                        artist_plays_df=artist_plays_df,
                        merge_level=merge_level,
                    )
                    if use_filtered_counts
                    else None
                )
                if metrics is not None and metrics[0] <= 0:
                    continue
                item = _convert(
                    kind,
                    candidate,
                    metrics,
                    _chart_for_candidate(kind, candidate, chart_lookup) if include_chart else None,
                )
                if item is not None:
                    rows.append(item)
        grouped[kind] = rows

    return MusicSearchResponse(
        query=query,
        limit_per_type=bounded_limit,
        total=sum(len(items) for items in grouped.values()),
        tracks=grouped["track"],
        albums=grouped["album"],
        artists=grouped["artist"],
    )
