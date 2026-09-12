"""Durable, exact-key cache for deterministic Billboard responses.

The in-process LRU caches remain useful while a worker is warm, but they are
not a storage boundary: a restart or an eviction turns a normal GET into a
full DataFrame build.  This module stores the JSON response in a small SQLite
sidecar and keeps the previous ready row as a last-known-good response while a
new dependency revision is rebuilt in the background.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import zlib
from pathlib import Path
from typing import Any, Callable

from backend.core.access_surface import public_readonly_db_guard_active
from backend.core.config import SPOTIFY_STATS_BILLBOARD_CACHE_PATH
from backend.core.db import enforce_sqlite_foreign_keys

logger = logging.getLogger(__name__)

CACHE_FORMAT_VERSION = 1
BILLBOARD_CACHE_BUILDER_VERSION = "billboard_persistent_snapshot_v1"
MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_ENTRIES = 256

BILLBOARD_CACHE_PATH = SPOTIFY_STATS_BILLBOARD_CACHE_PATH or str(
    Path(__file__).resolve().parents[3] / "data" / "billboard_cache.db"
)

_build_locks_guard = threading.Lock()
_build_locks: dict[str, threading.RLock] = {}


def _connect(cache_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(cache_path or BILLBOARD_CACHE_PATH)
    if public_readonly_db_guard_active():
        if not path.is_file():
            raise FileNotFoundError(path)
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=30,
            check_same_thread=False,
        )
        enforce_sqlite_foreign_keys(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return conn

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    enforce_sqlite_foreign_keys(conn)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS billboard_snapshots (
            cache_key TEXT PRIMARY KEY,
            request_key TEXT NOT NULL,
            family TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            builder_version TEXT NOT NULL,
            payload BLOB NOT NULL,
            uncompressed_bytes INTEGER NOT NULL,
            payload_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_billboard_snapshots_request
            ON billboard_snapshots(request_key, builder_version, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_billboard_snapshots_updated
            ON billboard_snapshots(updated_at DESC);
        """
    )
    conn.commit()
    return conn


def _encode_payload(payload: dict[str, Any]) -> tuple[bytes, int, str]:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    if len(raw) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("billboard persistent snapshot exceeds size limit")
    return zlib.compress(raw, level=6), len(raw), hashlib.sha256(raw).hexdigest()


