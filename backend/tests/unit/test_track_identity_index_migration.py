"""Index repair must preserve identity facts and the actual loader SQL semantics."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from backend.core import db, migrations

pytestmark = pytest.mark.unit
OLD_DDL = (
    "CREATE UNIQUE INDEX idx_track_l1_local_identity "
    "ON track_l1_identities(fallback_track_id) WHERE provider='local'"
)


def ddl(conn):
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='idx_track_l1_local_identity'"
    ).fetchone()[0]


@pytest.fixture
def identity_db(tmp_path, monkeypatch):
    seed = Path(__file__).parents[1] / "fixtures/seed.db"
    path = tmp_path / "identities.db"
    with sqlite3.connect(f"file:{seed}?mode=ro&immutable=1", uri=True) as source:
        conn = sqlite3.connect(path)
        source.backup(conn)
    monkeypatch.setattr(db, "DB_PATH", str(path))
    conn.execute("DROP INDEX idx_track_l1_local_identity")
    conn.execute(OLD_DDL)
    conn.commit()
    yield conn
    conn.close()
    db._load_plays_cached.cache_clear()
    db._load_plays_for_artists_cached.cache_clear()


def test_upgrade_and_canonical_noop(identity_db):
    conn = identity_db
    facts = conn.execute("SELECT * FROM track_l1_identities ORDER BY l1_id").fetchall()
    migrations.migrate_074(conn)
    assert "WHERE fallback_track_id IS NOT NULL" in ddl(conn)
    schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]
    traced = []
    conn.set_trace_callback(traced.append)
    migrations.migrate_074(conn)
    conn.set_trace_callback(None)
    assert not any(q.startswith(("DROP", "CREATE")) for q in traced)
    assert conn.execute("PRAGMA schema_version").fetchone()[0] == schema_version
    assert conn.execute("SELECT * FROM track_l1_identities ORDER BY l1_id").fetchall() == facts
    fresh = sqlite3.connect(":memory:")
    fresh.executescript(db.SCHEMA)
    assert "".join(ddl(fresh).split()) == "".join(ddl(conn).split())
    fresh.close()


@pytest.mark.parametrize("status", ["active", "superseded"])
def test_duplicate_fails_closed_with_old_index_and_facts(identity_db, status):
    conn = identity_db
    fallback = conn.execute("SELECT fallback_track_id FROM track_l1_identities LIMIT 1").fetchone()[
        0
    ]
    conn.execute(
        "INSERT INTO track_l1_identities(provider,fallback_track_id,identity_status) VALUES('other',?,?)",
        (fallback, status),
    )
    conn.commit()
    facts = conn.execute("SELECT * FROM track_l1_identities ORDER BY l1_id").fetchall()
    with pytest.raises(sqlite3.IntegrityError, match="duplicate non-null fallback_track_id"):
        migrations.migrate_074(conn)
    assert ddl(conn) == OLD_DDL
    assert conn.execute("SELECT * FROM track_l1_identities ORDER BY l1_id").fetchall() == facts
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO track_l1_identities(provider,fallback_track_id) VALUES('local',?)",
            (fallback,),
        )
    # The normal runner must not mark an unsuccessful migration as applied.
    conn.rollback()
    conn.execute("DELETE FROM schema_migrations WHERE version=74")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="Migration 74 blocked"):
        migrations.run_migrations()
    assert conn.execute("SELECT 1 FROM schema_migrations WHERE version=74").fetchone() is None
    assert ddl(conn) == OLD_DDL


def test_create_failure_rolls_back_drop_and_keeps_caller_transaction(identity_db):
    conn = identity_db
    conn.execute("BEGIN")
    before = conn.execute("PRAGMA schema_version").fetchone()[0]
    conn.set_authorizer(
        lambda action, *_: (
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_INDEX else sqlite3.SQLITE_OK
        )
    )
    with pytest.raises(sqlite3.DatabaseError):
        migrations.migrate_074(conn)
    conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    assert conn.in_transaction
    assert ddl(conn) == OLD_DDL
    assert conn.execute("PRAGMA schema_version").fetchone()[0] == before
    conn.rollback()
    migrations.migrate_074(conn)
    assert "IS NOT NULL" in ddl(conn)


def test_success_does_not_commit_caller_transaction(identity_db):
    conn = identity_db
    conn.execute("BEGIN")
    migrations.migrate_074(conn)
    assert conn.in_transaction
    conn.rollback()
    assert ddl(conn) == OLD_DDL


def test_runner_is_idempotent(identity_db):
    identity_db.execute("DELETE FROM schema_migrations WHERE version=74")
    identity_db.commit()
    migrations.run_migrations()
    version = identity_db.execute("PRAGMA schema_version").fetchone()[0]
    migrations.run_migrations()
    assert identity_db.execute("PRAGMA schema_version").fetchone()[0] == version
    assert identity_db.execute(
        "SELECT name FROM schema_migrations WHERE version=74"
    ).fetchone() == ("track_l1_fallback_index_repair",)


@pytest.mark.parametrize("loader", ["main", "artist", "billboard"])
def test_actual_query_plan_and_identity_boundaries(identity_db, monkeypatch, loader):
    from backend.domains.billboard import data_loader

    conn = identity_db
    # Synthetic local, non-local fallback, old relink owner, new owner and
    # superseded fallback. A source's catalog token differs from its play token.
    for tid in range(99001, 99006):
        conn.execute(
            "INSERT INTO tracks(track_id,track_name,artist_id) VALUES(?, 'Fixture', 1)",
            (tid,),
        )
        conn.execute("INSERT INTO track_artists(track_id,artist_id) VALUES(?,1)", (tid,))
    conn.executemany(
        "INSERT INTO track_l1_identities(l1_id,provider,fallback_track_id,identity_status,representative_track_id) VALUES(?,?,?,?,?)",
        [
            (99001, "local", 99001, "active", 99001),
            (99002, "other", 99002, "active", 99001),
            (99003, "local", 99003, "superseded", 99001),
            (99004, "spotify", 99004, "active", 99004),
            (99005, "local", 99005, "superseded", 99001),
        ],
    )
    conn.executemany(
        "INSERT INTO track_l1_external_ids(provider,external_track_id,l1_id,evidence_type) VALUES('spotify',?,?,?)",
        [
            ("relinked", 99004, "provider_relink"),
            ("additional", 99004, "provider_observed"),
            ("retired", 99003, "provider_observed"),
        ],
    )
    conn.execute("UPDATE tracks SET spotify_track_id='retired' WHERE track_id=99003")
    for offset, (tid, token) in enumerate(
        [
            (99001, None),
            (99002, None),
            (99003, "relinked"),
            (99003, "additional"),
            (99003, "retired"),
            (99005, None),
        ]
    ):
        conn.execute(
            "INSERT INTO plays(play_id,ts,track_id,spotify_track_id_at_play,ms_played,ts_year,ts_month,ts_week,ts_dow,ts_hour,ts_date,platform) VALUES(?,?,?,?,60000,2025,1,1,2,0,'2025-01-01','fixture')",
            (99001 + offset, f"2025-01-01T0{offset}:00:00Z", tid, token),
        )
    conn.commit()
    captured = []

    class CapturedError(Exception):
        pass

    def capture(sql, connection, params=None, **kwargs):
        captured.append((sql, params or []))
        raise CapturedError()

    monkeypatch.setattr(pd, "read_sql_query", capture)
    db._load_plays_cached.cache_clear()
    db._load_plays_for_artists_cached.cache_clear()
    data_loader.load_billboard_raw.cache_clear()
    with pytest.raises(CapturedError):
        if loader == "billboard":
            data_loader.load_billboard_raw(30000, True, 4, 0)
        else:
            fn = db.load_plays if loader == "main" else db.load_plays_for_artists
            fn(conn, min_ms=30000, music_only=True, merge_enabled=True)
    sql, params = captured[0]
    before = conn.execute(sql, params).fetchall()
    migrations.migrate_074(conn)
    cursor = conn.execute(sql, params)
    after = cursor.fetchall()
    assert after == before  # Order and every selected field, not only IDs.
    columns = [d[0] for d in cursor.description]
    rows = {r[columns.index("play_id")]: dict(zip(columns, r)) for r in after}
    identity = "track_id" if loader == "billboard" else "l1_id"
    resolved = "representative_track_id" if loader == "billboard" else "resolved_track_id"
    assert [rows[k][identity] for k in range(99001, 99007)] == [
        99001,
        99002,
        99004,
        99004,
        99003,
        99005,
    ]
    assert [rows[k][resolved] for k in range(99001, 99007)] == [
        99001,
        99001,
        99004,
        99004,
        99003,
        99005,
    ]
    assert [rows[k]["source_track_id"] for k in range(99001, 99007)] == [
        99001,
        99002,
        99003,
        99003,
        99003,
        99005,
    ]
    plan = [r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]
    assert not any("SCAN li_local" in node for node in plan)
    assert any("SEARCH li_local USING INDEX idx_track_l1_local_identity" in node for node in plan)


def test_index_name_on_another_table_fails_closed(identity_db):
    conn = identity_db
    conn.execute("DROP INDEX idx_track_l1_local_identity")
    conn.execute("CREATE INDEX idx_track_l1_local_identity ON tracks(track_id)")
    before = ddl(conn)
    with pytest.raises(sqlite3.IntegrityError, match="belongs to another table"):
        migrations.migrate_074(conn)
    assert ddl(conn) == before


def test_runner_ledger_failure_rolls_back_index(identity_db, monkeypatch):
    identity_db.execute("DELETE FROM schema_migrations WHERE version=74")
    identity_db.commit()

    class LedgerFailureConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith("INSERT INTO schema_migrations") and parameters[0] == 74:
                raise sqlite3.OperationalError("injected ledger write failure")
            return super().execute(sql, parameters)

    monkeypatch.setattr(
        db, "get_db", lambda **_: sqlite3.connect(db.DB_PATH, factory=LedgerFailureConnection)
    )
    with pytest.raises(sqlite3.OperationalError, match="ledger write failure"):
        migrations.run_migrations()
    assert ddl(identity_db) == OLD_DDL
    assert (
        identity_db.execute("SELECT 1 FROM schema_migrations WHERE version=74").fetchone() is None
    )
