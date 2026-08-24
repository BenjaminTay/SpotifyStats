from __future__ import annotations

import hashlib
import json
import sqlite3

import pandas as pd
import pytest

from backend.api import artist_identity as artist_identity_api
from backend.core import db as db_mod
from backend.core.migrations import migrate_028, migrate_029
from backend.domains.metadata.artist_identity import (
    canonicalize_artist_frame,
    create_artist_identity_group,
    get_artist_identity_map,
    get_identity_revision,
    list_artist_identity_events,
    list_artist_identity_groups,
    preview_artist_identity_merge,
    undo_artist_identity_event,
    update_artist_identity_group,
)


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
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            spotify_track_id TEXT
        );
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'primary',
            UNIQUE(track_id, artist_id)
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            ts TEXT,
            ts_date TEXT,
            ms_played INTEGER
        );
        CREATE TABLE artist_identity_aliases (
            alias_artist_id INTEGER PRIMARY KEY,
            canonical_artist_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.executemany(
        """INSERT INTO artists(
               artist_id, artist_name, spotify_artist_id, genres, image_url
           ) VALUES (?, ?, ?, ?, ?)""",
        [
            (532, "Jolin Tsai", "spotify-jolin", '["mandopop"]', "jolin.jpg"),
            (765, "JOLIN", "spotify-jolin", '["mandopop"]', "jolin.jpg"),
            (768, "JOLIN蔡依林", "spotify-other", '["mandopop"]', None),
            (900, "Guest", "spotify-guest", '["pop"]', None),
        ],
    )
    conn.execute(
        """INSERT INTO artist_identity_aliases(alias_artist_id, canonical_artist_id, reason)
           VALUES (765, 532, 'confirmed legacy alias')"""
    )
    conn.executemany(
        "INSERT INTO tracks(track_id, track_name, artist_id, spotify_track_id) VALUES (?, ?, ?, ?)",
        [(1, "Shared", 532, "stable-shared"), (2, "Other", 768, "stable-other")],
    )
    conn.executemany(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, ?)",
        [(1, 532, "primary"), (1, 765, "featured"), (2, 768, "primary")],
    )
    conn.executemany(
        "INSERT INTO plays(play_id, track_id, ts, ts_date, ms_played) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "2026-01-01T00:00:00Z", "2026-01-01", 60_000),
            (2, 2, "2026-01-02T00:00:00Z", "2026-01-02", 60_000),
        ],
    )
    migrate_028(conn)
    migrate_029(conn)
    conn.commit()
    return conn


def _raw_hash(conn: sqlite3.Connection) -> str:
    payload = {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]
        for table in ("artists", "tracks", "track_artists", "plays")
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def test_migration_promotes_legacy_alias_without_auto_adding_similar_name():
    conn = _database()
    mapping = get_artist_identity_map(conn)

    assert mapping[765].canonical_artist_id == 532
    assert mapping[765].display_name == "Jolin Tsai"
    assert mapping[768].canonical_artist_id == 768
    assert get_identity_revision(conn) == 1


def test_fanout_deduplicates_alias_credit_for_same_play():
    conn = _database()
    frame = pd.DataFrame(
        [
            {"play_id": 1, "track_id": 1, "artist_id": 532, "artist_name": "Jolin Tsai"},
            {"play_id": 1, "track_id": 1, "artist_id": 765, "artist_name": "JOLIN"},
        ]
    )

    resolved = canonicalize_artist_frame(frame, conn)

    assert len(resolved) == 1
    assert resolved.iloc[0]["artist_id"] == 532
    assert resolved.iloc[0]["artist_name"] == "Jolin Tsai"
    assert resolved.iloc[0]["raw_artist_id"] in {532, 765}


def test_primary_credit_display_is_canonical_without_dropping_events():
    conn = _database()
    frame = pd.DataFrame(
        [
            {"play_id": 1, "artist_id": 532, "artist_name": "Jolin Tsai"},
            {"play_id": 2, "artist_id": 765, "artist_name": "JOLIN"},
        ]
    )

    resolved = canonicalize_artist_frame(frame, conn, dedupe=False)

    assert len(resolved) == 2
    assert set(resolved["artist_id"]) == {532}
    assert set(resolved["artist_name"]) == {"Jolin Tsai"}
    assert set(resolved["raw_artist_id"]) == {532, 765}


def test_effective_event_key_keeps_expanded_plays_while_deduplicating_aliases():
    conn = _database()
    frame = pd.DataFrame(
        [
            {"_artist_event_id": 0, "play_id": 1, "artist_id": 532, "artist_name": "Jolin Tsai"},
            {"_artist_event_id": 0, "play_id": 1, "artist_id": 765, "artist_name": "JOLIN"},
            {"_artist_event_id": 1, "play_id": 1, "artist_id": 532, "artist_name": "Jolin Tsai"},
            {"_artist_event_id": 1, "play_id": 1, "artist_id": 765, "artist_name": "JOLIN"},
        ]
    )

    resolved = canonicalize_artist_frame(frame, conn)

    assert len(resolved) == 2
    assert resolved["_artist_event_id"].tolist() == [0, 1]
    assert set(resolved["artist_id"]) == {532}