def _decode_payload(row: sqlite3.Row) -> dict[str, Any]:
    expected_bytes = int(row["uncompressed_bytes"])
    if expected_bytes < 0 or expected_bytes > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("invalid Billboard snapshot size")
    compressed = bytes(row["payload"])
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(compressed, MAX_UNCOMPRESSED_BYTES + 1)
    if decompressor.unconsumed_tail:
        raise ValueError("Billboard snapshot exceeds decompression limit")
    raw += decompressor.flush()
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("Billboard snapshot has incomplete compressed data")
    if len(raw) != expected_bytes:
        raise ValueError("Billboard snapshot size mismatch")
    if hashlib.sha256(raw).hexdigest() != str(row["payload_sha256"]):
        raise ValueError("Billboard snapshot checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Billboard snapshot must be an object")
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _dependency_state(family: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build a stable source revision without using SQLite file timestamps."""
    from datetime import datetime, timezone

    from backend.core import db as db_module
    from backend.domains.billboard.chart_load_rank import billboard_revision_state
    from backend.domains.billboard.year_end import YEAR_END_SEMANTICS_VERSION
    from backend.services.yearly_review_service import database_revision

    state: dict[str, Any] = {
        "database_path": str(Path(db_module.DB_PATH).resolve()),
        "database_revision": database_revision(),
        "billboard_revision_state": list(billboard_revision_state()),
        "aggregation_builder_version": getattr(
            db_module,
            "_BILLBOARD_AGGREGATION_BUILDER_VERSION",
            "unknown",
        ),
        "year_end_semantics_version": YEAR_END_SEMANTICS_VERSION,
    }

    # A week crossing from open to complete is a time-based publication event,
    # even when no new import has happened. Historical annual rows do not need
    # to be invalidated by that clock boundary.
    selected_year = params.get("year")
    include_open_boundary = family != "year_end" or selected_year is None
    if family == "year_end" and selected_year is not None:
        include_open_boundary = int(selected_year) == datetime.now(timezone.utc).year
    if include_open_boundary:
        from backend.domains.billboard.week_coverage import current_open_billboard_week

        state["open_billboard_week"] = current_open_billboard_week(
            week_start_dow=int(params.get("bb_week_start_dow", 4)),
            week_start_hour=int(params.get("bb_week_start_hour", 0)),
        ).isoformat()
    return state


def build_cache_context(family: str, params: dict[str, Any]) -> dict[str, str]:
    """Return exact and request-only keys for one normalized response shape."""
    from backend.core import db as db_module

    request_payload = {
        "family": family,
        "builder_version": BILLBOARD_CACHE_BUILDER_VERSION,
        "database_path": str(Path(db_module.DB_PATH).resolve()),
        "params": params,
    }
    request_key = _digest(request_payload)
    dependencies = _dependency_state(family, params)
    source_revision = _digest(dependencies)
    return {
        "cache_key": _digest(
            {
                "request_key": request_key,
                "source_revision": source_revision,
                "builder_version": BILLBOARD_CACHE_BUILDER_VERSION,
            }
        ),
        "request_key": request_key,
        "family": family,
        "source_revision": source_revision,
        "builder_version": BILLBOARD_CACHE_BUILDER_VERSION,
    }


def _delete_row(conn: sqlite3.Connection, cache_key: str) -> None:
    if public_readonly_db_guard_active():
        return
    conn.execute("DELETE FROM billboard_snapshots WHERE cache_key=?", (cache_key,))
    conn.commit()


def load_persisted_snapshot(
    context: dict[str, str],
    *,
    allow_lkg: bool = True,
    cache_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Read an exact snapshot, then optionally the newest same-request LKG."""
    try:
        conn = _connect(cache_path)
    except (FileNotFoundError, OSError, sqlite3.Error):
        return None
    try:
        rows = [
            conn.execute(
                """SELECT cache_key, payload, uncompressed_bytes, payload_sha256
                   FROM billboard_snapshots
                   WHERE cache_key=? AND builder_version=?""",
                (context["cache_key"], context["builder_version"]),
            ).fetchone()
        ]
        if allow_lkg:
            rows.append(
                conn.execute(
                    """SELECT cache_key, payload, uncompressed_bytes, payload_sha256
                       FROM billboard_snapshots
                       WHERE request_key=? AND builder_version=?
                       ORDER BY updated_at DESC, rowid DESC LIMIT 1""",
                    (context["request_key"], context["builder_version"]),
                ).fetchone()
            )
        for row in rows:
            if row is None:
                continue
            try:
                return _decode_payload(row)
            except (ValueError, TypeError, json.JSONDecodeError, zlib.error):
                _delete_row(conn, str(row["cache_key"]))
        return None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def store_persisted_snapshot(
    context: dict[str, str],
    payload: dict[str, Any],
    *,
    cache_path: str | Path | None = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    """Atomically replace one snapshot and prune only the oldest rows."""
    if public_readonly_db_guard_active():
        return
    compressed, raw_bytes, checksum = _encode_payload(payload)
    conn = _connect(cache_path)
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO billboard_snapshots(
                       cache_key, request_key, family, source_revision,
                       builder_version, payload, uncompressed_bytes,
                       payload_sha256, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (
                    context["cache_key"],
                    context["request_key"],
                    context["family"],
                    context["source_revision"],
                    context["builder_version"],
                    compressed,
                    raw_bytes,
                    checksum,
                ),
            )
            if max_entries > 0:
                stale_rows = conn.execute(
                    """SELECT cache_key FROM billboard_snapshots
                       ORDER BY updated_at DESC, rowid DESC
                       LIMIT -1 OFFSET ?""",
                    (max_entries,),
                ).fetchall()
                conn.executemany(
                    "DELETE FROM billboard_snapshots WHERE cache_key=?",
                    [(str(row["cache_key"]),) for row in stale_rows],
                )
    finally:
        conn.close()


def clear_persisted_snapshots(cache_path: str | Path | None = None) -> None:
    """Delete sidecar rows for isolated tests and explicit local maintenance."""
    if public_readonly_db_guard_active():
        return
    conn = _connect(cache_path)
    try:
        conn.execute("DELETE FROM billboard_snapshots")
        conn.commit()
    finally:
        conn.close()


def _lock_for(cache_key: str) -> threading.RLock:
    with _build_locks_guard:
        return _build_locks.setdefault(cache_key, threading.RLock())


def get_or_build_billboard_snapshot(
    family: str,
    params: dict[str, Any],
    builder: Callable[[], dict[str, Any]],
    *,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    """Serve exact/LKG first, or serialize one cold build for an exact key."""
    try:
        context = build_cache_context(family, params)
    except Exception:
        logger.exception("Billboard persistent cache key construction failed")
        return builder()

    if not force_rebuild:
        cached = load_persisted_snapshot(context, allow_lkg=True)
        if cached is not None:
            return cached

    with _lock_for(context["cache_key"]):
        cached = load_persisted_snapshot(context, allow_lkg=not force_rebuild)
        if cached is not None:
            return cached
        result = builder()
        try:
            store_persisted_snapshot(context, result)
        except Exception:
            logger.exception("Billboard persistent cache write failed: family=%s", family)
        return result
