from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.domains.metadata.track_identity import (
    TRACK_IDENTITY_POLICY_VERSION,
    ensure_l1_identities,
    ensure_spotify_track_owner,
    ensure_track_projection_identity,
    extract_spotify_track_id,
    get_track_identity_revision,
    is_valid_spotify_track_id,
    l1_ids_for_track,
    refresh_play_source_links,
    resolve_canonical_track_id,
    validate_track_identity_invariants,
)

pytestmark = pytest.mark.unit


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE albums(album_id INTEGER PRIMARY KEY, album_name TEXT NOT NULL);
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER,
            album_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            track_id INTEGER,
            spotify_track_id_at_play TEXT
        );
        CREATE TABLE track_l1_identities(
            l1_id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'local',
            external_track_id TEXT,
            fallback_track_id INTEGER,
            identity_status TEXT NOT NULL DEFAULT 'active',
            representative_track_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX idx_track_l1_local_identity
            ON track_l1_identities(fallback_track_id)
            WHERE fallback_track_id IS NOT NULL;
        CREATE TABLE track_l1_external_ids(
            provider TEXT NOT NULL,
            external_track_id TEXT NOT NULL,
            l1_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'provider_observed',
            is_primary INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT,
            last_seen_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(provider, external_track_id)
        );
        CREATE TABLE track_l1_source_links(
            l1_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL,
            observed_plays INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT,
            last_seen_at TEXT,
            PRIMARY KEY(l1_id, track_id, evidence_type)
        );
        CREATE TABLE track_identity_state(
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL,
            policy_version TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE track_identity_events(
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            survivor_l1_id INTEGER,
            affected_l1_ids TEXT NOT NULL,
            before_json TEXT NOT NULL,
            after_json TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO track_identity_state VALUES (1, 0, 'spotify_owner_track_v1', datetime('now'));
        """
    )


def test_spotify_identity_token_and_strict_health_validation() -> None:
    valid = "5DpQ7EYvM9aCG90luO9PQW"
    assert extract_spotify_track_id(f"spotify:track:{valid}") == valid
    assert is_valid_spotify_track_id(valid) is True
    assert is_valid_spotify_track_id("fixture-track") is False
    assert extract_spotify_track_id("  ") is None


def test_same_spotify_id_is_one_l1_across_raw_tracks() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.executemany(
        "INSERT INTO tracks VALUES (?, ?, ?, ?, ?)",
        [
            (1, "假如我们还爱着", 256, 10, "5DpQ7EYvM9aCG90luO9PQW"),
            (2, "假如我們還愛著", 1579, 11, "5DpQ7EYvM9aCG90luO9PQW"),
        ],
    )

    first = ensure_track_projection_identity(
        conn,
        track_id=1,
        spotify_track_id="5DpQ7EYvM9aCG90luO9PQW",
    )
    second = ensure_track_projection_identity(
        conn,
        track_id=2,
        spotify_track_id="5DpQ7EYvM9aCG90luO9PQW",
    )

    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM track_l1_identities").fetchone()[0] == 2
    assert (
        conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id=?",
            ("5DpQ7EYvM9aCG90luO9PQW",),
        ).fetchone()[0]
        == first
    )
    assert l1_ids_for_track(conn, 1) == [first]
    assert l1_ids_for_track(conn, 2) == [first]
    # Each newly observed source-to-L1 relationship is an auditable identity
    # change, even when both sources converge on the same Spotify identity.
    assert get_track_identity_revision(conn) == 2


def test_governance_reference_resolves_alias_but_preserves_existing_owner() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.executemany(
        "INSERT INTO tracks VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Owner A", 1, 10, "spotify-a"),
            (2, "Historical alias", 1, 10, "spotify-a"),
            # Its raw projection points at A, but play-time evidence proves
            # this row owns another Spotify id and must remain canonical.
            (3, "Owner B", 1, 10, "spotify-a"),
        ],
    )
    ensure_spotify_track_owner(conn, spotify_track_id="spotify-a", track_id=1)
    ensure_spotify_track_owner(conn, spotify_track_id="spotify-b", track_id=3)

    assert resolve_canonical_track_id(conn, 1) == 1
    assert resolve_canonical_track_id(conn, 2) == 1
    assert resolve_canonical_track_id(conn, 3) == 3
    assert resolve_canonical_track_id(conn, 999) is None


def test_one_track_can_own_multiple_spotify_ids() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.execute("INSERT INTO tracks VALUES (1, '純妹妹', 256, 10, 'spotify-a')")
    first = ensure_spotify_track_owner(conn, spotify_track_id="spotify-a", track_id=1)
    second = ensure_spotify_track_owner(conn, spotify_track_id="spotify-b", track_id=1)

    assert first == second == 1
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_owners").fetchone()[0] == 2


def test_compatibility_identity_never_creates_a_synthetic_id() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.execute("INSERT INTO tracks VALUES (7, 'Song', 1, 1, 'spotify-a')")
    first = ensure_l1_identities(conn, spotify_track_ids=("spotify-a",), canonical_l1_id=7)
    canonical_id = first["spotify:spotify-a"]

    second = ensure_l1_identities(
        conn,
        spotify_track_ids=("spotify-b",),
        canonical_l1_id=canonical_id,
        evidence_type="manual_confirmed",
    )

    assert second["spotify:spotify-b"] == canonical_id
    assert canonical_id == 7
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM track_l1_external_ids WHERE l1_id=?", (canonical_id,)
        ).fetchone()[0]
        == 2
    )


def test_identity_ensure_is_idempotent_and_revision_changes_only_on_insert() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.execute("INSERT INTO tracks VALUES (1, 'Song', 1, 1, 'spotify-a')")
    first = ensure_l1_identities(conn, spotify_track_ids=("spotify-a",))
    first_revision = get_track_identity_revision(conn)
    second = ensure_l1_identities(conn, spotify_track_ids=("spotify-a",))

    assert first == second
    assert first_revision == 1
    assert get_track_identity_revision(conn) == first_revision
    assert (
        conn.execute("SELECT policy_version FROM track_identity_state").fetchone()[0]
        == TRACK_IDENTITY_POLICY_VERSION
    )


def test_projection_refresh_is_idempotent_for_local_track() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.execute("INSERT INTO tracks VALUES (1, 'Local only', 1, 1, NULL)")
    canonical_id = ensure_track_projection_identity(conn, track_id=1, spotify_track_id=None)
    first_revision = get_track_identity_revision(conn)
    assert (
        conn.execute(
            "SELECT identity_status FROM track_l1_identities WHERE l1_id=?",
            (canonical_id,),
        ).fetchone()[0]
        == "active"
    )

    refresh_play_source_links(conn)
    assert get_track_identity_revision(conn) == first_revision


def test_new_play_evidence_updates_counts_without_changing_identity_revision() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.execute("INSERT INTO tracks VALUES (1, 'Song', 1, 1, 'spotify-a')")
    conn.execute("INSERT INTO plays VALUES (1, '2026-01-01T00:00:00Z', 1, 'spotify-a')")
    ensure_track_projection_identity(conn, track_id=1, spotify_track_id="spotify-a")
    refresh_play_source_links(conn)
    revision = get_track_identity_revision(conn)

    conn.execute("INSERT INTO plays VALUES (2, '2026-01-02T00:00:00Z', 1, 'spotify-a')")
    refresh_play_source_links(conn)

    assert get_track_identity_revision(conn) == revision
    assert (
        conn.execute(
            """SELECT observed_plays FROM track_l1_source_links
            WHERE l1_id=1 AND track_id=1 AND evidence_type='play_at_time'"""
        ).fetchone()[0]
        == 2
    )


def test_existing_spotify_owner_cannot_be_reassigned_by_later_projection() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.executemany(
        "INSERT INTO tracks VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Song", 1, 1, "spotify-a"),
            (2, "Song", 1, 2, "spotify-b"),
        ],
    )
    first = ensure_track_projection_identity(conn, track_id=1, spotify_track_id="spotify-a")
    later = ensure_track_projection_identity(conn, track_id=2, spotify_track_id="spotify-a")

    assert first == later == 1
    assert (
        conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='spotify-a'"
        ).fetchone()[0]
        == 1
    )


def test_identity_health_detects_missing_play_mapping() -> None:
    conn = sqlite3.connect(":memory:")
    _schema(conn)
    conn.execute("INSERT INTO tracks VALUES (1, 'Song', 1, 1, 'spotify-a')")
    conn.execute("INSERT INTO plays VALUES (1, '2026-01-01T00:00:00Z', 1, 'spotify-b')")
    ensure_track_projection_identity(conn, track_id=1, spotify_track_id="spotify-a")

    health = validate_track_identity_invariants(conn)
    assert health.unresolved_play_identity_count == 1
    assert health.healthy is False


def test_l1_artist_projection_is_not_corrupted_by_numeric_id_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.core import db as db_mod

    path = tmp_path / "identity-collision.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE track_artists(
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE track_l1_identities(
            l1_id INTEGER PRIMARY KEY,
            representative_track_id INTEGER
        );
        INSERT INTO artists VALUES (1, 'Source A'), (2, 'Artist B'), (3, 'Artist C');
        INSERT INTO tracks VALUES
            (1, 'Source A', 1),
            (5, 'Representative B', 2),
            (9, 'Representative C', 3);
        INSERT INTO track_artists VALUES (1, 1, 'primary'), (5, 2, 'primary'), (9, 3, 'primary');
        INSERT INTO track_l1_identities VALUES (5, 9), (9, 5);
        """
    )
    conn.close()

    monkeypatch.setattr(db_mod, "DB_PATH", str(path))
    db_mod.get_track_artist_names_map.cache_clear()
    try:
        projected = db_mod.get_track_artist_names_map()
        assert projected[5] == ["Artist C"]
        assert projected[9] == ["Artist B"]
        raw = db_mod.get_raw_track_artist_names_map()
        assert raw[5] == ["Artist B"]
        assert raw[9] == ["Artist C"]
    finally:
        db_mod.get_track_artist_names_map.cache_clear()


def test_l1_album_projection_is_not_corrupted_by_numeric_id_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.core import db as db_mod
    from backend.domains.billboard.data_loader import load_track_album_map

    path = tmp_path / "album-identity-collision.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE albums(album_id INTEGER PRIMARY KEY, album_name TEXT NOT NULL);
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            album_id INTEGER
        );
        CREATE TABLE track_albums(track_id INTEGER NOT NULL, album_id INTEGER NOT NULL);
        CREATE TABLE track_l1_source_links(
            l1_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL
        );
        INSERT INTO albums VALUES (1, 'Source Album A'), (2, 'Source Album B');
        INSERT INTO tracks VALUES (1, 1), (5, 2);
        INSERT INTO track_l1_source_links VALUES
            (5, 1, 'play_at_time'),
            (9, 5, 'play_at_time');
        """
    )
    conn.close()

    monkeypatch.setattr(db_mod, "DB_PATH", str(path))
    load_track_album_map.cache_clear()
    try:
        projected = load_track_album_map().set_index("track_id")["album_list"].to_dict()
        assert projected[5] == ["Source Album A"]
        assert projected[9] == ["Source Album B"]
    finally:
        load_track_album_map.cache_clear()
