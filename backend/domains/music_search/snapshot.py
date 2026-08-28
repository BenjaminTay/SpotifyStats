"""Build and read exact music-search context snapshots outside keyword GETs."""

from __future__ import annotations

import gc
import json
import sqlite3
import time
from typing import Any, Literal, cast

import pandas as pd

from backend.core.cache_manager import invalidate, invalidate_except
from backend.core.config import MUSIC_SEARCH_STATISTICS_LKG
from backend.domains.ai_agent.entity_resolver import EntityType
from backend.domains.billboard.chart_power_score import (
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
)
from backend.domains.billboard.chart_ranking import (
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)
from backend.domains.billboard.chart_summaries import compute_track_summary
from backend.domains.billboard.week_coverage import (
    current_open_billboard_week,
    keep_complete_billboard_weeks,
)
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
    build_music_search_filter_context,
    music_search_snapshot_policy_key,
)
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.index import (
    get_music_search_index_state,
    mark_music_search_candidate_maintenance_pending,
)
from backend.domains.music_search.snapshot_lineage import (
    active_playback_lineage,
    music_search_snapshot_dependency_digest,
)
from backend.domains.music_search.variants import MUSIC_SEARCH_SNAPSHOT_VARIANTS
from backend.domains.music_search.year_end_projection import clear_year_end_projection
from backend.domains.playback.album_projects import compute_album_project_plays
from backend.domains.playback.logical_timeline import build_billboard_weighted_frame
from backend.domains.playback.track_groups import load_track_group_keys
from backend.models.music_search import (
    MusicSearchChartSummary,
    MusicSearchContextItem,
    MusicSearchContextResponse,
    MusicSearchSnapshotStatus,
)
from backend.services.music_search_service import (
    _album_chart_map,
    _artist_chart_map,
    _build_chart_lookup,
    _load_filtered_search_frames,
    _track_chart_map,
)

SnapshotBuildStatus = Literal["pending", "running", "ready", "failed", "stale"]
WeeklyLedgerRow = tuple[str, str, str, int, int, int, str]


def _snapshot_variant_state_exists(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_snapshot_variant_state'"""
        ).fetchone()
        is not None
    )


def _set_snapshot_variant_target(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    *,
    status: Literal["ready", "pending", "building", "failed"],
    last_error: str | None = None,
    replace_target: bool = True,
) -> None:
    """Record maintenance intent without changing the serving snapshot."""
    if not _snapshot_variant_state_exists(conn):
        return
    conflict_where = (
        ""
        if replace_target
        else (
            " WHERE music_search_snapshot_variant_state.target_filter_fingerprint="
            "excluded.target_filter_fingerprint"
        )
    )
    conn.execute(
        """INSERT INTO music_search_snapshot_variant_state(
               merge_level, dynamic_threshold, active_snapshot_key,
               active_filter_fingerprint, target_filter_fingerprint,
               maintenance_status, last_error, updated_at
           ) VALUES (?, ?, NULL, NULL, ?, ?, ?, datetime('now'))
           ON CONFLICT(merge_level, dynamic_threshold) DO UPDATE SET
               target_filter_fingerprint=excluded.target_filter_fingerprint,
               maintenance_status=excluded.maintenance_status,
               last_error=excluded.last_error,
               updated_at=datetime('now')"""
        + conflict_where,
        (
            context.merge_level,
            int(context.dynamic_threshold),
            context.filter_fingerprint,
            status,
            last_error[:500] if last_error else None,
        ),
    )


def _activate_snapshot_variant(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    snapshot_key: str,
) -> None:
    """Atomically point one variant at a completely published snapshot."""
    if not _snapshot_variant_state_exists(conn):
        return
    conn.execute(
        """INSERT INTO music_search_snapshot_variant_state(
               merge_level, dynamic_threshold, active_snapshot_key,
               active_filter_fingerprint, target_filter_fingerprint,
               maintenance_status, last_error, updated_at
           ) VALUES (?, ?, ?, ?, ?, 'ready', NULL, datetime('now'))
           ON CONFLICT(merge_level, dynamic_threshold) DO UPDATE SET
               active_snapshot_key=excluded.active_snapshot_key,
               active_filter_fingerprint=excluded.active_filter_fingerprint,
               target_filter_fingerprint=excluded.target_filter_fingerprint,
               maintenance_status='ready', last_error=NULL,
               updated_at=datetime('now')""",
        (
            context.merge_level,
            int(context.dynamic_threshold),
            snapshot_key,
            context.filter_fingerprint,
            context.filter_fingerprint,
        ),
    )


def _fail_snapshot_variant_target(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    *,
    last_error: str,
) -> None:
    """Fail only the target still owned by this builder invocation."""
    if not _snapshot_variant_state_exists(conn):
        return
    conn.execute(
        """UPDATE music_search_snapshot_variant_state
           SET maintenance_status='failed', last_error=?, updated_at=datetime('now')
           WHERE merge_level=? AND dynamic_threshold=?
             AND target_filter_fingerprint=?""",
        (
            last_error[:500],
            context.merge_level,
            int(context.dynamic_threshold),
            context.filter_fingerprint,
        ),
    )


