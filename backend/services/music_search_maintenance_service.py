"""Coordinate index and exact-snapshot rebuilds outside search GET requests."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.domains.metadata.artist_identity import get_identity_state
from backend.domains.metadata.track_credits import get_track_credit_state
from backend.domains.music_search.context import (
    MusicSearchFilterContext,
    build_music_search_filter_context,
)
from backend.domains.music_search.index import (
    get_music_search_index_state,
    music_search_source_revision,
    rebuild_music_search_index,
)
from backend.domains.music_search.revisions import (
    MusicSearchRevisionKind,
    bump_music_search_revisions,
)
from backend.domains.music_search.snapshot import (
    build_music_search_snapshot_set,
    get_ready_music_search_snapshot_key,
    mark_music_search_derived_data_dirty,
)
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.domains.settings.repository import SettingsRepository

MUSIC_SEARCH_SNAPSHOT_JOB_TYPE = "music_search_snapshot_rebuild"


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


def rebuild_current_music_search_derived_data(
    conn: sqlite3.Connection,
    *,
    rebuild_documents: bool = False,
) -> dict[str, Any]:
    if not _search_metadata_dependencies_ready(conn):
        raise RuntimeError("music-search metadata aggregate dependency is not ready")
    state = get_music_search_index_state(conn)
    expected_source = music_search_source_revision(conn)
    index_report: dict[str, Any] | None = None
    if (
        rebuild_documents
        or not state.get("active_generation_id")
        or state.get("source_revision") != expected_source
    ):
        index_report = rebuild_music_search_index(conn)
    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    snapshot_set_report = None
    if index_report is None and not rebuild_documents:
        snapshot_set_report = _revalidated_snapshot_set_report(conn, contexts)
    if snapshot_set_report is None:
        snapshot_set_report = build_music_search_snapshot_set(conn, contexts)
    default_snapshot = snapshot_set_report["variants"][0]
    return {
        "status": snapshot_set_report["status"],
        "index": index_report,
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


def mark_music_search_for_rebuild(
    *,
    reason: str,
    documents: bool = False,
    revision_kinds: tuple[MusicSearchRevisionKind, ...] = (),
    conn: sqlite3.Connection | None = None,
) -> None:
    """Fail closed immediately while an upstream rebuild is still pending."""
    target = conn or get_db(readonly=False)
    try:
        if revision_kinds:
            bump_music_search_revisions(target, *revision_kinds)
        mark_music_search_derived_data_dirty(
            target,
            reason=reason,
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
        if (
            rebuild_documents
            or not state.get("active_generation_id")
            or state.get("source_revision") != expected_source
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
    )
    return queue.enqueue_if_not_pending(job)
