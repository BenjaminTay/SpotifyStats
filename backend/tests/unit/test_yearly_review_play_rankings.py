from __future__ import annotations

import sqlite3

import pandas as pd

from backend.domains.yearly_review import play_rankings
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


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "play_id": 1,
                "track_id": 10,
                "track_name": "Song",
                "album_name": "Album",
                "artist_name": "Artist",
                "ms_played": 180_000,
                "ts": "2025-01-02T10:00:00",
                "ts_date": "2025-01-02",
                "ts_month": 1,
                "ts_year": 2025,
            },
            {
                "play_id": 2,
                "track_id": 10,
                "track_name": "Song",
                "album_name": "Album",
                "artist_name": "Artist",
                "ms_played": 180_000,
                "ts": "2025-02-03T10:00:00",
                "ts_date": "2025-02-03",
                "ts_month": 2,
                "ts_year": 2025,
            },
            {
                "play_id": 3,
                "track_id": 10,
                "track_name": "Song",
                "album_name": "Album",
                "artist_name": "Artist",
                "ms_played": 180_000,
                "ts": "2024-12-31T10:00:00",
                "ts_date": "2024-12-31",
                "ts_month": 12,
                "ts_year": 2024,
            },
        ]
    )


def test_builds_two_rankings_and_enriches_activity(monkeypatch) -> None:
    events = _events()
    annual = events[events["ts_year"] == 2025].copy()
    track_frame = annual.assign(canonical_track_id=10.0)
    album_frame = annual.assign(album_project_id=99.0)
    artist_frame = annual.copy()

    def fake_chart_rows(_conn, _frame, entity, metric, **_kwargs):
        base = {"rank": 1, "plays": 2, "hours": 0.1, "share_pct": 100.0}
        if entity == "track":
            base.update(track_id=10, track_name="Song", artist_name="Artist")
        elif entity == "album":
            base.update(album_project_id=99, album_name="Album", artist_name="Artist")
        else:
            base.update(artist_name="Artist")
        return 7, [{**base, "metric_seen": metric}]

    monkeypatch.setattr(play_rankings, "chart_rows", fake_chart_rows)
    result = play_rankings.build_play_rankings(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        event_frame=events,
        entity_frames=(track_frame, album_frame, artist_frame),
    )

    track = result["charts"]["track"]
    album = result["charts"]["album"]
    artist = result["charts"]["artist"]
    assert result["limits"] == {"track": 50, "album": 30, "artist": 30}
    assert track["available_count"] == 7
    assert track["by_plays"][0]["sort_metric"] == "plays"
    assert track["by_hours"][0]["sort_metric"] == "hours"
    assert track["by_plays"][0]["active_days"] == 2
    assert track["by_plays"][0]["active_months"] == 2
    assert track["by_plays"][0]["first_played"] == "2025-01-02"
    assert track["by_plays"][0]["last_played"] == "2025-02-03"
    assert track["by_plays"][0]["deep_link"] == "/music/tracks/10"
    assert album["by_plays"][0]["identity_key"] == "album-project:99"
    assert artist["by_plays"][0]["share_pct"] == 100.0
    assert artist["by_plays"][0]["share_denominator"] == 2
    assert artist["by_plays"][0]["share_denominator_scope"] == ("annual_logical_play_events")


def test_empty_year_has_stable_empty_contract() -> None:
    result = play_rankings.build_play_rankings(
        sqlite3.connect(":memory:"),
        2025,
        _context(),
        event_frame=pd.DataFrame(),
    )

    assert result["empty"] is True
    assert result["charts"]["track"]["by_plays"] == []
    assert result["charts"]["album"]["available_count"] == 0


def test_comparison_counts_use_canonical_album_project_aggregation(monkeypatch) -> None:
    events = _events().query("ts_year == 2025").copy()
    track_frame = events.assign(canonical_track_id=events["track_id"])
    album_frame = events.assign(album_project_id=[101.0, 202.0])
    artist_frame = events.assign(artist_name=["Artist", "Featured"])

    def fake_album_projects(*_args, **_kwargs):
        return pd.DataFrame(
            {
                "album_project_id": [101],
                "play_count": [2],
            }
        )

    monkeypatch.setattr(
        "backend.domains.playback.album_projects.compute_album_project_plays",
        fake_album_projects,
    )
    result = play_rankings.build_play_ranking_counts(
        sqlite3.connect(":memory:"),
        _context(),
        event_frame=events,
        entity_frames=(track_frame, album_frame, artist_frame),
    )

    assert result == {"track": 1, "album": 1, "artist": 2}
