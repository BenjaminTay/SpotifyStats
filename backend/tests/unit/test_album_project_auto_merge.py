"""Unit coverage for deterministic Album Project auto merging."""

from __future__ import annotations

import json
import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.playback.album_project_auto_merge import (
    apply_album_project_auto_merge_plan,
    plan_album_project_auto_merges,
)
from backend.domains.playback.album_projects import rebuild_album_projects

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _add_spotify_release(
    conn: sqlite3.Connection,
    *,
    spotify_album_id: str,
    album_name: str,
    album_artists: str,
    release_date: str,
    track_ids: list[str],
    album_type: str = "album",
) -> None:
    conn.execute(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date,
               album_artists, total_tracks, track_list
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            spotify_album_id,
            album_name,
            album_type,
            release_date,
            album_artists,
            len(track_ids),
            json.dumps(track_ids),
        ),
    )


def _add_local_album(
    conn: sqlite3.Connection,
    *,
    album_id: int,
    album_name: str,
    artist_id: int,
    artist_name: str,
    spotify_album_id: str,
    spotify_track_id: str,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO artists(artist_id, artist_name) VALUES (?, ?)",
        (artist_id, artist_name),
    )
    conn.execute(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
        (album_id, album_name, artist_id),
    )
    track_id = album_id * 10
    conn.execute(
        """INSERT INTO tracks(
               track_id, track_name, artist_id, album_id, spotify_track_id
           ) VALUES (?, ?, ?, ?, ?)""",
        (track_id, f"Song {album_id}", artist_id, album_id, spotify_track_id),
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, spotify_album_id
           ) VALUES (?, ?, ?)""",
        (spotify_track_id, f"Song {album_id}", spotify_album_id),
    )
    conn.execute(
        """INSERT INTO album_spotify_links(
               album_id, spotify_album_id, evidence, confidence,
               play_count, track_count
           ) VALUES (?, ?, 'fixture-track-membership', 1.0, 1, 1)""",
        (album_id, spotify_album_id),
    )
    conn.execute(
        """INSERT INTO plays(
               ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
               platform, ms_played, track_id, source_album_id
           ) VALUES (?, 2026, 1, 1, 3, 0, '2026-01-01',
                     'fixture', 180000, ?, ?)""",
        (f"2026-01-01T00:00:{album_id % 60:02d}Z", track_id, album_id),
    )


def _add_release_track_metadata(
    conn: sqlite3.Connection,
    *,
    spotify_album_id: str,
    tracks: list[tuple[str, str, str]],
) -> None:
    conn.executemany(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, isrc, spotify_album_id
           ) VALUES (?, ?, ?, ?)
           ON CONFLICT(spotify_track_id) DO UPDATE SET
               track_name=excluded.track_name,
               isrc=excluded.isrc,
               spotify_album_id=excluded.spotify_album_id""",
        ((track_id, track_name, isrc, spotify_album_id) for track_id, track_name, isrc in tracks),
    )


def _prepare_standalone_projects(conn: sqlite3.Connection) -> None:
    conn.commit()
    rebuild_album_projects(conn)


