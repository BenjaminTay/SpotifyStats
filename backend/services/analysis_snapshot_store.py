"""Bounded, atomic JSON result publications; reads never create a database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from pathlib import Path

from backend.core import config
from backend.core.access_surface import public_readonly_db_guard_active

MAX_BYTES = 32 * 1024 * 1024
MAX_KEYS = 16


def path() -> Path:
    return Path(
        config.SPOTIFY_STATS_ANALYSIS_CACHE_PATH
        or Path(__file__).resolve().parents[2] / "data/analysis_cache.db"
    )


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def decode(row) -> dict:
    size = row["raw_bytes"]
    if not 0 <= size <= MAX_BYTES:
        raise ValueError("Invalid analysis snapshot size")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(row["payload"], MAX_BYTES + 1)
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("Invalid analysis snapshot compression")
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Analysis snapshot checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Analysis snapshot must be an object")
    return value


def read(family: str, key: str, revision: str, version: str):
    if not path().is_file():
        return None
    conn = sqlite3.connect(f"{path().resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT * FROM analysis_snapshots
            WHERE family=? AND request_key=? AND builder_version=?
            ORDER BY (source_revision=?) DESC, publication_id DESC""",
            (family, key, version, revision),
        ).fetchall()
        for row in rows:
            try:
                return decode(row), dict(row)
            except (ValueError, zlib.error):
                continue  # A corrupt publication cannot hide a valid compatible LKG.
        return None
    finally:
        conn.close()


def publish(family: str, key: str, revision: str, version: str, payload: dict):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot publish analysis snapshots")
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    encoded = {
        "payload": zlib.compress(raw),
        "raw_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    decode(encoded)
    path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path(), timeout=30)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS analysis_snapshots (
            publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            family TEXT NOT NULL, request_key TEXT NOT NULL,
            source_revision TEXT NOT NULL, builder_version TEXT NOT NULL,
            payload BLOB NOT NULL, raw_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(family, request_key, source_revision, builder_version))""")
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO analysis_snapshots
                (family,request_key,source_revision,builder_version,payload,raw_bytes,sha256)
                VALUES(?,?,?,?,?,?,?)""",
                (
                    family,
                    key,
                    revision,
                    version,
                    encoded["payload"],
                    encoded["raw_bytes"],
                    encoded["sha256"],
                ),
            )
            conn.execute(
                """DELETE FROM analysis_snapshots WHERE family=? AND request_key=?
                AND publication_id NOT IN (SELECT publication_id FROM analysis_snapshots
                WHERE family=? AND request_key=? ORDER BY publication_id DESC LIMIT 2)""",
                (family, key, family, key),
            )
            conn.execute(
                """DELETE FROM analysis_snapshots WHERE request_key NOT IN
                (SELECT request_key FROM analysis_snapshots GROUP BY request_key
                ORDER BY MAX(publication_id) DESC LIMIT ?)""",
                (MAX_KEYS,),
            )
    finally:
        conn.close()
