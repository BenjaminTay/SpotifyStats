from __future__ import annotations

import pandas as pd

from backend.domains.yearly_review.comparison_window import (
    aligned_comparison_frames,
    previous_year_date,
)


def test_ytd_comparison_uses_same_calendar_window_in_previous_year() -> None:
    frame = pd.DataFrame(
        {
            "ts_date": [
                "2025-01-01",
                "2025-07-24",
                "2025-12-31",
                "2026-01-01",
                "2026-07-24",
            ],
            "ms_played": [1, 2, 100, 3, 4],
        }
    )

    result = aligned_comparison_frames(
        frame,
        report_year=2026,
        observed_start="2026-01-01",
        observed_end="2026-07-24",
    )

    assert result.current["ms_played"].sum() == 7
    assert result.baseline["ms_played"].sum() == 3
    assert result.current_start == "2026-01-01"
    assert result.current_end == "2026-07-24"
    assert result.baseline_start == "2025-01-01"
    assert result.baseline_end == "2025-07-24"


def test_previous_year_date_clamps_leap_day() -> None:
    assert previous_year_date("2024-02-29") == "2023-02-28"
