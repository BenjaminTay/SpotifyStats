from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Generator

import pytest

from backend.core.migrations import migrate_030
from backend.domains.metadata.track_credits import (
    apply_track_credit_override,
    get_effective_track_credits,
    get_track_credit_state,
    list_active_track_credit_overrides,
    preview_track_credit_override,
    search_track_credit_artist_candidates,
    undo_track_credit_event,
)


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL,
            spotify_artist_id TEXT,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE albums (album_id INTEGER PRIMARY KEY, album_name TEXT, artist_id INTEGER);
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            UNIQUE(track_id, artist_id)
        );
        CREATE TABLE track_albums (track_id INTEGER, album_id INTEGER);
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            ts TEXT,
            ts_date TEXT,
            ms_played INTEGER
        );
        CREATE TABLE artist_identity_groups (
            identity_id INTEGER PRIMARY KEY,
            canonical_artist_id INTEGER NOT NULL,
            display_artist_id INTEGER,
            display_name TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE artist_identity_members (
            membership_id INTEGER PRIMARY KEY,
            identity_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            active INTEGER NOT NULL
        );
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        INSERT INTO artists VALUES
            (42, 'Elton John', NULL, NULL, NULL),
            (53, 'Britney Spears', NULL, NULL, NULL),
            (54, 'Britney Alias', NULL, NULL, NULL);
        INSERT INTO albums VALUES (80, 'Hold Me Closer', 42);
        INSERT INTO tracks VALUES
            (175, 'Hold Me Closer', 42, 80, '72yP0DUlWPyH8P7IoxskwN');
        INSERT INTO track_artists VALUES (175, 42, 'primary');
        INSERT INTO spotify_artist_meta VALUES ('26dSoYclwsYLMAKD3tpOr4', 'Britney Spears');
        INSERT INTO plays VALUES
            (1, 175, '2022-08-26T00:00:00Z', '2022-08-26', 202245),
            (2, 175, '2022-08-26T00:04:00Z', '2022-08-26', 202245);
        """
    )
    migrate_030(database)
    database.commit()
    yield database
    database.close()


def _facts_hash(conn: sqlite3.Connection) -> str:
    payload = []
    for table, order in (
        ("tracks", "track_id"),
        ("track_artists", "track_id, artist_id"),
        ("plays", "play_id"),
    ):
        payload.append(
            (table, [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order}")])
        )
    return hashlib.sha256(repr(payload).encode()).hexdigest()


def _add_britney(conn: sqlite3.Connection, revision: int = 0) -> dict:
    return apply_track_credit_override(
        conn,
        track_id=175,
        artist_id=53,
        action="add",
        role="featured",
        evidence_type="spotify_track_credit",
        evidence_source="spotify:track:72yP0DUlWPyH8P7IoxskwN",
        reason="Spotify 正式曲目署名确认",
        expected_revision=revision,
        idempotency_key=f"hold-me-closer-{revision:08d}",
    )


def test_manual_featured_credit_preserves_raw_facts_and_single_track_event(conn):
    before_hash = _facts_hash(conn)
    result = _add_britney(conn)

    credits = get_effective_track_credits(conn, [175])
    assert [(row["artist_id"], row["role"]) for row in credits] == [
        (42, "primary"),
        (53, "featured"),
    ]
    assert result["revision"] == 1
    changes = list_active_track_credit_overrides(conn)
    assert [(item["track_id"], item["artist_id"], item["event_id"]) for item in changes] == [
        (175, 53, result["event_id"])
    ]
    assert _facts_hash(conn) == before_hash
    assert conn.execute("SELECT COUNT(*) FROM plays WHERE track_id=175").fetchone()[0] == 2


def test_identity_alias_overlap_is_canonicalized_and_deduplicated(conn):
    conn.executescript(
        """
        INSERT INTO artist_identity_groups VALUES (1, 53, 53, 'Britney Spears', 'active');
        INSERT INTO artist_identity_members VALUES (1, 1, 53, 1);
        INSERT INTO artist_identity_members VALUES (2, 1, 54, 1);
        """
    )
    _add_britney(conn)
    with pytest.raises(ValueError, match="canonical artist identity"):
        apply_track_credit_override(
            conn,
            track_id=175,
            artist_id=54,
            action="add",
            role="featured",
            evidence_type="user_confirmed",
            evidence_source=None,
            reason="alias overlap",
            expected_revision=1,
            idempotency_key="alias-overlap-0001",
        )
    credits = get_effective_track_credits(conn, [175])
    assert [row["artist_id"] for row in credits].count(53) == 1


def test_remove_and_undo_restore_prior_effective_state(conn):
    created = _add_britney(conn)
    removed = apply_track_credit_override(
        conn,
        track_id=175,
        artist_id=53,
        action="remove",
        role=None,
        evidence_type="user_confirmed",
        evidence_source=None,
        reason="临时移除验证",
        expected_revision=1,
        idempotency_key="remove-credit-0001",
    )
    assert [row["artist_id"] for row in get_effective_track_credits(conn, [175])] == [42]

    undone = undo_track_credit_event(
        conn,
        event_id=removed["event_id"],
        expected_revision=2,
        idempotency_key="undo-remove-00001",
        reason="撤销错误移除",
    )
    assert undone["revision"] == 3
    assert [row["artist_id"] for row in get_effective_track_credits(conn, [175])] == [42, 53]
    assert created["event_id"] != undone["event_id"]


def test_preview_reports_fanout_without_inflating_track_plays(conn):
    preview = preview_track_credit_override(
        conn,
        track_id=175,
        artist_id=53,
        action="add",
        role="featured",
    )
    assert preview["impact"]["artist_fanout_delta"] == 1
    assert preview["impact"]["single_track_play_delta"] == 0
    assert preview["impact"]["raw_play_count"] == 2
    assert preview["blocked"] is False
    assert get_track_credit_state(conn)["current_revision"] == 0


def test_candidate_surfaces_unique_provider_metadata_as_unverified_evidence(conn):
    candidate = next(
        item
        for item in search_track_credit_artist_candidates(conn, "Britney", 20)
        if item["artist_id"] == 53
    )
    assert candidate["external_ids"] == [
        {
            "provider": "spotify",
            "external_id": "26dSoYclwsYLMAKD3tpOr4",
            "evidence_type": "provider_metadata_name_match",
            "confidence": 0.8,
            "verified": 0,
        }
    ]
