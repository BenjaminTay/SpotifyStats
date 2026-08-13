"""Revision helpers for account archive source data and cache invalidation."""

from __future__ import annotations

import sqlite3
from typing import Literal

ArchiveRevisionKind = Literal["account_import", "collection_date"]


def ensure_archive_state(conn: sqlite3.Connection) -> None:
    """Create the small revision table for legacy/test databases."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_archive_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            account_import_revision INTEGER NOT NULL DEFAULT 0,
            collection_date_revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO account_archive_state(
            state_id, account_import_revision, collection_date_revision
        ) VALUES (1, 0, 0);
        """
    )


def get_archive_revisions(conn: sqlite3.Connection) -> dict[str, int]:
    """Return stable revision counters, defaulting to zero on legacy schemas."""
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_archive_state'"
    ).fetchone()
    if not table_exists:
        return {"account_import": 0, "collection_date": 0}
    row = conn.execute(
        "SELECT account_import_revision, collection_date_revision "
        "FROM account_archive_state WHERE state_id = 1"
    ).fetchone()
    if row is None:
        return {"account_import": 0, "collection_date": 0}
    return {"account_import": int(row[0] or 0), "collection_date": int(row[1] or 0)}


def bump_archive_revision(conn: sqlite3.Connection, kind: ArchiveRevisionKind) -> None:
    """Increment one archive input revision inside the caller's transaction."""
    ensure_archive_state(conn)
    column = {
        "account_import": "account_import_revision",
        "collection_date": "collection_date_revision",
    }[kind]
    conn.execute(
        f"UPDATE account_archive_state SET {column} = {column} + 1, "
        "updated_at = datetime('now') WHERE state_id = 1"
    )
