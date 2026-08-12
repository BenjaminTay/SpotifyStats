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

from backend.core.cache import singleflight
from backend.core.db import DB_PATH, get_db
from backend.domains.billboard.year_end import YEAR_END_SEMANTICS_VERSION
from backend.domains.metadata.artist_languages import artist_language_fact_revision
from backend.domains.settings.repository import SettingsRepository
from backend.domains.yearly_review.artifact_cache import (
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
from backend.models.yearly_review import (
    YearlyReviewAvailableYearsResponse,
    YearlyReviewFilterContext,
    YearlyReviewRecordsPage,
    YearlyReviewResponse,
)

YEARLY_REVIEW_SCHEMA_VERSION = "yearly_review_v2"
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
    """Fingerprint SQLite main/WAL file state so imports cannot reuse old reports."""
    parts: list[str] = []
    for path in (DB_PATH, f"{DB_PATH}-wal"):
        try:
            stat = os.stat(path)
            parts.append(f"{os.path.basename(path)}:{stat.st_size}:{stat.st_mtime_ns}")
        except FileNotFoundError:
            parts.append(f"{os.path.basename(path)}:missing")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


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


@singleflight
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


def _artifact(year: int, context: YearlyReviewFilterContext) -> dict[str, Any]:
    db_revision = database_revision()
    key = build_yearly_review_cache_key(
        year,
        context,
        language_revision=_language_revision(),
        db_revision=db_revision,
    )
    return _build_cached_artifact(year, context.model_dump_json(), key, db_revision)


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


def get_yearly_review_records(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage:
    artifact = _artifact(year, context)
    catalog = list(artifact["record_catalog"])
    total = len(catalog)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    items = catalog[start : start + page_size] if start < total else []
    report = artifact["report"]
    return YearlyReviewRecordsPage(
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
