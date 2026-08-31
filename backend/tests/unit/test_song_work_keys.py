from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.domains.playback.song_work_keys import (
    L3SongWorkConflictError,
    apply_l3_song_work_keys,
    load_l3_song_work_keys,
    resolve_l3_song_work_key,
)

pytestmark = pytest.mark.unit


def _modern_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL
        );
        CREATE TABLE track_l1_identities (
            l1_id INTEGER PRIMARY KEY,
            fallback_track_id INTEGER,
            identity_status TEXT NOT NULL,
            representative_track_id INTEGER
        );
        CREATE TABLE track_l1_source_links (
            l1_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL
        );
        CREATE TABLE track_identity_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            primary_track_id INTEGER,
            primary_l1_id INTEGER,
            scope TEXT NOT NULL,
            parent_group_id INTEGER,
            group_status TEXT NOT NULL
        );
        CREATE TABLE track_group_l1_members (
            group_id INTEGER NOT NULL,
            l1_id INTEGER NOT NULL
        );

        INSERT INTO tracks VALUES
            (101, 'Direct Member'),
            (102, 'Direct Wins'),
            (103, 'Parent Representative'),
            (104, 'Parent Child Version'),
            (105, '天黑黑'),
            (106, '天黑黑 Remastered'),
            (107, 'Singleton Song');
        INSERT INTO track_l1_identities VALUES
            (1, 101, 'active', 101),
            (2, 102, 'active', 102),
            (3, 103, 'active', 103),
            (4, 104, 'active', 104),
            (5, 105, 'active', 105),
            (6, 106, 'active', 106),
            (7, 107, 'active', 107);
        INSERT INTO track_l1_source_links VALUES
            (1, 101), (2, 102), (3, 103), (4, 104),
            (5, 105), (6, 106), (7, 107);
        INSERT INTO track_identity_state VALUES (1, 42);

        INSERT INTO track_groups VALUES
            (20, 'Other Recording', 102, 2, 'recording', 200, 'active'),
            (21, 'Parent Child Recording', 104, 4, 'recording', 200, 'active'),
            (200, 'Parent Composition', 103, 3, 'composition', NULL, 'active'),
            (201, 'Direct Composition', 102, 2, 'composition', NULL, 'active'),
            (5914, '天黑黑', 105, 5, 'recording', NULL, 'active'),
            (9999, 'Archived Composition', 107, 7, 'composition', NULL, 'archived');
        INSERT INTO track_group_l1_members VALUES
            (20, 2),
            (21, 4),
            (200, 3),
            (201, 2),
            (5914, 5), (5914, 6),
            (9999, 7);
        """
    )
    return conn


def test_resolution_priority_and_representative_metadata() -> None:
    conn = _modern_connection()
    try:
        rows = load_l3_song_work_keys(conn).set_index("l1_id")
    finally:
        conn.close()

    # A direct composition wins over a different recording parent.
    assert rows.loc[2, "canonical_song_key"] == "composition:201"
    assert rows.loc[2, "canonical_song_name"] == "Direct Composition"
    assert rows.loc[2, "representative_l1_id"] == 2
    assert rows.loc[2, "representative_track_id"] == 102
    assert rows.loc[2, "track_group_scope"] == "composition"

    # With no direct composition, the active recording parent is selected.
    assert rows.loc[4, "canonical_song_key"] == "composition:200"
    assert rows.loc[4, "canonical_song_name"] == "Parent Composition"
    assert rows.loc[4, "representative_l1_id"] == 3
    assert rows.loc[4, "representative_track_id"] == 103
    assert rows.loc[4, "track_group_scope"] == "composition"
    assert rows.loc[4, "recording_group_id"] == 21
    assert rows.loc[4, "track_identity_revision"] == 42

    # An archived group does not replace the singleton owner.
    assert rows.loc[7, "canonical_song_key"] == "l1:7"
    assert rows.loc[7, "canonical_song_name"] == "Singleton Song"
    assert rows.loc[7, "representative_track_id"] == 107
    assert rows.loc[7, "track_group_scope"] == "l1"


def test_recording_group_is_l3_fallback_for_tian_hei_hei_shape() -> None:
    conn = _modern_connection()
    try:
        rows = load_l3_song_work_keys(conn).set_index("l1_id")
        resolved = resolve_l3_song_work_key(conn, 6)
    finally:
        conn.close()

    assert rows.loc[5, "canonical_song_key"] == "recording:5914"
    assert rows.loc[6, "canonical_song_key"] == "recording:5914"
    assert rows.loc[6, "canonical_song_name"] == "天黑黑"
    assert rows.loc[6, "representative_l1_id"] == 5
    assert rows.loc[6, "representative_track_id"] == 105
    assert rows.loc[6, "track_group_scope"] == "recording"
    assert resolved == "recording:5914"


@pytest.mark.parametrize("scope", ["composition", "recording"])
def test_multiple_active_groups_at_one_scope_fail_closed(scope: str) -> None:
    conn = _modern_connection()
    try:
        group_id = 202 if scope == "composition" else 22
        conn.execute(
            """INSERT INTO track_groups VALUES
               (?, 'Conflicting Group', 102, 2, ?, NULL, 'active')""",
            (group_id, scope),
        )
        conn.execute("INSERT INTO track_group_l1_members VALUES (?, 2)", (group_id,))

        with pytest.raises(L3SongWorkConflictError) as error:
            load_l3_song_work_keys(conn)
    finally:
        conn.close()

    assert error.value.l1_id == 2
    assert error.value.scope == scope


def test_load_and_apply_are_idempotent() -> None:
    conn = _modern_connection()
    try:
        first_load = load_l3_song_work_keys(conn)
        second_load = load_l3_song_work_keys(conn)
        pd.testing.assert_frame_equal(first_load, second_load)

        source = pd.DataFrame(
            [
                {"track_id": 5, "track_name": "天黑黑"},
                {"track_id": 6, "track_name": "天黑黑 Remastered"},
                {"track_id": 7, "track_name": "Singleton Song"},
            ]
        )
        once = apply_l3_song_work_keys(source, conn)
        twice = apply_l3_song_work_keys(once, conn)
    finally:
        conn.close()

    pd.testing.assert_frame_equal(once, twice)
    assert once["canonical_song_key"].tolist() == [
        "recording:5914",
        "recording:5914",
        "l1:7",
    ]


def test_legacy_fixture_uses_stable_group_and_singleton_keys() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            primary_track_id INTEGER,
            scope TEXT NOT NULL,
            parent_group_id INTEGER
        );
        CREATE TABLE track_group_members (
            group_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL
        );
        INSERT INTO tracks VALUES
            (1, '天黑黑'), (2, '天黑黑 Remastered'), (3, 'Legacy Singleton');
        INSERT INTO track_groups VALUES
            (5914, '天黑黑', 1, 'recording', NULL);
        INSERT INTO track_group_members VALUES (5914, 1), (5914, 2);
        """
    )
    try:
        rows = load_l3_song_work_keys(conn).set_index("l1_id")
    finally:
        conn.close()

    assert rows.loc[1, "canonical_song_key"] == "recording:5914"
    assert rows.loc[2, "canonical_song_key"] == "recording:5914"
    assert rows.loc[2, "representative_track_id"] == 1
    assert rows.loc[2, "canonical_song_name"] == "天黑黑"
    assert rows.loc[3, "canonical_song_key"] == "l1:3"
    assert not any(str(value).startswith("legacy:") for value in rows["canonical_song_key"])
