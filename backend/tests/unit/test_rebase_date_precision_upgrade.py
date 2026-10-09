from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest

from backend.core import db as db_mod
from backend.core.migrations import LATEST_SCHEMA_VERSION, run_migrations
from backend.tests.unit.test_rebase_music_search_preflight_script import (
    ROOT,
    _populate_staged,
    _run_rebase,
)
from scripts.rebase_music_search_preflight import source_marker

pytestmark = pytest.mark.unit


def _schema_88(path: Path) -> None:
    shutil.copy2(ROOT / "backend/tests/fixtures/seed.db", path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=DELETE")
    for name, sql in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"):
        if "release_date_precision" in (sql or ""):
            conn.execute(f'DROP TRIGGER "{name}"')
    for table in ("spotify_album_meta", "album_projects"):
        conn.execute(f'ALTER TABLE "{table}" DROP COLUMN release_date_precision')
    conn.execute("DROP TABLE spotify_album_date_observations")
    conn.execute("DELETE FROM schema_migrations WHERE version>=89")
    for table in (
        "music_search_detail_entity_projection",
        "music_search_detail_source_facts",
        "music_search_detail_projection_state",
    ):
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.commit()
    conn.close()


def test_rebase_upgrades_schema_88_and_preserves_rollback_and_non_search_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline, staged, quiescent = (
        tmp_path / name for name in ("baseline.db", "staged.db", "quiescent.db")
    )
    _schema_88(baseline)
    rollback_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
    shutil.copy2(baseline, staged)
    shutil.copy2(baseline, quiescent)
    monkeypatch.setattr(db_mod, "DB_PATH", str(staged))
    run_migrations()
    _populate_staged(staged)
    with sqlite3.connect(quiescent) as conn:
        conn.execute("CREATE TABLE unrelated_release_write(value TEXT)")
        conn.execute("INSERT INTO unrelated_release_write VALUES ('preserved')")
    completed = _run_rebase(baseline, quiescent, staged, tmp_path / "result.json")
    assert completed.returncode == 0, completed.stderr
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == rollback_hash
    with sqlite3.connect(quiescent) as conn:
        assert (
            conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            == LATEST_SCHEMA_VERSION
        )
        assert (
            conn.execute("SELECT value FROM unrelated_release_write").fetchone()[0] == "preserved"
        )
    assert source_marker(quiescent) == source_marker(staged)


def test_source_marker_detects_date_observation_audit_only_drift(tmp_path: Path) -> None:
    target = tmp_path / "source.db"
    shutil.copy2(ROOT / "backend/tests/fixtures/seed.db", target)
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    before = source_marker(target)
    with sqlite3.connect(target) as conn:
        conn.execute(
            """INSERT INTO spotify_album_date_observations
               (spotify_album_id,release_date,release_date_precision,status,source)
               VALUES ('existing-album','2020','year','conflict','bounded_spotify_album_date')"""
        )
    assert source_marker(target) != before
