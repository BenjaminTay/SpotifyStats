"""Shadow rebuild for track-credit-sensitive artist weekly aggregates."""

from __future__ import annotations

import logging
from sqlite3 import Connection

from backend.core.cache_manager import invalidate_all
from backend.core.db import (
    aggregation_partial_base_is_compatible,
    build_aggregations,
    get_db,
    refresh_aggregation_semantic_proof,
)
from backend.core.job_queue import (
    Job,
    JobQueue,
    get_job_queue,
    queue_targets_connection,
)
from backend.domains.billboard.data_loader import load_billboard_raw_for_artists
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import (
    get_track_credit_revision,
    get_track_credit_state,
    list_track_credit_change_sets,
)
from backend.domains.metadata.track_identity import get_track_identity_revision
from backend.domains.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

TRACK_CREDIT_REBUILD_JOB_TYPE = "track_credit_rebuild"


def track_credit_rebuild_entity_id(revision: int) -> str:
    """Return the durable dedupe key for one track-credit revision."""
    return f"global:revision:{int(revision)}"


def ensure_track_credit_rebuild_job(
    revision: int,
    *,
    queue: JobQueue | None = None,
    conn: Connection | None = None,
) -> str | None:
    """Idempotently ensure that a specific revision has durable queue work.

    Revision-specific identities prevent a running older rebuild from
    swallowing a later mutation.  ``None`` means an equivalent job is already
    pending/running (or the supplied connection intentionally targets another
    database in an isolated test/maintenance process).
    """
    target_queue = queue or get_job_queue()
    if conn is not None and not queue_targets_connection(target_queue, conn):
        return None
    normalized_revision = int(revision)
    return target_queue.enqueue_if_not_pending(
        Job.create(
            TRACK_CREDIT_REBUILD_JOB_TYPE,
            "track_credit",
            track_credit_rebuild_entity_id(normalized_revision),
            revision=normalized_revision,
        )
    )


def _ensure_latest_if_needed(conn: Connection, job_revision: int) -> bool:
    """Return whether this job is obsolete after ensuring latest work exists."""
    state = get_track_credit_state(conn)
    current_revision = int(state.get("current_revision") or 0)
    active_revision = int(state.get("active_aggregate_revision") or 0)
    if active_revision < job_revision and current_revision <= job_revision:
        return False
    if current_revision > active_revision:
        ensure_track_credit_rebuild_job(current_revision, conn=conn)
    logger.info(
        "Superseding track-credit rebuild revision %s (current=%s, active=%s)",
        job_revision,
        current_revision,
        active_revision,
    )
    return True


def _is_role_only_change_range(
    conn: Connection,
    *,
    active_revision: int,
    target_revision: int,
) -> bool:
    """Return whether change-set evidence proves aggregates are unchanged."""
    if target_revision <= active_revision:
        return False
    changes = list_track_credit_change_sets(
        conn,
        after_revision=active_revision,
        through_revision=target_revision,
    )
    covered_revisions = {int(change["to_revision"]) for change in changes}
    expected_revisions = set(range(active_revision + 1, target_revision + 1))
    return (
        bool(changes)
        and covered_revisions == expected_revisions
        and all(not bool(change.get("statistics_membership_changed")) for change in changes)
    )


