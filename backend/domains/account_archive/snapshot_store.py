"""Compressed Archive family results with atomic active/previous publication."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from pathlib import Path

from backend.core import config, db
from backend.core.access_surface import public_readonly_db_guard_active
from backend.services.analysis_snapshot_store import decode

MAX_DISK_BYTES = 30 * 1024 * 1024


def path():
    return Path(
        config.SPOTIFY_STATS_ARCHIVE_CACHE_PATH
        or Path(db.DB_PATH).with_name("account_archive_cache.db")
    )


def connect(*, write=False):
    target = path()
    if write:
        if public_readonly_db_guard_active():
            raise PermissionError("Public requests cannot write Archive snapshots")
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target, timeout=30)
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS publications (
          generation INTEGER PRIMARY KEY, family TEXT NOT NULL, request_key TEXT NOT NULL,
          revision TEXT NOT NULL, payload BLOB NOT NULL, raw_bytes INTEGER NOT NULL,
          sha256 TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(family,request_key,revision));
        CREATE TABLE IF NOT EXISTS active (
          family TEXT NOT NULL, request_key TEXT NOT NULL, generation INTEGER,
          previous INTEGER, failed_revision TEXT, PRIMARY KEY(family,request_key));
        """)
    else:
        if not target.is_file():
            return None
        conn = sqlite3.connect(f"{target.resolve().as_uri()}?mode=ro", uri=True, timeout=1)
        conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def read(family, key):
    conn = connect()
    if conn is None:
        return None
    try:
        conn.execute("BEGIN")
        active = conn.execute(
            "SELECT * FROM active WHERE family=? AND request_key=?", (family, key)
        ).fetchone()
        if active is None:
            return None
        for generation in (active["generation"], active["previous"]):
            row = conn.execute(
                "SELECT * FROM publications WHERE generation=?", (generation,)
            ).fetchone()
            if row is not None:
                try:
                    return decode(row), {
                        **dict(row),
                        "failed_revision": active["failed_revision"],
                        "fallback": generation != active["generation"],
                    }
                except (ValueError, zlib.error):
                    continue
        return None
    finally:
        conn.close()


def publish(results, fence):
    prepared = []
    for family, key, revision, payload in results:
        raw = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode()
        encoded = {
            "payload": zlib.compress(raw),
            "raw_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        decode(encoded)
        prepared.append((family, key, revision, encoded))
    conn = connect(write=True)
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            for family, key, revision, encoded in prepared:
                old = conn.execute(
                    "SELECT generation FROM active WHERE family=? AND request_key=?", (family, key)
                ).fetchone()
                existing = conn.execute(
                    "SELECT generation FROM publications WHERE family=? AND request_key=? AND revision=?",
                    (family, key, revision),
                ).fetchone()
                if existing:
                    generation = existing[0]
                    conn.execute(
                        "UPDATE publications SET payload=?,raw_bytes=?,sha256=? WHERE generation=?",
                        (encoded["payload"], encoded["raw_bytes"], encoded["sha256"], generation),
                    )
                else:
                    generation = conn.execute(
                        "INSERT INTO publications(family,request_key,revision,payload,raw_bytes,sha256) VALUES(?,?,?,?,?,?)",
                        (
                            family,
                            key,
                            revision,
                            encoded["payload"],
                            encoded["raw_bytes"],
                            encoded["sha256"],
                        ),
                    ).lastrowid
                if not old or old[0] != generation:
                    conn.execute(
                        "INSERT OR REPLACE INTO active VALUES(?,?,?,?,NULL)",
                        (family, key, generation, old[0] if old else None),
                    )
                else:
                    conn.execute(
                        "UPDATE active SET failed_revision=NULL WHERE family=? AND request_key=?",
                        (family, key),
                    )
            conn.execute(
                "DELETE FROM publications WHERE generation NOT IN (SELECT generation FROM active WHERE generation IS NOT NULL UNION SELECT previous FROM active WHERE previous IS NOT NULL)"
            )
            if (
                conn.execute("PRAGMA page_count").fetchone()[0]
                * conn.execute("PRAGMA page_size").fetchone()[0]
                > MAX_DISK_BYTES
            ):
                raise ValueError("Archive active/previous storage exceeds 30 MiB")
            fence()
    finally:
        conn.close()


def mark_failed(targets):
    conn = connect(write=True)
    try:
        with conn:
            for family, key, revision in targets:
                conn.execute(
                    "INSERT INTO active(family,request_key,failed_revision) VALUES(?,?,?) ON CONFLICT(family,request_key) DO UPDATE SET failed_revision=excluded.failed_revision",
                    (family, key, revision),
                )
    finally:
        conn.close()


def failed_revision(family, key):
    conn = connect()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT failed_revision FROM active WHERE family=? AND request_key=?", (family, key)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()
