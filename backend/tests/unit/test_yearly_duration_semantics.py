from __future__ import annotations

import pandas as pd

from backend.domains.ai_reports.yearly_contract import (
    build_same_period_comparison_from_frame,
)
from backend.domains.playback.logical_timeline import attach_listening_duration_frame


def test_same_period_comparison_uses_attached_duration_and_event_counts() -> None:
    events = pd.DataFrame(
        [
            {
                "play_id": 1,
                "track_id": 10,
                "artist_name": "Artist",
                "ms_played": 180_000,
                "ts_date": "2025-01-01",
                "ts_year": 2025,
            },
            {
                "play_id": 2,
                "track_id": 10,
                "artist_name": "Artist",
                "ms_played": 180_000,
                "ts_date": "2026-01-01",
                "ts_year": 2026,
            },
        ]
    )
    duration = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        "play_id": 3 + offset,
                        "track_id": 10,
                        "artist_name": "Artist",
                        "ms_played": 20_000,
                        "ts_date": "2026-01-01",
                        "ts_year": 2026,
                    }
                    for offset in range(180)
                ]
            ),
        ],
        ignore_index=True,
    )
    attach_listening_duration_frame(events, duration)

    result = build_same_period_comparison_from_frame(
        events,
        year=2026,
        start_date="2026-01-01",
        end_date="2026-01-01",
    )

    assert result is not None
    assert result["current"]["plays"] == 1
    assert result["previous"]["plays"] == 1
    assert result["current"]["hours"] == 1.1
    assert result["previous"]["hours"] == 0.1
