from __future__ import annotations

import sqlite3

import pandas as pd

from backend.domains.yearly_review import orchestrator
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyFeaturedRecord,
    YearlyRecordsChapter,
    YearlyReviewFilterContext,
)


def _context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="artist-rev",
        artist_identity_revision=1,
        track_credit_revision=2,
        track_group_revision="track-rev",
        album_project_revision="album-rev",
        filter_fingerprint="fingerprint",
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "play_id": 1,
                "track_id": 1,
                "track_name": "Track",
                "artist_name": "Artist",
                "album_name": "Album",
                "ts_year": 2025,
                "ts_month": 1,
                "ts_date": "2025-01-01",
                "ts_hour": 20,
                "ts_dow": 2,
                "ms_played": 3_600_000,
            },
            {
                "play_id": 2,
                "track_id": 1,
                "track_name": "Track",
                "artist_name": "Artist",
                "album_name": "Album",
                "ts_year": 2024,
                "ts_month": 1,
                "ts_date": "2024-01-01",
                "ts_hour": 20,
                "ts_dow": 0,
                "ms_played": 3_600_000,
            },
        ]
    )


def _stats(year: int) -> dict:
    return {
        "year": year,
        "summary": {
            "total_plays": 1,
            "total_hours": 1.0,
            "active_days": 1,
            "unique_tracks": 1,
            "unique_albums": 1,
            "unique_artists": 1,
        },
        "monthly_distribution": [
            {"month": month, "plays": 1 if month == 1 else 0, "hours": 1 if month == 1 else 0}
            for month in range(1, 13)
        ],
        "hourly_distribution": [{"hour": hour, "plays": 0} for hour in range(24)],
        "weekday_distribution": [{"weekday": day, "plays": 0} for day in range(7)],
        "taste_profile": {},
        "release_era_profile": {},
        "taste_slices": [],
    }


def _billboard(year: int) -> dict:
    return {
        "year": year,
        "coverage": YearlyBillboardCoverage(status="empty", source_status="empty"),
        "meta": {},
        "charts": {"track": [], "album": [], "artist": []},
        "honors": {},
        "record_candidates": [],
        "record_catalog_counts": {"total": 0, "eligible": 0},
    }


def test_orchestrator_loads_play_and_entity_frames_once(monkeypatch) -> None:
    calls = {"plays": 0, "entities": 0, "stats": 0}
    frame = _frame()

    def fake_load(*_args, **_kwargs):
        calls["plays"] += 1
        return frame

    def fake_entities(*_args, **_kwargs):
        calls["entities"] += 1
        return frame.copy(), frame.copy(), frame.copy()

    def fake_stats(_conn, year, _context, **_kwargs):
        calls["stats"] += 1
        return _stats(year)

    monkeypatch.setattr(orchestrator, "load_plays", fake_load)
    monkeypatch.setattr(orchestrator, "_build_entity_frames", fake_entities)
    monkeypatch.setattr(orchestrator, "build_yearly_stats", fake_stats)
    monkeypatch.setattr(
        orchestrator,
        "build_play_rankings",
        lambda *_args, **_kwargs: orchestrator._empty_play_rankings(2025),
    )
    monkeypatch.setattr(orchestrator, "build_billboard_source", lambda *_args: _billboard(2025))
    monkeypatch.setattr(
        orchestrator,
        "build_playback_record_candidates",
        lambda *_args, **_kwargs: {"catalog_counts": {"total": 0}, "candidates": []},
    )
    curated_record = YearlyFeaturedRecord(
        record_id="curated-record",
        category="obsession",
        fact_type="track",
        title="年度精选",
        statement="只保留进入年报正文的精选纪录。",
        evidence_grade="A",
    )
    monkeypatch.setattr(
        orchestrator,
        "select_yearly_records",
        lambda *_args, **_kwargs: YearlyRecordsChapter(featured=[curated_record]),
    )
    monkeypatch.setattr(orchestrator, "build_taste_drivers", lambda *_args: {})

    result = orchestrator.build_yearly_review_artifact(
        sqlite3.connect(":memory:"), 2025, _context()
    )

    assert calls == {"plays": 1, "entities": 1, "stats": 1}
    assert result.report.filter_context.filter_fingerprint == "fingerprint"
    assert len(result.report.season.months) == 12
    assert result.record_catalog == [curated_record.model_dump(mode="json")]


