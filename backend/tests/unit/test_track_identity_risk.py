from __future__ import annotations

import sqlite3

import pytest

from backend.domains.metadata.track_identity_risk import (
    L1IdentitySplitPlanError,
    apply_split_plan,
    build_l1_external_identity_risk_plan,
    simulate_split_plan,
)

pytestmark = pytest.mark.unit


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            track_id INTEGER,
            spotify_track_id_at_play TEXT,
            content_type TEXT,
            ms_played INTEGER NOT NULL
        );
        CREATE TABLE track_l1_identities(
            l1_id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'local',
            external_track_id TEXT,
            fallback_track_id INTEGER,
            identity_status TEXT NOT NULL DEFAULT 'active',
            representative_track_id INTEGER,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE track_l1_external_ids(
            provider TEXT NOT NULL,
            external_track_id TEXT NOT NULL,
            l1_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'provider_observed',
            is_primary INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(provider, external_track_id)
        );
        CREATE TABLE spotify_track_owners(
            spotify_track_id TEXT PRIMARY KEY,
            track_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'import_match',
            updated_at TEXT DEFAULT (datetime('now'))
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
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE spotify_track_meta(
            spotify_track_id TEXT PRIMARY KEY,
            track_name TEXT NOT NULL,
            duration_ms INTEGER,
            popularity INTEGER,
            explicit INTEGER,
            track_number INTEGER,
            disc_number INTEGER,
            isrc TEXT,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_name TEXT NOT NULL,
            album_type TEXT,
            release_date TEXT
        );

        INSERT INTO artists VALUES (1, 'Artist');
        INSERT INTO track_identity_state VALUES (1, 7, 'spotify_owner_track_v1', datetime('now'));

        INSERT INTO tracks VALUES (1, 'Song', 1, 'base-id');
        INSERT INTO tracks VALUES (2, 'Song - 2018 Remastered', 1, 'remaster-id');
        INSERT INTO tracks VALUES (3, 'Stable', 1, 'stable-a');
        INSERT INTO tracks VALUES (4, 'Stable', 1, 'stable-b');
        INSERT INTO tracks VALUES (5, 'Uncertain', 1, 'uncertain-a');
        INSERT INTO tracks VALUES (6, 'Uncertain', 1, 'uncertain-b');
        INSERT INTO tracks VALUES (7, 'Video Song', 1, 'video-a');
        INSERT INTO tracks VALUES (8, 'Video Song', 1, 'video-b');

        INSERT INTO track_l1_identities(l1_id, fallback_track_id, representative_track_id)
        VALUES (1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4),
               (5, 5, 5), (6, 6, 6), (7, 7, 7), (8, 8, 8);

        INSERT INTO track_l1_external_ids(provider, external_track_id, l1_id, is_primary)
        VALUES ('spotify', 'base-id', 1, 1), ('spotify', 'remaster-id', 1, 0),
               ('spotify', 'stable-a', 3, 1), ('spotify', 'stable-b', 3, 0),
               ('spotify', 'uncertain-a', 5, 1), ('spotify', 'uncertain-b', 5, 0),
               ('spotify', 'video-a', 7, 1), ('spotify', 'video-b', 7, 0);
        INSERT INTO spotify_track_owners(spotify_track_id, track_id)
        VALUES ('base-id', 1), ('remaster-id', 1),
               ('stable-a', 3), ('stable-b', 3),
               ('uncertain-a', 5), ('uncertain-b', 5),
               ('video-a', 7), ('video-b', 7);
        INSERT INTO track_l1_source_links(l1_id, track_id, evidence_type)
        VALUES (1, 1, 'track_projection'), (1, 2, 'track_projection'),
               (3, 3, 'track_projection'), (3, 4, 'track_projection'),
               (5, 5, 'track_projection'), (5, 6, 'track_projection'),
               (7, 7, 'track_projection'), (7, 8, 'track_projection');

        INSERT INTO spotify_track_meta(
            spotify_track_id, track_name, duration_ms, explicit, isrc, spotify_album_id
        ) VALUES
            ('base-id', 'Song', 100000, 0, 'ISRC-BASE', 'album-a'),
            ('remaster-id', 'Song - 2018 Remastered', 115000, 0, 'ISRC-REMASTER', 'album-b'),
            ('stable-a', 'Stable', 200000, 0, 'ISRC-STABLE', 'album-a'),
            ('stable-b', 'Stable', 200900, 0, 'ISRC-STABLE', 'album-b'),
            ('uncertain-a', 'Uncertain', 180000, 0, 'ISRC-A', 'album-a'),
            ('uncertain-b', 'Uncertain', 186000, 0, 'ISRC-B', 'album-b'),
            ('video-a', 'Video Song', 210000, 0, 'ISRC-VIDEO', 'album-a'),
            ('video-b', 'Video Song', 210000, 0, 'ISRC-VIDEO', 'album-b');
        INSERT INTO spotify_album_meta VALUES
            ('album-a', 'Album', 'album', '2020-01-01'),
            ('album-b', 'Album (Deluxe)', 'album', '2021-01-01');

        INSERT INTO plays VALUES
            (1, '2026-01-01', 1, 'base-id', 'audio', 100000),
            (2, '2026-01-02', 1, 'base-id', 'audio', 100000),
            (3, '2026-01-03', 2, 'remaster-id', 'audio', 115000),
            (4, '2026-01-04', 7, 'video-a', 'audio', 210000),
            (5, '2026-01-05', 8, 'video-b', 'video', 210000);
        """
    )
    conn.commit()
    return conn


def _owner(plan: dict, l1_id: int) -> dict:
    return next(item for item in plan["owners"] if item["l1_id"] == l1_id)


def test_audit_classifies_keep_split_and_review_without_writes() -> None:
    conn = _database()
    before_changes = conn.total_changes

    plan = build_l1_external_identity_risk_plan(conn)

    assert plan["status"] == "ready"
    assert conn.total_changes == before_changes
    assert _owner(plan, 1)["recommendation"] == "split"
    assert _owner(plan, 3)["recommendation"] == "keep"
    assert _owner(plan, 5)["recommendation"] == "review"
    assert _owner(plan, 7)["recommendation"] == "review"
    assert plan["summary"] == {
        "multi_spotify_id_l1_count": 4,
        "reported_l1_count": 4,
        "keep_l1_count": 1,
        "split_l1_count": 1,
        "review_l1_count": 2,
        "auto_split_operation_count": 1,
        "multiple_isrc_l1_count": 2,
        "duration_conflict_l1_count": 1,
        "version_conflict_l1_count": 1,
        "video_conflict_l1_count": 1,
    }
    operation = plan["operations"][0]
    assert operation["source_l1_id"] == 1
    assert operation["target_l1_id"] == 2
    assert operation["external_track_id"] == "remaster-id"


def test_batch_apply_requires_transaction_and_preserves_raw_plays() -> None:
    conn = _database()
    plan = build_l1_external_identity_risk_plan(conn)
    before_plays = conn.execute("SELECT * FROM plays ORDER BY play_id").fetchall()

    with pytest.raises(L1IdentitySplitPlanError, match="begin a transaction"):
        apply_split_plan(conn, plan["confirmation_token"])

    conn.execute("BEGIN")
    result = apply_split_plan(conn, plan["confirmation_token"])

    assert result["status"] == "applied_uncommitted"
    assert result["operation_count"] == 1
    assert result["raw_plays_preserved"] is True
    assert (
        conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='remaster-id'"
        ).fetchone()[0]
        == 2
    )
    assert (
        conn.execute(
            "SELECT l1_id FROM track_l1_external_ids WHERE external_track_id='remaster-id'"
        ).fetchone()[0]
        == 2
    )
    assert conn.execute("SELECT * FROM plays ORDER BY play_id").fetchall() == before_plays
    assert (
        conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()[0]
        == 8
    )
    conn.rollback()

    assert (
        conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='remaster-id'"
        ).fetchone()[0]
        == 1
    )


def test_simulation_uses_memory_copy_and_rejects_stale_token() -> None:
    conn = _database()
    plan = build_l1_external_identity_risk_plan(conn)
    before_changes = conn.total_changes

    simulation = simulate_split_plan(conn, plan["confirmation_token"])

    assert simulation["status"] == "pass"
    assert simulation["simulated_operation_count"] == 1
    assert simulation["simulated_target_l1_ids"] == [2]
    assert conn.total_changes == before_changes
    assert (
        conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='remaster-id'"
        ).fetchone()[0]
        == 1
    )

    conn.execute(
        "UPDATE track_identity_state SET current_revision=current_revision+1 WHERE state_id=1"
    )
    conn.commit()
    with pytest.raises(ValueError, match="stale or invalid"):
        simulate_split_plan(conn, plan["confirmation_token"])


def test_missing_unique_existing_target_blocks_automatic_split() -> None:
    conn = _database()
    conn.execute("DELETE FROM track_l1_identities WHERE l1_id=2")
    conn.commit()

    plan = build_l1_external_identity_risk_plan(conn)

    owner = _owner(plan, 1)
    remaster = next(
        item for item in owner["external_ids"] if item["spotify_track_id"] == "remaster-id"
    )
    assert owner["recommendation"] == "review"
    assert remaster["recommendation"] == "review"
    assert remaster["blockers"] == ["missing_unique_existing_target_l1"]
    assert plan["operations"] == []
