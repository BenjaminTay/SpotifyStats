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