def test_three_member_change_display_remove_and_undo_preserves_raw_facts():
    conn = _database()
    before_hash = _raw_hash(conn)
    first_revision = get_identity_revision(conn)
    legacy_group = list_artist_identity_groups(conn)[0]

    merged = update_artist_identity_group(
        conn,
        identity_id=legacy_group["identity_id"],
        add_ids=[900],
        remove_ids=[],
        canonical_artist_id=532,
        display_name="蔡依林 Jolin Tsai",
        expected_revision=first_revision,
        idempotency_key="test-add-member-0001",
        reason="verified shared discography",
        confirm_external_id_conflict=True,
    )
    groups = list_artist_identity_groups(conn)
    assert {member["artist_id"] for member in groups[0]["members"]} == {532, 765, 900}
    assert groups[0]["display_name"] == "蔡依林 Jolin Tsai"

    removed = update_artist_identity_group(
        conn,
        identity_id=legacy_group["identity_id"],
        add_ids=[],
        remove_ids=[900],
        canonical_artist_id=765,
        display_name="JOLIN",
        expected_revision=merged["revision"],
        idempotency_key="test-remove-member-001",
        reason="undo mistaken member selection",
    )
    assert get_artist_identity_map(conn)[532].canonical_artist_id == 765

    undone = undo_artist_identity_event(
        conn,
        event_id=removed["event_id"],
        expected_revision=removed["revision"],
        idempotency_key="test-undo-event-00001",
        reason="restore prior group",
    )
    restored = list_artist_identity_groups(conn)[0]
    assert {member["artist_id"] for member in restored["members"]} == {532, 765, 900}
    assert restored["display_name"] == "蔡依林 Jolin Tsai"
    assert undone["revision"] == first_revision + 3
    assert [event["action"] for event in list_artist_identity_events(conn)[:3]] == [
        "undo",
        "update",
        "update",
    ]
    assert _raw_hash(conn) == before_hash


def test_verified_external_id_conflict_is_blocked_without_explicit_confirmation():
    conn = _database()
    preview = preview_artist_identity_merge(conn, [532, 768], 532, "Jolin Tsai")
    assert preview["blocked"] is True

    with pytest.raises(ValueError, match="外部 ID"):
        create_artist_identity_group(
            conn,
            artist_ids=[532, 768],
            canonical_artist_id=532,
            display_name="Jolin Tsai",
            expected_revision=get_identity_revision(conn),
            idempotency_key="test-external-conflict",
            reason="name alone is insufficient",
        )


def test_provider_metadata_selection_and_member_merge_are_restored_by_undo():
    conn = _database()
    group = list_artist_identity_groups(conn)[0]
    merged = update_artist_identity_group(
        conn,
        identity_id=group["identity_id"],
        add_ids=[768],
        remove_ids=[],
        canonical_artist_id=532,
        display_name="Jolin Tsai",
        provider_metadata_artist_id=765,
        expected_revision=get_identity_revision(conn),
        idempotency_key="test-provider-selection",
        reason="user confirmed same artist despite provider conflict",
        confirm_external_id_conflict=True,
    )
    current = list_artist_identity_groups(conn)[0]
    assert {member["artist_id"] for member in current["members"]} == {532, 765, 768}
    assert current["provider_metadata_artist_id"] == 765

    undo_artist_identity_event(
        conn,
        event_id=merged["event_id"],
        expected_revision=merged["revision"],
        idempotency_key="test-provider-selection-undo",
        reason="verify rollback",
    )
    restored = list_artist_identity_groups(conn)[0]
    assert {member["artist_id"] for member in restored["members"]} == {532, 765}
    assert restored["provider_metadata_artist_id"] is None


def test_identity_mutation_enqueue_invalidates_metadata_and_detail_caches(monkeypatch):
    invalidations: list[bool] = []

    class Queue:
        def enqueue_if_not_pending(self, job):
            assert job.payload["revision"] == 7
            return "identity-rebuild-job"

    monkeypatch.setattr(artist_identity_api, "invalidate_all", lambda: invalidations.append(True))
    monkeypatch.setattr(artist_identity_api, "get_job_queue", lambda: Queue())

    assert artist_identity_api._enqueue_rebuild(7) == "identity-rebuild-job"
    assert invalidations == [True]


