"""Strict within-open-week incremental publication for exact search snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from datetime import date, timedelta
from typing import Any, Literal, cast

import pandas as pd

from backend.domains.metadata.track_credits import get_effective_track_credits
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
    music_search_snapshot_policy_key,
)
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.music_search.snapshot_lineage import (
    active_playback_lineage,
    music_search_snapshot_dependency_digest,
)
from backend.domains.playback.album_projects import (
    compute_album_project_plays,
)
from backend.domains.playback.logical_delta import (
    build_tail_track_logical_delta,
    project_track_logical_delta,
)
from backend.domains.playback.track_groups import load_track_group_keys

logger = logging.getLogger(__name__)


def _incremental_plan_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_music_search_incremental_plan(change_set: Any) -> dict[str, Any] | None:
    """Serialize a bounded proof for same-week or one-boundary appends."""
    if getattr(change_set, "strategy", None) != "incremental":
        return None
    if int(getattr(change_set, "removed_count", 0) or 0) != 0:
        return None
    if not bool(getattr(change_set, "billboard_scope_exact", False)):
        return None
    previous_digest = str(getattr(change_set, "previous_dataset_digest", None) or "")
    generation_id = str(getattr(change_set, "generation_id", None) or "")
    previous_open = str(getattr(change_set, "previous_open_week", None) or "")
    current_open = str(getattr(change_set, "current_open_week", None) or "")
    if not previous_digest or not generation_id or not previous_open or not current_open:
        return None
    weeks = sorted(str(value) for value in getattr(change_set, "billboard_weeks", ()) or ())
    try:
        previous_open_date = date.fromisoformat(previous_open)
        current_open_date = date.fromisoformat(current_open)
    except ValueError:
        return None
    if current_open_date == previous_open_date:
        expected_weeks = [current_open]
        affected_completed_weeks: list[str] = []
    elif current_open_date == previous_open_date + timedelta(days=7):
        expected_weeks = [previous_open, current_open]
        affected_completed_weeks = [previous_open]
    else:
        return None
    if weeks != expected_weeks:
        return None
    added_count = int(getattr(change_set, "added_count", 0) or 0)
    if added_count <= 0 or added_count > 10_000:
        return None
    payload = {
        "schema_version": "music_search_incremental_snapshot_plan_v2",
        "source_generation_id": generation_id,
        "previous_dataset_digest": previous_digest,
        "added_count": added_count,
        "billboard_weeks": weeks,
        "affected_completed_weeks": affected_completed_weeks,
        "previous_open_week": previous_open,
        "current_open_week": current_open,
    }
    payload["change_set_digest"] = _incremental_plan_digest(payload)
    return payload


def _validated_incremental_plan(plan: dict[str, Any]) -> dict[str, Any] | None:
    if plan.get("schema_version") != "music_search_incremental_snapshot_plan_v2":
        return None
    generation_id = str(plan.get("source_generation_id") or "")
    previous_digest = str(plan.get("previous_dataset_digest") or "")
    previous_open = str(plan.get("previous_open_week") or "")
    current_open = str(plan.get("current_open_week") or "")
    try:
        added_count = int(plan.get("added_count") or 0)
        weeks = sorted(str(value) for value in plan.get("billboard_weeks", ()))
        affected_completed_weeks = sorted(
            str(value) for value in plan.get("affected_completed_weeks", ())
        )
        previous_open_date = date.fromisoformat(previous_open)
        current_open_date = date.fromisoformat(current_open)
    except (TypeError, ValueError):
        return None
    if current_open_date == previous_open_date:
        expected_weeks = [current_open]
        expected_completed_weeks: list[str] = []
    elif current_open_date == previous_open_date + timedelta(days=7):
        expected_weeks = [previous_open, current_open]
        expected_completed_weeks = [previous_open]
    else:
        return None
    if (
        not generation_id
        or not previous_digest
        or not previous_open
        or not current_open
        or added_count <= 0
        or added_count > 10_000
        or weeks != expected_weeks
        or affected_completed_weeks != expected_completed_weeks
    ):
        return None
    payload = {
        "schema_version": "music_search_incremental_snapshot_plan_v2",
        "source_generation_id": generation_id,
        "previous_dataset_digest": previous_digest,
        "added_count": added_count,
        "billboard_weeks": weeks,
        "affected_completed_weeks": affected_completed_weeks,
        "previous_open_week": previous_open,
        "current_open_week": current_open,
    }
    if str(plan.get("change_set_digest") or "") != _incremental_plan_digest(payload):
        return None
    payload["change_set_digest"] = str(plan["change_set_digest"])
    return payload


def _select_base_snapshot_keys(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    previous_dataset_digest: str,
    dependency_digest: str,
) -> dict[str, str] | None:
    selected: dict[str, str] = {}
    source_generations: set[str] = set()
    for context in contexts:
        row = conn.execute(
            """SELECT snapshot_key, source_generation_id
               FROM music_search_snapshot_meta
               WHERE policy_key=? AND source_dataset_digest=?
                 AND dependency_digest=? AND status IN ('ready', 'stale')
                 AND build_strategy IN ('shared_full', 'delta')
               ORDER BY COALESCE(activated_at, created_at) DESC
               LIMIT 1""",
            (
                music_search_snapshot_policy_key(context),
                previous_dataset_digest,
                dependency_digest,
            ),
        ).fetchone()
        if row is None or not row[0] or not row[1]:
            return None
        selected[context.filter_fingerprint] = str(row[0])
        source_generations.add(str(row[1]))
    if len(selected) != 6 or len(set(selected.values())) != 6 or len(source_generations) != 1:
        return None
    return selected


def _assert_base_snapshot_fence(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    base_keys: dict[str, str],
    *,
    previous_dataset_digest: str,
    dependency_digest: str,
    payload_proofs: dict[str, tuple[str, int, int]],
) -> None:
    source_generations: set[str] = set()
    for context in contexts:
        base_key = base_keys[context.filter_fingerprint]
        row = conn.execute(
            """SELECT policy_key, source_generation_id, source_dataset_digest,
                      dependency_digest, status, build_strategy
               FROM music_search_snapshot_meta WHERE snapshot_key=?""",
            (base_key,),
        ).fetchone()
        if row is None or (
            str(row[0] or "") != music_search_snapshot_policy_key(context)
            or not row[1]
            or str(row[2] or "") != previous_dataset_digest
            or str(row[3] or "") != dependency_digest
            or str(row[4] or "") not in {"ready", "stale"}
            or str(row[5] or "") not in {"shared_full", "delta"}
        ):
            raise RuntimeError("incremental snapshot base changed before publication")
        current_proof = _base_snapshot_payload_proof(conn, base_key)
        if current_proof != payload_proofs.get(base_key):
            raise RuntimeError("incremental snapshot base payload changed before publication")
        source_generations.add(str(row[1]))
    if len(source_generations) != 1:
        raise RuntimeError("incremental snapshot bases do not share one source generation")


def _base_snapshot_payload_proof(
    conn: sqlite3.Connection,
    snapshot_key: str,
) -> tuple[str, int, int]:
    activated_at = conn.execute(
        """SELECT COALESCE(activated_at, created_at, '')
           FROM music_search_snapshot_meta WHERE snapshot_key=?""",
        (snapshot_key,),
    ).fetchone()
    if activated_at is None:
        raise RuntimeError("incremental snapshot base disappeared")
    entity_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM music_search_entity_context WHERE snapshot_key=?",
            (snapshot_key,),
        ).fetchone()[0]
    )
    ledger_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM music_search_weekly_chart_context WHERE snapshot_key=?",
            (snapshot_key,),
        ).fetchone()[0]
    )
    return str(activated_at[0] or ""), entity_count, ledger_count


def _track_delta_maps(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    min_ms: int,
    music_only: bool,
    dynamic_threshold: bool,
    max_gap_minutes: int,
) -> dict[int, pd.DataFrame]:
    physical = build_tail_track_logical_delta(
        conn,
        generation_id=generation_id,
        min_ms=min_ms,
        music_only=music_only,
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
    )
    return {
        1: project_track_logical_delta(physical, merge_level=1),
        2: project_track_logical_delta(
            physical,
            merge_level=2,
            track_group_keys=load_track_group_keys(conn, 2),
        ),
        3: project_track_logical_delta(
            physical,
            merge_level=3,
            track_group_keys=load_track_group_keys(conn, 3),
        ),
    }


def _coalesced_metric_map(frame: pd.DataFrame, key: str) -> dict[int, tuple[int, int]]:
    if frame.empty:
        return {}
    grouped = frame.groupby(key, sort=False)[["play_events", "total_ms"]].sum()
    return {
        int(cast(Any, entity_id)): (int(row.play_events), int(row.total_ms))
        for entity_id, row in grouped.iterrows()
        if int(row.play_events) or int(row.total_ms)
    }


def _album_delta_map(
    conn: sqlite3.Connection,
    physical_delta: pd.DataFrame,
    *,
    merge_level: int,
    include_compilations: bool,
) -> dict[int, tuple[int, int]]:
    if physical_delta.empty:
        return {}
    weighted = physical_delta.rename(columns={"play_events": "play_count"})
    album_frame = compute_album_project_plays(
        weighted,
        conn,
        merge_level=merge_level,
        include_compilations=include_compilations,
    )
    if album_frame.empty:
        return {}
    album_frame = album_frame.rename(columns={"play_count": "play_events"})
    return _coalesced_metric_map(album_frame, "album_project_id")


def _artist_delta_map(
    conn: sqlite3.Connection,
    physical_delta: pd.DataFrame,
) -> dict[int, tuple[int, int]]:
    if physical_delta.empty:
        return {}
    track_ids = {int(value) for value in physical_delta["track_id"].unique()}
    credits = [
        (int(row["track_id"]), int(row["artist_id"]))
        for row in get_effective_track_credits(conn, track_ids)
        if int(row["track_id"]) in track_ids
    ]
    if not credits:
        return {}
    credit_frame = pd.DataFrame(credits, columns=["track_id", "artist_id"])
    expanded = physical_delta.merge(credit_frame, on="track_id", how="inner")
    return _coalesced_metric_map(expanded, "artist_id")


def _clone_and_apply_context_rows(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    base_snapshot_key: str,
    *,
    track_delta: pd.DataFrame,
    physical_delta: pd.DataFrame,
) -> list[tuple[Any, ...]] | None:
    columns = (
        "entity_key",
        "play_events",
        "total_ms",
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
    rows = conn.execute(
        f"""SELECT {", ".join(columns)} FROM music_search_entity_context
            WHERE snapshot_key=?""",
        (base_snapshot_key,),
    ).fetchall()
    by_key = {str(row[0]): list(row) for row in rows}
    candidate_generation = str(get_music_search_index_state(conn).get("active_generation_id") or "")
    candidate_keys = {
        str(row[0])
        for row in conn.execute(
            """SELECT entity_key FROM music_search_documents
               WHERE generation_id=? AND (kind!='track' OR merge_level=?)""",
            (candidate_generation, context.merge_level),
        ).fetchall()
    }
    if not set(by_key) <= candidate_keys:
        return None
    deltas: dict[str, tuple[int, int]] = {}
    for entity_id, values in _coalesced_metric_map(track_delta, "track_id").items():
        deltas[make_music_search_entity_key("track", entity_id)] = values
    album_kind: Literal["album", "album_project"] = (
        "album" if context.merge_level <= 1 else "album_project"
    )
    for entity_id, values in _album_delta_map(
        conn,
        physical_delta,
        merge_level=context.merge_level,
        include_compilations=context.include_compilations,
    ).items():
        deltas[make_music_search_entity_key(album_kind, entity_id)] = values
    for entity_id, values in _artist_delta_map(conn, physical_delta).items():
        deltas[make_music_search_entity_key("artist", entity_id)] = values

    if not set(deltas) <= candidate_keys:
        return None
    for entity_key, (play_delta, ms_delta) in deltas.items():
        row = by_key.setdefault(entity_key, [entity_key, 0, 0, *(None for _ in range(9))])
        row[1] = int(row[1]) + play_delta
        row[2] = int(row[2]) + ms_delta
        if int(row[1]) < 0 or int(row[2]) < 0:
            return None
    return [
        tuple(row)
        for row in by_key.values()
        if int(row[1]) > 0 or any(value is not None for value in row[3:])
    ]


def _candidate_keys_for_context(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    *,
    candidate_generation: str,
) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            """SELECT entity_key FROM music_search_documents
               WHERE generation_id=? AND (kind!='track' OR merge_level=?)""",
            (candidate_generation, context.merge_level),
        ).fetchall()
    }


def _base_weekly_ledger_rows(
    conn: sqlite3.Connection,
    snapshot_key: str,
    *,
    excluded_weeks: set[str],
) -> list[tuple[str, str, str, int, int, int, str]]:
    rows = conn.execute(
        """SELECT family, week, entity_key, rank, play_count, total_ms,
                  stable_sort_key
           FROM music_search_weekly_chart_context
           WHERE snapshot_key=?
           ORDER BY family, week, rank, entity_key""",
        (snapshot_key,),
    ).fetchall()
    return [
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            int(row[3]),
            int(row[4]),
            int(row[5]),
            str(row[6]),
        )
        for row in rows
        if str(row[1]) not in excluded_weeks
    ]


def build_incremental_music_search_snapshot_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    """Clone six compatible snapshots and apply a bounded lifetime delta."""
    validated_plan = _validated_incremental_plan(plan)
    if validated_plan is None:
        return None
    from backend.domains.music_search.snapshot import _validate_shared_full_contexts

    try:
        semantic_base_key = _validate_shared_full_contexts(contexts)
    except ValueError:
        return None
    if any(not context.merge_enabled for context in contexts):
        return None
    generation_id = str(validated_plan["source_generation_id"])
    previous_digest = str(validated_plan["previous_dataset_digest"])
    change_set_digest = str(validated_plan["change_set_digest"])
    active_generation, active_digest = active_playback_lineage(conn)
    if active_generation != generation_id or not active_digest or active_digest == previous_digest:
        return None
    try:
        dependency_digest = music_search_snapshot_dependency_digest(conn)
    except Exception:
        return None
    base_keys = _select_base_snapshot_keys(
        conn,
        contexts,
        previous_dataset_digest=previous_digest,
        dependency_digest=dependency_digest,
    )
    if base_keys is None:
        return None
    if set(base_keys.values()) & {context.filter_fingerprint for context in contexts}:
        return None
    base_payload_proofs = {
        base_key: _base_snapshot_payload_proof(conn, base_key) for base_key in base_keys.values()
    }
    representative = contexts[0]
    started = time.perf_counter()
    physical_by_threshold: dict[bool, pd.DataFrame] = {}
    projected_by_variant: dict[tuple[int, bool], pd.DataFrame] = {}
    rows_by_fingerprint: dict[str, list[tuple[Any, ...]]] = {}
    weekly_rows_by_fingerprint: dict[str, list[tuple[str, str, str, int, int, int, str]]] = {}
    for dynamic_threshold in {context.dynamic_threshold for context in contexts}:
        maps = _track_delta_maps(
            conn,
            generation_id=generation_id,
            min_ms=representative.min_ms,
            music_only=representative.music_only,
            dynamic_threshold=dynamic_threshold,
            max_gap_minutes=representative.max_merge_gap_minutes,
        )
        physical_by_threshold[dynamic_threshold] = maps[1]
        for merge_level, frame in maps.items():
            projected_by_variant[(merge_level, dynamic_threshold)] = frame
    for context in contexts:
        rows = _clone_and_apply_context_rows(
            conn,
            context,
            base_keys[context.filter_fingerprint],
            track_delta=projected_by_variant[(context.merge_level, context.dynamic_threshold)],
            physical_delta=physical_by_threshold[context.dynamic_threshold],
        )
        if rows is None:
            return None
        rows_by_fingerprint[context.filter_fingerprint] = rows

    affected_completed_weeks = set(validated_plan["affected_completed_weeks"])
    if affected_completed_weeks:
        from backend.domains.music_search.snapshot_ledger import (
            WeeklyLedgerValidationError,
            rebuild_context_rows_from_weekly_ledger,
        )
        from backend.domains.music_search.snapshot_week_delta import (
            MusicSearchWeekDeltaIncompatibleError,
            build_affected_complete_week_ledger_rows,
        )

        try:
            replacement_rows = build_affected_complete_week_ledger_rows(
                conn,
                contexts,
                change_generation_id=generation_id,
                affected_weeks=set(validated_plan["billboard_weeks"]),
                current_open_week=str(validated_plan["current_open_week"]),
            )
            candidate_generation = str(
                get_music_search_index_state(conn).get("active_generation_id") or ""
            )
            if not candidate_generation:
                return None
            for context in contexts:
                snapshot_key = context.filter_fingerprint
                base_key = base_keys[snapshot_key]
                combined_ledger = _base_weekly_ledger_rows(
                    conn,
                    base_key,
                    excluded_weeks=affected_completed_weeks,
                )
                combined_ledger.extend(replacement_rows[snapshot_key])
                lifetime_metrics = {
                    str(row[0]): (int(row[1]), int(row[2]))
                    for row in rows_by_fingerprint[snapshot_key]
                }
                rows_by_fingerprint[snapshot_key] = list(
                    rebuild_context_rows_from_weekly_ledger(
                        combined_ledger,
                        lifetime_metrics,
                        _candidate_keys_for_context(
                            conn,
                            context,
                            candidate_generation=candidate_generation,
                        ),
                        track_top_n=context.bb_top_n,
                        album_top_n=context.bb_album_top_n,
                        artist_top_n=context.bb_artist_top_n,
                    )
                )
                weekly_rows_by_fingerprint[snapshot_key] = combined_ledger
        except (MusicSearchWeekDeltaIncompatibleError, WeeklyLedgerValidationError, KeyError):
            logger.info(
                "Incremental music-search completed-week replacement was incompatible; "
                "using shared-full fallback",
                exc_info=True,
            )
            return None

    from backend.domains.music_search.snapshot import (
        _assert_shared_full_publish_fence,
        _prune_old_music_search_snapshot_bases,
        _validate_context_rows,
        prepare_music_search_snapshot_set,
    )

    for rows in rows_by_fingerprint.values():
        _validate_context_rows(rows)
    prepare_music_search_snapshot_set(conn, contexts)
    candidate_generation = str(get_music_search_index_state(conn).get("active_generation_id") or "")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _assert_shared_full_publish_fence(
            conn,
            contexts,
            source_generation_id=generation_id,
            candidate_generation_id=candidate_generation,
            semantic_base_key=contexts[0].semantic_base_key,
        )
        current_generation, current_digest = active_playback_lineage(conn)
        if current_generation != generation_id or current_digest != active_digest:
            raise RuntimeError("playback lineage changed during incremental snapshot publish")
        if music_search_snapshot_dependency_digest(conn) != dependency_digest:
            raise RuntimeError("snapshot dependencies changed during incremental publish")
        _assert_base_snapshot_fence(
            conn,
            contexts,
            base_keys,
            previous_dataset_digest=previous_digest,
            dependency_digest=dependency_digest,
            payload_proofs=base_payload_proofs,
        )
        reports: list[dict[str, Any]] = []
        for context in contexts:
            snapshot_key = context.filter_fingerprint
            base_key = base_keys[snapshot_key]
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
            conn.execute(
                "DELETE FROM music_search_weekly_chart_context WHERE snapshot_key=?",
                (snapshot_key,),
            )
            if affected_completed_weeks:
                conn.executemany(
                    """INSERT INTO music_search_weekly_chart_context(
                           snapshot_key, family, week, entity_key, rank,
                           play_count, total_ms, stable_sort_key
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(snapshot_key, *row) for row in weekly_rows_by_fingerprint[snapshot_key]],
                )
            else:
                conn.execute(
                    """INSERT INTO music_search_weekly_chart_context(
                           snapshot_key, family, week, entity_key, rank,
                           play_count, total_ms, stable_sort_key
                       )
                       SELECT ?, family, week, entity_key, rank,
                              play_count, total_ms, stable_sort_key
                       FROM music_search_weekly_chart_context WHERE snapshot_key=?""",
                    (snapshot_key, base_key),
                )
            conn.execute(
                """UPDATE music_search_snapshot_meta
                   SET status='ready', activated_at=datetime('now'), last_error=NULL,
                       policy_key=?, source_generation_id=?, source_dataset_digest=?,
                       base_snapshot_key=?, build_strategy='delta', dependency_digest=?,
                       change_set_digest=?
                   WHERE snapshot_key=?""",
                (
                    music_search_snapshot_policy_key(context),
                    generation_id,
                    active_digest,
                    base_key,
                    dependency_digest,
                    change_set_digest,
                    snapshot_key,
                ),
            )
            reports.append(
                {
                    "status": "ready",
                    "snapshot_key": snapshot_key,
                    "filter_fingerprint": snapshot_key,
                    "entity_count": len(rows_by_fingerprint[snapshot_key]),
                    "source_revision": context.source_revision,
                    "strategy": "incremental_snapshot_delta",
                    "semantic_base_key": context.semantic_base_key,
                    "merge_level": context.merge_level,
                    "dynamic_threshold": context.dynamic_threshold,
                    "builder_version": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                    "revalidated": False,
                    "reuse_reason": "compatible_previous_snapshot",
                }
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    prune_status = "completed"
    try:
        _prune_old_music_search_snapshot_bases(conn, semantic_base_key)
    except Exception:
        prune_status = "failed"
        logger.exception(
            "Incremental music-search snapshot published, but old snapshot pruning failed"
        )
    return {
        "status": "ready",
        "semantic_base_key": semantic_base_key,
        "ready_count": 6,
        "failed_count": 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "variants": reports,
        "strategy": "incremental_snapshot_delta",
        "base_snapshot_count": 6,
        "lifetime_scan": False,
        "chart_strategy": (
            "replace_affected_completed_weeks"
            if affected_completed_weeks
            else "clone_unchanged_open_week"
        ),
        "affected_completed_week_count": len(affected_completed_weeks),
        "prune_status": prune_status,
    }