def _publish_role_only_revision(conn: Connection, revision: int) -> bool:
    """Advance aggregate proof without recomputing unchanged artist facts."""
    state = get_track_credit_state(conn)
    active_revision = int(state.get("active_aggregate_revision") or 0)
    if not _is_role_only_change_range(
        conn,
        active_revision=active_revision,
        target_revision=revision,
    ):
        return False

    settings = SettingsRepository(conn).load_all()
    min_ms = int(settings.get("min_ms", 30_000))
    music_only = bool(settings.get("music_only", True))
    week_start_dow = int(settings.get("bb_week_start_dow", 4))
    week_start_hour = int(settings.get("bb_week_start_hour", 0))
    dynamic_threshold = True
    max_merge_gap_minutes = int(settings.get("max_merge_gap_minutes", 5))
    identity_revision = get_identity_revision(conn)
    track_identity_revision = get_track_identity_revision(conn)
    if not aggregation_partial_base_is_compatible(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        identity_revision=identity_revision,
        track_credit_revision=revision,
        track_identity_revision=track_identity_revision,
        mutable_dependency_keys=frozenset({"track_credit_revision"}),
    ):
        logger.info(
            "Track-credit role-only revision %s cannot reuse stale aggregate proof",
            revision,
        )
        return False

    conn.execute("BEGIN IMMEDIATE")
    current_state = get_track_credit_state(conn)
    if (
        int(current_state.get("current_revision") or 0) != revision
        or int(current_state.get("active_aggregate_revision") or 0) != active_revision
    ):
        conn.rollback()
        _ensure_latest_if_needed(conn, revision)
        return True
    conn.execute(
        """UPDATE track_credit_state
           SET active_aggregate_revision=?, rebuild_status='ready', last_error=NULL,
               updated_at=datetime('now') WHERE state_id=1""",
        (revision,),
    )
    refresh_aggregation_semantic_proof(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        identity_revision=identity_revision,
        track_credit_revision=revision,
        track_identity_revision=track_identity_revision,
    )
    from backend.domains.music_search.snapshot import (
        promote_role_only_music_search_snapshots,
    )
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.services.music_search_maintenance_service import (
        _current_filter_values,
        mark_music_search_for_rebuild,
    )

    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    statistics_promoted = promote_role_only_music_search_snapshots(conn, contexts)

    # Role labels affect candidate presentation, but canonical artist
    # membership and every aggregate/statistics value remain unchanged.
    mark_music_search_for_rebuild(
        reason="track credit role-only revision published",
        documents=True,
        revision_kinds=("candidate",),
        statistics=False,
        conn=conn,
    )
    # Candidate documents are cheap enough to rebuild in this already
    # background worker.  Calling the combined snapshot maintenance job here
    # would unnecessarily rebuild all four statistics variants.
    from backend.domains.music_search.index import rebuild_music_search_index

    try:
        rebuild_music_search_index(conn)
    except Exception:
        logger.exception(
            "Role-only credit revision %s published; candidate shadow rebuild will retry",
            revision,
        )
        from backend.services.music_search_maintenance_service import (
            enqueue_music_search_snapshot_rebuild,
        )

        enqueue_music_search_snapshot_rebuild(rebuild_documents=True, conn=conn)
        return True
    if not statistics_promoted:
        from backend.services.music_search_maintenance_service import (
            enqueue_music_search_snapshot_rebuild,
        )

        enqueue_music_search_snapshot_rebuild(rebuild_documents=False, conn=conn)
    return True


def _publish_membership_delta(conn: Connection, revision: int) -> bool:
    """Publish a bounded add/remove delta, or explicitly request full fallback."""
    state = get_track_credit_state(conn)
    active_revision = int(state.get("active_aggregate_revision") or 0)
    if revision <= active_revision:
        return False
    changes = list_track_credit_change_sets(
        conn,
        after_revision=active_revision,
        through_revision=revision,
    )
    covered_revisions = {int(change["to_revision"]) for change in changes}
    if covered_revisions != set(range(active_revision + 1, revision + 1)) or not any(
        bool(change.get("statistics_membership_changed")) for change in changes
    ):
        return False

    # Candidate documents are a separate, cheap shadow generation.  Publish
    # them first so a newly credited artist is present before snapshot rows are
    # validated; failure still leaves the previous candidate generation live.
    from backend.domains.music_search.index import rebuild_music_search_index
    from backend.domains.music_search.track_credit_delta import (
        TrackCreditDeltaIncompatibleError,
        apply_track_credit_statistics_delta,
    )
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.services.music_search_maintenance_service import (
        _current_filter_values,
        enqueue_music_search_snapshot_rebuild,
    )

    rebuild_music_search_index(conn)
    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    try:
        report = apply_track_credit_statistics_delta(
            conn,
            contexts,
            changes,
            target_revision=revision,
        )
    except TrackCreditDeltaIncompatibleError as exc:
        logger.info(
            "Track-credit revision %s requires shared-full fallback: %s",
            revision,
            exc,
        )
        return False
    logger.info("Published bounded track-credit statistics delta: %s", report)
    # The snapshot job will exact-reuse the four ready targets and builds the
    # year-end projection asynchronously; it does not rescan lifetime facts.
    enqueue_music_search_snapshot_rebuild(rebuild_documents=False, conn=conn)
    return True