def test_artist_play_cache_key_includes_identity_revision(monkeypatch):
    conn = _database()
    captured: dict[str, object] = {}

    def fake_loader(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(db_mod, "_load_plays_for_artists_cached", fake_loader)
    db_mod.load_plays_for_artists(conn)

    assert captured["identity_revision"] == get_identity_revision(conn)


def test_create_group_persists_audited_external_ids_and_remains_undoable():
    conn = _database()
    before_hash = _raw_hash(conn)
    created = create_artist_identity_group(
        conn,
        artist_ids=[532, 765],
        canonical_artist_id=532,
        display_name="Jolin Tsai",
        expected_revision=get_identity_revision(conn),
        idempotency_key="test-create-external-links",
        reason="user confirmed identity; stable provider evidence recorded",
        external_ids=[
            {
                "artist_id": artist_id,
                "provider": "musicbrainz",
                "external_id": "musicbrainz-jolin",
                "evidence_type": "provider_metadata_match",
                "evidence_source": "spotify_artist_meta",
                "confidence": 1.0,
                "verified": True,
            }
            for artist_id in (532, 765)
        ],
    )
    links = conn.execute(
        """SELECT artist_id, external_id, verified
           FROM artist_identity_external_ids
           WHERE provider='musicbrainz' ORDER BY artist_id"""
    ).fetchall()
    assert [tuple(row) for row in links] == [
        (532, "musicbrainz-jolin", 1),
        (765, "musicbrainz-jolin", 1),
    ]
    event = conn.execute(
        "SELECT after_json FROM artist_identity_events WHERE event_id=?",
        (created["event_id"],),
    ).fetchone()
    assert "musicbrainz-jolin" in event["after_json"]

    undo_artist_identity_event(
        conn,
        event_id=created["event_id"],
        expected_revision=created["revision"],
        idempotency_key="test-undo-external-links",
        reason="verify group rollback remains available",
    )
    assert {member["artist_id"] for member in list_artist_identity_groups(conn)[0]["members"]} == {
        532,
        765,
    }
    assert (
        conn.execute(
            """SELECT 1 FROM artist_identity_external_ids
               WHERE provider='musicbrainz'"""
        ).fetchone()
        is None
    )
    assert _raw_hash(conn) == before_hash


def test_update_group_persists_external_ids_in_audit_and_restores_them_on_undo():
    conn = _database()
    group = list_artist_identity_groups(conn)[0]
    before_links = [
        tuple(row)
        for row in conn.execute(
            """SELECT artist_id, provider, external_id, evidence_type,
                      evidence_source, confidence, verified
               FROM artist_identity_external_ids
               WHERE artist_id IN (532, 765)
               ORDER BY artist_id, provider, external_id"""
        )
    ]
    updated = update_artist_identity_group(
        conn,
        identity_id=group["identity_id"],
        add_ids=[],
        remove_ids=[],
        canonical_artist_id=532,
        display_name="Jolin Tsai",
        provider_metadata_artist_id=765,
        expected_revision=get_identity_revision(conn),
        idempotency_key="test-update-external-links",
        reason="user confirmed conflicting provider identities",
        confirm_external_id_conflict=True,
        external_ids=[
            {
                "artist_id": 532,
                "provider": "musicbrainz",
                "external_id": "musicbrainz-jolin-main",
                "evidence_type": "user_confirmed_provider_metadata",
                "evidence_source": "manual-review",
                "confidence": 1.0,
                "verified": True,
            },
            {
                "artist_id": 765,
                "provider": "musicbrainz",
                "external_id": "musicbrainz-jolin-alias",
                "evidence_type": "user_confirmed_provider_metadata",
                "evidence_source": "manual-review",
                "confidence": 1.0,
                "verified": True,
            },
        ],
    )
    event = conn.execute(
        "SELECT after_json FROM artist_identity_events WHERE event_id=?",
        (updated["event_id"],),
    ).fetchone()
    assert "musicbrainz-jolin-main" in event["after_json"]
    assert "musicbrainz-jolin-alias" in event["after_json"]

    repeated = update_artist_identity_group(
        conn,
        identity_id=group["identity_id"],
        add_ids=[],
        remove_ids=[],
        canonical_artist_id=532,
        display_name="Jolin Tsai",
        expected_revision=0,
        idempotency_key="test-update-external-links",
        reason="idempotent retry",
    )
    assert repeated == updated

    undo_artist_identity_event(
        conn,
        event_id=updated["event_id"],
        expected_revision=updated["revision"],
        idempotency_key="test-update-external-links-undo",
        reason="restore provider links",
    )
    restored_links = [
        tuple(row)
        for row in conn.execute(
            """SELECT artist_id, provider, external_id, evidence_type,
                      evidence_source, confidence, verified
               FROM artist_identity_external_ids
               WHERE artist_id IN (532, 765)
               ORDER BY artist_id, provider, external_id"""
        )
    ]
    assert restored_links == before_links


def test_create_group_requires_confirmation_for_prospective_provider_conflict():
    conn = _database()
    links = [
        {
            "artist_id": artist_id,
            "provider": "musicbrainz",
            "external_id": external_id,
            "evidence_type": "user_confirmed_provider_metadata",
            "confidence": 1.0,
            "verified": True,
        }
        for artist_id, external_id in ((532, "spotify-jolin"), (765, "spotify-other"))
    ]
    with pytest.raises(ValueError, match="provider / 外部 ID"):
        create_artist_identity_group(
            conn,
            artist_ids=[532, 765],
            canonical_artist_id=532,
            display_name="Jolin Tsai",
            expected_revision=get_identity_revision(conn),
            idempotency_key="test-prospective-conflict",
            reason="explicit confirmation is required",
            external_ids=links,
        )
