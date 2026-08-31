from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.metadata.l2_track_auto_merge import apply_l2_track_merge_plan
from backend.domains.metadata.l3_track_auto_merge import (
    apply_l3_track_merge_plan,
    build_l3_track_merge_plan,
)

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for artist_id in (1, 2, 3):
        conn.execute(
            "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
            (artist_id, f"Artist {artist_id}"),
        )
        conn.execute(
            "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
            (artist_id, f"Album {artist_id}", artist_id),
        )
    return conn


def _track(
    conn: sqlite3.Connection,
    track_id: int,
    name: str,
    *,
    artist_ids: tuple[int, ...] = (1,),
    plays: int = 0,
    isrc: str | None = None,
    duration_ms: int = 180_000,
) -> None:
    spotify_id = f"spotify-{track_id}"
    conn.execute(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, ?, ?, ?)""",
        (track_id, name, artist_ids[0], artist_ids[0], spotify_id),
    )
    for artist_id in artist_ids:
        conn.execute(
            "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
            (track_id, artist_id),
        )
    conn.execute(
        """INSERT INTO track_l1_identities(
               l1_id, fallback_track_id, identity_status, representative_track_id
           ) VALUES (?, ?, 'active', ?)""",
        (track_id, track_id, track_id),
    )
    conn.execute(
        """INSERT INTO track_l1_external_ids(
               provider, external_track_id, l1_id, evidence_type, is_primary
           ) VALUES ('spotify', ?, ?, 'provider_observed', 1)""",
        (spotify_id, track_id),
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, duration_ms, isrc)
           VALUES (?, ?, ?, ?)""",
        (spotify_id, name, duration_ms, isrc or f"ISRC-{track_id}"),
    )
    conn.execute(
        """INSERT INTO track_l1_source_links(
               l1_id, track_id, evidence_type, observed_plays
           ) VALUES (?, ?, 'play_at_time', ?)""",
        (track_id, track_id, plays),
    )
    for offset in range(plays):
        conn.execute(
            """INSERT INTO plays(
                   ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                   platform, ms_played, track_id, spotify_track_id_at_play
               ) VALUES (?, 2026, 1, 1, 4, 0, '2026-01-01',
                         'fixture', 180000, ?, ?)""",
            (f"2026-01-01T00:{track_id:02d}:{offset:02d}Z", track_id, spotify_id),
        )


def test_l3_merges_supported_versions_and_expands_the_complete_l2_unit() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Song", plays=5)
        _track(conn, 2, "song - 2025版", plays=2)
        _track(conn, 3, "Song - Acoustic Version", plays=4)
        _track(conn, 4, "Song - Live at Wembley", plays=3)
        _track(conn, 5, "Song (Taylor's Version)", plays=2)

        l2 = apply_l2_track_merge_plan(conn, commit=False, bump_revision=False)
        assert l2["status"] == "applied"
        recording = conn.execute(
            """SELECT groups.group_id, GROUP_CONCAT(members.l1_id) AS members
                 FROM track_groups groups
                 JOIN track_group_l1_members members ON members.group_id=groups.group_id
                WHERE groups.scope='recording' AND groups.group_status='active'
                GROUP BY groups.group_id"""
        ).fetchone()
        assert set(str(recording["members"]).split(",")) == {"1", "2"}

        plan = build_l3_track_merge_plan(conn)

        assert plan["desired_group_count"] == 1
        assert plan["groups"][0]["member_l1_ids"] == [1, 2, 3, 4, 5]
        assert plan["groups"][0]["recording_group_ids"] == [int(recording["group_id"])]
        assert plan["groups"][0]["primary_l1_id"] == 1
        assert set(plan["groups"][0]["relation_tags"]) == {"acoustic", "live", "rerecord"}

        before_plays = [tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")]
        report = apply_l3_track_merge_plan(conn, plan, commit=True)

        assert report["status"] == "applied"
        composition = conn.execute(
            """SELECT group_id FROM track_groups
                WHERE scope='composition' AND group_status='active'"""
        ).fetchone()
        assert composition is not None
        assert {
            int(row[0])
            for row in conn.execute(
                "SELECT l1_id FROM track_group_l1_members WHERE group_id=?",
                (int(composition["group_id"]),),
            )
        } == {1, 2, 3, 4, 5}
        assert conn.execute(
            "SELECT parent_group_id FROM track_groups WHERE group_id=?",
            (int(recording["group_id"]),),
        ).fetchone()[0] == int(composition["group_id"])
        assert [tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")] == (
            before_plays
        )

        # The same semantic pair is an explicit L2 rejection and an L3
        # acceptance; neither decision overwrites the other scope.
        statuses = {
            str(row["scope"]): str(row["status"])
            for row in conn.execute(
                """SELECT scope, status FROM track_group_candidates
                    WHERE MIN(original_l1_id, candidate_l1_id)=1
                      AND MAX(original_l1_id, candidate_l1_id)=3"""
            )
        }
        assert statuses == {"recording": "rejected", "composition": "accepted"}

        second = apply_l3_track_merge_plan(conn, commit=True)
        assert second["status"] == "unchanged"
        assert second["revision_bumped"] is False
    finally:
        conn.close()


def test_duration_and_isrc_conflicts_are_l3_warnings_not_vetoes() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Long Song", isrc="AAA", duration_ms=120_000)
        _track(
            conn,
            2,
            "Long Song - Extended Mix",
            isrc="BBB",
            duration_ms=600_000,
        )

        plan = build_l3_track_merge_plan(conn)

        assert plan["groups"][0]["member_l1_ids"] == [1, 2]
        assert plan["warning_reason_counts"] == {
            "disjoint_isrc": 1,
            "strong_duration_conflict": 1,
        }
    finally:
        conn.close()


@pytest.mark.parametrize(
    "alternate",
    [
        "Intro - Live",
        "Song - Spanish Version",
        "Song - Cover Version",
        "Song - Mashup",
        "Song - Reprise",
    ],
)
def test_structural_and_unsafe_relations_never_auto_merge(alternate: str) -> None:
    conn = _connection()
    try:
        base = "Intro" if alternate.startswith("Intro") else "Song"
        _track(conn, 1, base)
        _track(conn, 2, alternate)

        plan = build_l3_track_merge_plan(conn)

        assert plan["groups"] == []
        assert any(
            edge["reason"] == "blocked_composition_relation" for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_collaboration_requires_a_shared_original_artist_across_the_component() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Duet", artist_ids=(1,))
        _track(conn, 2, "Duet (feat. Guest)", artist_ids=(1, 2))
        _track(conn, 3, "Duet (feat. Other)", artist_ids=(2, 3))

        plan = build_l3_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert any(
            edge["reason"] == "component_artist_intersection_empty"
            for edge in plan["blocked_edges"]
        )
    finally:
        conn.close()


def test_composition_force_separate_outweighs_automatic_relation() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Song")
        _track(conn, 2, "Song - Acoustic")
        conn.execute(
            """INSERT INTO track_merge_overrides(
                   scope, left_l1_id, right_l1_id, action, reason
               ) VALUES ('composition', 1, 2, 'force_separate', 'different works')"""
        )

        plan = build_l3_track_merge_plan(conn)

        assert plan["groups"] == []
        assert plan["force_separate_pairs"] == [[1, 2]]
        assert any(edge["reason"] == "force_separate" for edge in plan["blocked_edges"])
    finally:
        conn.close()
