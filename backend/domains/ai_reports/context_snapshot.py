"""Persistent exact-key snapshots for yearly-report Agent context.

The cache shares the Yearly Review sidecar database, but owns an independent
table.  Snapshot keys are constructed by the caller so this module remains a
small persistence boundary rather than duplicating revision semantics.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import zlib
from pathlib import Path
from typing import Any

from backend.core.access_surface import public_readonly_db_guard_active
from backend.core.db import enforce_sqlite_foreign_keys
from backend.domains.yearly_review.artifact_cache import YEARLY_REVIEW_CACHE_PATH

CONTEXT_SNAPSHOT_FORMAT_VERSION = 1
DEFAULT_MAX_ENTRIES = 32
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_READY_STATUS = "ready"
_BUILDING_STATUS = "building"


def _connect(cache_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    path = Path(cache_path or YEARLY_REVIEW_CACHE_PATH)
    if public_readonly_db_guard_active():
        if not path.is_file():
            raise FileNotFoundError(path)
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
        enforce_sqlite_foreign_keys(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        return conn

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    enforce_sqlite_foreign_keys(conn)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS yearly_agent_context_snapshots (
               cache_key TEXT PRIMARY KEY,
               report_year INTEGER NOT NULL,
               filter_fingerprint TEXT NOT NULL,
               source_db_revision TEXT NOT NULL,
               builder_version TEXT NOT NULL,
               cache_format_version INTEGER NOT NULL,
               payload BLOB NOT NULL,
               payload_checksum TEXT NOT NULL,
               uncompressed_bytes INTEGER NOT NULL,
               status TEXT NOT NULL CHECK(status IN ('building', 'ready')),
               build_elapsed_ms INTEGER NOT NULL,
               created_at TEXT NOT NULL DEFAULT (datetime('now')),
               updated_at TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_yearly_agent_context_updated
           ON yearly_agent_context_snapshots(status, updated_at DESC)"""
    )
    conn.commit()
    return conn


def _encode_snapshot(snapshot: dict[str, Any]) -> tuple[bytes, str, int]:
    if not isinstance(snapshot, dict):
        raise TypeError("yearly Agent context snapshot must be an object")
    raw = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode()
    if len(raw) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("yearly Agent context snapshot exceeds persistent-cache size limit")
    return zlib.compress(raw, level=6), hashlib.sha256(raw).hexdigest(), len(raw)


