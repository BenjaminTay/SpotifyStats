"""Cached service facade for the deterministic Yearly Review V2."""

from __future__ import annotations

import hashlib
import json
import math
import os
from functools import lru_cache
from typing import Any

from backend.core.cache import singleflight
from backend.core.db import DB_PATH, get_db
from backend.domains.billboard.year_end import YEAR_END_SEMANTICS_VERSION
from backend.domains.metadata.artist_languages import artist_language_fact_revision
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
) -> dict[str, Any]:
    _ = cache_key
    context = YearlyReviewFilterContext.model_validate_json(context_json)
    conn = get_db(readonly=True)
    try:
        artifact = build_yearly_review_artifact(conn, year, context)
        return {
            "report": artifact.report.model_dump(mode="json"),
            "record_catalog": artifact.record_catalog,
        }
    finally:
        conn.close()


def _artifact(year: int, context: YearlyReviewFilterContext) -> dict[str, Any]:
    key = build_yearly_review_cache_key(
        year,
        context,
        language_revision=_language_revision(),
        db_revision=database_revision(),
    )
    return _build_cached_artifact(year, context.model_dump_json(), key)


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