def get_serving_music_search_snapshot(
    conn: sqlite3.Connection,
    *,
    filter_fingerprint: str,
    merge_level: int,
    dynamic_threshold: bool,
) -> dict[str, Any]:
    """Resolve current exact statistics or a validated last-known-good snapshot."""
    exact = conn.execute(
        """SELECT snapshot_key, status, builder_version
           FROM music_search_snapshot_meta WHERE filter_fingerprint=?""",
        (filter_fingerprint,),
    ).fetchone()
    if (
        exact is not None
        and str(exact[1] or "") == "ready"
        and str(exact[2] or "") == MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
    ):
        return {
            "snapshot_key": str(exact[0]),
            "status": "ready",
            "freshness": "current",
            "served_filter_fingerprint": filter_fingerprint,
            "target_filter_fingerprint": filter_fingerprint,
        }

    target_status = _snapshot_public_status(str(exact[1]) if exact is not None else None)
    if exact is not None and str(exact[2] or "") != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION:
        target_status = "stale"
    if not MUSIC_SEARCH_STATISTICS_LKG or not _snapshot_variant_state_exists(conn):
        return {
            "snapshot_key": None,
            "status": target_status,
            "freshness": "unavailable",
            "served_filter_fingerprint": None,
            "target_filter_fingerprint": filter_fingerprint,
        }
    state = conn.execute(
        """SELECT active_snapshot_key, active_filter_fingerprint,
                  target_filter_fingerprint, maintenance_status
           FROM music_search_snapshot_variant_state
           WHERE merge_level=? AND dynamic_threshold=?""",
        (int(merge_level), int(dynamic_threshold)),
    ).fetchone()
    if state is None or not state[0]:
        return {
            "snapshot_key": None,
            "status": target_status,
            "freshness": "unavailable",
            "served_filter_fingerprint": None,
            "target_filter_fingerprint": filter_fingerprint,
        }
    active = conn.execute(
        """SELECT filter_fingerprint, status, builder_version,
                  EXISTS(SELECT 1 FROM music_search_entity_context payload
                         WHERE payload.snapshot_key=meta.snapshot_key) AS has_payload
           FROM music_search_snapshot_meta meta WHERE snapshot_key=?""",
        (state[0],),
    ).fetchone()
    if (
        active is None
        or str(active[1] or "") not in {"ready", "stale"}
        or str(active[2] or "") != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
        or not bool(active[3])
    ):
        return {
            "snapshot_key": None,
            "status": target_status,
            "freshness": "unavailable",
            "served_filter_fingerprint": None,
            "target_filter_fingerprint": filter_fingerprint,
        }
    maintenance_status = str(state[3] or "pending")
    if maintenance_status in {"pending", "building"}:
        public_status: MusicSearchSnapshotStatus = "warming"
    elif maintenance_status == "failed":
        public_status = "failed"
    else:
        public_status = target_status if target_status != "unavailable" else "stale"
    return {
        "snapshot_key": str(state[0]),
        "status": public_status,
        "freshness": "last_known_good",
        "served_filter_fingerprint": str(active[0]),
        "target_filter_fingerprint": str(state[2] or filter_fingerprint),
    }


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
    merge_level: int | None = None,
    dynamic_threshold: bool | None = None,
    include_target_fingerprint: bool = True,
) -> MusicSearchContextResponse:
    serving: dict[str, Any] | None = None
    if merge_level is not None and dynamic_threshold is not None:
        serving = get_serving_music_search_snapshot(
            conn,
            filter_fingerprint=filter_fingerprint,
            merge_level=merge_level,
            dynamic_threshold=dynamic_threshold,
        )
        snapshot_key = serving["snapshot_key"]
        status = cast(MusicSearchSnapshotStatus, serving["status"])
    else:
        meta = conn.execute(
            """SELECT snapshot_key, status, builder_version
               FROM music_search_snapshot_meta WHERE filter_fingerprint=?""",
            (filter_fingerprint,),
        ).fetchone()
        if meta is not None and str(meta["builder_version"] or "") != (
            MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
        ):
            status = "stale"
        else:
            status = _snapshot_public_status(str(meta["status"]) if meta else None)
        snapshot_key = str(meta["snapshot_key"]) if meta is not None else None
    if snapshot_key is None or (serving is None and status != "ready") or not entity_keys:
        return MusicSearchContextResponse(
            snapshot_status=status,
            filter_fingerprint=filter_fingerprint,
            statistics_status=status,
            statistics_freshness=(serving["freshness"] if serving is not None else "unavailable"),
            served_filter_fingerprint=(
                serving["served_filter_fingerprint"] if serving is not None else None
            ),
            target_filter_fingerprint=(filter_fingerprint if include_target_fingerprint else None),
        )
    unique_keys = list(dict.fromkeys(entity_keys))[:30]
    placeholders = ",".join("?" for _ in unique_keys)
    rows = conn.execute(
        f"""SELECT * FROM music_search_entity_context
            WHERE snapshot_key=? AND entity_key IN ({placeholders})""",
        (snapshot_key, *unique_keys),
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
        snapshot_status=status,
        filter_fingerprint=filter_fingerprint,
        statistics_status=status,
        statistics_freshness=(serving["freshness"] if serving is not None else "current"),
        served_filter_fingerprint=(
            serving["served_filter_fingerprint"] if serving is not None else filter_fingerprint
        ),
        target_filter_fingerprint=(filter_fingerprint if include_target_fingerprint else None),
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
    if plays_df.empty:
        track_metrics = {}
    else:
        track_grouped = plays_df.groupby("track_id", sort=False)["ms_played"].agg(
            play_events="size", total_ms="sum"
        )
        track_metrics = {
            int(cast(Any, track_id)): (int(row.play_events), int(row.total_ms))
            for track_id, row in track_grouped.iterrows()
        }
    album_frame = compute_album_project_plays(
        plays_df,
        conn,
        merge_level=context.merge_level,
        include_compilations=context.include_compilations,
    )
    album_metrics = {
        int(row.album_project_id): (int(row.play_count), int(row.total_ms))
        for row in album_frame.itertuples(index=False)
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
    if artist_df.empty:
        artist_metrics = {}
    else:
        artist_grouped = artist_df.groupby("artist_id", sort=False)["ms_played"].agg(
            play_events="size", total_ms="sum"
        )
        artist_metrics = {
            int(cast(Any, artist_id)): (int(row.play_events), int(row.total_ms))
            for artist_id, row in artist_grouped.iterrows()
        }
    del artist_df
    invalidate("db")
    gc.collect()
    return track_metrics, album_metrics, artist_metrics


def _load_shared_logical_frames(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    selected_kinds: tuple[EntityType, ...],
) -> dict[bool, tuple[pd.DataFrame, pd.DataFrame]]:
    thresholds = {context.dynamic_threshold for context in contexts}
    if len(thresholds) != 1:
        raise ValueError("shared logical frames must be loaded for one threshold at a time")
    frames: dict[bool, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for dynamic_threshold in dict.fromkeys(context.dynamic_threshold for context in contexts):
        representative = next(
            context for context in contexts if context.dynamic_threshold == dynamic_threshold
        )
        plays_df, artist_df = _load_filtered_search_frames(
            conn,
            selected_kinds,
            min_ms=representative.min_ms,
            music_only=representative.music_only,
            merge_enabled=representative.merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=representative.max_merge_gap_minutes,
        )
        frames[dynamic_threshold] = (
            plays_df if plays_df is not None else pd.DataFrame(),
            artist_df if artist_df is not None else pd.DataFrame(),
        )
    return frames


def _shared_metric_maps(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    shared_frames: dict[bool, tuple[pd.DataFrame, pd.DataFrame]] | None = None,
) -> dict[tuple[int, bool], tuple[dict[int, tuple[int, int]], ...]]:
    """Build the four L2/L3 metric variants from one frame per threshold."""
    if shared_frames is None:
        result: dict[tuple[int, bool], tuple[dict[int, tuple[int, int]], ...]] = {}
        for dynamic_threshold in dict.fromkeys(context.dynamic_threshold for context in contexts):
            threshold_contexts = tuple(
                context for context in contexts if context.dynamic_threshold == dynamic_threshold
            )
            artist_frames = _load_shared_logical_frames(
                conn,
                threshold_contexts,
                ("artist",),
            )
            try:
                artist_result = _shared_metric_maps(
                    conn,
                    threshold_contexts,
                    shared_frames=artist_frames,
                )
            finally:
                artist_frames.clear()
                invalidate("db")
                gc.collect()
            primary_frames = _load_shared_logical_frames(
                conn,
                threshold_contexts,
                ("track", "album"),
            )
            try:
                primary_result = _shared_metric_maps(
                    conn,
                    threshold_contexts,
                    shared_frames=primary_frames,
                )
                for variant_key, (
                    variant_track_metrics,
                    variant_album_metrics,
                    _artist_metrics,
                ) in primary_result.items():
                    result[variant_key] = (
                        variant_track_metrics,
                        variant_album_metrics,
                        artist_result[variant_key][2],
                    )
            finally:
                primary_frames.clear()
                invalidate("db")
                gc.collect()
        return result

    frames = shared_frames
    metric_result: dict[tuple[int, bool], tuple[dict[int, tuple[int, int]], ...]] = {}
    for dynamic_threshold in dict.fromkeys(context.dynamic_threshold for context in contexts):
        primary, artists = frames[dynamic_threshold]
        artist_metrics: dict[int, tuple[int, int]] = {}
        if not artists.empty:
            grouped = artists.groupby("artist_id", sort=False)["ms_played"].agg(
                play_events="size", total_ms="sum"
            )
            artist_metrics = {
                int(cast(Any, artist_id)): (int(row.play_events), int(row.total_ms))
                for artist_id, row in grouped.iterrows()
            }
        for context in (item for item in contexts if item.dynamic_threshold == dynamic_threshold):
            primary_variant = primary.copy()
            if not primary_variant.empty and context.merge_level > 1:
                group_keys = load_track_group_keys(conn, context.merge_level)
                if not group_keys.empty:
                    primary_variant = primary_variant.merge(
                        group_keys[["track_id", "track_agg_id"]],
                        on="track_id",
                        how="left",
                    )
                    primary_variant["track_id"] = primary_variant["track_agg_id"].fillna(
                        primary_variant["track_id"]
                    )
            track_metrics: dict[int, tuple[int, int]] = {}
            if not primary_variant.empty:
                grouped = primary_variant.groupby("track_id", sort=False)["ms_played"].agg(
                    play_events="size", total_ms="sum"
                )
                track_metrics = {
                    int(cast(Any, track_id)): (int(row.play_events), int(row.total_ms))
                    for track_id, row in grouped.iterrows()
                }
            album_frame = compute_album_project_plays(
                primary_variant,
                conn,
                merge_level=context.merge_level,
                include_compilations=context.include_compilations,
            )
            album_metrics = {
                int(row.album_project_id): (int(row.play_count), int(row.total_ms))
                for row in album_frame.itertuples(index=False)
            }
            metric_result[(context.merge_level, context.dynamic_threshold)] = (
                track_metrics,
                album_metrics,
                artist_metrics,
            )
    return metric_result


def _ordinary_chart_uses_aggregates(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> bool:
    """Mirror whether the ordinary builder selects current weekly aggregates."""
    if not context.merge_enabled:
        return False
    from backend.core.db import _agg_param_hash, check_agg_valid
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import (
        get_track_credit_revision,
        get_track_credit_state,
    )

    credit_state = get_track_credit_state(conn)
    if credit_state.get("current_revision", 0) != credit_state.get("active_aggregate_revision", 0):
        return False
    param_hash = _agg_param_hash(
        context.min_ms,
        context.music_only,
        context.bb_week_start_dow,
        context.bb_week_start_hour,
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
        identity_revision=get_identity_revision(conn),
        track_credit_revision=get_track_credit_revision(conn),
    )
    if not check_agg_valid(conn, param_hash):
        return False
    try:
        tracks_exist = conn.execute("SELECT 1 FROM agg_weekly_tracks LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return False
    return tracks_exist is not None


def _ordinary_album_chart_has_track_fallback(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> bool:
    """Mirror whether ordinary album charts select source-aware aggregates."""
    if not _ordinary_chart_uses_aggregates(conn, context):
        return False
    try:
        source_rows_exist = conn.execute(
            "SELECT 1 FROM agg_weekly_track_sources LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return source_rows_exist is not None


def _weekly_ledger_rows(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    weekly: pd.DataFrame,
    weekly_album: pd.DataFrame,
    weekly_artist: pd.DataFrame,
) -> tuple[list[WeeklyLedgerRow], bool]:
    """Encode ranked weekly frames against active candidate entity keys."""
    generation_id = str(get_music_search_index_state(conn).get("active_generation_id") or "")
    if not generation_id:
        return [], False
    candidate_keys = {
        str(row[0])
        for row in conn.execute(
            """SELECT entity_key FROM music_search_documents
               WHERE generation_id=? AND (kind!='track' OR merge_level=?)""",
            (generation_id, context.merge_level),
        ).fetchall()
    }
    rows: list[WeeklyLedgerRow] = []
    complete = True

    def append_row(
        family: str,
        ranked_row: Any,
        entity_key: str | None,
        stable_payload: dict[str, Any],
    ) -> None:
        nonlocal complete
        if not entity_key or entity_key not in candidate_keys:
            complete = False
            return
        rows.append(
            (
                family,
                str(ranked_row.billboard_week),
                entity_key,
                int(ranked_row.rank),
                int(ranked_row.play_count),
                int(ranked_row.total_ms),
                json.dumps(
                    stable_payload,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            )
        )

    for row in weekly.itertuples(index=False):
        track_id = int(cast(Any, row.track_id))
        append_row(
            "track",
            row,
            make_music_search_entity_key("track", track_id),
            {
                "entity_id": track_id,
                "track_name": getattr(row, "track_name", None),
                "artist_name": getattr(row, "artist_name", None),
            },
        )
    album_kind: Literal["album", "album_project"] = (
        "album" if context.merge_level <= 1 else "album_project"
    )
    for row in weekly_album.itertuples(index=False):
        project_id = int(cast(Any, row.album_project_id))
        append_row(
            "album",
            row,
            make_music_search_entity_key(album_kind, project_id),
            {
                "entity_id": project_id,
                "album_name": getattr(row, "album_name", None),
                "artist_name": getattr(row, "artist_name", None),
            },
        )
    for row in weekly_artist.itertuples(index=False):
        artist_id = getattr(row, "artist_id", None)
        entity_key = (
            make_music_search_entity_key("artist", int(artist_id))
            if artist_id is not None and not pd.isna(artist_id)
            else None
        )
        append_row(
            "artist",
            row,
            entity_key,
            {
                "entity_id": int(artist_id)
                if artist_id is not None and not pd.isna(artist_id)
                else None,
                "artist_name": getattr(row, "artist_name", None),
            },
        )
    # L1 album rankings may contain the same album identity more than once
    # when legacy source rows fan into one candidate album.  The ledger is a
    # set of ranked facts, so byte-identical duplicates are safe to collapse.
    # Conflicting facts for one identity are not a valid delta base: retain one
    # deterministically so shared-full publication remains usable, but mark the
    # ledger incomplete and omit reusable lineage at the caller boundary.
    unique_rows: dict[tuple[str, str, str], WeeklyLedgerRow] = {}
    for ledger_row in rows:
        identity = (ledger_row[0], ledger_row[1], ledger_row[2])
        existing = unique_rows.get(identity)
        if existing is None:
            unique_rows[identity] = ledger_row
        elif existing != ledger_row:
            complete = False
            unique_rows[identity] = min(existing, ledger_row)
    return list(unique_rows.values()), complete


def _shared_chart_lookups(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    shared_frames: dict[bool, tuple[pd.DataFrame, pd.DataFrame]],
    *,
    weekly_ledger: dict[tuple[int, bool], tuple[list[WeeklyLedgerRow], bool]] | None = None,
) -> dict[tuple[int, bool], dict[str, dict[Any, MusicSearchChartSummary]]]:
    """Recompute each chart family globally from shared compact weekly rows."""
    result: dict[tuple[int, bool], dict[str, dict[Any, MusicSearchChartSummary]]] = {}
    for dynamic_threshold, (primary, artists) in shared_frames.items():
        representative = next(
            context for context in contexts if context.dynamic_threshold == dynamic_threshold
        )
        ordinary_uses_aggregates = _ordinary_chart_uses_aggregates(conn, representative)
        ordinary_has_track_fallback = _ordinary_album_chart_has_track_fallback(conn, representative)
        # Period loaders may carry a DataFrame-valued weighted-frame attr.
        # pandas.concat compares attrs for equality, and DataFrame equality is
        # not scalar.  The chart builder consumes the explicit logical-event
        # columns, so do not forward cache metadata into a fresh weighted frame.
        primary_events = primary.copy(deep=False)
        primary_events.attrs = {}
        # Match the two ordinary chart sources.  The general playback loader
        # keeps the track container in ``track_album_id`` and its name in
        # ``album_name``.  Billboard either falls back to raw rows, which have
        # no track-album fallback column, or uses a valid source-aware
        # aggregate that retains ``track_album_id``.  Mixing these schemas
        # changes L1 album eligibility for legacy rows whose source_album_id is
        # absent and shifts weekly ranks.
        if "source_album_name" in primary_events.columns:
            primary_events["album_name"] = primary_events["source_album_name"].fillna(
                primary_events.get("album_name")
            )
        if not ordinary_has_track_fallback:
            primary_events = primary_events.drop(columns=["track_album_id"], errors="ignore")
        artist_events = artists.copy(deep=False)
        artist_events.attrs = {}
        if "source_album_name" in artist_events.columns:
            artist_events["album_name"] = artist_events["source_album_name"].fillna(
                artist_events.get("album_name")
            )
        if not ordinary_has_track_fallback:
            artist_events = artist_events.drop(columns=["track_album_id"], errors="ignore")
        weighted = build_billboard_weighted_frame(
            primary_events,
            week_start_dow=representative.bb_week_start_dow,
            week_start_hour=representative.bb_week_start_hour,
        )
        artist_pre_agg: pd.DataFrame | None = None
        if ordinary_uses_aggregates and not artist_events.empty:
            if {"billboard_week", "play_count", "total_ms"} <= set(artist_events.columns):
                artist_weighted = artist_events
            else:
                from backend.core.db import load_agg_weekly_artists

                artist_weighted = load_agg_weekly_artists(conn)
            artist_pre_agg = artist_weighted
        else:
            artist_weighted = build_billboard_weighted_frame(
                artist_events,
                week_start_dow=representative.bb_week_start_dow,
                week_start_hour=representative.bb_week_start_hour,
            )
        open_week = current_open_billboard_week(
            week_start_dow=representative.bb_week_start_dow,
            week_start_hour=representative.bb_week_start_hour,
        )
        weighted = keep_complete_billboard_weeks(weighted, open_week=open_week)
        artist_weighted = keep_complete_billboard_weeks(artist_weighted, open_week=open_week)
        if artist_pre_agg is not None:
            artist_pre_agg = artist_weighted
        for context in (item for item in contexts if item.dynamic_threshold == dynamic_threshold):
            weekly = (
                compute_weekly_rankings(
                    weighted,
                    context.bb_top_n,
                    pre_agg=weighted,
                    merge_level=context.merge_level,
                )
                if not weighted.empty
                else pd.DataFrame()
            )
            weekly_album = (
                compute_album_weekly_rankings(
                    weighted,
                    context.bb_album_top_n,
                    pre_agg=weighted,
                    merge_level=context.merge_level,
                    include_compilations=context.include_compilations,
                )
                if not weighted.empty
                else pd.DataFrame()
            )
            weekly_artist = (
                compute_artist_weekly_rankings(
                    artist_weighted,
                    context.bb_artist_top_n,
                    pre_agg=artist_pre_agg,
                )
                if not artist_weighted.empty
                else pd.DataFrame()
            )
            data = {
                "weekly": weekly.to_dict("records"),
                "track_summary": (
                    compute_track_summary(weekly, weighted).to_dict("records")
                    if not weighted.empty
                    else []
                ),
                "weekly_album": weekly_album.to_dict("records"),
                "weekly_artist": weekly_artist.to_dict("records"),
                "power_scores": (
                    compute_power_scores(weekly, context.bb_top_n).to_dict("records")
                    if not weekly.empty
                    else []
                ),
                "album_power_scores": (
                    compute_album_power_scores(weekly_album, context.bb_album_top_n).to_dict(
                        "records"
                    )
                    if not weekly_album.empty
                    else []
                ),
                "artist_power_scores": (
                    compute_artist_power_scores(weekly_artist, context.bb_artist_top_n).to_dict(
                        "records"
                    )
                    if not weekly_artist.empty
                    else []
                ),
            }
            if weekly_ledger is not None:
                weekly_ledger[(context.merge_level, context.dynamic_threshold)] = (
                    _weekly_ledger_rows(conn, context, weekly, weekly_album, weekly_artist)
                )
            result[(context.merge_level, context.dynamic_threshold)] = {
                "track": _track_chart_map(data),
                "album": _album_chart_map(data),
                "artist": _artist_chart_map(data),
            }
    return result


def build_exact_weekly_ledger_for_context(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> list[WeeklyLedgerRow]:
    """Build one compact exact ledger during explicit maintenance work."""
    frames = _load_shared_logical_frames(
        conn,
        (context,),
        ("track", "album", "artist"),
    )
    ledger: dict[tuple[int, bool], tuple[list[WeeklyLedgerRow], bool]] = {}
    try:
        _shared_chart_lookups(conn, (context,), frames, weekly_ledger=ledger)
        rows, complete = ledger[(context.merge_level, context.dynamic_threshold)]
        if not complete:
            raise RuntimeError("music-search weekly ledger is not exact")
        return rows
    finally:
        frames.clear()
        invalidate_except("billboard", {"latest_snapshot"})
        invalidate("db")
        gc.collect()


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
    *,
    metric_maps: tuple[dict[int, tuple[int, int]], ...] | None = None,
    chart_lookup: dict[str, dict[Any, MusicSearchChartSummary]] | None = None,
) -> list[tuple[Any, ...]]:
    state = get_music_search_index_state(conn)
    generation_id = state.get("active_generation_id")
    if not generation_id:
        raise RuntimeError("music-search index generation is unavailable")
    track_metrics, album_metrics, artist_metrics = metric_maps or _metric_maps(conn, context)
    chart_lookup = chart_lookup or _build_chart_lookup(
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
                _activate_snapshot_variant(conn, context, context.filter_fingerprint)
                continue
            _set_snapshot_variant_target(conn, context, status="pending")
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


def promote_role_only_music_search_snapshots(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> bool:
    """Re-key exact statistics after a proven role-only credit revision.

    Role labels change candidate presentation but not artist membership or any
    metric.  Copying the compact, already-validated payload avoids all lifetime
    and Billboard computation while keeping fingerprint truthfulness.
    The caller owns the surrounding revision transaction.
    """
    if not contexts or not _snapshot_variant_state_exists(conn):
        return False
    sources: list[tuple[MusicSearchFilterContext, sqlite3.Row]] = []
    for context in contexts:
        row = conn.execute(
            """SELECT meta.*
               FROM music_search_snapshot_variant_state state
               JOIN music_search_snapshot_meta meta
                 ON meta.snapshot_key=state.active_snapshot_key
               WHERE state.merge_level=? AND state.dynamic_threshold=?
                 AND meta.status IN ('ready', 'stale')
                 AND meta.builder_version=?
                 AND EXISTS(
                     SELECT 1 FROM music_search_entity_context payload
                     WHERE payload.snapshot_key=meta.snapshot_key
                 )""",
            (
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            ),
        ).fetchone()
        if row is None:
            return False
        sources.append((context, row))

    dependency_digest = music_search_snapshot_dependency_digest(conn)
    ledger_exists = bool(
        conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_weekly_chart_context'"""
        ).fetchone()
    )
    for context, source in sources:
        source_key = str(source["snapshot_key"])
        target_key = context.filter_fingerprint
        if source_key == target_key:
            _activate_snapshot_variant(conn, context, target_key)
            continue
        clear_year_end_projection(conn, target_key)
        conn.execute(
            "DELETE FROM music_search_entity_context WHERE snapshot_key=?",
            (target_key,),
        )
        if ledger_exists:
            conn.execute(
                "DELETE FROM music_search_weekly_chart_context WHERE snapshot_key=?",
                (target_key,),
            )
        conn.execute("DELETE FROM music_search_snapshot_meta WHERE snapshot_key=?", (target_key,))
        conn.execute(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, source_revision, status,
                   created_at, activated_at, last_accessed_at, last_error,
                   semantic_base_key, merge_level, dynamic_threshold,
                   builder_version, policy_key, source_generation_id,
                   source_dataset_digest, base_snapshot_key, build_strategy,
                   dependency_digest, change_set_digest
               ) VALUES (?, ?, ?, 'ready', datetime('now'), datetime('now'), NULL, NULL,
                         ?, ?, ?, ?, ?, ?, ?, ?, 'role_only_rekey', ?, NULL)""",
            (
                target_key,
                target_key,
                context.source_revision,
                context.semantic_base_key,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                music_search_snapshot_policy_key(context),
                source["source_generation_id"],
                source["source_dataset_digest"],
                source_key,
                dependency_digest,
            ),
        )
        conn.execute(
            """INSERT INTO music_search_entity_context
               SELECT ?, entity_key, play_events, total_ms, peak_position,
                      peak_weeks, weeks_on_chart, weeks_at_no1, power_score,
                      power_rank, first_week, latest_week, first_peak_week
               FROM music_search_entity_context WHERE snapshot_key=?""",
            (target_key, source_key),
        )
        if ledger_exists:
            conn.execute(
                """INSERT INTO music_search_weekly_chart_context
                   SELECT ?, family, week, entity_key, rank, play_count,
                          total_ms, stable_sort_key
                   FROM music_search_weekly_chart_context WHERE snapshot_key=?""",
                (target_key, source_key),
            )
        _activate_snapshot_variant(conn, context, target_key)
    return True


def build_music_search_snapshot(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> dict[str, Any]:
    snapshot_key = context.filter_fingerprint
    candidate_generation_id = str(
        get_music_search_index_state(conn).get("active_generation_id") or ""
    )
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
    _set_snapshot_variant_target(
        conn,
        context,
        status="building",
        replace_target=False,
    )
    conn.commit()
    try:
        rows = _context_rows(conn, context)
        _validate_context_rows(rows)
        conn.execute("BEGIN IMMEDIATE")
        try:
            current_context = build_music_search_filter_context(
                conn,
                context.filter_values(),
            )
            if (
                current_context.filter_fingerprint != context.filter_fingerprint
                or current_context.source_revision != context.source_revision
            ):
                raise RuntimeError("music-search context changed during snapshot build")
            current_generation_id = str(
                get_music_search_index_state(conn).get("active_generation_id") or ""
            )
            if current_generation_id != candidate_generation_id:
                raise RuntimeError("candidate generation changed during snapshot build")
            if _snapshot_variant_state_exists(conn):
                owner = conn.execute(
                    """SELECT target_filter_fingerprint
                       FROM music_search_snapshot_variant_state
                       WHERE merge_level=? AND dynamic_threshold=?""",
                    (context.merge_level, int(context.dynamic_threshold)),
                ).fetchone()
                if owner is None or str(owner[0] or "") != context.filter_fingerprint:
                    raise RuntimeError("snapshot target ownership changed during build")
            clear_year_end_projection(conn, snapshot_key)
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
            _activate_snapshot_variant(conn, context, snapshot_key)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {
            "status": "ready",
            "snapshot_key": snapshot_key,
            "filter_fingerprint": context.filter_fingerprint,
            "entity_count": len(rows),
            "source_revision": context.source_revision,
        }
    except Exception as exc:
        conn.rollback()
        conn.execute(
            """UPDATE music_search_snapshot_meta
               SET status='failed', last_error=? WHERE snapshot_key=?""",
            (type(exc).__name__, snapshot_key),
        )
        _fail_snapshot_variant_target(
            conn,
            context,
            last_error=type(exc).__name__,
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
    if _snapshot_variant_state_exists(conn):
        active_bases = conn.execute(
            """SELECT DISTINCT meta.semantic_base_key
               FROM music_search_snapshot_variant_state state
               JOIN music_search_snapshot_meta meta
                 ON meta.snapshot_key=state.active_snapshot_key
               WHERE meta.semantic_base_key IS NOT NULL"""
        ).fetchall()
        for row in active_bases:
            if str(row[0]) not in keep:
                keep.append(str(row[0]))
    protected_active = (
        """
        AND snapshot_key NOT IN (
            SELECT active_snapshot_key
            FROM music_search_snapshot_variant_state
            WHERE active_snapshot_key IS NOT NULL
        )
    """
        if _snapshot_variant_state_exists(conn)
        else ""
    )
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
                      {protected_active}
                )""",
            tuple(keep),
        )
        if conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_weekly_chart_context'"""
        ).fetchone():
            conn.execute(
                f"""DELETE FROM music_search_weekly_chart_context
                    WHERE snapshot_key IN (
                        SELECT snapshot_key
                        FROM music_search_snapshot_meta
                        WHERE (semantic_base_key IS NULL
                               OR semantic_base_key NOT IN ({placeholders}))
                          AND status NOT IN ('pending', 'running')
                          {protected_active}
                    )""",
                tuple(keep),
            )
        if conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_entity_year_end'"""
        ).fetchone():
            for table in (
                "music_search_entity_year_end",
                "music_search_year_end_meta",
                "music_search_year_end_projection_state",
            ):
                conn.execute(
                    f"""DELETE FROM {table}
                        WHERE snapshot_key IN (
                            SELECT snapshot_key
                            FROM music_search_snapshot_meta
                            WHERE (semantic_base_key IS NULL
                                   OR semantic_base_key NOT IN ({placeholders}))
                              AND status NOT IN ('pending', 'running')
                              {protected_active}
                        )""",
                    tuple(keep),
                )
        snapshot_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_snapshot_meta)")
        }
        if "base_snapshot_key" in snapshot_columns:
            # Application connections may have foreign keys disabled, so
            # mirror ON DELETE SET NULL before removing an older lineage base.
            conn.execute(
                f"""UPDATE music_search_snapshot_meta
                    SET base_snapshot_key=NULL
                    WHERE base_snapshot_key IN (
                        SELECT snapshot_key
                        FROM music_search_snapshot_meta
                        WHERE (semantic_base_key IS NULL
                               OR semantic_base_key NOT IN ({placeholders}))
                          AND status NOT IN ('pending', 'running')
                          {protected_active}
                    )""",
                tuple(keep),
            )
        conn.execute(
            f"""DELETE FROM music_search_snapshot_meta
                WHERE (semantic_base_key IS NULL OR semantic_base_key NOT IN ({placeholders}))
                  AND status NOT IN ('pending', 'running')
                  {protected_active}""",
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
                # Keep the tiny latest-week snapshots warm for the home page.
                # Only the heavyweight per-variant chart frames need to be
                # released before the next exact search variant.
                invalidate_except("billboard", {"latest_snapshot"})
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


def _validate_shared_full_contexts(
    contexts: tuple[MusicSearchFilterContext, ...],
) -> str:
    expected_variants = {
        (variant.merge_level, variant.dynamic_threshold)
        for variant in MUSIC_SEARCH_SNAPSHOT_VARIANTS
    }
    actual_variants = {(context.merge_level, context.dynamic_threshold) for context in contexts}
    if len(contexts) != len(expected_variants) or actual_variants != expected_variants:
        raise ValueError("shared-full snapshot requires the exact four supported variants")
    semantic_base_keys = {context.semantic_base_key for context in contexts}
    if len(semantic_base_keys) != 1:
        raise ValueError("shared-full snapshot variants must share one semantic base")
    fingerprints = {context.filter_fingerprint for context in contexts}
    if len(fingerprints) != len(expected_variants):
        raise ValueError("shared-full snapshot variants must have unique fingerprints")
    return next(iter(semantic_base_keys))


def _active_playback_generation(conn: sqlite3.Connection) -> str | None:
    table_exists = conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='playback_import_state'"""
    ).fetchone()
    if table_exists is None:
        return None
    row = conn.execute(
        "SELECT active_generation_id FROM playback_import_state WHERE state_id=1"
    ).fetchone()
    return str(row[0]) if row is not None and row[0] else None


def _assert_shared_full_publish_fence(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    source_generation_id: str,
    candidate_generation_id: str,
    semantic_base_key: str,
) -> None:
    if _active_playback_generation(conn) != source_generation_id:
        raise RuntimeError("playback generation changed during shared-full snapshot build")
    index_state = get_music_search_index_state(conn)
    if str(
        index_state.get("active_generation_id") or ""
    ) != candidate_generation_id or index_state.get("status") not in {"ready", "degraded"}:
        raise RuntimeError("candidate index generation changed during shared-full snapshot build")
    for context in contexts:
        current = build_music_search_filter_context(conn, context.filter_values())
        if (
            current.semantic_base_key != semantic_base_key
            or current.filter_fingerprint != context.filter_fingerprint
            or current.source_revision != context.source_revision
        ):
            raise RuntimeError(
                "music-search semantic base changed during shared-full snapshot build"
            )
        if _snapshot_variant_state_exists(conn):
            owner = conn.execute(
                """SELECT target_filter_fingerprint
                   FROM music_search_snapshot_variant_state
                   WHERE merge_level=? AND dynamic_threshold=?""",
                (context.merge_level, int(context.dynamic_threshold)),
            ).fetchone()
            if owner is None or str(owner[0] or "") != context.filter_fingerprint:
                raise RuntimeError(
                    "music-search snapshot target ownership changed during shared-full build"
                )


def _publish_shared_full_snapshot_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    rows_by_fingerprint: dict[str, list[tuple[Any, ...]]],
    weekly_rows_by_fingerprint: dict[str, list[WeeklyLedgerRow]],
    *,
    source_generation_id: str,
    candidate_generation_id: str,
    semantic_base_key: str,
    source_dataset_digest: str | None,
    dependency_digest: str | None,
) -> None:
    """Fence and activate the exact four variants in one write transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _assert_shared_full_publish_fence(
            conn,
            contexts,
            source_generation_id=source_generation_id,
            candidate_generation_id=candidate_generation_id,
            semantic_base_key=semantic_base_key,
        )
        if source_dataset_digest is not None:
            current_generation_id, current_dataset_digest = active_playback_lineage(conn)
            if (
                current_generation_id != source_generation_id
                or current_dataset_digest != source_dataset_digest
            ):
                raise RuntimeError("playback lineage changed during shared-full snapshot build")
            if dependency_digest is None or (
                music_search_snapshot_dependency_digest(conn) != dependency_digest
            ):
                raise RuntimeError(
                    "snapshot dependencies changed during shared-full snapshot build"
                )
        conn.execute(
            """UPDATE music_search_snapshot_meta SET status='running', last_error=NULL
               WHERE snapshot_key IN ({})""".format(",".join("?" for _ in contexts)),
            tuple(context.filter_fingerprint for context in contexts),
        )
        for context in contexts:
            snapshot_key = context.filter_fingerprint
            clear_year_end_projection(conn, snapshot_key)
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
                [(snapshot_key, *row) for row in rows_by_fingerprint[snapshot_key]],
            )
            ledger_table_exists = conn.execute(
                """SELECT 1 FROM sqlite_master
                   WHERE type='table' AND name='music_search_weekly_chart_context'"""
            ).fetchone()
            if ledger_table_exists:
                conn.execute(
                    "DELETE FROM music_search_weekly_chart_context WHERE snapshot_key=?",
                    (snapshot_key,),
                )
                conn.executemany(
                    """INSERT INTO music_search_weekly_chart_context(
                           snapshot_key, family, week, entity_key, rank,
                           play_count, total_ms, stable_sort_key
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (snapshot_key, *row)
                        for row in weekly_rows_by_fingerprint.get(snapshot_key, [])
                    ],
                )
                conn.execute(
                    """UPDATE music_search_snapshot_meta
                       SET policy_key=?, source_generation_id=?, source_dataset_digest=?,
                           base_snapshot_key=NULL, build_strategy='shared_full',
                           dependency_digest=?, change_set_digest=NULL
                       WHERE snapshot_key=?""",
                    (
                        music_search_snapshot_policy_key(context),
                        source_generation_id,
                        source_dataset_digest,
                        dependency_digest,
                        snapshot_key,
                    ),
                )
        conn.execute(
            """UPDATE music_search_snapshot_meta
               SET status='ready', activated_at=datetime('now'), last_error=NULL
               WHERE snapshot_key IN ({})""".format(",".join("?" for _ in contexts)),
            tuple(context.filter_fingerprint for context in contexts),
        )
        for context in contexts:
            _activate_snapshot_variant(conn, context, context.filter_fingerprint)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def build_shared_full_music_search_snapshot_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    source_generation_id: str,
) -> dict[str, Any] | None:
    """Fully rebuild four L2/L3 variants from two shared logical-frame sets.

    No prior snapshot rows are cloned. This path is safe without structured
    source metadata on legacy snapshot rows, while eliminating the repeated
    lifetime loads formerly performed once per variant.
    """
    if not contexts or not source_generation_id:
        return None
    semantic_base_key = _validate_shared_full_contexts(contexts)
    if _active_playback_generation(conn) != source_generation_id:
        return None
    index_state = get_music_search_index_state(conn)
    if index_state.get("status") not in {"ready", "degraded"}:
        return None
    candidate_generation_id = str(index_state.get("active_generation_id") or "")
    if not candidate_generation_id:
        return None
    started = time.perf_counter()
    rows_by_fingerprint: dict[str, list[tuple[Any, ...]]] = {}
    weekly_rows_by_fingerprint: dict[str, list[WeeklyLedgerRow]] = {}
    duration_by_fingerprint: dict[str, float] = {}
    reports: list[dict[str, Any]] = []
    lineage_generation_id, source_dataset_digest = active_playback_lineage(conn)
    lineage_ready = lineage_generation_id == source_generation_id and bool(source_dataset_digest)
    dependency_digest: str | None = None
    if lineage_ready:
        try:
            dependency_digest = music_search_snapshot_dependency_digest(conn)
        except Exception:
            lineage_ready = False
    try:
        prepare_music_search_snapshot_set(conn, contexts)
        for context in contexts:
            _set_snapshot_variant_target(
                conn,
                context,
                status="building",
                replace_target=False,
            )
        conn.commit()
        for dynamic_threshold in dict.fromkeys(context.dynamic_threshold for context in contexts):
            threshold_contexts = tuple(
                context for context in contexts if context.dynamic_threshold == dynamic_threshold
            )
            metric_maps: dict[tuple[int, bool], tuple[dict[int, tuple[int, int]], ...]] = {}
            chart_lookups: dict[
                tuple[int, bool], dict[str, dict[Any, MusicSearchChartSummary]]
            ] = {}
            ledger_rows: dict[tuple[int, bool], list[WeeklyLedgerRow]] = {
                (context.merge_level, context.dynamic_threshold): []
                for context in threshold_contexts
            }
            ledger_complete: dict[tuple[int, bool], bool] = {
                (context.merge_level, context.dynamic_threshold): True
                for context in threshold_contexts
            }
            artist_frames = _load_shared_logical_frames(
                conn,
                threshold_contexts,
                ("artist",),
            )
            try:
                artist_metrics = _shared_metric_maps(
                    conn,
                    threshold_contexts,
                    shared_frames=artist_frames,
                )
                artist_ledger: dict[tuple[int, bool], tuple[list[WeeklyLedgerRow], bool]] = {}
                artist_charts = _shared_chart_lookups(
                    conn,
                    threshold_contexts,
                    artist_frames,
                    weekly_ledger=artist_ledger,
                )
                for variant, (variant_rows, complete) in artist_ledger.items():
                    ledger_rows[variant].extend(variant_rows)
                    ledger_complete[variant] = ledger_complete[variant] and complete
                for variant, (
                    _track_metrics,
                    _album_metrics,
                    artist_metric_map,
                ) in artist_metrics.items():
                    metric_maps[variant] = ({}, {}, artist_metric_map)
                for variant, lookup in artist_charts.items():
                    chart_lookups[variant] = {
                        "track": {},
                        "album": {},
                        "artist": lookup["artist"],
                    }
            finally:
                artist_frames.clear()
                invalidate_except("billboard", {"latest_snapshot"})
                invalidate("db")
                gc.collect()

            primary_frames = _load_shared_logical_frames(
                conn,
                threshold_contexts,
                ("track", "album"),
            )
            try:
                primary_metrics = _shared_metric_maps(
                    conn,
                    threshold_contexts,
                    shared_frames=primary_frames,
                )
                primary_ledger: dict[tuple[int, bool], tuple[list[WeeklyLedgerRow], bool]] = {}
                primary_charts = _shared_chart_lookups(
                    conn,
                    threshold_contexts,
                    primary_frames,
                    weekly_ledger=primary_ledger,
                )
                for variant, (variant_rows, complete) in primary_ledger.items():
                    ledger_rows[variant].extend(variant_rows)
                    ledger_complete[variant] = ledger_complete[variant] and complete
                for context in threshold_contexts:
                    variant_started = time.perf_counter()
                    variant = (context.merge_level, context.dynamic_threshold)
                    _, _, artist_metric_map = metric_maps[variant]
                    track_metrics, album_metrics, _ = primary_metrics[variant]
                    metric_maps[variant] = (
                        track_metrics,
                        album_metrics,
                        artist_metric_map,
                    )
                    chart_lookups[variant]["track"] = primary_charts[variant]["track"]
                    chart_lookups[variant]["album"] = primary_charts[variant]["album"]
                    rows = _context_rows(
                        conn,
                        context,
                        metric_maps=metric_maps[variant],
                        chart_lookup=chart_lookups[variant],
                    )
                    if ledger_complete[variant]:
                        # The compact ledger carries stable entity IDs. Rebuild
                        # chart summaries from it so shared-full and completed-week
                        # deltas use the same identity semantics; display-name
                        # collisions must never merge distinct albums or artists.
                        from backend.domains.music_search.snapshot_ledger import (
                            rebuild_context_rows_from_weekly_ledger,
                        )

                        candidate_keys = {
                            str(row[0])
                            for row in conn.execute(
                                """SELECT entity_key FROM music_search_documents
                                   WHERE generation_id=?
                                     AND (kind!='track' OR merge_level=?)""",
                                (candidate_generation_id, context.merge_level),
                            ).fetchall()
                        }
                        rows = list(
                            rebuild_context_rows_from_weekly_ledger(
                                ledger_rows[variant],
                                {str(row[0]): (int(row[1]), int(row[2])) for row in rows},
                                candidate_keys,
                                track_top_n=context.bb_top_n,
                                album_top_n=context.bb_album_top_n,
                                artist_top_n=context.bb_artist_top_n,
                            )
                        )
                    _validate_context_rows(rows)
                    rows_by_fingerprint[context.filter_fingerprint] = rows
                    weekly_rows_by_fingerprint[context.filter_fingerprint] = ledger_rows[variant]
                    if not ledger_complete[variant]:
                        lineage_ready = False
                    duration_by_fingerprint[context.filter_fingerprint] = round(
                        (time.perf_counter() - variant_started) * 1000,
                        3,
                    )
            finally:
                primary_frames.clear()
                metric_maps.clear()
                chart_lookups.clear()
                invalidate_except("billboard", {"latest_snapshot"})
                invalidate("db")
                gc.collect()
        _publish_shared_full_snapshot_set(
            conn,
            contexts,
            rows_by_fingerprint,
            weekly_rows_by_fingerprint,
            source_generation_id=source_generation_id,
            candidate_generation_id=candidate_generation_id,
            semantic_base_key=semantic_base_key,
            source_dataset_digest=source_dataset_digest if lineage_ready else None,
            dependency_digest=dependency_digest if lineage_ready else None,
        )
        for context in contexts:
            rows = rows_by_fingerprint[context.filter_fingerprint]
            reports.append(
                {
                    "status": "ready",
                    "snapshot_key": context.filter_fingerprint,
                    "filter_fingerprint": context.filter_fingerprint,
                    "entity_count": len(rows),
                    "source_revision": context.source_revision,
                    "strategy": "shared_full_snapshot_rebuild",
                    "semantic_base_key": context.semantic_base_key,
                    "merge_level": context.merge_level,
                    "dynamic_threshold": context.dynamic_threshold,
                    "builder_version": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                    "duration_ms": duration_by_fingerprint[context.filter_fingerprint],
                    "revalidated": False,
                    "reuse_reason": "shared_full_logical_frames",
                }
            )
    except Exception:
        conn.execute(
            """UPDATE music_search_snapshot_meta
               SET status='failed', last_error='shared_full_snapshot_failed'
               WHERE snapshot_key IN ({}) AND status IN ('pending', 'running')""".format(
                ",".join("?" for _ in contexts)
            ),
            tuple(context.filter_fingerprint for context in contexts),
        )
        for context in contexts:
            _fail_snapshot_variant_target(
                conn,
                context,
                last_error="shared_full_snapshot_failed",
            )
        conn.commit()
        raise
    finally:
        rows_by_fingerprint.clear()
        weekly_rows_by_fingerprint.clear()
        duration_by_fingerprint.clear()
        invalidate_except("billboard", {"latest_snapshot"})
        invalidate("db")
        gc.collect()
    _prune_old_music_search_snapshot_bases(conn, contexts[0].semantic_base_key)
    return {
        "status": "ready",
        "semantic_base_key": contexts[0].semantic_base_key,
        "ready_count": len(reports),
        "failed_count": 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "variants": reports,
        "strategy": "shared_full_snapshot_rebuild",
        "shared_logical_frame_sets": len({context.dynamic_threshold for context in contexts}),
        "chart_strategy": "full_family_recompute",
        "weekly_ledger_ready": lineage_ready,
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
               WHEN merge_level=3 AND dynamic_threshold=1 THEN 1
               WHEN merge_level=2 AND dynamic_threshold=0 THEN 2
               ELSE 3 END""",
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
        if _snapshot_variant_state_exists(conn):
            # Active rows are immutable serving facts.  Dirtiness belongs to
            # the next target, never to the last successfully published LKG.
            conn.execute(
                """UPDATE music_search_snapshot_variant_state
                   SET target_filter_fingerprint=NULL,
                       maintenance_status='pending', last_error=?,
                       updated_at=datetime('now')""",
                (reason[:200],),
            )
        else:
            # Compatibility for pre-migration and narrow unit-test schemas.
            conn.execute(
                """UPDATE music_search_snapshot_meta
                   SET status='stale', last_error=? WHERE status IN ('ready', 'pending')""",
                (reason[:200],),
            )
    if documents:
        mark_music_search_candidate_maintenance_pending(conn)
