import pandas as pd

from backend.domains.billboard.record_sequences import consecutive_chart_streaks


def test_consecutive_chart_streaks_keeps_the_longest_run_per_entity():
    frame = pd.DataFrame(
        [
            {"track_id": 1, "track_name": "One", "billboard_week": pd.Timestamp("2024-01-04")},
            {"track_id": 1, "track_name": "One", "billboard_week": pd.Timestamp("2024-01-11")},
            {"track_id": 1, "track_name": "One", "billboard_week": pd.Timestamp("2024-02-01")},
            {"track_id": 2, "track_name": "Two", "billboard_week": pd.Timestamp("2024-03-07")},
        ]
    )

    result = consecutive_chart_streaks(
        frame,
        group_columns=["track_id"],
        identity_columns=["track_id", "track_name"],
    ).set_index("track_id")

    assert int(result.loc[1, "连续周数"]) == 2
    assert result.loc[1, "起始周"] == pd.Timestamp("2024-01-04")
    assert result.loc[1, "结束周"] == pd.Timestamp("2024-01-11")
    assert int(result.loc[2, "连续周数"]) == 1
    assert result.loc[2, "起始周"] == result.loc[2, "结束周"]


def test_consecutive_chart_streaks_groups_composite_album_identity():
    frame = pd.DataFrame(
        [
            {
                "album_name": "Shared",
                "artist_name": "Artist A",
                "billboard_week": pd.Timestamp("2024-01-04"),
            },
            {
                "album_name": "Shared",
                "artist_name": "Artist A",
                "billboard_week": pd.Timestamp("2024-01-11"),
            },
            {
                "album_name": "Shared",
                "artist_name": "Artist B",
                "billboard_week": pd.Timestamp("2024-01-11"),
            },
        ]
    )

    result = consecutive_chart_streaks(
        frame,
        group_columns=["album_name", "artist_name"],
        identity_columns=["album_name", "artist_name"],
    ).set_index("artist_name")

    assert int(result.loc["Artist A", "连续周数"]) == 2
    assert int(result.loc["Artist B", "连续周数"]) == 1
