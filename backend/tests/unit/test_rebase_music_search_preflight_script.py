from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core import db as db_mod
from backend.core.migrations import (
    MIGRATIONS,
    migrate_032,
    migrate_034,
    migrate_035,
    run_migrations,
)
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.index import music_search_source_revision
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.services.music_search_maintenance_service import _current_filter_values

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "rebase_music_search_preflight.py"


def _create_baseline(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute(
        """CREATE TABLE plays(
               play_id INTEGER PRIMARY KEY,
               ts TEXT,
               ms_played INTEGER NOT NULL DEFAULT 0,
               track_id INTEGER
           )"""
    )
    conn.execute("INSERT INTO schema_migrations VALUES (34, 'search variants')")
    migrate_032(conn)
    migrate_034(conn)
    migrate_035(conn)
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='baseline-generation', status='ready',
               tokenizer='fts5_trigram', source_revision=?
           WHERE state_id=1""",
        (music_search_source_revision(conn),),
    )
    conn.commit()
    conn.close()


def _populate_staged(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id='staged-generation', status='ready',
               tokenizer='fts5_trigram', source_revision=?
           WHERE state_id=1""",
        (music_search_source_revision(conn),),
    )
    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    conn.execute("DELETE FROM music_search_snapshot_meta")
    for context in contexts:
        conn.execute(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, source_revision, status,
                   semantic_base_key, merge_level, dynamic_threshold, builder_version
               ) VALUES (?, ?, ?, 'ready', ?, ?, ?, ?)""",
            (
                context.filter_fingerprint,
                context.filter_fingerprint,
                context.source_revision,
                context.semantic_base_key,
                context.merge_level,
                int(context.dynamic_threshold),
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
            ),
        )
    conn.commit()
    conn.close()


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    baseline = tmp_path / "baseline.db"
    quiescent = tmp_path / "quiescent.db"
    staged = tmp_path / "staged.db"
    _create_baseline(baseline)
    shutil.copy2(baseline, quiescent)
    shutil.copy2(baseline, staged)
    _populate_staged(staged)
    return baseline, quiescent, staged


def _create_schema_33(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE schema_migrations(
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )
    for version, name, migration in MIGRATIONS:
        if version > 33:
            break
        try:
            migration(conn)
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if not any(
                fragment in message
                for fragment in ("already exists", "duplicate column name", "duplicate index name")
            ):
                raise
        conn.execute(
            "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
            (version, name),
        )
        conn.commit()
    conn.close()


def _run_rebase(
    baseline: Path,
    quiescent: Path,
    staged: Path,
    output: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline-db",
            str(baseline),
            "--quiescent-db",
            str(quiescent),
            "--staged-db",
            str(staged),
            "--json-output",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_rebase_preserves_non_search_writes_and_publishes_exact_ready_set(
    tmp_path: Path,
) -> None:
    baseline, quiescent, staged = _fixture_paths(tmp_path)
    conn = sqlite3.connect(quiescent)
    conn.execute("CREATE TABLE unrelated_release_write(value TEXT NOT NULL)")
    conn.execute("INSERT INTO unrelated_release_write VALUES ('preserved')")
    conn.commit()
    conn.close()
    output = tmp_path / "rebase.json"

    completed = _run_rebase(baseline, quiescent, staged, output)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert payload["source_equivalent"] is True
    assert payload["validation"]["ready_variants"] == 6
    assert payload["validation"]["unique_fingerprints"] == 6
    assert payload["validation"]["context_orphan_count"] == 0
    conn = sqlite3.connect(f"{quiescent.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    assert conn.execute("SELECT value FROM unrelated_release_write").fetchone()[0] == "preserved"
    assert (
        conn.execute(
            "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
        ).fetchone()[0]
        == "staged-generation"
    )
    conn.close()


def test_rebase_fails_closed_when_search_source_revision_changes(tmp_path: Path) -> None:
    baseline, quiescent, staged = _fixture_paths(tmp_path)
    conn = sqlite3.connect(quiescent)
    conn.execute("UPDATE music_search_revision_state SET playback_revision=playback_revision+1")
    conn.commit()
    conn.close()
    output = tmp_path / "rebase.json"

    completed = _run_rebase(baseline, quiescent, staged, output)

    assert completed.returncode == 1
    assert "search source changed during preflight" in completed.stderr
    assert not output.exists()
    conn = sqlite3.connect(f"{quiescent.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    assert (
        conn.execute(
            "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
        ).fetchone()[0]
        == "baseline-generation"
    )
    conn.close()


def test_rebase_migrates_schema_33_quiescent_copy_without_touching_rollback(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "schema-33-rollback.db"
    quiescent = tmp_path / "schema-33-quiescent.db"
    staged = tmp_path / "validated-staged.db"
    _create_schema_33(baseline)
    shutil.copy2(baseline, quiescent)
    shutil.copy2(baseline, staged)
    db_mod.DB_PATH = str(staged)
    run_migrations()
    _populate_staged(staged)
    output = tmp_path / "rebase-schema-33.json"

    completed = _run_rebase(baseline, quiescent, staged, output)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["source_equivalent"] is True
    rollback = sqlite3.connect(baseline)
    assert rollback.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 33
    rollback.close()
    promoted = sqlite3.connect(quiescent)
    assert promoted.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 36
    assert (
        promoted.execute(
            "SELECT COUNT(*) FROM music_search_snapshot_meta WHERE status='ready'"
        ).fetchone()[0]
        == 6
    )
    promoted.close()
