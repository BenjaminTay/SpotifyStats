"""Build and read exact music-search context snapshots outside keyword GETs."""

from __future__ import annotations

import gc
import sqlite3
import time
from typing import Any, Literal, cast

import pandas as pd

from backend.core.cache_manager import invalidate
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
)
from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.playback.album_projects import compute_album_project_plays
from backend.domains.playback.track_groups import load_track_group_keys
from backend.models.music_search import (
    MusicSearchChartSummary,
    MusicSearchContextItem,
    MusicSearchContextResponse,
    MusicSearchSnapshotStatus,
)
from backend.services.music_search_service import (
    _build_chart_lookup,
    _load_filtered_search_frames,
)

SnapshotBuildStatus = Literal["pending", "running", "ready", "failed", "stale"]


def _snapshot_public_status(status: str | None) -> MusicSearchSnapshotStatus:
    if status == "ready":
        return "ready"
    if status in {"pending", "running"}:
        return "warming"
    if status == "stale":
        return "stale"
    if status == "failed":
        return "failed"
    return "unavailable"


def get_music_search_snapshot_status(
    conn: sqlite3.Connection,
    filter_fingerprint: str,
) -> MusicSearchSnapshotStatus:
    row = conn.execute(
        """SELECT status, builder_version FROM music_search_snapshot_meta
           WHERE filter_fingerprint=?""",
        (filter_fingerprint,),
    ).fetchone()
    if row is None:
        return "unavailable"
    if str(row[1] or "") != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION:
        return "stale"
    return _snapshot_public_status(str(row[0]))


def get_ready_music_search_entity_keys(
    conn: sqlite3.Connection,
    filter_fingerprint: str,
) -> set[str] | None:
    snapshot_key = get_ready_music_search_snapshot_key(conn, filter_fingerprint)
    if snapshot_key is None:
        return None
    return {
        str(item[0])
        for item in conn.execute(
            "SELECT entity_key FROM music_search_entity_context WHERE snapshot_key=?",
            (snapshot_key,),
        ).fetchall()
    }


