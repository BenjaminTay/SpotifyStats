import math

import pandas as pd

from backend.domains.billboard.chart_power_score import (
    _DEBUT_NO1_BONUS,
    _LONGEVITY_FACTOR,
    _PEAK_BONUS,
    _TOP1_BONUS,
    _base_score,
    _competition_factor,
    _indiv_factor_no1,
    _indiv_factor_non_no1,
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
)


def _expected_weekly_score(rank, plays, week_total, baseline, week_median, runner_up):
    indiv = (
        _indiv_factor_no1(plays, runner_up)
        if rank == 1
        else _indiv_factor_non_no1(plays, week_median)
    )
    return _base_score(rank) * _competition_factor(week_total, baseline) * indiv


def test_track_power_scores_preserve_scalar_formula():
    weekly = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2024-01-05"),
                "track_id": 1,
                "track_name": "Alpha",
                "artist_name": "Artist A",
                "rank": 1,
                "play_count": 100,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-05"),
                "track_id": 2,
                "track_name": "Beta",
                "artist_name": "Artist B",
                "rank": 2,
                "play_count": 50,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-12"),
                "track_id": 1,
                "track_name": "Alpha",
                "artist_name": "Artist A",
                "rank": 2,
                "play_count": 60,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-12"),
                "track_id": 2,
                "track_name": "Beta",
                "artist_name": "Artist B",
                "rank": 1,
                "play_count": 80,
            },
        ]
    )

    result = compute_power_scores(weekly, top_n=30).set_index("track_id")
    baseline = pd.Series([150, 140]).median()
    alpha_raw = _expected_weekly_score(1, 100, 150, baseline, 75, 50) + _expected_weekly_score(
        2, 60, 140, baseline, 70, 60
    )
    expected_alpha = round(
        alpha_raw + math.sqrt(2) * _LONGEVITY_FACTOR + _PEAK_BONUS[1] + _DEBUT_NO1_BONUS
    )

    assert result.loc[1, "power_score"] == expected_alpha
    assert result.loc[1, "peak_position"] == 1
    assert result.loc[1, "weeks_on_chart"] == 2
    assert result.loc[1, "weeks_top5"] == 2
    assert result.loc[1, "weeks_top10"] == 2
    assert result.loc[1, "weeks_at_peak"] == 1


def test_album_and_artist_power_scores_preserve_no1_bonus():
    weekly_album = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2024-01-05"),
                "album_name": "Album A",
                "artist_name": "Artist A",
                "rank": 1,
                "play_count": 120,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-12"),
                "album_name": "Album A",
                "artist_name": "Artist A",
                "rank": 2,
                "play_count": 70,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-05"),
                "album_name": "Album B",
                "artist_name": "Artist B",
                "rank": 2,
                "play_count": 60,
            },
        ]
    )
    weekly_artist = weekly_album.rename(columns={"album_name": "unused"})[
        ["billboard_week", "artist_name", "rank", "play_count"]
    ]

    album_result = compute_album_power_scores(weekly_album, top_n=20).set_index(
        ["album_name", "artist_name"]
    )
    artist_result = compute_artist_power_scores(weekly_artist, top_n=20).set_index("artist_name")

    assert album_result.loc[("Album A", "Artist A"), "power_score"] >= _TOP1_BONUS
    assert artist_result.loc["Artist A", "power_score"] >= _TOP1_BONUS
    assert album_result.loc[("Album A", "Artist A"), "weeks_at_peak"] == 1
    assert artist_result.loc["Artist A", "weeks_on_chart"] == 2
