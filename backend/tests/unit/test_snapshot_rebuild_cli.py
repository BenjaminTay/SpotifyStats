"""Snapshot backfill CLIs must migrate old copies before opening readers."""

from __future__ import annotations

import importlib
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

from backend.core import db
from backend.core.migrations import LATEST_SCHEMA_VERSION

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("kind", ["account_archive", "governance"])
def test_rebuild_cli_migrates_existing_copy_before_maintenance(tmp_path, monkeypatch, kind):
    target = tmp_path / "old.db"
    shutil.copy2(Path(__file__).parents[1] / "fixtures" / "seed.db", target)
    monkeypatch.setattr(db, "DB_PATH", str(target))
    module = importlib.import_module(f"scripts.rebuild_{kind}")
    service = importlib.import_module(f"backend.services.{kind}_snapshot_service")
    calls = []

    def verify_migrated(conn, *args):
        latest = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        assert latest == LATEST_SCHEMA_VERSION
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "account_archive_source_revisions" in tables
        assert "governance_source_revisions" in tables
        calls.append(True)
        return {"published": []}

    monkeypatch.setattr(service, "ensure", verify_migrated)
    monkeypatch.setattr(sys, "argv", ["rebuild", "--db", str(target)])
    module.main()
    assert calls == [True]
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 117
