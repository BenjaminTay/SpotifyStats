"""Collection growth and exact archive facts for the music archive journey."""

from __future__ import annotations

import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.domains.account_archive.overview import (
    _database_path,
    _pct,
    load_saved_track_rows,
)
from backend.models.account_archive import ArchiveFilterContext

ARCHIVE_JOURNEY_CACHE_TTL_SECONDS = 300


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def _growth_points(rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict], int]:
    timezone = ZoneInfo("Asia/Shanghai")
    annual_counts: Counter[int] = Counter()
    quarterly_counts: Counter[tuple[int, int]] = Counter()
    invalid_dates = 0
    for row in rows:
        value = row.get("added_date")
        parsed = _parse_timestamp(value)
        if parsed is None:
            if value:
                invalid_dates += 1
            continue
        local = parsed.astimezone(timezone)
        quarter = (local.month - 1) // 3 + 1
        annual_counts[local.year] += 1
        quarterly_counts[(local.year, quarter)] += 1

    annual: list[dict] = []
    cumulative = 0
    if annual_counts:
        for year in range(min(annual_counts), max(annual_counts) + 1):
            count = annual_counts[year]
            cumulative += count
            annual.append(
                {
                    "period": str(year),
                    "year": year,
                    "quarter": None,
                    "saved_tracks": count,
                    "cumulative_saved_tracks": cumulative,
                }
            )

    quarterly: list[dict] = []
    cumulative = 0
    if quarterly_counts:
        start_year, start_quarter = min(quarterly_counts)
        end_year, end_quarter = max(quarterly_counts)
        year, quarter = start_year, start_quarter
        while (year, quarter) <= (end_year, end_quarter):
            count = quarterly_counts[(year, quarter)]
            cumulative += count
            quarterly.append(
                {
                    "period": f"{year}-Q{quarter}",
                    "year": year,
                    "quarter": quarter,
                    "saved_tracks": count,
                    "cumulative_saved_tracks": cumulative,
                }
            )
            quarter += 1
            if quarter == 5:
                year += 1
                quarter = 1
    return annual, quarterly, invalid_dates


def _release_years(rows: list[dict[str, Any]]) -> list[int]:
    years: list[int] = []
    for row in rows:
        release_date = str(row.get("release_date") or "")
        if len(release_date) < 4 or not release_date[:4].isdigit():
            continue
        year = int(release_date[:4])
        if 1900 <= year <= 2100:
            years.append(year)
    return years


def _collection_milestones(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dated = sorted(
        (row for row in rows if _parse_timestamp(row.get("added_date")) is not None),
        key=lambda row: (
            _parse_timestamp(row.get("added_date")),
            str(row.get("track_uri") or ""),
        ),
    )
    targets: list[int] = []
    target = 100
    while target <= len(dated) and len(targets) < 8:
        targets.append(target)
        target *= 2

    milestones: list[dict[str, Any]] = []
    for ordinal in targets:
        row = dated[ordinal - 1]
        local_album_id = row.get("local_album_id")
        local_track_id = row.get("local_l1_id")
        cover_url = None
        if local_album_id is not None and (row.get("image_path") or row.get("image_url")):
            cover_url = f"/covers/albums/{int(local_album_id)}.jpg"
        milestones.append(
            {
                "ordinal": ordinal,
                "track_name": row.get("track_name") or "",
                "artist_name": row.get("artist_name") or "",
                "album_name": row.get("album_name"),
                "added_date": row.get("added_date"),
                "cover_url": cover_url,
                "deep_link": (
                    f"/music/tracks/{int(local_track_id)}" if local_track_id is not None else None
                ),
            }
        )
    return milestones


def build_collection_journey(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    rows = load_saved_track_rows(conn)
    annual, quarterly, invalid_dates = _growth_points(rows)
    dated = sum(1 for row in rows if _parse_timestamp(row.get("added_date")) is not None)
    known_duration_rows = [row for row in rows if int(row.get("duration_ms") or 0) > 0]
    release_years = _release_years(rows)
    if not rows:
        status = "unavailable"
    elif dated == len(rows) and len(known_duration_rows) == len(rows):
        status = "available"
    else:
        status = "partial"

    return {
        "schema_version": "account_archive_journey_v2",
        "content_version": "account_archive_journey_v2_0",
        "data_revision": context.source_revision,
        "status": status,
        "filter_context": context.model_dump(mode="json"),
        "coverage": {
            "saved_tracks": len(rows),
            "saved_tracks_with_date": dated,
            "invalid_added_dates": invalid_dates,
            "saved_tracks_with_known_duration": len(known_duration_rows),
            "duration_coverage_pct": _pct(len(known_duration_rows), len(rows)),
        },
        "duration": {
            "known_duration_ms": sum(int(row["duration_ms"]) for row in known_duration_rows),
            "release_year_start": min(release_years) if release_years else None,
            "release_year_end": max(release_years) if release_years else None,
        },
        "annual_growth": annual,
        "quarterly_growth": quarterly,
        "milestones": _collection_milestones(rows),
    }


@ttl_cached(ARCHIVE_JOURNEY_CACHE_TTL_SECONDS, namespace="account_archive")
def _get_collection_journey_cached(
    db_path: str, context_json: str, cache_key: str
) -> dict[str, Any]:
    del cache_key
    context = ArchiveFilterContext.model_validate_json(context_json)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        return build_collection_journey(conn, context)
    finally:
        conn.close()


register_ttl("account_archive", "collection_journey", _get_collection_journey_cached)


def get_collection_journey(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    db_path = _database_path(conn)
    cache_key = f"journey:{context.filter_fingerprint}"
    if db_path and os.path.exists(db_path):
        return _get_collection_journey_cached(db_path, context.model_dump_json(), cache_key)
    return build_collection_journey(conn, context)
