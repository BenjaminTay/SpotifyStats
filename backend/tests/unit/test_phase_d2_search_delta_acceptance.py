from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import phase_d2_search_delta_acceptance as acceptance

pytestmark = pytest.mark.unit


def test_parse_args_preserves_within_week_default_and_accepts_cross_week() -> None:
    default = acceptance.parse_args([])
    cross_week = acceptance.parse_args(["--scenario", "cross-week"])

    assert default.scenario == "within-open-week"
    assert cross_week.scenario == "cross-week"


def test_cross_week_boundary_places_entire_event_in_next_open_week() -> None:
    boundary = acceptance._compute_cross_week_boundary(
        old_end=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        duration_ms=60_000,
        week_start_dow=4,
        week_start_hour=0,
        margin_seconds=1.0,
    )

    assert boundary.previous_open_week == date(2025, 12, 26)
    assert boundary.current_open_week == date(2026, 1, 2)
    assert boundary.gap_seconds == 14_401.0


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


def test_cross_week_scope_requires_exact_adjacent_open_weeks() -> None:
    boundary = acceptance.CrossWeekBoundary(
        gap_seconds=1.0,
        previous_open_week=date(2026, 8, 21),
        current_open_week=date(2026, 8, 28),
    )
    valid = SimpleNamespace(
        strategy="incremental",
        added_count=1,
        removed_count=0,
        previous_open_week="2026-08-21",
        current_open_week="2026-08-28",
        billboard_weeks=("2026-08-21", "2026-08-28"),
        billboard_scope_exact=True,
    )
    acceptance._assert_cross_week_scope(valid, boundary)

    for override in (
        {"current_open_week": "2026-09-04"},
        {"billboard_weeks": ("2026-08-28",)},
        {"billboard_weeks": ("2026-08-14", "2026-08-21", "2026-08-28")},
        {"billboard_scope_exact": False},
        {"removed_count": 1},
    ):
        values = vars(valid) | override
        with pytest.raises(acceptance.AcceptanceError):
            acceptance._assert_cross_week_scope(SimpleNamespace(**values), boundary)


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
    assert report["delta_lineage_ready"] is False  # the production gate requires all four
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


def _create_week_transition_database(
    path: Path,
    variants: tuple[acceptance.SnapshotVariant, ...],
    *,
    target: bool,
) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE music_search_weekly_chart_context(
               snapshot_key TEXT, family TEXT, week TEXT, entity_key TEXT, rank INTEGER,
               play_count INTEGER, total_ms INTEGER, stable_sort_key TEXT
           )"""
    )
    for variant in variants:
        conn.execute(
            "INSERT INTO music_search_weekly_chart_context VALUES (?,?,?,?,?,?,?,?)",
            (
                variant.fingerprint,
                "track",
                "2026-08-14",
                "track:private",
                1,
                1,
                60_000,
                "private-stable-key",
            ),
        )
        if target:
            conn.execute(
                "INSERT INTO music_search_weekly_chart_context VALUES (?,?,?,?,?,?,?,?)",
                (
                    variant.fingerprint,
                    "track",
                    "2026-08-21",
                    "track:private",
                    1,
                    2,
                    120_000,
                    "private-stable-key",
                ),
            )
    conn.commit()
    conn.close()


def test_cross_week_transition_proves_publication_exclusion_and_privacy(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "baseline.db"
    delta_path = tmp_path / "delta.db"
    full_path = tmp_path / "full.db"
    matrix = ((2, True), (3, True), (2, False), (3, False))
    baseline_variants = tuple(
        acceptance.SnapshotVariant(f"base-{index}", merge_level, dynamic)
        for index, (merge_level, dynamic) in enumerate(matrix)
    )
    target_variants = tuple(
        acceptance.SnapshotVariant(f"target-{index}", merge_level, dynamic)
        for index, (merge_level, dynamic) in enumerate(matrix)
    )
    _create_week_transition_database(baseline_path, baseline_variants, target=False)
    _create_week_transition_database(delta_path, target_variants, target=True)
    _create_week_transition_database(full_path, target_variants, target=True)
    boundary = acceptance.CrossWeekBoundary(
        gap_seconds=1.0,
        previous_open_week=date(2026, 8, 21),
        current_open_week=date(2026, 8, 28),
    )

    acceptance._assert_baseline_open_weeks_unpublished(
        baseline_path,
        baseline_variants,
        boundary,
    )
    report = acceptance._compare_cross_week_transition(
        baseline_path,
        delta_path,
        full_path,
        baseline_variants=baseline_variants,
        target_variants=target_variants,
        boundary=boundary,
    )

    assert report["passed"] is True
    assert report["baseline_open_week_excluded"] is True
    assert report["newly_completed_week_published"] is True
    assert report["current_open_week_excluded"] is True
    assert report["historical_weeks_unchanged"] is True
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert "2026-08-21" not in encoded
    assert "2026-08-28" not in encoded
    assert "track:private" not in encoded
    assert "private-stable-key" not in encoded
    assert acceptance.PRIVACY_REPORT["week_boundary_values_emitted"] is False

    conn = sqlite3.connect(delta_path)
    conn.execute(
        "INSERT INTO music_search_weekly_chart_context VALUES (?,?,?,?,?,?,?,?)",
        (
            target_variants[0].fingerprint,
            "track",
            "2026-08-28",
            "track:private",
            1,
            1,
            60_000,
            "private-stable-key",
        ),
    )
    conn.commit()
    conn.close()
    rejected = acceptance._compare_cross_week_transition(
        baseline_path,
        delta_path,
        full_path,
        baseline_variants=baseline_variants,
        target_variants=target_variants,
        boundary=boundary,
    )
    assert rejected["passed"] is False
    assert rejected["current_open_week_excluded"] is False
