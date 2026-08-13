"""Cached service facade for the deterministic Yearly Review V2."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from backend.core.db import get_db
from backend.domains.billboard.year_end import YEAR_END_SEMANTICS_VERSION
from backend.domains.metadata.artist_languages import artist_language_fact_revision
from backend.domains.settings.repository import SettingsRepository
from backend.domains.yearly_review.artifact_cache import (
    has_persisted_artifact,
    load_persisted_artifact,
    store_persisted_artifact,
)
from backend.domains.yearly_review.context import build_yearly_review_context
from backend.domains.yearly_review.orchestrator import build_yearly_review_artifact
from backend.domains.yearly_review.policies import (
    HIGHLIGHT_POLICY_VERSION,
    RELATIONSHIP_POLICY_VERSION,
    SEASON_STAGE_POLICY_VERSION,
)
from backend.domains.yearly_review.versions import (
    YEARLY_REVIEW_CONTENT_VERSION,
    YEARLY_REVIEW_SCHEMA_VERSION,
)
from backend.models.yearly_review import (
    YearlyReviewAvailableYearsResponse,
    YearlyReviewFilterContext,
    YearlyReviewGenerationResponse,
    YearlyReviewRecordsPage,
    YearlyReviewResponse,
)
from backend.services.yearly_review_generation import (
    PreparedYearlyReview,
    YearlyReviewGenerationCoordinator,
)

logger = logging.getLogger(__name__)
_persistent_cache_bypass: ContextVar[bool] = ContextVar(
    "yearly_review_persistent_cache_bypass",
    default=False,
)
_prewarm_lock = threading.Lock()
_prewarm_thread: threading.Thread | None = None


@contextmanager
def bypass_yearly_review_persistent_cache():
    """Force a true recompute while still refreshing the persistent artifact."""
    token = _persistent_cache_bypass.set(True)
    try:
        yield
    finally:
        _persistent_cache_bypass.reset(token)


def database_revision() -> str:
    """Fingerprint report source facts without reacting to unrelated SQLite writes.

    File mtimes and WAL sizes also change when jobs, task logs, or cache rows are
    written.  Keying the annual artifact on those physical details caused a hot
    request to rebuild even though no playback fact had changed.  Imports are
    append-only in normal operation, so stable core-table cardinalities, maxima,
    total duration, and the schema migration version form the source revision;
    governed metadata has its own explicit revisions in the cache key.
    """
    conn = get_db(readonly=True)
    try:
        row = conn.execute(
            """SELECT
                   (SELECT COUNT(*) FROM plays) AS play_count,
                   (SELECT COALESCE(MAX(play_id), 0) FROM plays) AS max_play_id,
                   (SELECT COALESCE(MAX(ts), '') FROM plays) AS latest_play_ts,
                   (SELECT COALESCE(SUM(ms_played), 0) FROM plays) AS total_ms,
                   (SELECT COUNT(*) FROM tracks) AS track_count,
                   (SELECT COALESCE(MAX(track_id), 0) FROM tracks) AS max_track_id,
                   (SELECT COUNT(*) FROM albums) AS album_count,
                   (SELECT COALESCE(MAX(album_id), 0) FROM albums) AS max_album_id,
                   (SELECT COUNT(*) FROM artists) AS artist_count,
                   (SELECT COALESCE(MAX(artist_id), 0) FROM artists) AS max_artist_id,
                   (SELECT COALESCE(MAX(version), 0) FROM schema_migrations)
                       AS schema_version"""
        ).fetchone()
        encoded = json.dumps(list(row), ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()[:20]
    finally:
        conn.close()


def _language_revision() -> str:
    conn = get_db(readonly=True)
    try:
        return artist_language_fact_revision(conn)
    except Exception:
        return "unavailable"
    finally:
        conn.close()


def build_yearly_review_cache_key(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    language_revision: str,
    db_revision: str,
) -> str:
    payload = {
        "year": year,
        "schema_version": YEARLY_REVIEW_SCHEMA_VERSION,
        "content_version": YEARLY_REVIEW_CONTENT_VERSION,
        "filter_fingerprint": context.filter_fingerprint,
        "relationship_policy_version": RELATIONSHIP_POLICY_VERSION,
        "highlight_policy_version": HIGHLIGHT_POLICY_VERSION,
        "season_stage_policy_version": SEASON_STAGE_POLICY_VERSION,
        "billboard_semantics_version": YEAR_END_SEMANTICS_VERSION,
        "display_taxonomy_version": context.display_taxonomy_version,
        "artist_metadata_revision": context.artist_metadata_revision,
        "language_revision": language_revision,
        "artist_identity_revision": context.artist_identity_revision,
        "track_credit_revision": context.track_credit_revision,
        "track_group_revision": context.track_group_revision,
        "album_project_revision": context.album_project_revision,
        "database_revision": db_revision,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


@lru_cache(maxsize=16)
def _build_cached_artifact(
    year: int,
    context_json: str,
    cache_key: str,
    db_revision: str,
) -> dict[str, Any]:
    context = YearlyReviewFilterContext.model_validate_json(context_json)
    if not _persistent_cache_bypass.get():
        try:
            persisted = load_persisted_artifact(cache_key)
        except Exception:
            logger.exception("Yearly Review persistent cache read failed")
        else:
            if persisted is not None:
                return persisted

    conn = get_db(readonly=True)
    try:
        artifact = build_yearly_review_artifact(conn, year, context)
        result = {
            "report": artifact.report.model_dump(mode="json"),
            "record_catalog": artifact.record_catalog,
        }
    finally:
        conn.close()
    try:
        store_persisted_artifact(
            cache_key,
            result,
            year=year,
            filter_fingerprint=context.filter_fingerprint,
            source_db_revision=db_revision,
        )
    except Exception:
        logger.exception("Yearly Review persistent cache write failed")
    return result


def _prepare_artifact(year: int, context: YearlyReviewFilterContext) -> PreparedYearlyReview:
    db_revision = database_revision()
    return _prepare_artifact_with_revisions(
        year,
        context,
        db_revision=db_revision,
        language_revision=_language_revision(),
    )


def _prepare_artifact_with_revisions(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    db_revision: str,
    language_revision: str,
) -> PreparedYearlyReview:
    key = build_yearly_review_cache_key(
        year,
        context,
        language_revision=language_revision,
        db_revision=db_revision,
    )
    return PreparedYearlyReview(
        year=year,
        context=context,
        context_json=context.model_dump_json(),
        cache_key=key,
        db_revision=db_revision,
    )


def _prepare_artifacts(
    years: list[int], context: YearlyReviewFilterContext
) -> dict[int, PreparedYearlyReview]:
    db_revision = database_revision()
    language_revision = _language_revision()
    return {
        year: _prepare_artifact_with_revisions(
            year,
            context,
            db_revision=db_revision,
            language_revision=language_revision,
        )
        for year in dict.fromkeys(years)
    }


def _refresh_prepared_artifact(prepared: PreparedYearlyReview) -> PreparedYearlyReview:
    filters = SimpleNamespace(
        min_ms=prepared.context.min_ms,
        music_only=prepared.context.music_only,
        merge_enabled=prepared.context.merge_enabled,
        dynamic_threshold=prepared.context.dynamic_threshold,
        max_merge_gap_minutes=prepared.context.max_merge_gap_minutes,
        merge_level=prepared.context.merge_level,
        include_compilations=prepared.context.include_compilations,
        bb_top_n=prepared.context.bb_top_n,
        bb_album_top_n=prepared.context.bb_album_top_n,
        bb_artist_top_n=prepared.context.bb_artist_top_n,
        bb_week_start_dow=prepared.context.bb_week_start_dow,
        bb_week_start_hour=prepared.context.bb_week_start_hour,
    )
    conn = get_db(readonly=True)
    try:
        context = build_yearly_review_context(conn, filters)
    finally:
        conn.close()
    return _prepare_artifact(prepared.year, context)


def _build_prepared_artifact(prepared: PreparedYearlyReview) -> dict[str, Any]:
    return _build_cached_artifact(
        prepared.year,
        prepared.context_json,
        prepared.cache_key,
        prepared.db_revision,
    )


_generation_coordinator = YearlyReviewGenerationCoordinator(
    prepare=_prepare_artifact,
    refresh=_refresh_prepared_artifact,
    build=_build_prepared_artifact,
    is_ready=has_persisted_artifact,
)


def _artifact(year: int, context: YearlyReviewFilterContext) -> dict[str, Any]:
    if _persistent_cache_bypass.get():
        return _build_prepared_artifact(_prepare_artifact(year, context))
    return _generation_coordinator.get_or_build(year, context)


def build_default_yearly_review_context() -> YearlyReviewFilterContext:
    """Build the same default context used by an omitted-query API request."""
    conn = get_db(readonly=True)
    try:
        settings = SettingsRepository(conn).load_all()
        filters = SimpleNamespace(
            min_ms=int(settings["min_ms"]),
            music_only=bool(settings["music_only"]),
            merge_enabled=bool(settings["merge_enabled"]),
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
            merge_level=2,
            include_compilations=bool(settings["include_compilations"]),
            bb_top_n=int(settings["bb_top_n"]),
            bb_album_top_n=int(settings["bb_album_top_n"]),
            bb_artist_top_n=int(settings["bb_artist_top_n"]),
            bb_week_start_dow=int(settings["bb_week_start_dow"]),
            bb_week_start_hour=int(settings["bb_week_start_hour"]),
        )
        return build_yearly_review_context(conn, filters)
    finally:
        conn.close()


def prewarm_latest_yearly_review() -> int | None:
    """Persist the latest report in a background-safe, exact-key cache."""
    available = get_yearly_review_available_years()
    if available.latest_year is None:
        return None
    get_yearly_review(available.latest_year, build_default_yearly_review_context())
    return available.latest_year


def prewarm_yearly_reviews(
    years: list[int],
    context: YearlyReviewFilterContext,
    *,
    foreground_year: int | None = None,
) -> YearlyReviewGenerationResponse:
    """Queue exact-context reports, putting the visible year ahead of background work."""
    requested = list(dict.fromkeys(years))
    if foreground_year is not None and foreground_year not in requested:
        requested.append(foreground_year)
    available = set(get_yearly_review_available_years().years)
    unavailable = [year for year in requested if year not in available]
    if unavailable:
        joined = ",".join(str(year) for year in unavailable)
        raise ValueError(f"unavailable_years:{joined}")
    prepared = _prepare_artifacts(requested, context)
    if foreground_year is not None:
        _generation_coordinator.enqueue_prepared(
            prepared[foreground_year],
            foreground=True,
        )
    for year in sorted((year for year in requested if year != foreground_year), reverse=True):
        _generation_coordinator.enqueue_prepared(
            prepared[year],
            foreground=False,
        )
    tasks = []
    for year in requested:
        status = _generation_coordinator.status_prepared(prepared[year])
        if status is not None:
            tasks.append(status)
    return YearlyReviewGenerationResponse(tasks=tasks)


def get_yearly_review_generation_status(
    context: YearlyReviewFilterContext,
    *,
    years: list[int] | None = None,
) -> YearlyReviewGenerationResponse:
    requested = years if years is not None else get_yearly_review_available_years().years
    prepared = _prepare_artifacts(requested, context)
    tasks = []
    for year in dict.fromkeys(requested):
        status = _generation_coordinator.status_prepared(prepared[year])
        if status is not None:
            tasks.append(status)
    return YearlyReviewGenerationResponse(tasks=tasks)


def start_yearly_review_prewarm_thread() -> threading.Thread | None:
    """Start one deduplicated daemon rebuild for the latest default report."""
    global _prewarm_thread
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    with _prewarm_lock:
        if _prewarm_thread is not None and _prewarm_thread.is_alive():
            return _prewarm_thread

        def run() -> None:
            try:
                year = prewarm_latest_yearly_review()
                if year is not None:
                    logger.info("Yearly Review persistent cache prewarmed for %d", year)
            except Exception:
                logger.exception("Yearly Review persistent cache prewarm failed")

        _prewarm_thread = threading.Thread(
            target=run,
            name="yearly-review-persistent-prewarm",
            daemon=True,
        )
        _prewarm_thread.start()
        return _prewarm_thread


def get_yearly_review(
    year: int,
    context: YearlyReviewFilterContext,
) -> YearlyReviewResponse:
    return YearlyReviewResponse.model_validate(_artifact(year, context)["report"])


def get_cached_yearly_review_artifact(
    year: int,
    context: YearlyReviewFilterContext,
) -> dict[str, Any] | None:
    """Return an exact persistent hit without queueing or building a report.

    Lightweight consumers such as the home page must never turn a preview read
    into a 10+ second annual-report generation.  This helper deliberately
    bypasses both the generation coordinator and the in-process builder cache.
    """
    prepared = _prepare_artifact(year, context)
    try:
        if not has_persisted_artifact(prepared.cache_key):
            return None
        return load_persisted_artifact(prepared.cache_key)
    except Exception:
        logger.exception("Yearly Review cache-only preview read failed")
        return None


def get_cached_yearly_review(
    year: int,
    context: YearlyReviewFilterContext,
) -> YearlyReviewResponse | None:
    artifact = get_cached_yearly_review_artifact(year, context)
    if artifact is None:
        return None
    return YearlyReviewResponse.model_validate(artifact["report"])


def yearly_review_cache_state(context: YearlyReviewFilterContext) -> str:
    """Cheap exact-key readiness token for lightweight composite caches."""
    latest = get_yearly_review_available_years().latest_year
    if latest is None:
        return "unavailable"
    prepared = _prepare_artifact(latest, context)
    try:
        ready = has_persisted_artifact(prepared.cache_key)
    except Exception:
        ready = False
    return f"{latest}:{prepared.cache_key}:{int(ready)}"


def get_yearly_review_records(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage:
    artifact = _artifact(year, context)
    return _records_page_from_artifact(
        artifact,
        year=year,
        context=context,
        page=page,
        page_size=page_size,
    )


def get_cached_yearly_review_records(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage | None:
    artifact = get_cached_yearly_review_artifact(year, context)
    if artifact is None:
        return None
    return _records_page_from_artifact(
        artifact,
        year=year,
        context=context,
        page=page,
        page_size=page_size,
    )


def _records_page_from_artifact(
    artifact: dict[str, Any],
    *,
    year: int,
    context: YearlyReviewFilterContext,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage:
    catalog = list(artifact["record_catalog"])
    total = len(catalog)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    items = catalog[start : start + page_size] if start < total else []
    report = artifact["report"]
    return YearlyReviewRecordsPage(
        content_version=report.get("methodology", {}).get(
            "content_version", YEARLY_REVIEW_CONTENT_VERSION
        ),
        year=year,
        filter_fingerprint=context.filter_fingerprint,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        items=items,
        catalog_counts=report.get("records", {}).get("catalog_counts", {}),
    )


def get_yearly_review_available_years() -> YearlyReviewAvailableYearsResponse:
    conn = get_db(readonly=True)
    try:
        rows = conn.execute(
            """SELECT DISTINCT ts_year FROM plays
               WHERE ts_year BETWEEN 2000 AND 2100
               ORDER BY ts_year"""
        ).fetchall()
    finally:
        conn.close()
    years = [int(row[0]) for row in rows]
    return YearlyReviewAvailableYearsResponse(
        years=years,
        latest_year=years[-1] if years else None,
    )


from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("yearly_review", "report_artifact", _build_cached_artifact)
