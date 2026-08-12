from __future__ import annotations

import sqlite3

import pandas as pd

from backend.domains.yearly_review import playback_records_adapter
from backend.domains.yearly_review.playback_records_adapter import (
    build_playback_record_candidates,
    normalize_record_catalog,
)
from backend.models.yearly_review import YearlyReviewFilterContext


def _context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=45,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=12,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="a",
        artist_identity_revision=1,
        track_credit_revision=1,
        track_group_revision="t",
        album_project_revision="p",
        filter_fingerprint="f",
    )


def _records() -> dict:
    return {
        "obsession": {
            "daily_binge": {
                "track": [
                    {
                        "track_id": 12,
                        "track_name": "Loop",
                        "artist_name": "Singer",
                        "plays": 18,
                        "date": "2025-03-01",
                    }
                ]
            }
        },
        "longevity": {"user_active_streak": [{"streak_days": 42, "start_date": "2025-01-01"}]},
        "time_patterns": {
            "late_night_peak_day": [
                {"name": "深夜播放", "value": 31, "unit": "次", "date": "2025-06-01"}
            ]
        },
    }


def test_normalizes_nested_catalog_with_stable_provenance() -> None:
    first, counts = normalize_record_catalog(_records(), source="playback_records")
    second, _ = normalize_record_catalog(_records(), source="playback_records")

    assert counts == {"longevity": 1, "obsession": 1, "time_patterns": 1}
    assert first[0].candidate_id == second[0].candidate_id
    assert first[0].record_key == "obsession.daily_binge.track"
    assert first[0].entity_refs[0].deep_link == "/music/tracks/12"
    assert first[0].primary_metric.key == "plays"
    assert first[0].raw_values["date"] == "2025-03-01"
    assert first[1].eligible is True
    assert first[1].deep_link == "/analysis/records#longevity"
    assert first[2].primary_metric.label == "深夜播放"
    assert first[2].primary_metric.unit == "次"


def test_build_adapter_uses_injected_annual_payload_without_exposing_it_as_main_report() -> None:
    payload = {
        "period": {"period": "custom", "start_date": "2025-01-01", "end_date": "2025-12-31"},
        "meta": {"total_plays": 120},
        "records": _records(),
    }
    result = build_playback_record_candidates(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        payload=payload,
    )

    assert result["year"] == 2025
    assert result["catalog_counts"]["total"] == 3
    assert result["catalog_counts"]["eligible"] == 3
    assert result["period"]["start_date"] == "2025-01-01"


def test_build_adapter_reuses_preloaded_yearly_frames(monkeypatch) -> None:
    event_frame = pd.DataFrame([{"ts_date": "2025-01-01"}])
    entity_frames = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    captured = {}

    def fake_records(**kwargs):
        captured.update(kwargs)
        return {
            "period": {
                "period": "custom",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
            "meta": {"total_plays": 1},
            "records": {},
        }

    monkeypatch.setattr(
        playback_records_adapter,
        "_get_analysis_records_uncached",
        fake_records,
    )

    build_playback_record_candidates(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        event_frame=event_frame,
        entity_frames=entity_frames,
    )

    assert captured["preloaded_event_frame"] is event_frame
    assert captured["preloaded_entity_frames"] is entity_frames


def test_localized_billboard_record_keeps_track_reference() -> None:
    candidates, _ = normalize_record_catalog(
        {
            "championship": {
                "triple_no1": [{"track_id": 88, "歌曲": "三冠曲", "艺人": "歌手", "专辑": "专辑"}]
            }
        },
        source="billboard_records",
        fallback_base="/billboard/records",
    )

    assert candidates[0].entity_refs[0].entity_type == "track"
    assert candidates[0].entity_refs[0].name == "三冠曲"
    assert candidates[0].deep_link == "/music/tracks/88"
