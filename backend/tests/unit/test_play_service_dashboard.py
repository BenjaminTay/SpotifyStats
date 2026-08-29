from __future__ import annotations

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


def test_get_random_track_reuses_preloaded_dataframe(monkeypatch):
    from backend.services import play_service

    df = pd.DataFrame(
        [
            {
                "play_id": 1,
                "track_id": 10,
                "track_name": "Once Cached",
                "artist_name": "Fast Path",
                "album_name": "Single Load",
                "ts_date": "2026-01-01",
            }
        ]
    )

    def fail_loader(*args, **kwargs):
        raise AssertionError("get_random_track should reuse the provided DataFrame")

    monkeypatch.setattr(play_service, "_load_filtered_plays", fail_loader)

    result = play_service.get_random_track(
        conn=None,
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        df=df,
    )

    assert result == {
        "track_name": "Once Cached",
        "artist_name": "Fast Path",
        "album_name": "Single Load",
        "last_played": "2026-01-01",
        "total_plays": 1,
    }


def test_get_top_tracks_resolves_covers_only_for_top_n(monkeypatch):
    from backend.services import play_service

    df = pd.DataFrame(
        [
            {
                "play_id": play_id,
                "track_id": track_id,
                "track_name": f"Track {track_id}",
                "artist_name": "Artist",
            }
            for play_id, track_id in enumerate([10, 10, 10, 20, 20, 30], start=1)
        ]
    )
    resolved_ids: list[int] = []

    def resolve_covers(_conn, track_ids):
        resolved_ids.extend(int(value) for value in track_ids)
        return {10: "/covers/albums/10.jpg"}

    monkeypatch.setattr(play_service, "_track_cover_urls", resolve_covers)

    result = play_service.get_top_tracks(
        conn=None,
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        n=1,
        df=df,
    )

    assert resolved_ids == [10]
    assert result == [
        {
            "track_id": 10,
            "track_name": "Track 10",
            "artist_name": "Artist",
            "plays": 3,
            "cover_url": "/covers/albums/10.jpg",
        }
    ]


def test_late_night_top_tracks_filters_early_hours(monkeypatch):
    from backend.services import play_service

    df = pd.DataFrame(
        [
            {
                "play_id": 1,
                "track_id": 10,
                "track_name": "Midnight Rain",
                "artist_name": "Taylor Swift",
                "ts_hour": 1,
                "ms_played": 180_000,
            },
            {
                "play_id": 2,
                "track_id": 10,
                "track_name": "Midnight Rain",
                "artist_name": "Taylor Swift",
                "ts_hour": 5,
                "ms_played": 120_000,
            },
            {
                "play_id": 3,
                "track_id": 20,
                "track_name": "Daylight",
                "artist_name": "Taylor Swift",
                "ts_hour": 13,
                "ms_played": 200_000,
            },
        ]
    )

    monkeypatch.setattr(play_service, "_load_filtered_plays", lambda *args, **kwargs: df)
    monkeypatch.setattr(
        play_service, "_track_cover_urls", lambda conn, track_ids: {10: "/covers/track/10.jpg"}
    )

    result = play_service.get_late_night_top_tracks(
        conn=None,
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        limit=10,
    )

    assert result["window"] == "00:00-05:59"
    assert result["total_late_night_plays"] == 2
    assert result["tracks"] == [
        {
            "rank": 1,
            "track_id": 10,
            "track_name": "Midnight Rain",
            "artist_name": "Taylor Swift",
            "plays": 2,
            "hours": 0.08,
            "share_pct": 100.0,
            "cover_url": "/covers/track/10.jpg",
        }
    ]