def handle_track_credit_rebuild(job: Job) -> None:
    conn = get_db(readonly=False)
    revision = int(job.payload.get("revision") or get_track_credit_revision(conn))
    try:
        if _ensure_latest_if_needed(conn, revision):
            return
        if _publish_role_only_revision(conn, revision):
            return
        if _publish_membership_delta(conn, revision):
            return
        conn.execute(
            """UPDATE track_credit_state
               SET rebuild_status='running', last_error=NULL, updated_at=datetime('now')
               WHERE state_id=1 AND current_revision=?""",
            (revision,),
        )
        conn.commit()
        settings = SettingsRepository(conn).load_all()
        min_ms = int(settings.get("min_ms", 30_000))
        music_only = bool(settings.get("music_only", True))
        week_start_dow = int(settings.get("bb_week_start_dow", 4))
        week_start_hour = int(settings.get("bb_week_start_hour", 0))
        dynamic_threshold = True
        max_merge_gap_minutes = int(settings.get("max_merge_gap_minutes", 5))

        identity_revision = get_identity_revision(conn)
        track_identity_revision = get_track_identity_revision(conn)
        if not aggregation_partial_base_is_compatible(
            conn,
            min_ms=min_ms,
            music_only=music_only,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            identity_revision=identity_revision,
            track_credit_revision=revision,
            track_identity_revision=track_identity_revision,
            mutable_dependency_keys=frozenset(
                {"track_credit_revision", "credit_membership_revision"}
            ),
        ):
            logger.info(
                "Track-credit revision %s requires a full Billboard aggregate rebuild",
                revision,
            )
            build_aggregations(
                min_ms=min_ms,
                music_only=music_only,
                week_start_dow=week_start_dow,
                week_start_hour=week_start_hour,
                dynamic_threshold=dynamic_threshold,
                max_merge_gap_minutes=max_merge_gap_minutes,
            )
            conn.close()
            conn = get_db(readonly=False)
            from backend.services.music_search_maintenance_service import (
                enqueue_music_search_snapshot_rebuild,
                mark_music_search_for_rebuild,
            )

            mark_music_search_for_rebuild(
                reason="track credit full aggregate fallback published",
                documents=True,
                revision_kinds=("metadata", "candidate"),
                conn=conn,
            )
            enqueue_music_search_snapshot_rebuild(
                rebuild_documents=True,
                conn=conn,
            )
            return

        invalidate_all()
        frame = load_billboard_raw_for_artists(
            min_ms,
            music_only,
            week_start_dow,
            week_start_hour,
            dynamic_threshold,
            max_merge_gap_minutes,
        )
        from backend.domains.playback.logical_timeline import (
            get_billboard_weighted_frame,
        )

        weighted = get_billboard_weighted_frame(frame)
        if weighted is None:
            weighted = frame
        if not weighted.empty and not {"play_count", "total_ms"} <= set(weighted.columns):
            weighted = weighted.copy()
            weighted["play_count"] = 1
            weighted["total_ms"] = weighted["ms_played"]
        grouped = (
            weighted.groupby(["billboard_week", "artist_id"], as_index=False).agg(
                play_count=("play_count", "sum"), total_ms=("total_ms", "sum")
            )
            if not weighted.empty
            else weighted
        )
        rows = (
            [
                (
                    str(row.billboard_week),
                    int(row.artist_id),
                    int(row.play_count),
                    int(row.total_ms),
                )
                for row in grouped.itertuples(index=False)
            ]
            if not grouped.empty
            else []
        )
        conn.execute(
            """CREATE TEMP TABLE IF NOT EXISTS agg_weekly_artists_credit_shadow (
                   billboard_week TEXT NOT NULL,
                   artist_id INTEGER NOT NULL,
                   play_count INTEGER NOT NULL,
                   total_ms INTEGER NOT NULL,
                   PRIMARY KEY (billboard_week, artist_id)
               )"""
        )
        conn.execute("DELETE FROM agg_weekly_artists_credit_shadow")
        conn.executemany(
            """INSERT INTO agg_weekly_artists_credit_shadow(
                   billboard_week, artist_id, play_count, total_ms
               ) VALUES (?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        if get_track_credit_revision(conn) != revision:
            conn.rollback()
            _ensure_latest_if_needed(conn, revision)
            return
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute(
            """INSERT INTO agg_weekly_artists(
                   billboard_week, artist_id, play_count, total_ms
               ) SELECT billboard_week, artist_id, play_count, total_ms
                 FROM agg_weekly_artists_credit_shadow"""
        )
        refresh_aggregation_semantic_proof(
            conn,
            min_ms=min_ms,
            music_only=music_only,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            identity_revision=identity_revision,
            track_credit_revision=revision,
            track_identity_revision=track_identity_revision,
            build_strategy="credit_full_artist",
        )
        conn.execute(
            """UPDATE track_credit_state
               SET active_aggregate_revision=?, rebuild_status='ready', last_error=NULL,
                   updated_at=datetime('now') WHERE state_id=1""",
            (revision,),
        )
        from backend.services.music_search_maintenance_service import (
            enqueue_music_search_snapshot_rebuild,
            mark_music_search_for_rebuild,
        )

        mark_music_search_for_rebuild(
            reason="track credit aggregate published",
            documents=True,
            revision_kinds=("metadata", "candidate"),
            conn=conn,
        )
        enqueue_music_search_snapshot_rebuild(
            rebuild_documents=True,
            conn=conn,
        )
    except Exception as exc:
        conn.rollback()
        # A newer mutation makes every result and failure from this worker
        # obsolete.  Preserve the newer revision's pending state and ensure its
        # own revision-specific job exists instead of poisoning it as failed.
        if _ensure_latest_if_needed(conn, revision):
            return
        conn.execute(
            """UPDATE track_credit_state
               SET rebuild_status='failed', last_error=?, updated_at=datetime('now')
               WHERE state_id=1 AND current_revision=?""",
            (str(exc)[:500], revision),
        )
        conn.commit()
        raise
    finally:
        conn.close()
        invalidate_all()
