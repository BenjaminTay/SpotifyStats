"""Independent release-cycle facts survive an empty playback window."""

import pandas as pd
import pytest

from backend.services.release_cycle_service import compute_release_metrics

pytestmark = pytest.mark.unit


def test_empty_playback_window_preserves_published_ranks_and_lifetime_half_life():
    metrics = compute_release_metrics(
        {
            "album_timeline": pd.DataFrame(),
            "album_ranks": pd.DataFrame(
                {
                    "billboard_week": ["2025-01-03", "2025-01-10", "2025-01-17"],
                    "week_offset": [0, 1, 2],
                    "rank": [8, 2, 2],
                    "play_count": [12, 20, 18],
                }
            ),
            "album_half_life": 32,
        }
    )

    assert metrics["debut_rank"] == 8
    assert metrics["peak_rank"] == 2
    assert metrics["weeks_to_peak"] == 1
    assert metrics["weeks_on_chart"] == 3
    assert metrics["half_life"] == 32
    assert metrics["release_week_plays"] == 0
    assert metrics["artist_impact"] is None
    assert metrics["market_impact"] is None


def test_zero_playback_without_chart_history_keeps_zero_and_missing_distinct():
    metrics = compute_release_metrics({"album_timeline": pd.DataFrame()})

    assert metrics["release_week_plays"] == 0
    assert metrics["peak_play_count"] == 0
    assert metrics["weeks_on_chart"] == 0
    assert metrics["debut_rank"] is None
    assert metrics["peak_rank"] is None
    assert metrics["weeks_to_peak"] is None
    assert metrics["half_life"] is None
    assert metrics["artist_impact"] is None
    assert metrics["market_impact"] is None