def get_ready_music_search_snapshot_key(
    conn: sqlite3.Connection,
    filter_fingerprint: str,
) -> str | None:
    """Return the exact ready snapshot key without loading its entity set."""
    row = conn.execute(
        """SELECT snapshot_key FROM music_search_snapshot_meta
           WHERE filter_fingerprint=? AND status='ready'
             AND builder_version=?""",
        (filter_fingerprint, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
    ).fetchone()
    return str(row[0]) if row is not None else None


def lookup_music_search_context(
    conn: sqlite3.Connection,
    *,
    filter_fingerprint: str,
    entity_keys: list[str],
) -> MusicSearchContextResponse:
    meta = conn.execute(
        """SELECT snapshot_key, status, builder_version FROM music_search_snapshot_meta
           WHERE filter_fingerprint=?""",
        (filter_fingerprint,),
    ).fetchone()
    if meta is not None and str(meta["builder_version"] or "") != (
        MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
    ):
        status: MusicSearchSnapshotStatus = "stale"
    else:
        status = _snapshot_public_status(str(meta["status"]) if meta else None)
    if meta is None or status != "ready" or not entity_keys:
        return MusicSearchContextResponse(
            snapshot_status=status,
            filter_fingerprint=filter_fingerprint,
        )
    unique_keys = list(dict.fromkeys(entity_keys))[:30]
    placeholders = ",".join("?" for _ in unique_keys)
    rows = conn.execute(
        f"""SELECT * FROM music_search_entity_context
            WHERE snapshot_key=? AND entity_key IN ({placeholders})""",
        (meta["snapshot_key"], *unique_keys),
    ).fetchall()
    items: dict[str, MusicSearchContextItem] = {}
    for row in rows:
        chart_values = {
            key: row[key]
            for key in (
                "peak_position",
                "peak_weeks",
                "weeks_on_chart",
                "weeks_at_no1",
                "power_score",
                "power_rank",
                "first_week",
                "latest_week",
                "first_peak_week",
            )
        }
        chart = (
            MusicSearchChartSummary(**chart_values)
            if any(value is not None for value in chart_values.values())
            else None
        )
        items[str(row["entity_key"])] = MusicSearchContextItem(
            play_events=int(row["play_events"]),
            total_ms=int(row["total_ms"]),
            chart=chart,
        )
    return MusicSearchContextResponse(
        snapshot_status="ready",
        filter_fingerprint=filter_fingerprint,
        items=items,
    )


def _metric_maps(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> tuple[dict[int, tuple[int, int]], dict[int, tuple[int, int]], dict[int, tuple[int, int]]]:
    plays_df, _artist_df = _load_filtered_search_frames(
        conn,
        ("track", "album"),
        min_ms=context.min_ms,
        music_only=context.music_only,
        merge_enabled=context.merge_enabled,
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
    )
    plays_df = plays_df if plays_df is not None else pd.DataFrame()
    if not plays_df.empty and context.merge_level > 1:
        group_keys = load_track_group_keys(conn, context.merge_level)
        if not group_keys.empty:
            plays_df = plays_df.merge(
                group_keys[["track_id", "track_agg_id"]],
                on="track_id",
                how="left",
            )
            plays_df["track_id"] = plays_df["track_agg_id"].fillna(plays_df["track_id"])
    track_metrics = (
        {
            int(cast(Any, track_id)): (int(len(group)), int(group["ms_played"].sum()))
            for track_id, group in plays_df.groupby("track_id")
        }
        if not plays_df.empty
        else {}
    )
    album_frame = compute_album_project_plays(
        plays_df,
        conn,
        merge_level=context.merge_level,
        include_compilations=context.include_compilations,
    )
    album_metrics = {
        int(row["album_project_id"]): (int(row["play_count"]), int(row["total_ms"]))
        for _, row in album_frame.iterrows()
    }

    # Artist fan-out can be substantially larger than the primary play frame.
    # The three metric maps are compact, so release the primary cache before
    # loading fan-out instead of holding both lifetime DataFrames concurrently.
    del plays_df, album_frame
    invalidate("db")
    gc.collect()
    _plays_df, artist_df = _load_filtered_search_frames(
        conn,
        ("artist",),
        min_ms=context.min_ms,
        music_only=context.music_only,
        merge_enabled=context.merge_enabled,
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
    )
    artist_df = artist_df if artist_df is not None else pd.DataFrame()
    artist_metrics = (
        {
            int(cast(Any, artist_id)): (int(len(group)), int(group["ms_played"].sum()))
            for artist_id, group in artist_df.groupby("artist_id")
        }
        if not artist_df.empty
        else {}
    )
    del artist_df
    invalidate("db")
    gc.collect()
    return track_metrics, album_metrics, artist_metrics


def _chart_has_fact(chart: MusicSearchChartSummary | None) -> bool:
    return chart is not None and any(
        value is not None
        for value in (
            chart.peak_position,
            chart.weeks_on_chart,
            chart.power_rank,
            chart.first_week,
        )
    )


def _context_rows(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> list[tuple[Any, ...]]:
    state = get_music_search_index_state(conn)
    generation_id = state.get("active_generation_id")
    if not generation_id:
        raise RuntimeError("music-search index generation is unavailable")
    track_metrics, album_metrics, artist_metrics = _metric_maps(conn, context)
    chart_lookup = _build_chart_lookup(
        min_ms=context.min_ms,
        music_only=context.music_only,
        bb_top_n=context.bb_top_n,
        bb_album_top_n=context.bb_album_top_n,
        bb_artist_top_n=context.bb_artist_top_n,
        bb_week_start_dow=context.bb_week_start_dow,
        bb_week_start_hour=context.bb_week_start_hour,
        year_start=context.year_start,
        year_end=context.year_end,
        merge_enabled=context.merge_enabled,
        merge_level=context.merge_level,
        include_compilations=context.include_compilations,
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
    )
    album_document_kind = "album" if context.merge_level <= 1 else "album_project"
    documents = conn.execute(
        """SELECT entity_key, kind, track_id, album_id, album_project_id,
                  artist_id, album_name, artist_name
           FROM music_search_documents
           WHERE generation_id=? AND kind IN ('track', ?, 'artist')
             AND (kind!='track' OR merge_level=?)""",
        (generation_id, album_document_kind, context.merge_level),
    ).fetchall()
    result: list[tuple[Any, ...]] = []
    for document in documents:
        kind = str(document["kind"])
        chart: MusicSearchChartSummary | None
        if kind == "track":
            entity_id = int(document["track_id"])
            play_events, total_ms = track_metrics.get(entity_id, (0, 0))
            chart = chart_lookup["track"].get(entity_id)
        elif kind in {"album", "album_project"}:
            entity_id = int(
                document["album_id"] if kind == "album" else document["album_project_id"]
            )
            play_events, total_ms = album_metrics.get(entity_id, (0, 0))
            chart = chart_lookup["album"].get(
                (str(document["album_name"]), str(document["artist_name"]))
            )
        else:
            entity_id = int(document["artist_id"])
            play_events, total_ms = artist_metrics.get(entity_id, (0, 0))
            chart = chart_lookup["artist"].get(str(document["artist_name"]))
        if play_events <= 0 and not _chart_has_fact(chart):
            continue
        result.append(
            (
                str(document["entity_key"]),
                play_events,
                total_ms,
                chart.peak_position if chart else None,
                chart.peak_weeks if chart else None,
                chart.weeks_on_chart if chart else None,
                chart.weeks_at_no1 if chart else None,
                chart.power_score if chart else None,
                chart.power_rank if chart else None,
                chart.first_week if chart else None,
                chart.latest_week if chart else None,
                chart.first_peak_week if chart else None,
            )
        )
    return result


def _validate_context_rows(rows: list[tuple[Any, ...]]) -> None:
    entity_keys = [str(row[0]) for row in rows]
    if len(entity_keys) != len(set(entity_keys)):
        raise ValueError("duplicate music-search snapshot entity key")
    for row in rows:
        play_events = int(row[1])
        total_ms = int(row[2])
        peak_position = row[3]
        weeks_on_chart = row[5]
        power_rank = row[8]
        if play_events < 0 or total_ms < 0:
            raise ValueError("negative music-search snapshot metric")
        if peak_position is not None and int(peak_position) < 1:
            raise ValueError("invalid music-search peak position")
        if weeks_on_chart is not None and int(weeks_on_chart) < 0:
            raise ValueError("invalid music-search weeks-on-chart")
        if power_rank is not None and int(power_rank) < 1:
            raise ValueError("invalid music-search power rank")


def prepare_music_search_snapshot_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> None:
    """Publish pending metadata for every variant in one short transaction."""
    if not contexts:
        raise ValueError("music-search snapshot set requires at least one variant")
    semantic_base_keys = {context.semantic_base_key for context in contexts}
    if len(semantic_base_keys) != 1:
        raise ValueError("music-search snapshot variants must share one semantic base")
    with conn:
        for context in contexts:
            if get_ready_music_search_snapshot_key(conn, context.filter_fingerprint) is not None:
                continue
            conn.execute(
                """INSERT INTO music_search_snapshot_meta(
                       snapshot_key, filter_fingerprint, source_revision, status,
                       created_at, activated_at, last_error, semantic_base_key,
                       merge_level, dynamic_threshold, builder_version
                   ) VALUES (?, ?, ?, 'pending', datetime('now'), NULL, NULL, ?, ?, ?, ?)
                   ON CONFLICT(snapshot_key) DO UPDATE SET
                       filter_fingerprint=excluded.filter_fingerprint,
                       source_revision=excluded.source_revision,
                       status='pending', created_at=datetime('now'),
                       activated_at=NULL, last_error=NULL,
                       semantic_base_key=excluded.semantic_base_key,
                       merge_level=excluded.merge_level,
                       dynamic_threshold=excluded.dynamic_threshold,
                       builder_version=excluded.builder_version""",
                (
                    context.filter_fingerprint,
                    context.filter_fingerprint,
                    context.source_revision,
                    context.semantic_base_key,
                    context.merge_level,
                    int(context.dynamic_threshold),
                    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                ),
            )


def build_music_search_snapshot(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> dict[str, Any]:
    snapshot_key = context.filter_fingerprint
    conn.execute(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status, created_at,
               activated_at, last_error, semantic_base_key, merge_level,
               dynamic_threshold, builder_version
           ) VALUES (?, ?, ?, 'running', datetime('now'), NULL, NULL, ?, ?, ?, ?)
           ON CONFLICT(snapshot_key) DO UPDATE SET
               filter_fingerprint=excluded.filter_fingerprint,
               source_revision=excluded.source_revision,
               status='running', created_at=datetime('now'), activated_at=NULL,
               last_error=NULL, semantic_base_key=excluded.semantic_base_key,
               merge_level=excluded.merge_level,
               dynamic_threshold=excluded.dynamic_threshold,
               builder_version=excluded.builder_version""",
        (
            snapshot_key,
            context.filter_fingerprint,
            context.source_revision,
            context.semantic_base_key,
            context.merge_level,
            int(context.dynamic_threshold),
            MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
        ),
    )
    conn.commit()
    try:
        rows = _context_rows(conn, context)
        _validate_context_rows(rows)
        with conn:
            conn.execute(
                "DELETE FROM music_search_entity_context WHERE snapshot_key=?",
                (snapshot_key,),
            )
            conn.executemany(
                """INSERT INTO music_search_entity_context(
                       snapshot_key, entity_key, play_events, total_ms,
                       peak_position, peak_weeks, weeks_on_chart, weeks_at_no1,
                       power_score, power_rank, first_week, latest_week, first_peak_week
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(snapshot_key, *row) for row in rows],
            )
            conn.execute(
                """UPDATE music_search_snapshot_meta
                   SET status='ready', activated_at=datetime('now'), last_error=NULL
                   WHERE snapshot_key=?""",
                (snapshot_key,),
            )
        return {
            "status": "ready",
            "snapshot_key": snapshot_key,
            "filter_fingerprint": context.filter_fingerprint,
            "entity_count": len(rows),
            "source_revision": context.source_revision,
        }
    except Exception as exc:
        conn.execute(
            """UPDATE music_search_snapshot_meta
               SET status='failed', last_error=? WHERE snapshot_key=?""",
            (type(exc).__name__, snapshot_key),
        )
        conn.commit()
        raise


def _prune_old_music_search_snapshot_bases(
    conn: sqlite3.Connection,
    current_semantic_base_key: str,
) -> None:
    rows = conn.execute(
        """SELECT semantic_base_key,
                  MAX(COALESCE(activated_at, created_at)) AS latest_at
           FROM music_search_snapshot_meta
           WHERE semantic_base_key IS NOT NULL
           GROUP BY semantic_base_key
           ORDER BY (semantic_base_key=?) DESC, latest_at DESC""",
        (current_semantic_base_key,),
    ).fetchall()
    keep = [str(row[0]) for row in rows[:2]]
    if current_semantic_base_key not in keep:
        keep.insert(0, current_semantic_base_key)
    placeholders = ",".join("?" for _ in keep)
    with conn:
        # Normal application connections do not enable SQLite foreign-key
        # enforcement, so ON DELETE CASCADE cannot be relied on here.  Delete
        # payload rows explicitly before removing their snapshot metadata.
        conn.execute(
            f"""DELETE FROM music_search_entity_context
                WHERE snapshot_key IN (
                    SELECT snapshot_key
                    FROM music_search_snapshot_meta
                    WHERE (semantic_base_key IS NULL
                           OR semantic_base_key NOT IN ({placeholders}))
                      AND status NOT IN ('pending', 'running')
                )""",
            tuple(keep),
        )
        conn.execute(
            f"""DELETE FROM music_search_snapshot_meta
                WHERE (semantic_base_key IS NULL OR semantic_base_key NOT IN ({placeholders}))
                  AND status NOT IN ('pending', 'running')""",
            tuple(keep),
        )


def build_music_search_snapshot_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> dict[str, Any]:
    """Build all supported variants sequentially and publish each independently."""
    prepare_music_search_snapshot_set(conn, contexts)
    started = time.perf_counter()
    reports: list[dict[str, Any]] = []
    ready_count = 0
    failed_count = 0
    for context in contexts:
        variant_started = time.perf_counter()
        existing_snapshot_key = get_ready_music_search_snapshot_key(
            conn, context.filter_fingerprint
        )
        if existing_snapshot_key is not None:
            entity_count = int(
                conn.execute(
                    """SELECT COUNT(*) FROM music_search_entity_context
                       WHERE snapshot_key=?""",
                    (existing_snapshot_key,),
                ).fetchone()[0]
            )
            report = {
                "status": "ready",
                "snapshot_key": existing_snapshot_key,
                "filter_fingerprint": context.filter_fingerprint,
                "entity_count": entity_count,
                "source_revision": context.source_revision,
                "revalidated": True,
                "reuse_reason": "exact_statistics_fingerprint_ready",
            }
            ready_count += 1
        else:
            try:
                report = build_music_search_snapshot(conn, context)
                report["revalidated"] = False
                report["reuse_reason"] = None
                ready_count += 1
            except Exception as exc:
                failed_count += 1
                report = {
                    "status": "failed",
                    "snapshot_key": context.filter_fingerprint,
                    "filter_fingerprint": context.filter_fingerprint,
                    "entity_count": 0,
                    "source_revision": context.source_revision,
                    "error_type": type(exc).__name__,
                    "revalidated": False,
                    "reuse_reason": None,
                }
            finally:
                # Each heavyweight variant is independent.  Release its cache
                # before continuing so a resumed set stays within host limits.
                invalidate("billboard")
                invalidate("db")
                gc.collect()
        report.update(
            {
                "semantic_base_key": context.semantic_base_key,
                "merge_level": context.merge_level,
                "dynamic_threshold": context.dynamic_threshold,
                "builder_version": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                "duration_ms": round((time.perf_counter() - variant_started) * 1000, 3),
            }
        )
        reports.append(report)

    _prune_old_music_search_snapshot_bases(conn, contexts[0].semantic_base_key)
    overall_status = "ready" if failed_count == 0 else ("failed" if ready_count == 0 else "partial")
    return {
        "status": overall_status,
        "semantic_base_key": contexts[0].semantic_base_key,
        "ready_count": ready_count,
        "failed_count": failed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "variants": reports,
    }


def list_music_search_snapshot_variants(
    conn: sqlite3.Connection,
    semantic_base_key: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT snapshot_key, filter_fingerprint, status, merge_level,
                  dynamic_threshold, builder_version, activated_at, last_error,
                  (SELECT COUNT(*) FROM music_search_entity_context context
                   WHERE context.snapshot_key=meta.snapshot_key) AS entity_count
           FROM music_search_snapshot_meta meta
           WHERE semantic_base_key=?
           ORDER BY CASE
               WHEN merge_level=2 AND dynamic_threshold=1 THEN 0
               WHEN merge_level=1 AND dynamic_threshold=1 THEN 1
               WHEN merge_level=3 AND dynamic_threshold=1 THEN 2
               WHEN merge_level=2 AND dynamic_threshold=0 THEN 3
               WHEN merge_level=1 AND dynamic_threshold=0 THEN 4
               ELSE 5 END""",
        (semantic_base_key,),
    ).fetchall()
    return [dict(row) for row in rows]


def mark_music_search_derived_data_dirty(
    conn: sqlite3.Connection,
    *,
    reason: str,
    snapshots: bool = True,
    documents: bool = False,
) -> None:
    if snapshots:
        conn.execute(
            """UPDATE music_search_snapshot_meta
               SET status='stale', last_error=? WHERE status IN ('ready', 'pending')""",
            (reason[:200],),
        )
    if documents:
        conn.execute(
            """UPDATE music_search_index_state
               SET source_revision=NULL, candidate_index_version=NULL,
                   updated_at=datetime('now') WHERE state_id=1"""
        )
