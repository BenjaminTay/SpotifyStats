"""Regression tests for stable inferred album-project identities."""

from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.playback import album_projects


def _connection(*, foreign_keys: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}")
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
    return conn


def _add_release(
    conn: sqlite3.Connection,
    *,
    album_id: int,
    track_id: int,
    group_id: int,
    name: str,
    album_type: str = "album",
) -> None:
    conn.execute(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, 1)",
        (album_id, name),
    )
    conn.execute(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, 1, ?, ?)""",
        (track_id, f"{name} Track", album_id, f"track:{track_id}"),
    )
    conn.execute(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date, total_tracks
           ) VALUES (?, ?, ?, '2026-01-01', 10)""",
        (f"spotify:album:{album_id}", name, album_type),
    )
    conn.execute(
        """INSERT INTO release_groups(
               group_id, canonical_name, artist_id, primary_album_id, scope
           ) VALUES (?, ?, 1, ?, 'release')""",
        (group_id, name, album_id),
    )
    conn.execute(
        "INSERT INTO release_group_members(group_id, album_id) VALUES (?, ?)",
        (group_id, album_id),
    )
    conn.execute(
        """INSERT INTO plays(
               ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
               platform, ms_played, track_id, source_album_id
           ) VALUES (?, 2026, 1, 2, 0, 12, '2026-01-05',
                     'fixture', 180000, ?, ?)""",
        (f"2026-01-05T12:{track_id % 60:02d}:00Z", track_id, album_id),
    )


def _snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    return {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2")]
        for table in (
            "album_projects",
            "album_project_albums",
            "album_project_tracks",
        )
    }


