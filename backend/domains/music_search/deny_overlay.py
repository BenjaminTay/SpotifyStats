"""Immediate search exclusions that remain effective across LKG generations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def deny_overlay_available(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_entity_deny_overlay'"""
        ).fetchone()
        is not None
    )


def deny_music_search_entities(
    conn: sqlite3.Connection,
    entity_keys: Iterable[str],
    *,
    reason: str,
    target_source_revision: str | None = None,
) -> None:
    """Write privacy/display revocations in the caller's mutation transaction."""
    if not deny_overlay_available(conn):
        raise RuntimeError("music-search deny overlay requires migration 63")
    rows = [
        (str(entity_key), reason[:200], target_source_revision)
        for entity_key in dict.fromkeys(entity_keys)
        if str(entity_key)
    ]
    conn.executemany(
        """INSERT INTO music_search_entity_deny_overlay(
               entity_key, reason, target_source_revision, created_at
           ) VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(entity_key) DO UPDATE SET
               reason=excluded.reason,
               target_source_revision=excluded.target_source_revision,
               created_at=datetime('now')""",
        rows,
    )


def denied_music_search_entity_keys(
    conn: sqlite3.Connection,
    entity_keys: Iterable[str],
) -> set[str]:
    values = tuple(dict.fromkeys(str(value) for value in entity_keys if str(value)))
    if not values or not deny_overlay_available(conn):
        return set()
    placeholders = ",".join("?" for _ in values)
    return {
        str(row[0])
        for row in conn.execute(
            f"""SELECT entity_key FROM music_search_entity_deny_overlay
                WHERE entity_key IN ({placeholders})""",
            values,
        ).fetchall()
    }


def clear_confirmed_music_search_denials(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    source_revision: str,
) -> int:
    """Clear only exclusions proven absent from the newly active generation."""
    if not deny_overlay_available(conn):
        return 0
    cursor = conn.execute(
        """DELETE FROM music_search_entity_deny_overlay AS denied
           WHERE denied.target_source_revision=?
             AND NOT EXISTS (
                 SELECT 1 FROM music_search_documents document
                 WHERE document.generation_id=?
                   AND document.entity_key=denied.entity_key
             )""",
        (source_revision, generation_id),
    )
    return max(0, int(cursor.rowcount))
