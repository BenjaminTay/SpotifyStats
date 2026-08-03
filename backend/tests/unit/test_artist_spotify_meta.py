from __future__ import annotations

import sqlite3

from backend.core.migrations import migrate_028, migrate_029
from backend.domains.metadata.artist_identity import (
    get_identity_revision,
    list_artist_identity_groups,
    update_artist_identity_group,
)
from backend.domains.metadata.artist_spotify_meta import resolve_artist_spotify_meta


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL UNIQUE,
            spotify_artist_id TEXT,
            genres TEXT,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE artist_identity_aliases (
            alias_artist_id INTEGER PRIMARY KEY,
            canonical_artist_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            spotify_track_id TEXT
        );
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'primary'
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            ts_date TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO artists VALUES (?, ?, ?, ?, ?, ?)",
        [
            (532, "Jolin Tsai", None, None, None, None),
            (765, "JOLIN", None, None, None, None),
            (768, "JOLIN蔡依林", None, None, None, None),
            (900, "Third Member", None, None, None, None),
        ],
    )
    conn.execute(
        "INSERT INTO artist_identity_aliases VALUES (765, 532, 'verified', datetime('now'))"
    )
    conn.executemany(
        "INSERT INTO spotify_artist_meta VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("spotify-jolin", "JOLIN", 61, 1_239_003, '["mandopop"]', "jolin.jpg"),
            ("spotify-other", "JOLIN蔡依林", 7, 3_807, '["pop"]', "other.jpg"),
        ],
    )
    migrate_028(conn)
    migrate_029(conn)
    conn.commit()
    return conn


def test_alias_metadata_resolves_for_raw_canonical_and_custom_display_names():
    conn = _database()
    for name in ("Jolin Tsai", "JOLIN"):
        resolved = resolve_artist_spotify_meta(conn, name)
        assert resolved.source == "identity_member_name"
        assert resolved.metadata["spotify_artist_id"] == "spotify-jolin"
        assert resolved.metadata["popularity"] == 61
        assert resolved.metadata["followers"] == 1_239_003

    group = list_artist_identity_groups(conn)[0]
    result = update_artist_identity_group(
        conn,
        identity_id=group["identity_id"],
        add_ids=[900],
        remove_ids=[],
        canonical_artist_id=765,
        display_name="蔡依林 Jolin Tsai",
        expected_revision=get_identity_revision(conn),
        idempotency_key="metadata-custom-display",
        reason="verified identity",
    )
    assert result["revision"] > 1
    custom = resolve_artist_spotify_meta(conn, "蔡依林 Jolin Tsai")
    assert custom.metadata["spotify_artist_id"] == "spotify-jolin"
    assert custom.metadata["followers"] == 1_239_003


def test_verified_external_id_takes_priority_over_member_display_names():
    conn = _database()
    conn.execute(
        """INSERT INTO artist_identity_external_ids(
               artist_id, provider, external_id, evidence_type, confidence, verified
           ) VALUES (532, 'spotify', 'spotify-jolin', 'manual', 1.0, 1)"""
    )
    resolved = resolve_artist_spotify_meta(conn, "Jolin Tsai")
    assert resolved.source == "verified_external_id"
    assert resolved.metadata["artist_name"] == "JOLIN"


def test_multiple_provider_ids_are_diagnostic_conflict_and_never_arbitrary():
    conn = _database()
    group = list_artist_identity_groups(conn)[0]
    update_artist_identity_group(
        conn,
        identity_id=group["identity_id"],
        add_ids=[768],
        remove_ids=[],
        canonical_artist_id=532,
        display_name="Jolin Tsai",
        expected_revision=get_identity_revision(conn),
        idempotency_key="metadata-conflict-member",
        reason="conflict fixture",
        confirm_external_id_conflict=True,
    )
    resolved = resolve_artist_spotify_meta(conn, "Jolin Tsai")
    assert resolved.metadata is None
    assert resolved.has_conflict is True
    assert resolved.source == "identity_member_name"
    assert resolved.conflict_external_ids == ("spotify-jolin", "spotify-other")


def test_user_selected_provider_member_resolves_confirmed_identity_conflict():
    conn = _database()
    group = list_artist_identity_groups(conn)[0]
    update_artist_identity_group(
        conn,
        identity_id=group["identity_id"],
        add_ids=[768],
        remove_ids=[],
        canonical_artist_id=532,
        display_name="Jolin Tsai",
        provider_metadata_artist_id=765,
        expected_revision=get_identity_revision(conn),
        idempotency_key="metadata-selected-member",
        reason="user confirmed same artist despite different Spotify provider ids",
        confirm_external_id_conflict=True,
    )

    resolved = resolve_artist_spotify_meta(conn, "JOLIN蔡依林")
    assert resolved.source == "user_selected_provider_metadata"
    assert resolved.metadata["spotify_artist_id"] == "spotify-jolin"
    assert resolved.metadata["popularity"] == 61
    assert resolved.metadata["followers"] == 1_239_003
    assert resolved.conflict_external_ids == ("spotify-jolin", "spotify-other")


def test_independent_similar_artist_keeps_own_provider_metadata():
    conn = _database()
    resolved = resolve_artist_spotify_meta(conn, "JOLIN蔡依林")
    assert resolved.has_conflict is False
    assert resolved.metadata["spotify_artist_id"] == "spotify-other"
    assert resolved.metadata["popularity"] == 7
    assert resolved.metadata["followers"] == 3_807
