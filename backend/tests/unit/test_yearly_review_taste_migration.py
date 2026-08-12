from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pandas as pd

from backend.domains.yearly_review import taste_migration
from backend.domains.yearly_review.taste_migration import (
    build_taste_drivers,
    build_taste_migration,
)
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewCoverage,
    YearlyTasteAxisCoverage,
    YearlyTasteCoverage,
)


def _profile(style: float, scene: float, language: float) -> dict:
    return {
        "primary_styles": {
            "buckets": [
                {"key": "pop", "label": "Pop", "share_pct": style},
                {"key": "rock", "label": "Rock", "share_pct": 100 - style},
            ]
        },
        "regional_pop": {
            "buckets": [
                {"key": "c-pop", "label": "C-Pop", "share_pct": scene},
                {"key": "unknown", "label": "尚未归类", "share_pct": 100 - scene},
            ]
        },
        "language_dist": {
            "buckets": [
                {"key": "zh", "label": "中文", "share_pct": language},
                {"key": "en", "label": "英文", "share_pct": 100 - language},
            ]
        },
    }


def _coverage() -> YearlyReviewCoverage:
    return YearlyReviewCoverage(
        status="complete",
        play=YearlyPlayCoverage(status="complete"),
        billboard=YearlyBillboardCoverage(status="complete", source_status="complete"),
        comparison=YearlyComparisonCoverage(),
        taste=YearlyTasteCoverage(
            style=YearlyTasteAxisCoverage(
                known_pct=92, level="core", conclusion_allowed=True, caveat_required=False
            ),
            scene=YearlyTasteAxisCoverage(
                known_pct=30, level="insufficient", conclusion_allowed=False
            ),
            language=YearlyTasteAxisCoverage(
                known_pct=98, level="core", conclusion_allowed=True, caveat_required=False
            ),
        ),
    )


def test_migration_requires_coverage_and_named_driver() -> None:
    stats = {
        "taste_profile": _profile(60, 30, 50),
        "taste_slices": [
            {"slice_key": "first_half", "taste_profile": _profile(40, 20, 30)},
            {"slice_key": "second_half", "taste_profile": _profile(70, 50, 60)},
        ],
    }
    result = build_taste_migration(
        stats,
        _coverage(),
        drivers={
            "style": {
                "pop": [
                    {
                        "entity_type": "artist",
                        "name": "Driver Artist",
                        "driver_share_pct": 70,
                    }
                ]
            },
            "language": {
                "zh": [
                    {
                        "entity_type": "artist",
                        "name": "Chinese Artist",
                        "driver_share_pct": 45,
                    }
                ]
            },
        },
    )

    ids = {item.headline_id for item in result.observations}
    assert "taste_migration_style" in ids
    assert "taste_migration_language" in ids
    assert "taste_migration_scene" not in ids
    assert result.coverage_notes["scene"] == "暂无法判断"
    assert any(row["key"] == "unknown" for row in result.distributions["scene"])


def test_high_coverage_without_driver_does_not_invent_cause() -> None:
    stats = {
        "taste_profile": _profile(60, 30, 50),
        "taste_slices": [
            {"slice_key": "first_half", "taste_profile": _profile(40, 20, 30)},
            {"slice_key": "second_half", "taste_profile": _profile(70, 50, 60)},
        ],
    }
    result = build_taste_migration(stats, _coverage())

    assert result.observations == []
    assert result.changes["style"][0]["delta_pct"] == 30.0


def test_release_era_migration_uses_embedded_profiles_and_explicit_unknown() -> None:
    stats = {
        "taste_profile": _profile(60, 30, 50),
        "release_era_profile": {
            "known_pct": 90,
            "unknown_hours": 1,
            "buckets": [
                {"key": "2020s", "share_pct": 60},
                {"key": "unknown", "share_pct": 10},
            ],
        },
        "taste_slices": [
            {
                "slice_key": "first_half",
                "taste_profile": _profile(40, 20, 30),
                "release_era": {
                    "buckets": [
                        {"key": "2020s", "share_pct": 40},
                        {"key": "unknown", "share_pct": 10},
                    ]
                },
            },
            {
                "slice_key": "second_half",
                "taste_profile": _profile(70, 50, 60),
                "release_era": {
                    "buckets": [
                        {"key": "2020s", "share_pct": 70},
                        {"key": "unknown", "share_pct": 10},
                    ]
                },
            },
        ],
    }
    coverage = _coverage()
    coverage.taste.release_era = YearlyTasteAxisCoverage(
        known_pct=90,
        unknown_hours=1,
        level="core",
        conclusion_allowed=True,
        caveat_required=False,
    )

    result = build_taste_migration(
        stats,
        coverage,
        drivers={
            "release_era": {
                "2020s": [
                    {
                        "entity_type": "track",
                        "entity_id": 3,
                        "name": "New Track",
                        "artist_name": "Artist",
                        "delta_share_pct": 30,
                        "driver_share_pct": 55,
                    }
                ]
            }
        },
    )

    assert result.changes["release_era"][0]["delta_pct"] == 30.0
    assert any(row["key"] == "unknown" for row in result.distributions["release_era"])
    assert result.observations[0].headline_id == "taste_migration_release_era"


