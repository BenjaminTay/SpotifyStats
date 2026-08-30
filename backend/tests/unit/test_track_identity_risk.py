from __future__ import annotations

import sqlite3

import pytest

from backend.domains.metadata.track_identity import (
    refresh_play_source_links,
    synchronize_track_identity_projection,
)
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
        CREATE TABLE track_artists(
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY(track_id, artist_id, role)
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
        INSERT INTO track_artists
        SELECT track_id, artist_id, 'primary' FROM tracks;

        INSERT INTO track_l1_identities(l1_id, fallback_track_id, representative_track_id)
        VALUES (1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4),
               (5, 5, 5), (6, 6, 6), (7, 7, 7), (8, 8, 8);
        UPDATE track_l1_identities SET identity_status='superseded' WHERE l1_id IN (4, 6);

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


def _add_governance_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE track_groups(
            group_id INTEGER PRIMARY KEY,
            scope TEXT NOT NULL,
            group_status TEXT NOT NULL,
            primary_l1_id INTEGER
        );
        CREATE TABLE track_group_l1_members(
            group_id INTEGER NOT NULL,
            l1_id INTEGER NOT NULL,
            PRIMARY KEY(group_id, l1_id)
        );
        CREATE TABLE track_group_candidates(
            candidate_id INTEGER PRIMARY KEY,
            original_l1_id INTEGER NOT NULL,
            candidate_l1_id INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        """
    )


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
        "existing_target_split_operation_count": 1,
        "created_target_split_operation_count": 0,
        "shadow_identity_candidate_count": 0,
        "auto_supersede_operation_count": 0,
        "blocked_shadow_identity_count": 0,
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
    before_tracks = conn.execute("SELECT * FROM tracks ORDER BY track_id").fetchall()
    before_track_artists = conn.execute(
        "SELECT * FROM track_artists ORDER BY track_id, artist_id, role"
    ).fetchall()

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
    assert conn.execute("SELECT * FROM tracks ORDER BY track_id").fetchall() == before_tracks
    assert (
        conn.execute("SELECT * FROM track_artists ORDER BY track_id, artist_id, role").fetchall()
        == before_track_artists
    )
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


def test_simulation_accepts_preexisting_health_debt_when_plan_does_not_worsen_it() -> None:
    conn = _database()
    conn.execute("UPDATE track_l1_identities SET representative_track_id=NULL WHERE l1_id=8")
    conn.commit()
    plan = build_l1_external_identity_risk_plan(conn)

    simulation = simulate_split_plan(conn, plan["confirmation_token"])

    assert simulation["status"] == "pass"
    assert simulation["preexisting_identity_health"]["representative_missing_count"] == 1
    assert simulation["identity_health"]["representative_missing_count"] == 0
    assert simulation["health_regressions"] == {}


def test_apply_can_defer_revision_bump_to_outer_governance_transaction() -> None:
    conn = _database()
    plan = build_l1_external_identity_risk_plan(conn)

    conn.execute("BEGIN")
    result = apply_split_plan(
        conn,
        plan["confirmation_token"],
        bump_revision=False,
    )

    assert result["semantic_changed"] is True
    assert result["revision_bumped"] is False
    assert (
        conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()[0]
        == 7
    )
    conn.rollback()


def test_missing_identity_is_created_for_one_distinct_existing_track() -> None:
    conn = _database()
    conn.execute("DELETE FROM track_l1_identities WHERE l1_id=2")
    conn.commit()

    plan = build_l1_external_identity_risk_plan(conn)

    owner = _owner(plan, 1)
    remaster = next(
        item for item in owner["external_ids"] if item["spotify_track_id"] == "remaster-id"
    )
    assert owner["recommendation"] == "split"
    assert remaster["recommendation"] == "split"
    assert remaster["creation_target_track_ids"] == [2]
    assert plan["operations"][0]["operation"] == "create_provider_l1_and_reassign"

    before_tracks = conn.execute("SELECT * FROM tracks ORDER BY track_id").fetchall()
    conn.execute("BEGIN")
    result = apply_split_plan(conn, plan["confirmation_token"])
    conn.commit()

    assert result["created_target_l1_ids"] == [2]
    assert (
        conn.execute("SELECT identity_status FROM track_l1_identities WHERE l1_id=2").fetchone()[0]
        == "active"
    )
    assert (
        conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='remaster-id'"
        ).fetchone()[0]
        == 2
    )
    assert conn.execute("SELECT * FROM tracks ORDER BY track_id").fetchall() == before_tracks
    assert build_l1_external_identity_risk_plan(conn)["operations"] == []


def test_shared_isrc_duration_and_semantics_find_existing_owner_without_projection() -> None:
    conn = _database()
    conn.executescript(
        """
        DELETE FROM track_l1_identities WHERE l1_id=2;
        UPDATE tracks SET spotify_track_id=NULL WHERE track_id=2;
        UPDATE plays SET track_id=1 WHERE spotify_track_id_at_play='remaster-id';
        INSERT INTO tracks VALUES (9, 'Song - 2018 Remastered', 1, 'target-id');
        INSERT INTO track_l1_identities(l1_id, fallback_track_id, representative_track_id)
        VALUES (9, 9, 9);
        INSERT INTO track_l1_external_ids(provider, external_track_id, l1_id, is_primary)
        VALUES ('spotify', 'target-id', 9, 1);
        INSERT INTO spotify_track_owners(spotify_track_id, track_id)
        VALUES ('target-id', 9);
        INSERT INTO track_l1_source_links(l1_id, track_id, evidence_type)
        VALUES (9, 9, 'track_projection');
        INSERT INTO spotify_track_meta(
            spotify_track_id, track_name, duration_ms, explicit, isrc, spotify_album_id
        ) VALUES ('target-id', 'Song - 2018 Remastered', 114500, 0, 'ISRC-REMASTER', 'album-b');
        """
    )
    conn.commit()

    plan = build_l1_external_identity_risk_plan(conn)
    remaster = next(
        item
        for item in _owner(plan, 1)["external_ids"]
        if item["spotify_track_id"] == "remaster-id"
    )

    assert remaster["eligible_target_l1_ids"] == [9]
    assert remaster["target_resolution"] == "shared_isrc_duration_semantics"
    assert remaster["recommendation"] == "split"
    operation = next(
        item for item in plan["operations"] if item.get("external_track_id") == "remaster-id"
    )
    assert operation["operation"] == "reassign_external_identity"
    assert operation["target_l1_id"] == 9


def test_strong_conflict_without_distinct_track_owner_remains_explicitly_blocked() -> None:
    conn = _database()
    conn.executescript(
        """
        DELETE FROM track_l1_identities WHERE l1_id=2;
        UPDATE tracks SET spotify_track_id=NULL WHERE track_id=2;
        UPDATE plays SET track_id=1 WHERE spotify_track_id_at_play='remaster-id';
        """
    )
    conn.commit()

    plan = build_l1_external_identity_risk_plan(conn)
    remaster = next(
        item
        for item in _owner(plan, 1)["external_ids"]
        if item["spotify_track_id"] == "remaster-id"
    )

    assert remaster["recommendation"] == "review"
    assert remaster["creation_target_track_ids"] == []
    assert "provider_identity_requires_distinct_track_owner" in remaster["blockers"]
    assert not any(item.get("external_track_id") == "remaster-id" for item in plan["operations"])


def test_zero_evidence_projection_shadow_is_superseded_and_stays_superseded() -> None:
    conn = _database()
    conn.executescript(
        """
        INSERT INTO tracks VALUES (9, 'Song', 1, 'base-id');
        INSERT INTO track_l1_identities(l1_id, fallback_track_id, representative_track_id)
        VALUES (9, 9, 9);
        INSERT INTO track_l1_source_links(l1_id, track_id, evidence_type)
        VALUES (1, 9, 'track_projection'), (9, 9, 'track_projection');
        """
    )
    conn.commit()

    plan = build_l1_external_identity_risk_plan(conn)
    shadow = next(item for item in plan["shadow_identities"] if item["l1_id"] == 9)
    assert shadow == {
        "l1_id": 9,
        "track_id": 9,
        "target_l1_ids": [1],
        "recommendation": "supersede",
        "blockers": [],
    }

    before_tracks = conn.execute("SELECT * FROM tracks ORDER BY track_id").fetchall()
    conn.execute("BEGIN")
    result = apply_split_plan(conn, plan["confirmation_token"])
    conn.commit()
    assert result["superseded_shadow_l1_ids"] == [9]
    assert (
        conn.execute("SELECT identity_status FROM track_l1_identities WHERE l1_id=9").fetchone()[0]
        == "superseded"
    )
    assert conn.execute("SELECT * FROM tracks ORDER BY track_id").fetchall() == before_tracks

    refresh_play_source_links(conn)
    assert (
        conn.execute("SELECT identity_status FROM track_l1_identities WHERE l1_id=9").fetchone()[0]
        == "superseded"
    )
    synchronize_track_identity_projection(conn)
    assert (
        conn.execute("SELECT identity_status FROM track_l1_identities WHERE l1_id=9").fetchone()[0]
        == "superseded"
    )
    assert build_l1_external_identity_risk_plan(conn)["operations"] == []


def test_historical_group_and_rejected_candidate_do_not_block_shadow_cleanup() -> None:
    conn = _database()
    _add_governance_tables(conn)
    conn.executescript(
        """
        INSERT INTO tracks VALUES
            (9, 'Song', 1, 'base-id'),
            (10, 'Song', 1, 'base-id'),
            (11, 'Song', 1, 'base-id'),
            (12, 'Song', 1, 'base-id');
        INSERT INTO track_artists VALUES
            (9, 1, 'primary'), (10, 1, 'primary'),
            (11, 1, 'primary'), (12, 1, 'primary');
        INSERT INTO track_l1_identities(l1_id, fallback_track_id, representative_track_id)
        VALUES (9, 9, 9), (10, 10, 10), (11, 11, 11), (12, 12, 12);
        INSERT INTO track_l1_source_links(l1_id, track_id, evidence_type) VALUES
            (1, 9, 'track_projection'), (9, 9, 'track_projection'),
            (1, 10, 'track_projection'), (10, 10, 'track_projection'),
            (1, 11, 'track_projection'), (11, 11, 'track_projection'),
            (1, 12, 'track_projection'), (12, 12, 'track_projection');
        INSERT INTO track_groups VALUES
            (1, 'recording', 'archived', 9),
            (2, 'recording', 'active', 10);
        INSERT INTO track_group_l1_members VALUES (1, 9), (2, 10);
        INSERT INTO track_group_candidates VALUES
            (1, 9, 1, 'rejected'),
            (2, 11, 1, 'pending'),
            (3, 12, 1, 'accepted');
        """
    )
    conn.commit()

    plan = build_l1_external_identity_risk_plan(conn)
    shadows = {item["l1_id"]: item for item in plan["shadow_identities"]}

    assert shadows[9]["recommendation"] == "supersede"
    assert shadows[9]["blockers"] == []
    assert shadows[10]["blockers"] == ["active_group_reference"]
    assert shadows[11]["blockers"] == ["unresolved_group_candidate_reference"]
    assert shadows[12]["blockers"] == ["unresolved_group_candidate_reference"]

    before_raw = {
        table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        for table in ("plays", "tracks", "track_artists")
    }
    conn.execute("BEGIN")
    result = apply_split_plan(conn, plan["confirmation_token"])
    conn.commit()

    assert 9 in result["superseded_shadow_l1_ids"]
    assert (
        conn.execute("SELECT identity_status FROM track_l1_identities WHERE l1_id=9").fetchone()[0]
        == "superseded"
    )
    assert (
        conn.execute("SELECT group_status FROM track_groups WHERE group_id=1").fetchone()[0]
        == "archived"
    )
    assert (
        conn.execute("SELECT 1 FROM track_group_l1_members WHERE group_id=1 AND l1_id=9").fetchone()
        is not None
    )
    assert (
        conn.execute("SELECT status FROM track_group_candidates WHERE candidate_id=1").fetchone()[0]
        == "rejected"
    )
    assert {
        table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        for table in ("plays", "tracks", "track_artists")
    } == before_raw
