from __future__ import annotations

import sqlite3

import pandas as pd

from backend.core.db import load_plays_for_artists
from backend.services import analysis_stats_service


def test_artist_chart_loads_only_the_credited_artist_frame(monkeypatch) -> None:
    calls: list[object] = []
    frame = pd.DataFrame(
        [
            {
                "track_id": 1,
                "artist_name": "Artist",
                "album_name": "Album",
                "ts": "2025-01-01T00:00:00",
                "ts_date": "2025-01-01",
                "ms_played": 60_000,
            }
        ]
    )

    def fake_load_period_plays(*args, **kwargs):
        calls.append(kwargs.get("_loader"))
        return (
            frame,
            frame,
            {
                "period": "custom",
                "label": "自定义",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
        )

    monkeypatch.setattr(analysis_stats_service, "load_period_plays", fake_load_period_plays)
    monkeypatch.setattr(
        analysis_stats_service,
        "chart_rows",
        lambda *args, **kwargs: (1, [{"rank": 1, "artist_name": "Artist", "plays": 1}]),
    )

    with sqlite3.connect(":memory:") as conn:
        result = analysis_stats_service._build_analysis_charts(
            conn,
            min_ms=30_000,
            music_only=True,
            merge_enabled=True,
            period="custom",
            start_date="2025-01-01",
            end_date="2025-12-31",
            entity="artist",
            metric="plays",
            limit=5,
            offset=0,
        )

    assert calls == [load_plays_for_artists]
    assert result["total"] == 1
    assert result["rows"][0]["artist_name"] == "Artist"
