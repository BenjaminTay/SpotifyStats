from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from backend.core import db as db_mod
from backend.core.migrations import run_migrations
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.variants import build_music_search_variant_contexts
from backend.domains.music_search.year_end_projection import (
    YEAR_END_PROJECTION_BUILDER_VERSION,
    year_end_projection_set_status,
)
from backend.services.music_search_maintenance_service import _current_filter_values
from backend.tests.unit.test_prepare_music_search_resume_script import _run, _run_bootstrap
from backend.tests.unit.test_rebase_music_search_preflight_script import (
    ROOT,
    _populate_staged,
    _run_rebase,
)
from scripts.rebase_music_search_preflight import (
    SCOPED_SNAPSHOT_TABLES,
    _copy_derived_tables,
    source_marker,
)

pytestmark = pytest.mark.unit


def _payload(conn: sqlite3.Connection, key: str, label: str) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO music_search_snapshot_meta(
               snapshot_key,filter_fingerprint,source_revision,status,
               semantic_base_key,merge_level,dynamic_threshold,builder_version
           ) VALUES (?, ?, ?, 'ready', 'historical-base', 2, 0, ?)""",
        (key, key, label, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
    )
    conn.execute(
        """INSERT INTO music_search_entity_context(snapshot_key,entity_key,play_events,total_ms,peak_position)
           VALUES (?, 'track:3', 1, 30000, 1)""",
        (key,),
    )
    conn.execute(
        """INSERT INTO music_search_weekly_chart_context VALUES
           (?, 'track', '2026-01-02', 'track:3', 1, 1, 30000, ?)""",
        (key, label),
    )
    conn.execute(
        """INSERT INTO music_search_year_end_meta VALUES
           (?, 2026, 'year_to_date', 0, 1, 52, '2026-01-02', '2026-01-02')""",
        (key,),
    )
    conn.execute(
        """INSERT INTO music_search_entity_year_end VALUES
           (?, 'track', 'track:3', 2026, 1, 1, 1, 1, 1, 1, 1, 1, 1, '2026-01-02', '2026-01-02')""",
        (key,),
    )
    conn.execute(
        """INSERT INTO music_search_year_end_projection_state VALUES
           (?, ?, 'ready', ?, NULL)""",
        (key, YEAR_END_PROJECTION_BUILDER_VERSION, label),
    )


def _paths(tmp_path: Path) -> tuple[Path, Path, tuple[str, ...]]:
    candidate = tmp_path / "candidate.db"
    target = tmp_path / "target.db"
    shutil.copy2(ROOT / "backend/tests/fixtures/seed.db", candidate)
    db_mod.DB_PATH = str(candidate)
    run_migrations()
    _populate_staged(candidate)
    shutil.copy2(candidate, target)
    with closing(sqlite3.connect(candidate)) as conn:
        conn.row_factory = sqlite3.Row
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        keys = tuple(context.filter_fingerprint for context in contexts)
        for key in (*keys, "shared-history", "candidate-only-history"):
            _payload(conn, key, "candidate")
        conn.commit()
    with closing(sqlite3.connect(target)) as conn:
        _payload(conn, "shared-history", "target")
        _payload(conn, "target-only-history", "target")
        conn.commit()
    assert source_marker(candidate) == source_marker(target)
    return target, candidate, keys


def _rows(path: Path, key: str) -> dict:
    with closing(sqlite3.connect(path)) as conn:
        return {
            table: conn.execute(
                f'SELECT * FROM "{table}" WHERE snapshot_key=? ORDER BY 1,2',
                (key,),
            ).fetchall()
            for table in SCOPED_SNAPSHOT_TABLES
        }


@pytest.mark.parametrize("entry", ["normal", "bootstrap", "rebase"])
def test_install_copies_current_secondary_without_replacing_target_history(
    tmp_path: Path,
    entry: str,
) -> None:
    target, candidate, keys = _paths(tmp_path)
    history = {key: _rows(target, key) for key in ("shared-history", "target-only-history")}
    source_before = source_marker(target)
    expected = {key: _rows(candidate, key) for key in keys}
    output = tmp_path / "install.json"
    if entry == "rebase":
        result = _run_rebase(target, target, candidate, output)
        installed = target
    else:
        result = (_run if entry == "normal" else _run_bootstrap)(target, candidate, output)
        installed = candidate
    assert result.returncode == 0, result.stderr
    assert source_marker(installed) == source_before
    assert {key: _rows(installed, key) for key in keys} == expected
    assert {key: _rows(installed, key) for key in history} == history
    assert not any(_rows(installed, "candidate-only-history").values())
    with closing(sqlite3.connect(installed)) as conn:
        conn.row_factory = sqlite3.Row
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        assert year_end_projection_set_status(conn, contexts)["ready_count"] == 4


def test_install_rejects_secondary_inventory_mismatch_without_writes(tmp_path: Path) -> None:
    target, candidate, _keys = _paths(tmp_path)
    with closing(sqlite3.connect(candidate)) as conn:
        conn.execute("DROP TABLE music_search_year_end_projection_state")
        conn.commit()
    with closing(sqlite3.connect(target)) as conn:
        before = list(conn.iterdump())
    with pytest.raises(ValueError, match="inventory mismatch"):
        _copy_derived_tables(target, candidate)
    with closing(sqlite3.connect(target)) as conn:
        assert list(conn.iterdump()) == before


def test_install_rolls_back_when_current_annual_entities_have_no_metadata(tmp_path: Path) -> None:
    target, candidate, keys = _paths(tmp_path)
    with closing(sqlite3.connect(candidate)) as conn:
        conn.execute("DELETE FROM music_search_year_end_meta WHERE snapshot_key=?", (keys[0],))
        conn.commit()
    with closing(sqlite3.connect(target)) as conn:
        before = list(conn.iterdump())
    with pytest.raises(ValueError, match="no annual metadata"):
        _copy_derived_tables(target, candidate)
    with closing(sqlite3.connect(target)) as conn:
        assert list(conn.iterdump()) == before


def test_install_rejects_source_drift_without_secondary_writes(tmp_path: Path) -> None:
    target, candidate, _keys = _paths(tmp_path)
    with closing(sqlite3.connect(target)) as conn:
        conn.execute(
            "UPDATE tracks SET track_name=track_name||' changed' WHERE track_id=(SELECT MIN(track_id) FROM tracks)"
        )
        conn.commit()
    with closing(sqlite3.connect(target)) as conn:
        before = list(conn.iterdump())
    with pytest.raises(ValueError, match="source changed"):
        _copy_derived_tables(target, candidate)
    with closing(sqlite3.connect(target)) as conn:
        assert list(conn.iterdump()) == before
