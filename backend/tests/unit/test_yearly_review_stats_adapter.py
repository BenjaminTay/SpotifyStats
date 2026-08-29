from __future__ import annotations

import sqlite3

import pandas as pd

from backend.domains.yearly_review import stats_adapter
from backend.models.yearly_review import YearlyReviewFilterContext


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
        bb_week_start_hour=12,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="a",
        artist_identity_revision=1,
        track_credit_revision=1,
        track_group_revision="t",
        album_project_revision="p",
        filter_fingerprint="f",
    )


def _frame() -> pd.DataFrame:
    rows = []
    for play_id, date, month, hour in (
        (1, "2025-01-02", 1, 8),
        (2, "2025-03-05", 3, 22),
        (3, "2025-07-10", 7, 22),
        (4, "2025-12-11", 12, 23),
        (5, "2024-12-11", 12, 23),
    ):
        parsed = pd.Timestamp(date)
        rows.append(
            {
                "play_id": play_id,
                "track_id": play_id,
                "track_name": f"Track {play_id}",
                "album_name": "Album",
                "artist_name": "Artist",
                "ms_played": 3_600_000,
                "ts": f"{date}T{hour:02d}:00:00",
                "ts_date": date,
                "ts_year": parsed.year,
                "ts_month": month,
                "ts_hour": hour,
                "ts_dow": parsed.dayofweek,
                "platform": "ios",
                "reason_start": "trackdone",
                "reason_end": "trackdone",
                "shuffle": False,
            }
        )
    return pd.DataFrame(rows)


def test_builds_time_distributions_and_stable_taste_slices(monkeypatch) -> None:
    calls: list[int] = []

    def fake_taste(_conn, frame):
        calls.append(len(frame))
        return {"display_taxonomy_version": "consumer_v1", "plays_seen": len(frame)}

    monkeypatch.setattr(stats_adapter, "build_consumer_taste_profile", fake_taste)
    result = stats_adapter.build_yearly_stats(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        event_frame=_frame(),
    )

    assert result["summary"]["total_plays"] == 4
    assert result["summary"]["total_hours"] == 4.0
    assert len(result["hourly_distribution"]) == 24
    assert len(result["weekday_distribution"]) == 7
    assert len(result["monthly_distribution"]) == 12
    assert result["monthly_distribution"][0]["active_days"] == 1
    assert [item["slice_key"] for item in result["taste_slices"]] == [
        "q1",
        "q2",
        "q3",
        "q4",
        "first_half",
        "second_half",
    ]
    assert result["taste_slices"][0]["plays"] == 2
    assert result["taste_slices"][3]["plays"] == 1
    assert result["release_era_profile"]["known_pct"] == 0.0
    assert all("release_era" in item for item in result["taste_slices"])
    assert calls == [4, 2, 0, 1, 1, 2, 2]


def test_empty_year_keeps_all_buckets_and_slices(monkeypatch) -> None:
    monkeypatch.setattr(
        stats_adapter,
        "build_consumer_taste_profile",
        lambda _conn, frame: {"plays_seen": len(frame)},
    )
    result = stats_adapter.build_yearly_stats(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        event_frame=pd.DataFrame(),
    )

    assert result["empty"] is True
    assert len(result["monthly_distribution"]) == 12
    assert len(result["taste_slices"]) == 6
    assert result["release_era_profile"] == {
        "known_pct": 0.0,
        "unknown_hours": 0.0,
        "buckets": [],
    }


def test_comparison_stats_only_builds_time_facts() -> None:
    result = stats_adapter.build_yearly_comparison_stats(
        2025,
        event_frame=_frame(),
    )

    assert result["summary"]["total_plays"] == 4
    assert result["summary"]["total_hours"] == 4.0
    assert len(result["hourly_distribution"]) == 24
    assert len(result["monthly_distribution"]) == 12
    assert "taste_profile" not in result
    assert "taste_slices" not in result


def test_release_era_distribution_preserves_unknown_time(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {"track_name": "Old", "artist_name": "A", "ms_played": 3_600_000},
            {"track_name": "New", "artist_name": "B", "ms_played": 7_200_000},
            {"track_name": "Missing", "artist_name": "C", "ms_played": 3_600_000},
        ]
    )
    monkeypatch.setattr(
        stats_adapter,
        "_fetch_track_release_years",
        lambda _conn, _pairs: {("Old", "A"): 1998, ("New", "B"): 2024},
    )

    result = stats_adapter.build_release_era_distribution(sqlite3.connect(":memory:"), frame)

    assert result["known_pct"] == 75.0
    assert result["unknown_hours"] == 1.0
    assert result["buckets"] == [
        {"key": "2020s", "label": "2020s", "hours": 2.0, "share_pct": 50.0},
        {"key": "1990s", "label": "1990s", "hours": 1.0, "share_pct": 25.0},
        {"key": "unknown", "label": "未知年代", "hours": 1.0, "share_pct": 25.0},
    ]
