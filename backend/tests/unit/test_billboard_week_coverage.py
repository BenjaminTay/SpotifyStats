from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.domains.billboard.week_coverage import (
    keep_complete_billboard_weeks,
    open_billboard_week_for_latest_timestamp,
)
from backend.domains.playback.logical_timeline import (
    attach_billboard_weighted_frame,
    get_billboard_weighted_frame,
)

pytestmark = pytest.mark.unit


def test_latest_play_marks_its_containing_chart_week_as_open() -> None:
    # 2026-08-21 15:39 UTC is Friday 23:39 in Asia/Shanghai.  With a Friday
    # noon boundary, the new week has only been observed for about 12 hours.
    assert open_billboard_week_for_latest_timestamp(
        "2026-08-21T15:39:05Z",
        week_start_dow=4,
        week_start_hour=12,
    ) == date(2026, 8, 21)


def test_timestamp_before_noon_keeps_the_previous_friday_as_open() -> None:
    assert open_billboard_week_for_latest_timestamp(
        "2026-08-21T03:59:59Z",
        week_start_dow=4,
        week_start_hour=12,
    ) == date(2026, 8, 14)


def test_complete_week_filter_drops_open_week_from_events_and_weights() -> None:
    events = pd.DataFrame(
        {
            "billboard_week": [date(2026, 8, 7), date(2026, 8, 14), date(2026, 8, 21)],
            "play_count": [1, 1, 1],
        }
    )
    weighted = pd.DataFrame(
        {
            "billboard_week": [
                date(2026, 8, 7),
                date(2026, 8, 14),
                date(2026, 8, 21),
                date(2026, 8, 21),
            ],
            "play_count": [1, 0, 1, 0],
        }
    )
    attach_billboard_weighted_frame(events, weighted)

    result = keep_complete_billboard_weeks(events, open_week=date(2026, 8, 21))

    assert result["billboard_week"].tolist() == [date(2026, 8, 7), date(2026, 8, 14)]
    filtered_weighted = get_billboard_weighted_frame(result)
    assert filtered_weighted is not None
    assert filtered_weighted["billboard_week"].tolist() == [
        date(2026, 8, 7),
        date(2026, 8, 14),
    ]