def test_case_only_duplicate_is_planned_and_applied_once() -> None:
    conn = _connection()
    try:
        _add_spotify_release(
            conn,
            spotify_album_id="spotify-case-album",
            album_name="Bad Boy",
            album_artists="A-Mei",
            release_date="1997-06-07",
            track_ids=["case-track-a", "case-track-b"],
        )
        _add_local_album(
            conn,
            album_id=10,
            album_name="Bad Boy",
            artist_id=1,
            artist_name="A-Mei",
            spotify_album_id="spotify-case-album",
            spotify_track_id="case-track-a",
        )
        _add_local_album(
            conn,
            album_id=11,
            album_name="BAD BOY",
            artist_id=1,
            artist_name="A-Mei",
            spotify_album_id="spotify-case-album",
            spotify_track_id="case-track-b",
        )
        _prepare_standalone_projects(conn)

        plan = plan_album_project_auto_merges(conn)

        assert len(plan.candidates) == 1
        candidate = plan.candidates[0]
        assert candidate.album_ids == (10, 11)
        assert candidate.canonical_name == "Bad Boy"
        assert "complete_track_list_match" in candidate.evidence_codes

        report = apply_album_project_auto_merge_plan(conn, plan)

        assert report.groups_created == 1
        assert report.projects_merged == 2
        assert report.requires_downstream_refresh is True
        project = conn.execute(
            "SELECT project_id, canonical_name FROM album_projects WHERE project_type='album'"
        ).fetchall()
        assert len(project) == 1
        assert project[0]["canonical_name"] == "Bad Boy"
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id=?",
                (project[0]["project_id"],),
            )
        } == {10, 11}
        identity = conn.execute(
            """SELECT external_album_id, evidence_type, confidence, is_primary
                 FROM album_project_external_ids WHERE project_id=?""",
            (project[0]["project_id"],),
        ).fetchone()
        assert tuple(identity) == ("spotify-case-album", "catalog_exact", 1.0, 1)
        project_identity = conn.execute(
            """SELECT normalized_name, album_artist_key, identity_policy_version
                 FROM album_projects WHERE project_id=?""",
            (project[0]["project_id"],),
        ).fetchone()
        assert tuple(project_identity) == (
            "bad boy",
            "a-mei",
            "spotify_complete_release_v2",
        )
        assert not plan_album_project_auto_merges(conn).candidates
    finally:
        conn.close()


def test_shared_complete_release_merges_multi_artist_soundtrack_projects() -> None:
    conn = _connection()
    try:
        _add_spotify_release(
            conn,
            spotify_album_id="wicked-soundtrack",
            album_name="Wicked: The Soundtrack",
            album_artists="Wicked Movie Cast",
            release_date="2024-11-22",
            track_ids=["wicked-a", "wicked-b", "wicked-c"],
        )
        for album_id, artist_id, artist_name, track_id in (
            (20, 1, "Cynthia Erivo", "wicked-a"),
            (21, 2, "Ariana Grande", "wicked-b"),
            (22, 3, "Jonathan Bailey", "wicked-c"),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name="Wicked: The Soundtrack",
                artist_id=artist_id,
                artist_name=artist_name,
                spotify_album_id="wicked-soundtrack",
                spotify_track_id=track_id,
            )
        _prepare_standalone_projects(conn)

        plan = plan_album_project_auto_merges(conn)

        assert len(plan.candidates) == 1
        assert plan.candidates[0].project_ids == (1, 2, 3)
        assert plan.candidates[0].album_ids == (20, 21, 22)

        apply_album_project_auto_merge_plan(conn, plan)

        project = conn.execute(
            """SELECT project_id, canonical_name, release_date
                 FROM album_projects WHERE project_type='soundtrack'"""
        ).fetchall()
        assert len(project) == 1
        assert tuple(project[0])[1:] == ("Wicked: The Soundtrack", "2024-11-22")
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id=?",
                (project[0]["project_id"],),
            )
        } == {20, 21, 22}
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT track_id FROM album_project_tracks WHERE project_id=?",
                (project[0]["project_id"],),
            )
        } == {200, 210, 220}
    finally:
        conn.close()


