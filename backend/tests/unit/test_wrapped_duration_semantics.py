from __future__ import annotations

import sqlite3
from typing import cast

import pandas as pd

from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.services import wrapped_service


def _row(*, play_id: int, year: int, ms_played: int) -> dict:
    return {
        "play_id": play_id,
        "track_id": 10,
        "track_name": "Song",
        "artist_name": "Artist",
        "album_name": "Album",
        "ms_played": ms_played,
        "ts": f"{year}-01-01T10:00:00Z",
        "ts_date": f"{year}-01-01",
        "ts_year": year,
        "ts_month": 1,
        "ts_hour": 10,
    }


def test_wrapped_uses_attached_duration_without_increasing_play_counts(monkeypatch) -> None:
    events = pd.DataFrame(
        [
            _row(play_id=1, year=2025, ms_played=180_000),
            _row(play_id=2, year=2024, ms_played=180_000),
        ]
    )
    duration = pd.DataFrame(
        [
            *events.to_dict("records"),
            _row(play_id=3, year=2025, ms_played=20_000),
        ]
    )
    attach_listening_duration_frame(events, duration)
    artist_events = events.copy()
    attach_listening_duration_frame(artist_events, duration.copy())

    monkeypatch.setattr(wrapped_service, "load_plays", lambda *_args, **_kwargs: events)
    monkeypatch.setattr(
        wrapped_service,
        "load_plays_for_artists",
        lambda *_args, **_kwargs: artist_events,
    )
    monkeypatch.setattr(wrapped_service, "_build_personality", lambda *_args: {})
    monkeypatch.setattr(
        wrapped_service,
        "_build_top_lists",
        lambda _conn, artist_agg, track_agg, album_agg: {
            "artist": artist_agg.reset_index().to_dict("records"),
            "track": track_agg.to_dict("records"),
            "album": album_agg.to_dict("records"),
        },
    )
    monkeypatch.setattr(wrapped_service, "_build_genre_panorama", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(wrapped_service, "_build_time_story", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(wrapped_service, "_build_music_map", lambda *_args: {})
    monkeypatch.setattr(wrapped_service, "_build_discovery_returns", lambda *_args: {})
    monkeypatch.setattr(wrapped_service, "_build_listening_depth", lambda *_args: {})
    monkeypatch.setattr(wrapped_service, "_build_special_moments", lambda *_args: {})
    monkeypatch.setattr(
        wrapped_service,
        "_build_monthly_drilldown",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(wrapped_service, "_build_comparison", lambda *_args, **_kwargs: {})

    result = wrapped_service._build_wrapped_full(
        cast(sqlite3.Connection, object()),
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        year=2025,
        merge_level=1,
    )

    assert result["hero"]["total_plays"] == 1
    assert result["hero"]["total_minutes"] == 3.0
    assert result["top_lists"]["track"][0]["plays"] == 1
    assert result["top_lists"]["track"][0]["hours"] == 200_000 / 3_600_000
