import pandas as pd

from backend.domains.billboard.chart_ranking import _add_running_metrics


def test_add_running_metrics_matches_group_peak_week_semantics():
    weekly = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2024-01-05"),
                "track_id": 1,
                "rank": 5,
                "play_count": 10,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-12"),
                "track_id": 1,
                "rank": 3,
                "play_count": 12,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-19"),
                "track_id": 1,
                "rank": 3,
                "play_count": 11,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-05"),
                "track_id": 2,
                "rank": 1,
                "play_count": 20,
            },
        ]
    )

    result = _add_running_metrics(weekly, ["track_id"])

    track_one = result[result["track_id"] == 1].sort_values("billboard_week")
    assert track_one["running_peak"].tolist() == [5, 3, 3]
    assert track_one["running_wks"].tolist() == [1, 2, 3]
    assert track_one["running_peak_wks"].tolist() == [1, 1, 2]

    track_two = result[result["track_id"] == 2].iloc[0]
    assert track_two["running_peak"] == 1
    assert track_two["running_wks"] == 1
    assert track_two["running_peak_wks"] == 1
    assert "_peak_week" not in result.columns


def test_add_running_metrics_accepts_empty_frame():
    empty = pd.DataFrame(columns=["billboard_week", "track_id", "rank"])

    result = _add_running_metrics(empty, ["track_id"])

    assert result.empty
