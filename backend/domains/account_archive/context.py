"""Unified statistical context and cache fingerprint for music archive metrics."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository
from backend.models.account_archive import ArchiveFilterContext

ACCOUNT_ARCHIVE_FILTER_VERSION = "account_archive_filter_v3"
ACCOUNT_ARCHIVE_TIMEZONE = "Asia/Shanghai"


def _value(source: Mapping[str, Any] | object, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _track_group_revision(conn: sqlite3.Connection) -> str:
    from backend.domains.account_archive.snapshot_revision import GROUPS, revision_or_legacy

    return revision_or_legacy(conn, GROUPS)


def _play_bounds(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    if not _table_exists(conn, "plays"):
        return None, None
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM plays WHERE ts IS NOT NULL AND TRIM(ts) != ''"
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def _local_date(iso_timestamp: str | None) -> str | None:
    if not iso_timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(ZoneInfo(ACCOUNT_ARCHIVE_TIMEZONE)).date().isoformat()


def _fingerprint(values: Mapping[str, Any]) -> str:
    payload = {"fingerprint_version": ACCOUNT_ARCHIVE_FILTER_VERSION, **values}
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def resolve_archive_filters(conn: sqlite3.Connection, filters) -> dict[str, Any]:
    settings = SettingsRepository(conn).load_all()
    min_ms = _value(filters, "min_ms")
    merge_enabled = _value(filters, "merge_enabled")
    max_merge_gap_minutes = _value(filters, "max_merge_gap_minutes")
    values: dict[str, Any] = {
        "min_ms": int(settings.get("min_ms", SETTINGS_DEFAULTS["min_ms"]))
        if min_ms is None
        else int(min_ms),
        "music_only": True,
        "merge_enabled": bool(settings.get("merge_enabled", True))
        if merge_enabled is None
        else bool(merge_enabled),
        "dynamic_threshold": bool(_value(filters, "dynamic_threshold", True)),
        "max_merge_gap_minutes": int(
            settings.get("max_merge_gap_minutes", SETTINGS_DEFAULTS["max_merge_gap_minutes"])
        )
        if max_merge_gap_minutes is None
        else int(max_merge_gap_minutes),
        "merge_level": int(_value(filters, "merge_level", 2)),
        "timezone": ACCOUNT_ARCHIVE_TIMEZONE,
    }
    return values


def build_archive_filter_context(
    conn: sqlite3.Connection, filters: Mapping[str, Any] | object, *, family: str | None = None
) -> ArchiveFilterContext:
    """Build-time context; public snapshot reads only resolve filter values."""
    from backend.domains.account_archive.snapshot_revision import (
        FAMILIES,
        family_revision,
        revision_or_legacy,
    )

    values = resolve_archive_filters(conn, filters)
    fingerprint = _fingerprint(values)
    first_play_at, latest_play_at = _play_bounds(conn)
    values.update(
        {
            "first_play_at": first_play_at,
            "latest_play_at": latest_play_at,
            "latest_play_date": _local_date(latest_play_at),
            "source_revision": revision_or_legacy(conn, FAMILIES["cohorts"])
            if family is None
            else family_revision(conn, family),
            "track_group_revision": _track_group_revision(conn)
            if family in (None, "cohorts", "returns", "discovery")
            else "not_used",
        }
    )
    values["filter_fingerprint"] = fingerprint
    return ArchiveFilterContext(**values)
