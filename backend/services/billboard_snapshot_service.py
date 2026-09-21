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


def _year_end_snapshot_params(filters: dict, year: int | None) -> dict:
    """Return the exact normalized params used by the Year-End API."""
    from backend.domains.billboard.year_end import (
        YEAR_END_ALBUM_TOP_N,
        YEAR_END_ARTIST_TOP_N,
        YEAR_END_TRACK_TOP_N,
    )

    filter_names = (
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
    return {
        **{key: filters[key] for key in filter_names if key in filters},
        "year": year,
        "year_end_top_n": YEAR_END_TRACK_TOP_N,
        "year_end_album_top_n": YEAR_END_ALBUM_TOP_N,
        "year_end_artist_top_n": YEAR_END_ARTIST_TOP_N,
    }


def _billboard_default_snapshots_available(*, allow_lkg: bool) -> bool:
    """Return whether every default Billboard response has an exact snapshot.

    Startup should only enqueue a rebuild for a missing, corrupt, or stale
    snapshot.  In particular, a healthy process restart must not turn into a
    forced full Billboard rebuild merely because the application started.
    """
    from backend.domains.billboard.persistent_cache import (
        build_cache_context,
        load_persisted_snapshot,
    )

    filters = configured_billboard_filters()
    for family in ("weekly", "all_time", "full_data", "records", "power_scores", "summaries"):
        context = build_cache_context(family, filters)
        if load_persisted_snapshot(context, allow_lkg=allow_lkg) is None:
            return False

    latest_context = build_cache_context(
        "year_end",
        _year_end_snapshot_params(filters, year=None),
    )
    latest = load_persisted_snapshot(latest_context, allow_lkg=allow_lkg)
    if latest is None:
        return False
    available_years = latest.get("meta", {}).get("available_years", [])
    if not isinstance(available_years, list):
        return False
    for year in available_years:
        context = build_cache_context(
            "year_end",
            _year_end_snapshot_params(filters, year=int(year)),
        )
        if load_persisted_snapshot(context, allow_lkg=allow_lkg) is None:
            return False
    return True


def billboard_default_snapshots_ready() -> bool:
    return _billboard_default_snapshots_available(allow_lkg=False)


def billboard_default_snapshots_have_lkg() -> bool:
    return _billboard_default_snapshots_available(allow_lkg=True)


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
    if reason == "application startup":
        try:
            if billboard_default_snapshots_ready():
                logger.info("Billboard snapshots already current; startup rebuild skipped.")
                return None
        except Exception:
            logger.exception("Unable to verify default Billboard snapshots before startup enqueue")
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
    from backend.domains.billboard.build_context import BillboardBuildContext
    from backend.domains.billboard.persistent_cache import _lock_for, build_cache_context
    from backend.services.billboard_service import (
        compute_all_time_staged,
        compute_billboard_data,
        compute_power_scores_staged,
        compute_records_staged,
        compute_summaries_staged,
        compute_weekly_data,
        compute_year_end_staged,
    )

    filters = configured_billboard_filters()
    generation = build_cache_context("full_data", filters)
    # Keep concurrent maintenance callers from dividing family ownership and
    # rebuilding the same invocation-local facts in separate contexts.
    with _lock_for("generation:" + generation["cache_key"]):
        with BillboardBuildContext(filters) as facts:
            compute_weekly_data(**filters, force_rebuild=True, _build_context=facts)
            compute_all_time_staged(**filters, force_rebuild=True, _build_context=facts)
            compute_billboard_data(**filters, force_rebuild=True, _build_context=facts)
            compute_records_staged(**filters, force_rebuild=True, _build_context=facts)
            # An existing exact all_time row can short-circuit its staged builder.
            # Ensure the independently readable families also exist in that case.
            compute_power_scores_staged(**filters, force_rebuild=True, _build_context=facts)
            compute_summaries_staged(**filters, force_rebuild=True, _build_context=facts)
            year_end_filters = _year_end_snapshot_params(filters, year=None)
            year_end_filters.pop("year")
            latest = compute_year_end_staged(
                **year_end_filters, year=None, force_rebuild=True, _build_context=facts
            )
            years = latest.get("meta", {}).get("available_years", [])
            rebuilt_years: list[int] = []
            for year in years:
                compute_year_end_staged(
                    **year_end_filters, year=int(year), force_rebuild=True, _build_context=facts
                )
                rebuilt_years.append(int(year))
            # all_time publishes power_scores and summaries through its existing
            # staged builder; records needs its own publication in addition to full_data.
            return {
                "families": [
                    "weekly",
                    "all_time",
                    "full_data",
                    "records",
                    "power_scores",
                    "summaries",
                    "year_end",
                ],
                "years": rebuilt_years,
            }


def handle_billboard_snapshot_rebuild(job: Job) -> None:
    """JobQueue handler; stale LKG rows remain available if this fails."""
    result = rebuild_default_billboard_snapshots()
    logger.info(
        "Billboard snapshots rebuilt: reason=%s years=%s",
        job.payload.get("reason", "unknown"),
        result.get("years", []),
    )