def test_weak_link_without_complete_track_list_never_auto_merges() -> None:
    conn = _connection()
    try:
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   album_artists, total_tracks, track_list
               ) VALUES ('weak-album', 'Weak Album', 'album', '2024-01-01',
                         'Artist', 2, NULL)"""
        )
        for album_id, album_name, track_id in (
            (30, "Weak Album", "weak-a"),
            (31, "WEAK ALBUM", "weak-b"),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=album_name,
                artist_id=1,
                artist_name="Artist",
                spotify_album_id="weak-album",
                spotify_track_id=track_id,
            )
        _prepare_standalone_projects(conn)

        plan = plan_album_project_auto_merges(conn)

        assert plan.candidates == ()
        assert dict(plan.skipped_reason_counts)["incomplete_track_list"] == 2
    finally:
        conn.close()


def test_compilation_policy_and_existing_bundle_are_frozen() -> None:
    conn = _connection()
    try:
        _add_spotify_release(
            conn,
            spotify_album_id="best-of",
            album_name="Artist Best Of",
            album_artists="Artist",
            release_date="2020-01-01",
            track_ids=["best-a", "best-b"],
        )
        for album_id, album_name, track_id in (
            (40, "Artist Best Of", "best-a"),
            (41, "ARTIST BEST OF", "best-b"),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=album_name,
                artist_id=1,
                artist_name="Artist",
                spotify_album_id="best-of",
                spotify_track_id=track_id,
            )

        _add_spotify_release(
            conn,
            spotify_album_id="bundle-album",
            album_name="Bundle Album",
            album_artists="Artist",
            release_date="2025-01-01",
            track_ids=["bundle-original", "bundle-acoustic"],
        )
        for album_id, name, track_id in (
            (50, "Bundle Album", "bundle-original"),
            (51, "Bundle Album Acoustic Collection", "bundle-acoustic"),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=name,
                artist_id=1,
                artist_name="Artist",
                spotify_album_id="bundle-album",
                spotify_track_id=track_id,
            )
        conn.execute(
            """INSERT INTO release_groups(
                   group_id, canonical_name, artist_id, primary_album_id,
                   scope, is_manual
               ) VALUES (500, 'Bundle Album', 1, 50, 'release', 0)"""
        )
        conn.executemany(
            "INSERT INTO release_group_members(group_id, album_id) VALUES (500, ?)",
            [(50,), (51,)],
        )
        _prepare_standalone_projects(conn)
        before = [
            tuple(row)
            for row in conn.execute("SELECT album_id FROM album_project_albums ORDER BY album_id")
        ]

        plan = plan_album_project_auto_merges(conn)

        assert plan.candidates == ()
        assert dict(plan.skipped_reason_counts)["compilation_policy_frozen"] == 2
        assert before == [
            tuple(row)
            for row in conn.execute("SELECT album_id FROM album_project_albums ORDER BY album_id")
        ]
        bundle_project = conn.execute(
            "SELECT project_id FROM album_projects WHERE canonical_name='Bundle Album'"
        ).fetchone()
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id=?",
                (bundle_project[0],),
            )
        } == {50, 51}
    finally:
        conn.close()


def test_sun_yanzi_original_and_remaster_merge_but_2004_namesake_stays_separate() -> None:
    conn = _connection()
    try:
        original_ids = [f"yanzi-original-{index}" for index in range(1, 6)]
        remaster_ids = [f"yanzi-remaster-{index}" for index in range(1, 6)]
        namesake_ids = [f"yanzi-2004-{index}" for index in range(1, 6)]
        _add_spotify_release(
            conn,
            spotify_album_id="yanzi-2000",
            album_name="孫燕姿同名專輯",
            album_artists="Stefanie Sun",
            release_date="2000-06-09",
            track_ids=original_ids,
        )
        _add_spotify_release(
            conn,
            spotify_album_id="yanzi-2000-remaster",
            album_name="同名專輯 (Remastered)",
            album_artists="Stefanie Sun",
            release_date="2000",
            track_ids=remaster_ids,
        )
        _add_spotify_release(
            conn,
            spotify_album_id="yanzi-2004",
            album_name="孫燕姿STEFANIE同名專輯",
            album_artists="Stefanie Sun",
            release_date="2004-10-29",
            track_ids=namesake_ids,
        )
        for album_id, album_name, spotify_album_id, spotify_track_id in (
            (60, "孫燕姿同名專輯", "yanzi-2000", original_ids[0]),
            (61, "同名專輯", "yanzi-2000-remaster", remaster_ids[0]),
            # The 2004 namesake has a different complete repertoire and must
            # remain a distinct local container despite the artist/title words.
            (62, "孫燕姿STEFANIE同名專輯", "yanzi-2004", namesake_ids[0]),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=album_name,
                artist_id=1,
                artist_name="Stefanie Sun",
                spotify_album_id=spotify_album_id,
                spotify_track_id=spotify_track_id,
            )
        original_tracks = [
            (track_id, f"Debut Song {index}", f"SGA00{index:03d}")
            for index, track_id in enumerate(original_ids, start=1)
        ]
        remaster_tracks = [
            (track_id, f"Debut Song {index} - 2024 Remastered", f"SGR24{index:03d}")
            for index, track_id in enumerate(remaster_ids, start=1)
        ]
        namesake_tracks = [
            (track_id, f"Namesake Song {index}", f"SGN04{index:03d}")
            for index, track_id in enumerate(namesake_ids, start=1)
        ]
        _add_release_track_metadata(conn, spotify_album_id="yanzi-2000", tracks=original_tracks)
        _add_release_track_metadata(
            conn, spotify_album_id="yanzi-2000-remaster", tracks=remaster_tracks
        )
        _add_release_track_metadata(conn, spotify_album_id="yanzi-2004", tracks=namesake_tracks)
        _prepare_standalone_projects(conn)

        plan = plan_album_project_auto_merges(conn)

        assert len(plan.candidates) == 1
        candidate = plan.candidates[0]
        assert candidate.album_ids == (60, 61)
        assert candidate.primary_album_id == 60
        assert candidate.spotify_album_ids == ("yanzi-2000", "yanzi-2000-remaster")
        assert candidate.relation_types == ("remaster_equivalent",)
        assert "remaster_equivalent" in candidate.evidence_codes

        apply_album_project_auto_merge_plan(conn, plan)

        merged_project_id = int(
            conn.execute(
                "SELECT project_id FROM album_project_albums WHERE album_id=60"
            ).fetchone()[0]
        )
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id=?",
                (merged_project_id,),
            )
        } == {60, 61}
        assert (
            conn.execute(
                "SELECT project_id FROM album_project_albums WHERE album_id=62"
            ).fetchone()[0]
            != merged_project_id
        )
        identities = [
            tuple(row)
            for row in conn.execute(
                """SELECT external_album_id, evidence_type, is_primary
                     FROM album_project_external_ids
                    WHERE project_id=? ORDER BY external_album_id""",
                (merged_project_id,),
            )
        ]
        assert identities == [
            ("yanzi-2000", "remaster_equivalent", 1),
            ("yanzi-2000-remaster", "remaster_equivalent", 0),
        ]
        assert plan_album_project_auto_merges(conn).candidates == ()
        assert (
            apply_album_project_auto_merge_plan(
                conn, plan_album_project_auto_merges(conn)
            ).requires_downstream_refresh
            is False
        )
    finally:
        conn.close()


def test_deluxe_superset_merges_only_with_complete_ordered_base_tracklist() -> None:
    conn = _connection()
    try:
        base_ids = [f"deluxe-base-{index}" for index in range(1, 6)]
        deluxe_ids = [f"deluxe-expanded-{index}" for index in range(1, 8)]
        _add_spotify_release(
            conn,
            spotify_album_id="deluxe-base",
            album_name="Five",
            album_artists="Artist",
            release_date="2020-01-01",
            track_ids=base_ids,
        )
        _add_spotify_release(
            conn,
            spotify_album_id="deluxe-expanded",
            album_name="Five (Deluxe Edition)",
            album_artists="Artist",
            release_date="2020-06-01",
            track_ids=deluxe_ids,
        )
        for album_id, name, spotify_album_id, track_id in (
            (70, "Five", "deluxe-base", base_ids[0]),
            (71, "Five (Deluxe Edition)", "deluxe-expanded", deluxe_ids[0]),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=name,
                artist_id=1,
                artist_name="Artist",
                spotify_album_id=spotify_album_id,
                spotify_track_id=track_id,
            )
        base_tracks = [
            (track_id, f"Track {index}", f"BASE{index:04d}")
            for index, track_id in enumerate(base_ids, start=1)
        ]
        deluxe_tracks = [
            (track_id, f"Track {index}", f"DELUXE{index:04d}")
            for index, track_id in enumerate(deluxe_ids, start=1)
        ]
        _add_release_track_metadata(conn, spotify_album_id="deluxe-base", tracks=base_tracks)
        _add_release_track_metadata(conn, spotify_album_id="deluxe-expanded", tracks=deluxe_tracks)
        _prepare_standalone_projects(conn)

        plan = plan_album_project_auto_merges(conn)

        assert len(plan.candidates) == 1
        assert plan.candidates[0].relation_types == ("deluxe_superset",)
        assert plan.candidates[0].primary_album_id == 70
    finally:
        conn.close()


def test_catalog_alias_requires_same_date_and_complete_ordered_repertoire() -> None:
    conn = _connection()
    try:
        left_ids = [f"alias-left-{index}" for index in range(1, 4)]
        right_ids = [f"alias-right-{index}" for index in range(1, 4)]
        _add_spotify_release(
            conn,
            spotify_album_id="alias-left",
            album_name="Album: One",
            album_artists="Artist",
            release_date="2022-02-02",
            track_ids=left_ids,
        )
        _add_spotify_release(
            conn,
            spotify_album_id="alias-right",
            album_name="Album One",
            album_artists="Artist",
            release_date="2022-02-02",
            track_ids=right_ids,
        )
        for album_id, name, spotify_album_id, track_id in (
            (80, "Album: One", "alias-left", left_ids[0]),
            (81, "Album One", "alias-right", right_ids[0]),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=name,
                artist_id=1,
                artist_name="Artist",
                spotify_album_id=spotify_album_id,
                spotify_track_id=track_id,
            )
        for spotify_album_id, track_ids in (
            ("alias-left", left_ids),
            ("alias-right", right_ids),
        ):
            _add_release_track_metadata(
                conn,
                spotify_album_id=spotify_album_id,
                tracks=[
                    (track_id, f"Alias Song {index}", f"ALIAS{index:04d}")
                    for index, track_id in enumerate(track_ids, start=1)
                ],
            )
        _prepare_standalone_projects(conn)

        plan = plan_album_project_auto_merges(conn)

        assert len(plan.candidates) == 1
        assert plan.candidates[0].relation_types == ("catalog_alias_equivalent",)
        apply_album_project_auto_merge_plan(conn, plan)
        project_id = int(
            conn.execute(
                "SELECT project_id FROM album_project_albums WHERE album_id=80"
            ).fetchone()[0]
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM album_project_external_ids WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            == 2
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("album_name", "album_type"),
    [
        ("World Tour Live", "album"),
        ("Acoustic Collection", "album"),
        ("The Remixes", "album"),
        ("Album (Taylor's Version)", "album"),
        ("Artist Greatest Hits", "compilation"),
    ],
)
def test_alternate_and_compilation_releases_fail_closed(
    album_name: str,
    album_type: str,
) -> None:
    conn = _connection()
    try:
        spotify_album_id = f"blocked-{album_type}-{len(album_name)}"
        track_ids = [f"{spotify_album_id}-a", f"{spotify_album_id}-b"]
        _add_spotify_release(
            conn,
            spotify_album_id=spotify_album_id,
            album_name=album_name,
            album_artists="Artist",
            release_date="2023-01-01",
            track_ids=track_ids,
            album_type=album_type,
        )
        for album_id, local_name, track_id in (
            (90, album_name, track_ids[0]),
            (91, album_name.upper(), track_ids[1]),
        ):
            _add_local_album(
                conn,
                album_id=album_id,
                album_name=local_name,
                artist_id=1,
                artist_name="Artist",
                spotify_album_id=spotify_album_id,
                spotify_track_id=track_id,
            )
        _prepare_standalone_projects(conn)

        assert plan_album_project_auto_merges(conn).candidates == ()
    finally:
        conn.close()