def test_rebuild_reuses_inferred_ids_and_replaces_membership_with_foreign_keys_off() -> None:
    conn = _connection(foreign_keys=False)
    try:
        _add_release(conn, album_id=1, track_id=101, group_id=11, name="Alpha")
        conn.execute(
            "INSERT INTO albums(album_id, album_name, artist_id) VALUES (10, 'Alpha Deluxe', 1)"
        )
        conn.execute(
            """INSERT INTO tracks(track_id, track_name, artist_id, album_id)
               VALUES (110, 'Alpha Bonus', 1, 10)"""
        )
        conn.execute(
            """INSERT INTO plays(
                   ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                   platform, ms_played, track_id, source_album_id
               ) VALUES ('2026-02-01T12:00:00Z', 2026, 2, 5, 6, 12,
                         '2026-02-01', 'fixture', 180000, 110, 10)"""
        )
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date, total_tracks
               ) VALUES ('spotify:alpha-deluxe', 'Alpha Deluxe', 'single', '2026-02-01', 1)"""
        )
        conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (11, 10)")

        # A manual project intentionally collides with what standalone inference
        # would otherwise create. Its metadata and memberships must remain exact.
        conn.execute("INSERT INTO albums(album_id, album_name, artist_id) VALUES (90, 'Manual', 1)")
        conn.execute(
            """INSERT INTO tracks(track_id, track_name, artist_id, album_id)
               VALUES (190, 'Manual Track', 1, 90)"""
        )
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date, total_tracks
               ) VALUES ('spotify:manual', 'Manual', 'album', '2026-02-02', 10)"""
        )
        conn.execute(
            """INSERT INTO album_projects(
                   project_id, canonical_name, artist_id, primary_album_id, release_date,
                   scope, project_type, include_in_charts, is_manual
               ) VALUES (900, 'Manual', 1, 90, '1999-01-01', 'release',
                         'curated', 0, 1)"""
        )
        conn.execute(
            """INSERT INTO album_project_albums(
                   project_id, album_id, role, source_bucket, inferred
               ) VALUES (900, 90, 'manual-primary', 'other', 0)"""
        )
        conn.execute(
            """INSERT INTO album_project_tracks(
                   project_id, track_id, membership_role, min_merge_level,
                   source_album_id, is_exclusive, inferred
               ) VALUES (900, 190, 'manual-only', 3, 90, 1, 0)"""
        )
        conn.commit()

        album_projects.rebuild_album_projects(conn)
        first = _snapshot(conn)
        alpha_id = int(
            conn.execute(
                "SELECT project_id FROM album_projects WHERE canonical_name = 'Alpha'"
            ).fetchone()[0]
        )
        sequence = int(
            conn.execute(
                "SELECT seq FROM sqlite_sequence WHERE name = 'album_projects'"
            ).fetchone()[0]
        )

        album_projects.rebuild_album_projects(conn)
        assert _snapshot(conn) == first
        assert (
            int(
                conn.execute(
                    "SELECT seq FROM sqlite_sequence WHERE name = 'album_projects'"
                ).fetchone()[0]
            )
            == sequence
        )

        # Membership is replaced, not accumulated, while the owner ID remains
        # stable. As a single, the removed edition is not inferred separately.
        conn.execute("DELETE FROM release_group_members WHERE group_id = 11 AND album_id = 10")
        conn.commit()
        album_projects.rebuild_album_projects(conn)
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id = ?", (alpha_id,)
            )
        } == {1}
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT track_id FROM album_project_tracks WHERE project_id = ?", (alpha_id,)
            )
        } == {101}

        _add_release(conn, album_id=2, track_id=102, group_id=12, name="Beta")
        conn.commit()
        album_projects.rebuild_album_projects(conn)

        assert (
            int(
                conn.execute(
                    "SELECT project_id FROM album_projects WHERE canonical_name = 'Alpha'"
                ).fetchone()[0]
            )
            == alpha_id
        )
        beta_id = int(
            conn.execute(
                "SELECT project_id FROM album_projects WHERE canonical_name = 'Beta'"
            ).fetchone()[0]
        )
        assert beta_id != alpha_id

        # Removing the source project and classifying its album as a single makes
        # it disappear on the next rebuild. With foreign keys disabled, explicit
        # child cleanup must still leave no orphan relationships.
        conn.execute("DELETE FROM release_group_members WHERE group_id = 12")
        conn.execute("DELETE FROM release_groups WHERE group_id = 12")
        conn.execute(
            "UPDATE spotify_album_meta SET album_type = 'single' WHERE spotify_album_id = 'spotify:album:2'"
        )
        conn.commit()
        album_projects.rebuild_album_projects(conn)

        assert (
            conn.execute("SELECT 1 FROM album_projects WHERE project_id = ?", (beta_id,)).fetchone()
            is None
        )
        for table in ("album_project_albums", "album_project_tracks"):
            assert (
                conn.execute(f"SELECT 1 FROM {table} WHERE project_id = ?", (beta_id,)).fetchone()
                is None
            )
        manual = conn.execute(
            """SELECT release_date, project_type, include_in_charts, is_manual
               FROM album_projects WHERE project_id = 900"""
        ).fetchone()
        assert tuple(manual) == ("1999-01-01", "curated", 0, 1)
        assert tuple(
            conn.execute(
                "SELECT role, source_bucket FROM album_project_albums WHERE project_id = 900"
            ).fetchone()
        ) == ("manual-primary", "other")
        assert tuple(
            conn.execute(
                """SELECT membership_role, min_merge_level, is_exclusive
                   FROM album_project_tracks WHERE project_id = 900"""
            ).fetchone()
        ) == ("manual-only", 3, 1)
    finally:
        conn.close()


def test_rebuild_rolls_back_membership_clear_when_population_fails(monkeypatch) -> None:
    conn = _connection(foreign_keys=True)
    try:
        _add_release(conn, album_id=1, track_id=101, group_id=11, name="Alpha")
        conn.commit()
        album_projects.rebuild_album_projects(conn)
        before = _snapshot(conn)

        def fail_population(*args, **kwargs) -> None:
            raise RuntimeError("fixture failure")

        monkeypatch.setattr(album_projects, "_populate_album_projects", fail_population)
        with pytest.raises(RuntimeError, match="fixture failure"):
            album_projects.rebuild_album_projects(conn)

        assert _snapshot(conn) == before
    finally:
        conn.close()