def _decode_snapshot(payload: bytes, expected_checksum: str, expected_bytes: int) -> dict[str, Any]:
    if expected_bytes < 0 or expected_bytes > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("invalid yearly Agent context snapshot size")
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(payload, MAX_UNCOMPRESSED_BYTES + 1)
    if decompressor.unconsumed_tail:
        raise ValueError("yearly Agent context snapshot exceeds decompression limit")
    raw += decompressor.flush()
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("yearly Agent context snapshot has invalid compressed data")
    if len(raw) > MAX_UNCOMPRESSED_BYTES or len(raw) != expected_bytes:
        raise ValueError("yearly Agent context snapshot size mismatch")
    if not expected_checksum or not hmac.compare_digest(
        hashlib.sha256(raw).hexdigest(), expected_checksum
    ):
        raise ValueError("yearly Agent context snapshot checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("yearly Agent context snapshot must be an object")
    return value


def load_context_snapshot(
    cache_key: str,
    *,
    cache_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    """Return an exact ready snapshot, rejecting and deleting corrupt rows."""
    try:
        conn = _connect(cache_path)
    except (FileNotFoundError, sqlite3.Error):
        return None
    try:
        try:
            row = conn.execute(
                """SELECT payload, payload_checksum, uncompressed_bytes,
                          cache_format_version
                   FROM yearly_agent_context_snapshots
                   WHERE cache_key=? AND status=?""",
                (cache_key, _READY_STATUS),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None or int(row["cache_format_version"]) != CONTEXT_SNAPSHOT_FORMAT_VERSION:
            return None
        try:
            return _decode_snapshot(
                bytes(row["payload"]),
                str(row["payload_checksum"]),
                int(row["uncompressed_bytes"]),
            )
        except (ValueError, TypeError, json.JSONDecodeError, zlib.error):
            if not public_readonly_db_guard_active():
                conn.execute(
                    "DELETE FROM yearly_agent_context_snapshots WHERE cache_key=?",
                    (cache_key,),
                )
                conn.commit()
            return None
    finally:
        conn.close()


def has_context_snapshot(
    cache_key: str,
    *,
    cache_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Check for an exact ready snapshot without inflating its payload."""
    try:
        conn = _connect(cache_path)
    except (FileNotFoundError, sqlite3.Error):
        return False
    try:
        try:
            row = conn.execute(
                """SELECT 1 FROM yearly_agent_context_snapshots
                   WHERE cache_key=? AND status=? AND cache_format_version=?""",
                (cache_key, _READY_STATUS, CONTEXT_SNAPSHOT_FORMAT_VERSION),
            ).fetchone()
        except sqlite3.Error:
            return False
        return row is not None
    finally:
        conn.close()


def delete_context_snapshot(
    cache_key: str,
    *,
    cache_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Delete one snapshot; public read-only surfaces are always a safe no-op."""
    if public_readonly_db_guard_active():
        return False
    try:
        conn = _connect(cache_path)
    except sqlite3.Error:
        return False
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM yearly_agent_context_snapshots WHERE cache_key=?",
                (cache_key,),
            )
        return cursor.rowcount > 0
    finally:
        conn.close()


def _prune_with_connection(conn: sqlite3.Connection, max_entries: int) -> int:
    if max_entries <= 0:
        return 0
    stale_rows = conn.execute(
        """SELECT cache_key FROM yearly_agent_context_snapshots
           WHERE status=?
           ORDER BY updated_at DESC, rowid DESC
           LIMIT -1 OFFSET ?""",
        (_READY_STATUS, max_entries),
    ).fetchall()
    conn.executemany(
        "DELETE FROM yearly_agent_context_snapshots WHERE cache_key=?",
        [(str(row["cache_key"]),) for row in stale_rows],
    )
    return len(stale_rows)


def prune_context_snapshots(
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    cache_path: str | os.PathLike[str] | None = None,
) -> int:
    """Prune oldest ready snapshots while preserving public read-only safety."""
    if public_readonly_db_guard_active():
        return 0
    try:
        conn = _connect(cache_path)
    except sqlite3.Error:
        return 0
    try:
        with conn:
            return _prune_with_connection(conn, max_entries)
    finally:
        conn.close()


def store_context_snapshot(
    cache_key: str,
    snapshot: dict[str, Any],
    *,
    year: int,
    filter_fingerprint: str,
    source_db_revision: str,
    builder_version: str,
    build_elapsed_ms: int,
    cache_path: str | os.PathLike[str] | None = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    """Atomically publish a complete ready snapshot and prune older entries.

    ``building`` and ``ready`` are written in one transaction. Concurrent
    readers therefore continue to see the previous ready row until the new
    payload and metadata are fully committed.
    """
    if public_readonly_db_guard_active():
        raise PermissionError("public read-only surface cannot store Agent context snapshots")
    if not cache_key:
        raise ValueError("yearly Agent context snapshot cache key is required")
    payload, checksum, raw_bytes = _encode_snapshot(snapshot)
    # Verify the encoded value before opening the publication transaction.
    _decode_snapshot(payload, checksum, raw_bytes)

    conn = _connect(cache_path)
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO yearly_agent_context_snapshots(
                       cache_key, report_year, filter_fingerprint, source_db_revision,
                       builder_version, cache_format_version, payload, payload_checksum,
                       uncompressed_bytes, status, build_elapsed_ms, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (
                    cache_key,
                    int(year),
                    filter_fingerprint,
                    source_db_revision,
                    builder_version,
                    CONTEXT_SNAPSHOT_FORMAT_VERSION,
                    payload,
                    checksum,
                    raw_bytes,
                    _BUILDING_STATUS,
                    max(0, int(build_elapsed_ms)),
                ),
            )
            conn.execute(
                """UPDATE yearly_agent_context_snapshots
                   SET status=?, updated_at=datetime('now')
                   WHERE cache_key=?""",
                (_READY_STATUS, cache_key),
            )
            _prune_with_connection(conn, max_entries)
    finally:
        conn.close()
