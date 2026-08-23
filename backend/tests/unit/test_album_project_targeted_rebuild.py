"""Unit coverage for bounded Album Project rebuilds."""

from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.playback import album_projects

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(1, "Artist"), (2, "Various Artists")],
    )
    conn.executemany(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
        [
            (1, "Alpha", 1),
            (2, "Alpha Deluxe", 1),
            (3, "Beta", 1),
            (4, "Compilation", 2),
            (5, "Manual", 1),
        ],
    )
    conn.executemany(
        """INSERT INTO tracks(
               track_id, track_name, artist_id, album_id, spotify_track_id
           ) VALUES (?, ?, ?, ?, ?)""",
        [
            (101, "Alpha Song", 1, 1, "track-alpha"),
            (102, "Alpha Bonus", 1, 2, "track-alpha-bonus"),
            (103, "Beta Song", 1, 3, "track-beta"),
            (104, "Compilation Exclusive", 2, 4, "track-exclusive"),
            (105, "Manual Song", 1, 5, "track-manual"),
        ],
    )
    conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (101, 4)")
    conn.executemany(
        """INSERT INTO plays(
               play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
               ts_date, platform, ms_played, track_id, source_album_id
           ) VALUES (?, ?, 2026, 1, 1, 3, 0, '2026-01-01',
                     'fixture', 180000, ?, ?)""",
        [
            (1, "2026-01-01T00:00:01Z", 101, 1),
            (2, "2026-01-01T00:00:02Z", 101, 4),
            (3, "2026-01-01T00:00:03Z", 102, 2),
            (4, "2026-01-01T00:00:04Z", 103, 3),
            (5, "2026-01-01T00:00:05Z", 104, 4),
            (6, "2026-01-01T00:00:06Z", 105, 5),
        ],
    )
    conn.executemany(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date, total_tracks
           ) VALUES (?, ?, ?, '2026-01-01', 10)""",
        [
            ("spotify-alpha", "Alpha", "album"),
            ("spotify-alpha-deluxe", "Alpha Deluxe", "album"),
            ("spotify-beta", "Beta", "album"),
            ("spotify-compilation", "Compilation", "compilation"),
            ("spotify-manual", "Manual", "album"),
        ],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, spotify_album_id
           ) VALUES (?, ?, ?)""",
        [
            ("track-alpha", "Alpha Song", "spotify-alpha"),
            ("track-alpha-bonus", "Alpha Bonus", "spotify-alpha-deluxe"),
            ("track-beta", "Beta Song", "spotify-beta"),
            ("track-exclusive", "Compilation Exclusive", "spotify-compilation"),
            ("track-manual", "Manual Song", "spotify-manual"),
        ],
    )
    conn.executemany(
        """INSERT INTO release_groups(
               group_id, canonical_name, artist_id, primary_album_id, scope
           ) VALUES (?, ?, 1, ?, 'release')""",
        [(11, "Alpha", 1), (12, "Beta", 3)],
    )
    conn.executemany(
        "INSERT INTO release_group_members(group_id, album_id) VALUES (?, ?)",
        [(11, 1), (11, 2), (12, 3)],
    )
    conn.execute(
        """INSERT INTO album_projects(
               project_id, canonical_name, artist_id, primary_album_id, release_date,
               scope, project_type, include_in_charts, is_manual
           ) VALUES (900, 'Manual', 1, 5, '1999-01-01', 'release',
                     'curated', 0, 1)"""
    )
    conn.execute(
        """INSERT INTO album_project_albums(
               project_id, album_id, role, source_bucket, inferred
           ) VALUES (900, 5, 'manual-primary', 'other', 0)"""
    )
    conn.execute(
        """INSERT INTO album_project_tracks(
               project_id, track_id, membership_role, min_merge_level,
               source_album_id, is_exclusive, inferred
           ) VALUES (900, 105, 'manual-only', 3, 5, 1, 0)"""
    )
    conn.commit()
    album_projects.rebuild_album_projects(conn)
    return conn


