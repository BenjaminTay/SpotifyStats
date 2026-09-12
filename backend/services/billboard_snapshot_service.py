"""Background generation for durable Billboard response snapshots."""

from __future__ import annotations

import logging
from sqlite3 import Connection

from backend.core.db import get_db
from backend.core.job_queue import Job, JobQueue, get_job_queue, queue_targets_connection
from backend.domains.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

BILLBOARD_SNAPSHOT_REBUILD_JOB_TYPE = "billboard_snapshot_rebuild"
BILLBOARD_SNAPSHOT_ENTITY_ID = "default"


def configured_billboard_filters(conn: Connection | None = None) -> dict:
    """Return the exact default filter set used by omitted-query endpoints."""
    owns_conn = conn is None
    target = conn or get_db(readonly=True)
    try:
        settings = SettingsRepository(target).load_all()
        return {
            "min_ms": int(settings.get("min_ms", 30_000)),
            "music_only": bool(settings.get("music_only", True)),
            "merge_enabled": bool(settings.get("merge_enabled", True)),
            "bb_top_n": int(settings.get("bb_top_n", 30)),
            "bb_album_top_n": int(settings.get("bb_album_top_n", 20)),
            "bb_artist_top_n": int(settings.get("bb_artist_top_n", 20)),
            "bb_week_start_dow": int(settings.get("bb_week_start_dow", 4)),
            "bb_week_start_hour": int(settings.get("bb_week_start_hour", 0)),
            "year_start": None,
            "year_end": None,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": int(settings.get("max_merge_gap_minutes", 5)),
            "merge_level": 2,
            "include_compilations": bool(settings.get("include_compilations", False)),
        }
    finally:
        if owns_conn:
            target.close()


def enqueue_billboard_snapshot_rebuild(
    reason: str,
    *,
    queue: JobQueue | None = None,
    conn: Connection | None = None,
) -> str | None:
    """Queue one deduplicated default snapshot rebuild after a mutation."""
    target_queue = queue or get_job_queue()
    # A queue created by a standalone unit/maintenance function has no worker
    # lifecycle yet. Do not leave an in-memory job that can never run.
    if getattr(target_queue, "database_path", None) is None:
        return None
    try:
        from backend.domains.billboard.chart_load_rank import billboard_revision_state

        state = billboard_revision_state()
        if not (state[0] == state[1] and state[2] == state[3] and state[4] == "ready:ready"):
            return None
    except Exception:
        logger.exception("Unable to verify Billboard dependencies before enqueue")
        return None
    if conn is not None and not queue_targets_connection(target_queue, conn):
        return None
    return target_queue.enqueue_if_not_pending(
        Job.create(
            BILLBOARD_SNAPSHOT_REBUILD_JOB_TYPE,
            "billboard",
            BILLBOARD_SNAPSHOT_ENTITY_ID,
            reason=reason,
        )
    )


def rebuild_default_billboard_snapshots() -> dict[str, object]:
    """Force-build the default response families for the current source state."""
    from backend.services.billboard_service import (
        compute_all_time_staged,
        compute_billboard_data,
        compute_weekly_data,
        compute_year_end_staged,
    )

    filters = configured_billboard_filters()
    compute_weekly_data(**filters, force_rebuild=True)
    compute_all_time_staged(**filters, force_rebuild=True)
    compute_billboard_data(**filters, force_rebuild=True)
    year_end_filter_names = (
        "min_ms",
        "music_only",
        "bb_top_n",
        "bb_album_top_n",
        "bb_artist_top_n",
        "bb_week_start_dow",
        "bb_week_start_hour",
        "merge_level",
        "dynamic_threshold",
        "max_merge_gap_minutes",
        "include_compilations",
        "merge_enabled",
    )
    year_end_filters = {key: filters[key] for key in year_end_filter_names if key in filters}
    latest = compute_year_end_staged(**year_end_filters, year=None, force_rebuild=True)
    years = latest.get("meta", {}).get("available_years", [])
    rebuilt_years: list[int] = []
    for year in years:
        compute_year_end_staged(**year_end_filters, year=int(year), force_rebuild=True)
        rebuilt_years.append(int(year))
    return {"families": ["weekly", "all_time", "full_data", "year_end"], "years": rebuilt_years}


def handle_billboard_snapshot_rebuild(job: Job) -> None:
    """JobQueue handler; stale LKG rows remain available if this fails."""
    result = rebuild_default_billboard_snapshots()
    logger.info(
        "Billboard snapshots rebuilt: reason=%s years=%s",
        job.payload.get("reason", "unknown"),
        result.get("years", []),
    )