def test_orchestrator_passes_only_aligned_ytd_baseline_to_comparison_consumers(
    monkeypatch,
) -> None:
    frame = pd.DataFrame(
        [
            {"ts_year": 2026, "ts_date": "2026-01-01", "ts_month": 1, "ms_played": 1},
            {"ts_year": 2026, "ts_date": "2026-07-24", "ts_month": 7, "ms_played": 2},
            {"ts_year": 2025, "ts_date": "2025-01-01", "ts_month": 1, "ms_played": 3},
            {"ts_year": 2025, "ts_date": "2025-07-24", "ts_month": 7, "ms_played": 4},
            {"ts_year": 2025, "ts_date": "2025-12-31", "ts_month": 12, "ms_played": 100},
        ]
    )
    captured: dict[str, int] = {}

    def fake_stats(_conn, year, _context, *, event_frame):
        captured[f"stats_{year}"] = int(event_frame["ms_played"].sum())
        stats = _stats(year)
        stats["summary"]["total_plays"] = len(event_frame)
        stats["summary"]["total_hours"] = float(event_frame["ms_played"].sum())
        return stats

    monkeypatch.setattr(
        orchestrator,
        "_build_entity_frames",
        lambda *_args, **_kwargs: (frame.copy(), frame.copy(), frame.copy()),
    )
    monkeypatch.setattr(orchestrator, "build_yearly_stats", fake_stats)
    monkeypatch.setattr(
        orchestrator,
        "build_play_rankings",
        lambda *_args, **_kwargs: orchestrator._empty_play_rankings(2026),
    )
    monkeypatch.setattr(orchestrator, "build_play_ranking_counts", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(orchestrator, "build_billboard_source", lambda *_args: _billboard(2026))
    monkeypatch.setattr(
        orchestrator,
        "build_playback_record_candidates",
        lambda *_args, **_kwargs: {"catalog_counts": {}, "candidates": []},
    )
    monkeypatch.setattr(orchestrator, "build_taste_drivers", lambda *_args: {})

    result = orchestrator.build_yearly_review_artifact(
        sqlite3.connect(":memory:"), 2026, _context(), event_frame=frame
    )

    assert result.report.coverage.comparison.comparable is True
    assert result.report.coverage.comparison.aligned_end == "2025-07-24"
    assert captured["stats_2025"] == 7
    hours = next(metric for metric in result.report.passport.metrics if metric.key == "total_hours")
    assert hours.comparison_value == 7.0


def test_noncritical_section_failure_degrades_without_losing_report(monkeypatch) -> None:
    frame = _frame()
    monkeypatch.setattr(
        orchestrator,
        "_build_entity_frames",
        lambda *_args, **_kwargs: (frame.copy(), frame.copy(), frame.copy()),
    )
    monkeypatch.setattr(
        orchestrator, "build_yearly_stats", lambda _conn, year, *_args, **_kwargs: _stats(year)
    )
    monkeypatch.setattr(
        orchestrator,
        "build_play_rankings",
        lambda *_args, **_kwargs: orchestrator._empty_play_rankings(2025),
    )
    monkeypatch.setattr(orchestrator, "build_billboard_source", lambda *_args: _billboard(2025))
    monkeypatch.setattr(
        orchestrator,
        "build_playback_record_candidates",
        lambda *_args, **_kwargs: {"catalog_counts": {}, "candidates": []},
    )
    monkeypatch.setattr(
        orchestrator, "build_honors", lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(
        orchestrator,
        "build_listening_life",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad chapter")),
    )
    monkeypatch.setattr(orchestrator, "build_taste_drivers", lambda *_args: {})

    result = orchestrator.build_yearly_review_artifact(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        event_frame=frame,
    )

    assert result.report.passport is not None
    assert result.report.honors.play_leaders == {}
    assert result.report.listening_life.observations == []
    assert any(
        item.startswith("section_unavailable:honors")
        for item in result.report.methodology.internal_diagnostics
    )
    assert any("年度荣誉" in item for item in result.report.methodology.limitations)
    assert any("收听生活" in item for item in result.report.methodology.limitations)
