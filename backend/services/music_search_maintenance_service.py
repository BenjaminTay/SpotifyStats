"""Coordinate index and exact-snapshot rebuilds outside search GET requests."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections.abc import Mapping
from typing import Any

from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.domains.metadata.artist_identity import get_identity_state
from backend.domains.metadata.track_credits import get_track_credit_state
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
    build_music_search_filter_context,
    legacy_v2_statistics_identity,
    legacy_v2_statistics_source_revision,
    music_search_variant_fingerprint,
)
from backend.domains.music_search.index import (
    expected_candidate_index_version,
    get_music_search_index_state,
    legacy_v2_music_search_source_revision,
    music_search_source_revision,
    rebuild_music_search_index,
)
from backend.domains.music_search.revisions import (
    MusicSearchRevisionKind,
    bump_music_search_revisions,
)
from backend.domains.music_search.snapshot import (
    build_music_search_snapshot_set,
    build_shared_full_music_search_snapshot_set,
    get_ready_music_search_snapshot_key,
    mark_music_search_derived_data_dirty,
    prepare_music_search_snapshot_set,
)
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.domains.playback.logical_timeline import PLAYBACK_EVENT_POLICY_VERSION
from backend.domains.settings.repository import SettingsRepository

MUSIC_SEARCH_SNAPSHOT_JOB_TYPE = "music_search_snapshot_rebuild"
logger = logging.getLogger(__name__)


class MusicSearchStatisticsReuseRequiredError(RuntimeError):
    """Raised when a reuse-only maintenance pass cannot reuse all six variants."""


def _search_metadata_dependencies_ready(conn: sqlite3.Connection) -> bool:
    for state in (get_identity_state(conn), get_track_credit_state(conn)):
        if state.get("rebuild_status") != "ready":
            return False
        if int(state.get("current_revision") or 0) != int(
            state.get("active_aggregate_revision") or 0
        ):
            return False
    return True


def _current_filter_values(conn: sqlite3.Connection) -> dict[str, Any]:
    settings = SettingsRepository(conn).load_all()
    return {
        "min_ms": int(settings.get("min_ms", 30000)),
        "music_only": bool(settings.get("music_only", True)),
        "merge_enabled": bool(settings.get("merge_enabled", True)),
        "dynamic_threshold": True,
        "max_merge_gap_minutes": int(settings.get("max_merge_gap_minutes", 5)),
        "merge_level": 2,
        "include_compilations": bool(settings.get("include_compilations", False)),
        "bb_top_n": int(settings.get("bb_top_n", 30)),
        "bb_album_top_n": int(settings.get("bb_album_top_n", 20)),
        "bb_artist_top_n": int(settings.get("bb_artist_top_n", 20)),
        "bb_week_start_dow": int(settings.get("bb_week_start_dow", 4)),
        "bb_week_start_hour": int(settings.get("bb_week_start_hour", 0)),
        "year_start": None,
        "year_end": None,
    }


def _revalidated_snapshot_set_report(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> dict[str, Any] | None:
    """Return the exact ready set without rebuilding any persisted rows."""
    if not all(
        get_ready_music_search_snapshot_key(conn, context.filter_fingerprint) is not None
        for context in contexts
    ):
        return None

    rows = conn.execute(
        """SELECT meta.snapshot_key, meta.filter_fingerprint, meta.status,
                  meta.builder_version,
                  (SELECT COUNT(*) FROM music_search_entity_context context
                   WHERE context.snapshot_key=meta.snapshot_key) AS entity_count
           FROM music_search_snapshot_meta meta
           WHERE meta.filter_fingerprint IN ({})""".format(",".join("?" for _ in contexts)),
        tuple(context.filter_fingerprint for context in contexts),
    ).fetchall()
    rows_by_fingerprint = {str(row[1]): row for row in rows}
    if len(rows_by_fingerprint) != len(contexts):
        return None

    variants = []
    for context in contexts:
        row = rows_by_fingerprint[context.filter_fingerprint]
        variants.append(
            {
                "status": "ready",
                "snapshot_key": str(row[0]),
                "filter_fingerprint": context.filter_fingerprint,
                "entity_count": int(row[4]),
                "source_revision": context.source_revision,
                "semantic_base_key": context.semantic_base_key,
                "merge_level": context.merge_level,
                "dynamic_threshold": context.dynamic_threshold,
                "builder_version": str(row[3]),
                "duration_ms": 0.0,
                "revalidated": True,
            }
        )
    return {
        "status": "ready",
        "semantic_base_key": contexts[0].semantic_base_key,
        "ready_count": len(variants),
        "failed_count": 0,
        "duration_ms": 0.0,
        "variants": variants,
        "revalidated": True,
    }


def build_shared_full_music_search_plan(
    conn: sqlite3.Connection,
    *,
    change_set: Any,
) -> dict[str, Any] | None:
    """Validate append semantics and serialize a bounded shared-rebuild plan."""
    if getattr(change_set, "strategy", None) != "incremental":
        return None
    semantic = dict(getattr(change_set, "semantic_revisions", {}) or {})
    filters = _current_filter_values(conn)
    setting_keys = (
        "min_ms",
        "music_only",
        "merge_enabled",
        "max_merge_gap_minutes",
        "bb_week_start_dow",
        "bb_week_start_hour",
        "include_compilations",
    )
    encoded = json.dumps(
        {key: filters.get(key) for key in setting_keys},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    settings_digest = hashlib.sha256(encoded.encode()).hexdigest()[:20]
    contexts = build_music_search_variant_contexts(conn, filters)
    current = contexts[0]
    if (
        semantic.get("playback_policy") != PLAYBACK_EVENT_POLICY_VERSION
        or semantic.get("settings") != settings_digest
        or int(semantic.get("artist_identity", -1)) != current.artist_identity_revision
        or int(semantic.get("track_credit", -1)) != current.track_credit_revision
    ):
        return None
    return {
        "schema_version": "music_search_shared_full_snapshot_v1",
        "source_generation_id": str(change_set.generation_id),
        "semantic_revisions": semantic,
    }


def _adopt_legacy_v2_snapshot_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> bool:
    """Re-key an exact current v2 set without recalculating statistics."""
    legacy = [legacy_v2_statistics_identity(conn, context) for context in contexts]
    legacy_bases = {base for base, _fingerprint in legacy}
    if len(legacy_bases) != 1:
        return False
    legacy_fingerprints = [fingerprint for _base, fingerprint in legacy]
    placeholders = ",".join("?" for _ in legacy_fingerprints)
    rows = conn.execute(
        f"""SELECT snapshot_key, filter_fingerprint, status, builder_version,
                   merge_level, dynamic_threshold, created_at, activated_at,
                   last_accessed_at, source_revision, semantic_base_key
            FROM music_search_snapshot_meta
            WHERE filter_fingerprint IN ({placeholders})""",
        tuple(legacy_fingerprints),
    ).fetchall()
    by_fingerprint = {str(row[1]): row for row in rows}
    selected_rows = [by_fingerprint.get(fingerprint) for fingerprint in legacy_fingerprints]
    if any(row is None for row in selected_rows) or any(
        str(row[2]) != "ready" or str(row[3]) != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
        for row in selected_rows
        if row is not None
    ):
        selected_rows = _source_equivalent_legacy_v2_rows(conn, contexts)
    if selected_rows is None or any(row is None for row in selected_rows):
        return False

    with conn:
        for context, row in zip(contexts, selected_rows):
            assert row is not None
            old_snapshot_key = str(row[0])
            new_snapshot_key = context.filter_fingerprint
            if old_snapshot_key == new_snapshot_key:
                continue
            conn.execute(
                "DELETE FROM music_search_entity_context WHERE snapshot_key=?",
                (new_snapshot_key,),
            )
            conn.execute(
                "DELETE FROM music_search_snapshot_meta WHERE snapshot_key=?",
                (new_snapshot_key,),
            )
            conn.execute(
                """INSERT INTO music_search_snapshot_meta(
                       snapshot_key, filter_fingerprint, source_revision, status,
                       created_at, activated_at, last_accessed_at, last_error,
                       semantic_base_key, merge_level, dynamic_threshold,
                       builder_version
                   ) VALUES (?, ?, ?, 'ready', ?, ?, ?, NULL, ?, ?, ?, ?)""",
                (
                    new_snapshot_key,
                    new_snapshot_key,
                    context.source_revision,
                    row[6],
                    row[7],
                    row[8],
                    context.semantic_base_key,
                    context.merge_level,
                    int(context.dynamic_threshold),
                    str(row[3]),
                ),
            )
            conn.execute(
                """UPDATE music_search_entity_context SET snapshot_key=?
                   WHERE snapshot_key=?""",
                (new_snapshot_key, old_snapshot_key),
            )
            conn.execute(
                "DELETE FROM music_search_snapshot_meta WHERE snapshot_key=?",
                (old_snapshot_key,),
            )
    return True


def _source_equivalent_legacy_v2_rows(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> list[sqlite3.Row | tuple[Any, ...]] | None:
    """Find one complete v2 set whose statistical inputs are still exact.

    The old opaque base included a random candidate generation id.  A changed
    generation must not force statistical recalculation when the persistent
    revisions, candidate source, builders, and full six-variant matrix remain
    identical.
    """
    if not contexts:
        return None
    index_state = get_music_search_index_state(conn)
    stored_index_source = str(index_state.get("source_revision") or "")
    normalization_version = str(index_state.get("normalization_version") or "")
    if not stored_index_source or not normalization_version:
        return None
    if stored_index_source != legacy_v2_music_search_source_revision(
        conn,
        normalization_version=normalization_version,
    ):
        return None
    expected_source = legacy_v2_statistics_source_revision(conn, contexts[0])
    current_base = contexts[0].semantic_base_key
    base_rows = conn.execute(
        """SELECT semantic_base_key,
                  MAX(COALESCE(activated_at, created_at, '')) AS latest_at
           FROM music_search_snapshot_meta
           WHERE source_revision=? AND status='ready' AND builder_version=?
             AND semantic_base_key IS NOT NULL AND semantic_base_key!=?
           GROUP BY semantic_base_key
           HAVING COUNT(*)=6
           ORDER BY latest_at DESC""",
        (expected_source, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION, current_base),
    ).fetchall()
    expected_variants = {(context.merge_level, context.dynamic_threshold) for context in contexts}
    for base_row in base_rows:
        base = str(base_row[0])
        rows = conn.execute(
            """SELECT snapshot_key, filter_fingerprint, status, builder_version,
                      merge_level, dynamic_threshold, created_at, activated_at,
                      last_accessed_at, source_revision, semantic_base_key
               FROM music_search_snapshot_meta
               WHERE semantic_base_key=?""",
            (base,),
        ).fetchall()
        by_variant: dict[tuple[int, bool], sqlite3.Row | tuple[Any, ...]] = {}
        valid = len(rows) == 6
        for row in rows:
            variant = (int(row[4]), bool(row[5]))
            fingerprint = str(row[1])
            if (
                variant in by_variant
                or str(row[0]) != fingerprint
                or str(row[2]) != "ready"
                or str(row[3]) != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
                or str(row[9]) != expected_source
                or fingerprint
                != music_search_variant_fingerprint(
                    base,
                    merge_level=variant[0],
                    dynamic_threshold=variant[1],
                )
            ):
                valid = False
                break
            by_variant[variant] = row
        if valid and set(by_variant) == expected_variants:
            return [
                by_variant[(context.merge_level, context.dynamic_threshold)] for context in contexts
            ]
    return None


def _ensure_current_music_search_candidate_index(
    conn: sqlite3.Connection,
    *,
    rebuild_documents: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Build or revalidate the lightweight candidate index only."""
    state = get_music_search_index_state(conn)
    expected_source = music_search_source_revision(conn)
    expected_index_version = expected_candidate_index_version(conn)
    index_report: dict[str, Any] | None = None
    index_rebuild_reasons = []
    if rebuild_documents:
        index_rebuild_reasons.append("explicit_rebuild_requested")
    if not state.get("active_generation_id"):
        index_rebuild_reasons.append("candidate_generation_missing")
    if state.get("source_revision") != expected_source:
        index_rebuild_reasons.append("candidate_source_revision_changed")
    if state.get("candidate_index_version") != expected_index_version:
        index_rebuild_reasons.append("candidate_index_version_changed")
    if index_rebuild_reasons:
        index_report = rebuild_music_search_index(conn)
    final_index_state = get_music_search_index_state(conn)
    candidate_report = {
        "action": "rebuilt" if index_report is not None else "revalidated",
        "reasons": index_rebuild_reasons or ["exact_candidate_index_version_ready"],
        "candidate_index_version": final_index_state.get("candidate_index_version"),
        "content_digest": final_index_state.get("content_digest"),
        "generation_id": final_index_state.get("active_generation_id"),
    }
    return index_report, candidate_report


