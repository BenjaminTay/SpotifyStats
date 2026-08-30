from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.metadata.l2_track_auto_merge import (
    apply_l2_track_merge_plan,
    build_l2_track_merge_plan,
)
from backend.domains.metadata.track_title_identity import normalize_l2_track_title

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
    conn.execute("INSERT INTO albums(album_id, album_name, artist_id) VALUES (1, 'Album', 1)")
    return conn


def _track(conn: sqlite3.Connection, track_id: int, name: str, plays: int = 0) -> None:
    spotify_id = f"spotify-{track_id}"
    conn.execute(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, 1, 1, ?)""",
        (track_id, name, spotify_id),
    )
    conn.execute(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, 1, 'primary')",
        (track_id,),
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
           VALUES (?, ?, 180000, ?)""",
        (spotify_id, name, f"ISRC-{track_id}"),
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
            (f"2026-01-01T00:00:{track_id + offset:02d}Z", track_id, spotify_id),
        )


def test_title_normalizer_removes_packaging_but_preserves_recording_suffix() -> None:
    assert normalize_l2_track_title("純妹妹 - 2025版").key == ("纯妹妹", ())
    assert normalize_l2_track_title("Song - 2018 Remastered").key == ("song", ())
    assert normalize_l2_track_title("Song (Explicit)").key == ("song", ())
    assert normalize_l2_track_title("Yoü And I").key != normalize_l2_track_title("You And I").key
    assert normalize_l2_track_title("Running Up That Hill (A Deal With God)").key == (
        "running up that hill a deal with god",
        (),
    )
    assert (
        normalize_l2_track_title("Song - Kungs Remix").key
        != normalize_l2_track_title("Song - ILLENIUM Remix").key
    )
    assert (
        normalize_l2_track_title("Song (feat. A)").key
        != normalize_l2_track_title("Song (feat. B)").key
    )


def test_same_artist_and_normalized_title_merge_while_semantic_versions_stay_separate() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "純妹妹", plays=1)
        _track(conn, 2, "纯妹妹 - 2025版", plays=2)
        _track(conn, 3, "Song", plays=1)
        _track(conn, 4, "Song - Kungs Remix", plays=1)
        _track(conn, 5, "Song - ILLENIUM Remix", plays=1)

        plan = build_l2_track_merge_plan(conn)

        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 2]]
        assert plan["groups"][0]["primary_l1_id"] == 2
        assert plan["groups"][0]["evidence_types"] == ["canonical_artist_normalized_title"]
    finally:
        conn.close()


def test_force_separate_outweighs_auto_merge_and_apply_is_idempotent() -> None:
    conn = _connection()
    try:
        _track(conn, 1, "Same", plays=1)
        _track(conn, 2, "same", plays=2)
        _track(conn, 3, "SAME", plays=3)
        conn.execute(
            """INSERT INTO track_merge_overrides(
                   scope, left_l1_id, right_l1_id, action, reason
               ) VALUES ('recording', 1, 2, 'force_separate', 'known exception')"""
        )
        conn.commit()
        before_plays = [tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")]
        before_revision = conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()[0]

        plan = build_l2_track_merge_plan(conn)
        assert [group["member_l1_ids"] for group in plan["groups"]] == [[1, 3]]
        assert any(edge["reason"] == "force_separate" for edge in plan["blocked_edges"])

        report = apply_l2_track_merge_plan(conn, plan, commit=True)
        assert report["status"] == "applied"
        assert report["track_identity_revision"] == before_revision + 1
        group = conn.execute(
            """SELECT automatic_artist_id, automatic_title_key,
                      automatic_version_tag, identity_policy_version
                 FROM track_groups WHERE group_status='active'"""
        ).fetchone()
        assert tuple(group) == (1, "same", "", plan["policy_version"])
        assert [
            tuple(row) for row in conn.execute("SELECT * FROM plays ORDER BY play_id")
        ] == before_plays

        second = apply_l2_track_merge_plan(conn, commit=True)
        assert second["status"] == "unchanged"
        assert second["track_identity_revision"] == before_revision + 1
    finally:
        conn.close()
