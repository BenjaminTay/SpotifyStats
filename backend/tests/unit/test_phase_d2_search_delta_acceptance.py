from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import phase_d2_search_delta_acceptance as acceptance

pytestmark = pytest.mark.unit


def test_same_open_week_gate_rejects_boundary_and_completed_week() -> None:
    acceptance._assert_same_open_week(
        SimpleNamespace(
            previous_open_week="2026-08-21",
            current_open_week="2026-08-21",
            billboard_weeks=("2026-08-21",),
            billboard_scope_exact=True,
        )
    )

    with pytest.raises(acceptance.AcceptanceError):
        acceptance._assert_same_open_week(
            SimpleNamespace(
                previous_open_week="2026-08-21",
                current_open_week="2026-08-28",
                billboard_weeks=("2026-08-21", "2026-08-28"),
                billboard_scope_exact=True,
            )
        )
    with pytest.raises(acceptance.AcceptanceError):
        acceptance._assert_same_open_week(
            SimpleNamespace(
                previous_open_week="2026-08-21",
                current_open_week="2026-08-21",
                billboard_weeks=("2026-08-14", "2026-08-21"),
                billboard_scope_exact=True,
            )
        )


def _create_comparison_database(path: Path, *, delta: bool) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE music_search_entity_context(
               snapshot_key TEXT, entity_key TEXT, play_events INTEGER, total_ms INTEGER,
               peak_position INTEGER, peak_weeks INTEGER, weeks_on_chart INTEGER,
               weeks_at_no1 INTEGER, power_score REAL, power_rank INTEGER,
               first_week TEXT, latest_week TEXT, first_peak_week TEXT
           )"""
    )
    conn.execute(
        """CREATE TABLE music_search_weekly_chart_context(
               snapshot_key TEXT, family TEXT, week TEXT, entity_key TEXT, rank INTEGER,
               play_count INTEGER, total_ms INTEGER, stable_sort_key TEXT
           )"""
    )
    conn.execute(
        """CREATE TABLE music_search_snapshot_meta(
               snapshot_key TEXT PRIMARY KEY, source_generation_id TEXT,
               source_dataset_digest TEXT, base_snapshot_key TEXT, build_strategy TEXT,
               dependency_digest TEXT, change_set_digest TEXT
           )"""
    )
    conn.execute(
        "INSERT INTO music_search_entity_context VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("target", "track:1", 2, 120000, 1, 1, 1, 1, 5.0, 1, "w", "w", "w"),
    )
    conn.execute(
        "INSERT INTO music_search_weekly_chart_context VALUES (?,?,?,?,?,?,?,?)",
        ("target", "track", "w", "track:1", 1, 1, 60000, "stable"),
    )
    if delta:
        conn.execute(
            "INSERT INTO music_search_snapshot_meta VALUES (?,?,?,?,?,?,?)",
            ("base", "base-gen", "before", None, "shared_full", "dep", None),
        )
        conn.execute(
            "INSERT INTO music_search_snapshot_meta VALUES (?,?,?,?,?,?,?)",
            ("target", "next-gen", "after", "base", "delta", "dep", "change"),
        )
    else:
        conn.execute(
            "INSERT INTO music_search_snapshot_meta VALUES (?,?,?,?,?,?,?)",
            ("target", "next-gen", "after", None, "shared_full", "dep", None),
        )
    conn.commit()
    conn.close()


def test_snapshot_comparison_checks_payload_ledger_and_delta_lineage(tmp_path: Path) -> None:
    delta = tmp_path / "delta.db"
    full = tmp_path / "full.db"
    _create_comparison_database(delta, delta=True)
    _create_comparison_database(full, delta=False)
    variants = (acceptance.SnapshotVariant("target", 2, True),)

    report = acceptance._compare_snapshot_outputs(
        delta,
        full,
        variants,
        baseline_digest="before",
        appended_digest="after",
    )
    assert report["contexts_equal"] is True
    assert report["delta_lineage_ready"] is False  # the production gate requires all six
    assert report["variants"][0]["lineage_ready"] is True
    assert report["variants"][0]["passed"] is True

    conn = sqlite3.connect(full)
    conn.execute(
        "UPDATE music_search_weekly_chart_context SET total_ms=total_ms+1 WHERE snapshot_key='target'"
    )
    conn.commit()
    conn.close()
    mismatch = acceptance._compare_snapshot_outputs(
        delta,
        full,
        variants,
        baseline_digest="before",
        appended_digest="after",
    )
    assert mismatch["contexts_equal"] is True
    assert mismatch["weekly_ledgers_equal"] is False
    assert mismatch["variants"][0]["ledger_delta_only_rows"] == 1
    assert mismatch["variants"][0]["ledger_reference_only_rows"] == 1