def schedule_current_music_search_derived_data_rebuild(
    conn: sqlite3.Connection,
    *,
    rebuild_documents: bool = False,
    prewarm_yearly_review: bool = False,
    shared_full_snapshot_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish candidates now and defer the six expensive exact snapshots."""
    if not _search_metadata_dependencies_ready(conn):
        raise RuntimeError("music-search metadata aggregate dependency is not ready")
    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    index_report, candidate_report = _ensure_current_music_search_candidate_index(
        conn,
        rebuild_documents=rebuild_documents,
    )
    ready_report = _revalidated_snapshot_set_report(conn, contexts)
    if ready_report is not None:
        return {
            "status": "ready",
            "index": index_report,
            "candidate_index": candidate_report,
            "snapshot": ready_report["variants"][0],
            "snapshot_set": ready_report,
            "job_id": None,
        }

    # Write the full current set as pending before the job is queued so GET
    # readers report `warming` instead of falling through to unavailable/zero.
    prepare_music_search_snapshot_set(conn, contexts)
    enqueue_options: dict[str, Any] = {"conn": conn}
    if prewarm_yearly_review:
        enqueue_options["prewarm_yearly_review"] = True
    if shared_full_snapshot_plan is not None:
        enqueue_options["shared_full_snapshot_plan"] = dict(shared_full_snapshot_plan)
    job_id = enqueue_music_search_snapshot_rebuild(**enqueue_options)
    default_context = contexts[0]
    return {
        "status": "warming",
        "index": index_report,
        "candidate_index": candidate_report,
        "snapshot": {
            "status": "warming",
            "snapshot_key": default_context.filter_fingerprint,
            "filter_fingerprint": default_context.filter_fingerprint,
            "entity_count": 0,
            "source_revision": default_context.source_revision,
        },
        "snapshot_set": {
            "status": "warming",
            "semantic_base_key": default_context.semantic_base_key,
            "ready_count": 0,
            "failed_count": 0,
            "variants": [],
        },
        "job_id": job_id,
    }


def rebuild_current_music_search_derived_data(
    conn: sqlite3.Connection,
    *,
    rebuild_documents: bool = False,
    statistics_reuse_only: bool = False,
    shared_full_snapshot_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not _search_metadata_dependencies_ready(conn):
        raise RuntimeError("music-search metadata aggregate dependency is not ready")
    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    snapshot_set_report = _revalidated_snapshot_set_report(conn, contexts)
    if snapshot_set_report is None and _adopt_legacy_v2_snapshot_set(conn, contexts):
        snapshot_set_report = _revalidated_snapshot_set_report(conn, contexts)
    if snapshot_set_report is None and statistics_reuse_only:
        raise MusicSearchStatisticsReuseRequiredError(
            "all six exact music-search statistics variants must be maintained separately"
        )

    index_report, candidate_report = _ensure_current_music_search_candidate_index(
        conn,
        rebuild_documents=rebuild_documents,
    )
    # Index generation changes do not invalidate statistics.  Only the exact
    # statistics fingerprint controls whether the six variants are reused.
    snapshot_set_report = snapshot_set_report or _revalidated_snapshot_set_report(conn, contexts)
    shared_frame_fallback_reason: str | None = None
    if snapshot_set_report is None:
        if (
            shared_full_snapshot_plan is not None
            and shared_full_snapshot_plan.get("schema_version")
            == "music_search_shared_full_snapshot_v1"
        ):
            try:
                snapshot_set_report = build_shared_full_music_search_snapshot_set(
                    conn,
                    contexts,
                    source_generation_id=str(
                        shared_full_snapshot_plan.get("source_generation_id") or ""
                    ),
                )
                if snapshot_set_report is None:
                    shared_frame_fallback_reason = "incompatible_shared_full_plan"
            except Exception as exc:
                shared_frame_fallback_reason = type(exc).__name__
                logger.exception(
                    "Shared-frame music-search snapshot publish failed; falling back to full"
                )
        if shared_frame_fallback_reason is not None:
            # The shared build may have been fenced out by a concurrent import,
            # settings revision, or candidate generation.  Never feed its stale
            # context tuple into the compatibility full builder.
            contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
            snapshot_set_report = _revalidated_snapshot_set_report(conn, contexts)
        snapshot_set_report = snapshot_set_report or build_music_search_snapshot_set(conn, contexts)
        if shared_frame_fallback_reason is not None:
            snapshot_set_report["strategy"] = "full_fallback"
            snapshot_set_report["fallback_reason"] = shared_frame_fallback_reason
    default_snapshot = snapshot_set_report["variants"][0]
    return {
        "status": snapshot_set_report["status"],
        "index": index_report,
        "candidate_index": candidate_report,
        # Compatibility for callers that report the default L2/dynamic result.
        "snapshot": default_snapshot,
        "snapshot_set": snapshot_set_report,
    }


def handle_music_search_snapshot_rebuild(job: Job) -> None:
    conn = get_db(readonly=False)
    try:
        report = rebuild_current_music_search_derived_data(
            conn,
            rebuild_documents=bool(job.payload.get("rebuild_documents", False)),
            shared_full_snapshot_plan=(
                job.payload.get("shared_full_snapshot_plan")
                if isinstance(job.payload.get("shared_full_snapshot_plan"), dict)
                else None
            ),
        )
        # A setting/import mutation may land while a long six-variant build is
        # running.  Its exact base key differs, so enqueue one follow-up set;
        # the all-ready check makes this a no-op for an unchanged base.
        enqueue_music_search_snapshot_rebuild(conn=conn)
        if report["status"] != "ready":
            snapshot_set = report["snapshot_set"]
            raise RuntimeError(
                "music-search snapshot set incomplete: "
                f"ready={snapshot_set['ready_count']} failed={snapshot_set['failed_count']}"
            )
    finally:
        conn.close()
    if job.payload.get("prewarm_yearly_review"):
        from backend.services.yearly_review_service import start_yearly_review_prewarm_thread

        start_yearly_review_prewarm_thread()


def mark_music_search_for_rebuild(
    *,
    reason: str,
    documents: bool = False,
    revision_kinds: tuple[MusicSearchRevisionKind, ...] = (),
    conn: sqlite3.Connection | None = None,
    statistics: bool | None = None,
) -> None:
    """Fail closed immediately while an upstream rebuild is still pending."""
    target = conn or get_db(readonly=False)
    try:
        if revision_kinds:
            bump_music_search_revisions(target, *revision_kinds)
        statistic_kinds = {"playback", "billboard", "metadata", "settings"}
        invalidate_statistics = (
            statistics
            if statistics is not None
            else bool(set(revision_kinds) & statistic_kinds) or not revision_kinds
        )
        mark_music_search_derived_data_dirty(
            target,
            reason=reason,
            snapshots=invalidate_statistics,
            documents=documents,
        )
        target.commit()
    finally:
        if conn is None:
            target.close()


def _music_search_rebuild_job_key(
    *,
    rebuild_documents: bool,
    conn: sqlite3.Connection | None = None,
) -> str:
    target = conn or get_db()
    try:
        state = get_music_search_index_state(target)
        expected_source = music_search_source_revision(target)
        expected_index_version = expected_candidate_index_version(target)
        if (
            rebuild_documents
            or not state.get("active_generation_id")
            or state.get("source_revision") != expected_source
            or state.get("candidate_index_version") != expected_index_version
        ):
            return f"documents:{expected_source}"
        context = build_music_search_filter_context(
            target,
            _current_filter_values(target),
        )
        return f"snapshot-set:{context.semantic_base_key}"
    finally:
        if conn is None:
            target.close()


def enqueue_music_search_snapshot_rebuild(
    *,
    rebuild_documents: bool = False,
    entity_id: str | None = None,
    conn: sqlite3.Connection | None = None,
    prewarm_yearly_review: bool = False,
    shared_full_snapshot_plan: Mapping[str, Any] | None = None,
) -> str | None:
    queue = get_job_queue()
    if conn is not None and not queue_targets_connection(queue, conn):
        return None
    dependency_conn = conn or get_db()
    try:
        if not _search_metadata_dependencies_ready(dependency_conn):
            return None
    finally:
        if conn is None:
            dependency_conn.close()
    exact_key = entity_id or _music_search_rebuild_job_key(
        rebuild_documents=rebuild_documents,
        conn=conn,
    )
    if entity_id is None and exact_key.startswith("snapshot-set:"):
        target = conn or get_db()
        try:
            contexts = build_music_search_variant_contexts(
                target,
                _current_filter_values(target),
            )
            if all(
                get_ready_music_search_snapshot_key(target, context.filter_fingerprint) is not None
                for context in contexts
            ):
                return None
        finally:
            if conn is None:
                target.close()
    job = Job.create(
        MUSIC_SEARCH_SNAPSHOT_JOB_TYPE,
        "music_search_snapshot",
        exact_key,
        rebuild_documents=rebuild_documents,
        prewarm_yearly_review=prewarm_yearly_review,
        shared_full_snapshot_plan=(
            dict(shared_full_snapshot_plan) if shared_full_snapshot_plan is not None else None
        ),
    )
    return queue.enqueue_if_not_pending(job)