def test_driver_builder_uses_governed_genre_and_language_resolvers(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT)")
    conn.executemany("INSERT INTO artists VALUES (?, ?)", [(1, "Early"), (2, "Late")])
    monkeypatch.setattr(
        taste_migration,
        "build_primary_artist_ms",
        lambda _conn, frame: ({int(frame.iloc[0]["track_id"]): 3_600_000}, 0),
    )
    monkeypatch.setattr(
        taste_migration,
        "resolve_artist_genres_map",
        lambda _conn, names: {name: SimpleNamespace(name=name) for name in names},
    )
    monkeypatch.setattr(
        taste_migration,
        "display_style_keys",
        lambda fact: ["pop"] if fact.name == "Late" else ["rock"],
    )
    monkeypatch.setattr(taste_migration, "display_scene_keys", lambda _fact: [])
    monkeypatch.setattr(
        taste_migration,
        "resolve_artist_languages_map",
        lambda _conn, ids: {
            artist_id: SimpleNamespace(
                classification="single_language",
                primary_language_code="zh" if artist_id == 2 else "en",
            )
            for artist_id in ids
        },
    )
    monkeypatch.setattr(
        taste_migration,
        "_fetch_track_release_years",
        lambda _conn, _pairs: {("Old Song", "Early"): 1998, ("New Song", "Late"): 2024},
    )
    early = pd.DataFrame(
        {
            "track_id": [1],
            "track_name": ["Old Song"],
            "artist_name": ["Early"],
            "ms_played": [3_600_000],
        }
    )
    late = pd.DataFrame(
        {
            "track_id": [2],
            "track_name": ["New Song"],
            "artist_name": ["Late"],
            "ms_played": [3_600_000],
        }
    )
    result = build_taste_drivers(conn, early, late)

    assert result["style"]["pop"][0]["name"] == "Late"
    assert result["style"]["pop"][0]["delta_share_pct"] == 100.0
    assert result["language"]["zh"][0]["name"] == "Late"
    assert result["release_era"]["2020s"][0]["name"] == "New Song"
    assert result["release_era"]["2020s"][0]["delta_share_pct"] == 100.0


def test_ytd_taste_migration_compares_completed_quarters_not_partial_half() -> None:
    stats = {
        "year": 2026,
        "taste_profile": _profile(60, 30, 50),
        "taste_slices": [
            {"slice_key": "q1", "taste_profile": _profile(40, 20, 30)},
            {"slice_key": "q2", "taste_profile": _profile(70, 50, 60)},
            {"slice_key": "first_half", "taste_profile": _profile(55, 35, 45)},
            {"slice_key": "second_half", "taste_profile": _profile(100, 100, 100)},
        ],
    }
    coverage = _coverage()
    coverage.status = "year_to_date"
    coverage.play.status = "year_to_date"
    coverage.play.observed_start = "2026-01-01"
    coverage.play.observed_end = "2026-07-24"

    result = build_taste_migration(stats, coverage)

    assert result.comparison.mode == "completed_quarters"
    assert result.comparison.status == "available"
    assert result.comparison.from_slice_key == "q1"
    assert result.comparison.to_slice_key == "q2"
    assert result.comparison.from_label == "第一季度"
    assert result.comparison.to_label == "第二季度"
    assert result.comparison.from_start == "2026-01-01"
    assert result.comparison.to_end == "2026-06-30"
    assert result.changes["style"][0]["delta_pct"] == 30.0


def test_early_ytd_taste_migration_is_distribution_only() -> None:
    stats = {
        "year": 2026,
        "taste_profile": _profile(60, 30, 50),
        "taste_slices": [
            {"slice_key": "q1", "taste_profile": _profile(40, 20, 30)},
        ],
    }
    coverage = _coverage()
    coverage.status = "year_to_date"
    coverage.play.status = "year_to_date"
    coverage.play.observed_start = "2026-01-01"
    coverage.play.observed_end = "2026-04-15"

    result = build_taste_migration(stats, coverage)

    assert result.comparison.mode == "distribution_only"
    assert result.comparison.status == "insufficient_completed_periods"
    assert result.observations == []
    assert all(rows == [] for rows in result.changes.values())
