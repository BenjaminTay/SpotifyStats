from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_059
from backend.domains.metadata.historical_fk_cleanup import apply_cleanup, build_cleanup_plan
from backend.domains.metadata.track_identity import resolve_canonical_track_id

pytestmark = pytest.mark.unit


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        PRAGMA foreign_keys=OFF;
        CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL);
        INSERT INTO schema_migrations VALUES (59, 'cleanup support');
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE albums(
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id)
        );
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            album_id INTEGER REFERENCES albums(album_id),
            spotify_track_id TEXT
        );
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER REFERENCES tracks(track_id),
            ms_played INTEGER NOT NULL
        );
        CREATE TABLE spotify_track_owners(
            spotify_track_id TEXT PRIMARY KEY,
            track_id INTEGER NOT NULL REFERENCES tracks(track_id)
        );
        CREATE TABLE track_artists(
            track_id INTEGER REFERENCES tracks(track_id),
            artist_id INTEGER REFERENCES artists(artist_id)
        );
        CREATE TABLE track_l1_identities(
            l1_id INTEGER PRIMARY KEY,
            fallback_track_id INTEGER REFERENCES tracks(track_id),
            representative_track_id INTEGER REFERENCES tracks(track_id)
        );
        CREATE TABLE track_l1_source_links(
            l1_id INTEGER REFERENCES track_l1_identities(l1_id),
            track_id INTEGER REFERENCES tracks(track_id)
        );
        CREATE TABLE track_groups(group_id INTEGER PRIMARY KEY);
        CREATE TABLE track_group_members(
            group_id INTEGER REFERENCES track_groups(group_id),
            track_id INTEGER REFERENCES tracks(track_id),
            UNIQUE(group_id, track_id)
        );
        CREATE TABLE ai_task_runs(task_id TEXT PRIMARY KEY);
        CREATE TABLE ai_task_events(
            event_id INTEGER PRIMARY KEY,
            task_id TEXT REFERENCES ai_task_runs(task_id)
        );
        CREATE TABLE ai_tool_calls(
            tool_call_id INTEGER PRIMARY KEY,
            task_id TEXT REFERENCES ai_task_runs(task_id)
        );
        CREATE TABLE chat_sessions(id INTEGER PRIMARY KEY);
        CREATE TABLE chat_messages(
            id INTEGER PRIMARY KEY,
            session_id INTEGER REFERENCES chat_sessions(id)
        );
        CREATE TABLE track_id_aliases(
            alias_track_id INTEGER PRIMARY KEY,
            canonical_track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            reason TEXT NOT NULL,
            CHECK(alias_track_id != canonical_track_id)
        );
        CREATE TABLE historical_fk_cleanup_runs(
            run_id TEXT PRIMARY KEY,
            plan_token TEXT NOT NULL,
            status TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE historical_fk_cleanup_archive(
            run_id TEXT NOT NULL REFERENCES historical_fk_cleanup_runs(run_id),
            source_table TEXT NOT NULL,
            source_row_key TEXT NOT NULL,
            row_json TEXT NOT NULL,
            archived_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(run_id, source_table, source_row_key)
        );

        INSERT INTO artists VALUES (1, 'Valid Artist');
        INSERT INTO albums VALUES (1, 'Valid Album', 1);
        INSERT INTO albums VALUES (2, 'Stale Album', 99);
        INSERT INTO tracks VALUES (1, 'Song', 1, 1, 'spotify-a');
        INSERT INTO tracks VALUES (2, 'Song', 99, 2, 'spotify-a');
        INSERT INTO plays VALUES (1, 1, 12345);
        INSERT INTO spotify_track_owners VALUES ('spotify-a', 1);
        INSERT INTO track_artists VALUES (2, 99);
        INSERT INTO track_l1_identities VALUES (1, 1, 1);
        INSERT INTO track_l1_identities VALUES (2, 2, 2);
        INSERT INTO track_l1_source_links VALUES (1, 2);
        INSERT INTO track_groups VALUES (1);
        INSERT INTO track_group_members VALUES (1, 2);
        INSERT INTO ai_task_events VALUES (1, 'missing-task');
        INSERT INTO ai_tool_calls VALUES (1, 'missing-task');
        INSERT INTO chat_messages VALUES (1, 99);
        """
    )
    conn.commit()
    return conn


def test_cleanup_is_previewed_revision_locked_and_preserves_plays() -> None:
    conn = _database()
    preview = build_cleanup_plan(conn)
    assert preview["status"] == "ready"
    assert preview["counts"] == {
        "foreign_key_violations": 6,
        "track_aliases": 1,
        "stale_identities": 1,
        "stale_albums": 1,
        "orphan_ai_rows": 2,
        "orphan_chat_messages": 1,
    }

    result = apply_cleanup(conn, preview["confirmation_token"])

    assert result["status"] == "completed"
    assert result["play_totals"] == {"rows": 1, "milliseconds": 12345}
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT COUNT(*) FROM historical_fk_cleanup_archive").fetchone()[0] == 9
    assert resolve_canonical_track_id(conn, 2) == 1


def test_migration_59_repairs_legacy_release_group_self_reference() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        PRAGMA foreign_keys=OFF;
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY);
        CREATE TABLE albums(album_id INTEGER PRIMARY KEY);
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY);
        CREATE TABLE release_groups(
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            artist_id INTEGER REFERENCES artists(artist_id),
            primary_album_id INTEGER REFERENCES albums(album_id),
            scope TEXT NOT NULL,
            parent_group_id INTEGER REFERENCES release_groups_new(group_id),
            is_manual INTEGER,
            created_at TEXT,
            UNIQUE(canonical_name, artist_id, scope)
        );
        CREATE TABLE release_group_members(
            group_id INTEGER REFERENCES release_groups(group_id),
            album_id INTEGER REFERENCES albums(album_id)
        );
        INSERT INTO artists VALUES (1);
        INSERT INTO albums VALUES (1);
        INSERT INTO release_groups VALUES (1, 'Album', 1, 1, 'release', NULL, 0, NULL);
        INSERT INTO release_group_members VALUES (1, 1);
        """
    )

    migrate_059(conn)
    conn.commit()

    parent_targets = {
        row[2]
        for row in conn.execute("PRAGMA foreign_key_list(release_groups)").fetchall()
        if row[3] == "parent_group_id"
    }
    assert parent_targets == {"release_groups"}
    assert conn.execute("SELECT COUNT(*) FROM release_group_members").fetchone()[0] == 1
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("DELETE FROM release_group_members WHERE group_id=1")
    conn.execute("DELETE FROM release_groups WHERE group_id=1")
