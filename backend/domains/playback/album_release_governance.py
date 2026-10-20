"""Durable album separation decisions, retired links and merge audit evidence."""

from __future__ import annotations

import itertools
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS album_release_separations (
    left_album_id INTEGER NOT NULL REFERENCES albums(album_id),
    right_album_id INTEGER NOT NULL REFERENCES albums(album_id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(left_album_id, right_album_id),
    CHECK(left_album_id < right_album_id)
);
CREATE TABLE IF NOT EXISTS album_project_redirects (
    retired_project_id INTEGER PRIMARY KEY,
    target_project_id INTEGER NOT NULL REFERENCES album_projects(project_id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(retired_project_id != target_project_id)
);
CREATE TABLE IF NOT EXISTS album_release_merge_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_project_id INTEGER NOT NULL,
    policy_version TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS album_release_content_relations (
    base_album_id INTEGER NOT NULL REFERENCES albums(album_id),
    member_album_id INTEGER NOT NULL REFERENCES albums(album_id),
    relation_type TEXT NOT NULL,
    PRIMARY KEY(base_album_id, member_album_id),
    CHECK(base_album_id != member_album_id)
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def separated_pairs(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='album_release_separations'"
    ).fetchone():
        return set()
    return {
        tuple(row)
        for row in conn.execute(
            "SELECT left_album_id,right_album_id FROM album_release_separations"
        )
    }


def preserve_separation(conn: sqlite3.Connection, left_ids, right_ids=None, *, reason: str) -> None:
    pairs = (
        itertools.combinations(sorted(set(left_ids)), 2)
        if right_ids is None
        else itertools.product(left_ids, right_ids)
    )
    conn.executemany(
        "INSERT OR IGNORE INTO album_release_separations(left_album_id,right_album_id,reason) VALUES(?,?,?)",
        [(min(a, b), max(a, b), reason) for a, b in pairs if a != b],
    )


def resolve_project_redirect(conn: sqlite3.Connection, project_id: int) -> int:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='album_project_redirects'"
    ).fetchone():
        return project_id
    seen = set()
    while project_id not in seen:
        seen.add(project_id)
        row = conn.execute(
            "SELECT target_project_id FROM album_project_redirects WHERE retired_project_id=?",
            (project_id,),
        ).fetchone()
        if row is None:
            return project_id
        project_id = int(row[0])
    raise ValueError("Album Project redirect cycle")
