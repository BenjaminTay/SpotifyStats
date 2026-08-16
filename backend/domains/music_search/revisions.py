"""Persistent O(1) revision state for music-search derived data."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from typing import Literal

MusicSearchRevisionKind = Literal["playback", "billboard", "metadata", "settings"]


@dataclass(frozen=True)
class MusicSearchRevisionState:
    playback_revision: int = 0
    billboard_revision: int = 0
    metadata_revision: int = 0
    settings_revision: int = 0
    updated_at: str | None = None

    def values(self) -> dict[str, int | str | None]:
        return asdict(self)


def _table_exists(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_revision_state'"""
        ).fetchone()
        is not None
    )


def get_music_search_revision_state(
    conn: sqlite3.Connection,
) -> MusicSearchRevisionState:
    """Read the singleton revision row without deriving facts from large tables.

    The zero fallback keeps offline schema inspection safe before migration 34;
    normal application startup always runs migrations before serving requests.
    This helper intentionally never creates or updates schema from a GET path.
    """
    if not _table_exists(conn):
        return MusicSearchRevisionState()
    row = conn.execute(
        """SELECT playback_revision, billboard_revision, metadata_revision,
                  settings_revision, updated_at
           FROM music_search_revision_state WHERE state_id=1"""
    ).fetchone()
    if row is None:
        return MusicSearchRevisionState()
    return MusicSearchRevisionState(
        playback_revision=int(row[0]),
        billboard_revision=int(row[1]),
        metadata_revision=int(row[2]),
        settings_revision=int(row[3]),
        updated_at=str(row[4]) if row[4] is not None else None,
    )


def bump_music_search_revisions(
    conn: sqlite3.Connection,
    *kinds: MusicSearchRevisionKind,
) -> MusicSearchRevisionState:
    """Increment selected revisions in the caller's transaction.

    No commit is performed here.  Mutation callers can therefore publish the
    revision and the business fact atomically, while maintenance callers can
    commit at their explicit success boundary.
    """
    selected = tuple(dict.fromkeys(kinds))
    if not selected:
        return get_music_search_revision_state(conn)
    invalid = set(selected) - {"playback", "billboard", "metadata", "settings"}
    if invalid:
        raise ValueError(f"unsupported music-search revision kinds: {sorted(invalid)}")
    if not _table_exists(conn):
        raise RuntimeError("music_search_revision_state requires migration 34")

    assignments = [f"{kind}_revision={kind}_revision+1" for kind in selected]
    assignments.append("updated_at=datetime('now')")
    cursor = conn.execute(
        f"""UPDATE music_search_revision_state SET {", ".join(assignments)}
            WHERE state_id=1"""
    )
    if cursor.rowcount != 1:
        raise RuntimeError("music_search_revision_state singleton is missing")
    return get_music_search_revision_state(conn)
