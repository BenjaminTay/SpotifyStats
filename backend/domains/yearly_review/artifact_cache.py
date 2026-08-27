"""Persistent sidecar cache for deterministic Yearly Review V2 artifacts."""

from __future__ import annotations

import json
import os
import sqlite3
import zlib
from pathlib import Path
from typing import Any

from backend.core.access_surface import public_readonly_db_guard_active
from backend.core.db import DB_PATH, enforce_sqlite_foreign_keys

CACHE_FORMAT_VERSION = 1
DEFAULT_MAX_ENTRIES = 32
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
YEARLY_REVIEW_CACHE_PATH = os.environ.get(
    "SPOTIFY_STATS_YEARLY_CACHE_PATH",
    str(Path(DB_PATH).with_name("yearly_review_cache.db")),
)


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
        """CREATE TABLE IF NOT EXISTS yearly_review_artifacts (
               cache_key TEXT PRIMARY KEY,
               report_year INTEGER NOT NULL,
               filter_fingerprint TEXT NOT NULL,
               source_db_revision TEXT NOT NULL,
               cache_format_version INTEGER NOT NULL,
               payload BLOB NOT NULL,
               uncompressed_bytes INTEGER NOT NULL,
               created_at TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_yearly_artifacts_created
           ON yearly_review_artifacts(created_at DESC)"""
    )
    conn.commit()
    return conn


def _encode_artifact(artifact: dict[str, Any]) -> tuple[bytes, int]:
    raw = json.dumps(
        artifact,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode()
    if len(raw) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("yearly review artifact exceeds persistent-cache size limit")
    return zlib.compress(raw, level=6), len(raw)


def _decode_artifact(payload: bytes, expected_bytes: int) -> dict[str, Any]:
    if expected_bytes < 0 or expected_bytes > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("invalid yearly review artifact size")
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(payload, MAX_UNCOMPRESSED_BYTES + 1)
    if decompressor.unconsumed_tail:
        raise ValueError("yearly review artifact exceeds decompression limit")
    raw += decompressor.flush()
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("yearly review artifact has trailing or incomplete compressed data")
    if len(raw) > MAX_UNCOMPRESSED_BYTES or len(raw) != expected_bytes:
        raise ValueError("yearly review artifact size mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("yearly review artifact must be an object")
    if not isinstance(value.get("report"), dict) or not isinstance(
        value.get("record_catalog"), list
    ):
        raise ValueError("yearly review artifact has an invalid shape")
    return value


def load_persisted_artifact(
    cache_key: str,
    *,
    cache_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    """Return an exact persistent-cache hit, deleting corrupt rows safely."""
    try:
        conn = _connect(cache_path)
    except (FileNotFoundError, sqlite3.Error):
        return None
    try:
        try:
            row = conn.execute(
                """SELECT payload, uncompressed_bytes, cache_format_version
                   FROM yearly_review_artifacts WHERE cache_key=?""",
                (cache_key,),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None or int(row["cache_format_version"]) != CACHE_FORMAT_VERSION:
            return None
        try:
            return _decode_artifact(bytes(row["payload"]), int(row["uncompressed_bytes"]))
        except (ValueError, TypeError, json.JSONDecodeError, zlib.error):
            if not public_readonly_db_guard_active():
                conn.execute("DELETE FROM yearly_review_artifacts WHERE cache_key=?", (cache_key,))
                conn.commit()
            return None
    finally:
        conn.close()


def has_persisted_artifact(
    cache_key: str,
    *,
    cache_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Check an exact persistent hit without inflating its payload."""
    try:
        conn = _connect(cache_path)
    except (FileNotFoundError, sqlite3.Error):
        return False
    try:
        try:
            row = conn.execute(
                """SELECT 1 FROM yearly_review_artifacts
                   WHERE cache_key=? AND cache_format_version=?""",
                (cache_key, CACHE_FORMAT_VERSION),
            ).fetchone()
        except sqlite3.Error:
            return False
        return row is not None
    finally:
        conn.close()


def store_persisted_artifact(
    cache_key: str,
    artifact: dict[str, Any],
    *,
    year: int,
    filter_fingerprint: str,
    source_db_revision: str,
    cache_path: str | os.PathLike[str] | None = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    """Atomically persist one artifact and prune the oldest exact-key entries."""
    payload, raw_bytes = _encode_artifact(artifact)
    conn = _connect(cache_path)
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO yearly_review_artifacts(
                       cache_key, report_year, filter_fingerprint, source_db_revision,
                       cache_format_version, payload, uncompressed_bytes, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    cache_key,
                    year,
                    filter_fingerprint,
                    source_db_revision,
                    CACHE_FORMAT_VERSION,
                    payload,
                    raw_bytes,
                ),
            )
            if max_entries > 0:
                stale_rows = conn.execute(
                    """SELECT cache_key FROM yearly_review_artifacts
                       ORDER BY created_at DESC, rowid DESC
                       LIMIT -1 OFFSET ?""",
                    (max_entries,),
                ).fetchall()
                conn.executemany(
                    "DELETE FROM yearly_review_artifacts WHERE cache_key=?",
                    [(str(row["cache_key"]),) for row in stale_rows],
                )
    finally:
        conn.close()