def _tables(conn: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    return {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2")]
        for table in (
            "album_projects",
            "album_project_albums",
            "album_project_tracks",
        )
    }


def _project_rows(
    conn: sqlite3.Connection,
    project_id: int,
) -> dict[str, list[tuple[object, ...]]]:
    return {
        table: [
            tuple(row)
            for row in conn.execute(
                f"SELECT * FROM {table} WHERE project_id=? ORDER BY 1, 2",
                (project_id,),
            )
        ]
        for table in (
            "album_projects",
            "album_project_albums",
            "album_project_tracks",
        )
    }


def _project_id(conn: sqlite3.Connection, name: str) -> int:
    return int(
        conn.execute(
            "SELECT project_id FROM album_projects WHERE canonical_name=?",
            (name,),
        ).fetchone()[0]
    )


def _add_exclusive_track_to_alpha(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (104, 2)")
    next_play_id = int(
        conn.execute("SELECT COALESCE(MAX(play_id), 0) + 1 FROM plays").fetchone()[0]
    )
    conn.execute(
        """INSERT INTO plays(
               play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
               ts_date, platform, ms_played, track_id, source_album_id
           ) VALUES (?, '2026-01-02T00:00:00Z', 2026, 1, 1, 4, 0,
                     '2026-01-02', 'fixture', 180000, 104, 2)""",
        (next_play_id,),
    )
    conn.commit()


def test_targeted_rebuild_preserves_unaffected_and_manual_rows_exactly() -> None:
    conn = _connection()
    try:
        alpha_id = _project_id(conn, "Alpha")
        beta_id = _project_id(conn, "Beta")
        compilation_id = _project_id(conn, "Compilation")
        beta_before = _project_rows(conn, beta_id)
        manual_before = _project_rows(conn, 900)
        _add_exclusive_track_to_alpha(conn)

        report = album_projects.rebuild_album_projects_for_impact(
            conn,
            local_album_ids={2},
            impact_scope_exact=True,
            max_affected_ratio=1.0,
        )

        assert report.strategy == "targeted"
        assert report.fallback_reason is None
        assert report.affected_album_count == 3
        assert report.affected_release_group_count == 1
        assert _project_id(conn, "Alpha") == alpha_id
        assert _project_rows(conn, beta_id) == beta_before
        assert _project_rows(conn, 900) == manual_before
        assert (
            conn.execute(
                "SELECT 1 FROM album_projects WHERE project_id=?",
                (compilation_id,),
            ).fetchone()
            is None
        )
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT track_id FROM album_project_tracks WHERE project_id=?",
                (alpha_id,),
            )
        } == {101, 102, 104}
    finally:
        conn.close()


def test_empty_exact_impact_is_targeted_noop() -> None:
    conn = _connection()
    try:
        before = _tables(conn)

        report = album_projects.rebuild_album_projects_for_impact(
            conn,
            impact_scope_exact=True,
        )

        assert report.strategy == "targeted"
        assert report.affected_album_count == 0
        assert report.affected_project_count == 0
        assert report.affected_track_count == 0
        assert _tables(conn) == before
    finally:
        conn.close()


def test_targeted_rebuild_matches_full_rebuild_for_closed_impact() -> None:
    targeted = _connection()
    full = sqlite3.connect(":memory:")
    full.row_factory = sqlite3.Row
    targeted.backup(full)
    try:
        _add_exclusive_track_to_alpha(targeted)
        _add_exclusive_track_to_alpha(full)

        report = album_projects.rebuild_album_projects_for_impact(
            targeted,
            spotify_album_ids={"spotify-alpha-deluxe"},
            spotify_track_ids={"track-exclusive"},
            impact_scope_exact=True,
            max_affected_ratio=1.0,
        )
        album_projects.rebuild_album_projects(full)

        assert report.strategy == "targeted"
        assert _tables(targeted) == _tables(full)
    finally:
        targeted.close()
        full.close()


def test_full_rebuild_ignores_stale_album_observations_but_preserves_manual_projects() -> None:
    conn = _connection()
    try:
        manual_before = _project_rows(conn, 900)
        conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (101, 3)")
        conn.execute(
            """INSERT INTO tracks(
                   track_id, track_name, artist_id, album_id, spotify_track_id
               ) VALUES (106, 'Orphan Observation', 1, 1, 'track-orphan')"""
        )
        conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (106, 3)")
        conn.execute("DELETE FROM plays WHERE track_id=101")
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
                   ts_date, platform, ms_played, track_id, source_album_id
               ) VALUES (1, '2026-01-01T00:00:00Z', 2026, 1, 1, 3, 0,
                         '2026-01-01', 'fixture', 180000, 101, 3)"""
        )
        conn.commit()

        album_projects.rebuild_album_projects(conn)

        beta_id = _project_id(conn, "Beta")
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT track_id FROM album_project_tracks WHERE project_id=?",
                (beta_id,),
            )
        } == {101, 103}
        assert not conn.execute(
            """SELECT 1
               FROM album_project_tracks apt
               JOIN album_projects ap ON ap.project_id=apt.project_id
               WHERE apt.track_id=101 AND ap.canonical_name IN ('Alpha', 'Compilation')"""
        ).fetchall()
        assert not conn.execute("SELECT 1 FROM album_project_tracks WHERE track_id=106").fetchall()
        assert _project_rows(conn, 900) == manual_before
        assert conn.execute(
            "SELECT 1 FROM track_albums WHERE track_id=101 AND album_id=4"
        ).fetchone()
    finally:
        conn.close()


@pytest.mark.parametrize(
    (
        "local_album_ids",
        "impact_scope_exact",
        "has_deletions",
        "max_affected_albums",
        "reason",
    ),
    [
        (set(), False, False, 500, "impact_scope_inexact"),
        (set(), True, True, 500, "deletion_semantics"),
        ({1}, True, False, 0, "closure_too_large"),
        ({999}, True, False, 500, "closure_unproven"),
    ],
)
def test_unproven_or_oversized_impact_falls_back_to_full(
    local_album_ids: set[int],
    impact_scope_exact: bool,
    has_deletions: bool,
    max_affected_albums: int,
    reason: str,
) -> None:
    conn = _connection()
    try:
        report = album_projects.rebuild_album_projects_for_impact(
            conn,
            local_album_ids=local_album_ids,
            impact_scope_exact=impact_scope_exact,
            has_deletions=has_deletions,
            max_affected_albums=max_affected_albums,
        )

        assert report.strategy == "full"
        assert report.fallback_reason == reason
        assert report.affected_project_count == 3
    finally:
        conn.close()
