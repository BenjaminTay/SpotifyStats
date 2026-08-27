from __future__ import annotations

import sqlite3

import pytest

from backend.core import db as db_mod

pytestmark = pytest.mark.unit


def test_application_connections_enable_foreign_keys(monkeypatch, tmp_path) -> None:
    database = tmp_path / "foreign-keys.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(database))

    writer = db_mod.get_db(readonly=False)
    reader = db_mod.get_db(readonly=True)
    auxiliary = db_mod.connect_sqlite_path(database)
    try:
        assert writer.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert reader.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert auxiliary.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        auxiliary.close()
        reader.close()
        writer.close()


def test_enforcement_fails_when_called_inside_transaction() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE probe(value INTEGER)")
    conn.execute("INSERT INTO probe VALUES (1)")
    with pytest.raises(RuntimeError, match="could not be enabled"):
        db_mod.enforce_sqlite_foreign_keys(conn)
