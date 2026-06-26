from __future__ import annotations

import pandas as pd

from backend.domains.billboard.year_end import (
    build_honors,
    build_year_end_response,
    sort_year_end_rows,
)


def _week(date: str) -> pd.Timestamp:
    return pd.Timestamp(date)


def _track_row(
    date: str,
    track_id: int,
    name: str,
    artist: str,
    plays: int,
    rank: int,
) -> dict:
    return {
        "billboard_week": _week(date),
        "track_id": track_id,
        "track_name": name,
        "artist_name": artist,
        "artist_names": [artist],
        "album_name": f"{name} Album",
        "play_count": plays,
        "total_ms": plays * 1000,
        "rank": rank,
        "cover_url": None,
    }


def _album_row(date: str, album: str, artist: str, plays: int, rank: int) -> dict:
    return {
        "billboard_week": _week(date),
        "album_name": album,
        "artist_name": artist,
        "play_count": plays,
        "total_ms": plays * 1000,
        "rank": rank,
        "cover_url": None,
        "release_date": date,
        "album_type": "album",
    }


def _artist_row(date: str, artist: str, plays: int, rank: int) -> dict:
    return {
        "billboard_week": _week(date),
        "artist_name": artist,
        "play_count": plays,
        "total_ms": plays * 1000,
        "rank": rank,
        "cover_url": None,
    }


def _empty_album() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "billboard_week",
            "album_name",
            "artist_name",
            "play_count",
            "total_ms",
            "rank",
            "cover_url",
        ]
    )


def _empty_artist() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "billboard_week",
            "artist_name",
            "play_count",
            "total_ms",
            "rank",
            "cover_url",
        ]
    )


def test_year_end_scores_filter_to_selected_billboard_year_before_aggregating():
    weekly = pd.DataFrame(
        [
            _track_row("2024-12-27", 1, "Old Giant", "Artist A", 400, 1),
            _track_row("2025-01-03", 1, "Old Giant", "Artist A", 5, 10),
            _track_row("2025-01-03", 2, "Annual Winner", "Artist B", 100, 1),
        ]
    )

    response = build_year_end_response(
        weekly=weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=30,
        album_top_n=20,
        artist_top_n=20,
        week_start_dow=4,
        week_start_hour=0,
    )

    assert response["meta"]["year"] == 2025
    assert response["meta"]["available_years"] == [2024, 2025]
    assert response["meta"]["total_weeks"] == 1
    assert response["tracks"][0]["track_id"] == 2

    old_giant = next(row for row in response["tracks"] if row["track_id"] == 1)
    assert old_giant["weeks_on_chart"] == 1
    assert old_giant["chart_plays"] == 5
    assert old_giant["first_week"] == "2025-01-03T00:00:00"
    assert old_giant["last_week"] == "2025-01-03T00:00:00"


def test_track_year_end_score_uses_no1_weeks_instead_of_debut_no1_bonus():
    weekly = pd.DataFrame(
        [
            _track_row("2024-12-27", 2, "Prior-Year Entry", "Artist B", 80, 2),
            _track_row("2024-12-27", 900, "Old Context", "Artist Z", 100, 1),
            _track_row("2025-01-03", 1, "True Debut No1", "Artist A", 100, 1),
            _track_row("2025-01-03", 901, "Runner A", "Artist Z", 80, 2),
            _track_row("2025-01-10", 2, "Prior-Year Entry", "Artist B", 100, 1),
            _track_row("2025-01-10", 902, "Runner B", "Artist Z", 80, 2),
        ]
    )

    response = build_year_end_response(
        weekly=weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=30,
        album_top_n=20,
        artist_top_n=20,
        week_start_dow=4,
        week_start_hour=0,
    )

    true_debut = next(row for row in response["tracks"] if row["track_id"] == 1)
    prior_entry = next(row for row in response["tracks"] if row["track_id"] == 2)

    assert true_debut["is_true_debut_no1"] is True
    assert prior_entry["is_true_debut_no1"] is False
    assert true_debut["weeks_at_no1"] == 1
    assert prior_entry["weeks_at_no1"] == 1
    assert true_debut["year_end_score"] == prior_entry["year_end_score"]


def test_sort_year_end_rows_uses_score_then_no1_then_peak_then_top10_then_plays():
    rows = [
        {
            "name": "A",
            "year_end_score": 500,
            "weeks_at_no1": 1,
            "peak_position": 1,
            "weeks_top10": 3,
            "chart_plays": 80,
        },
        {
            "name": "B",
            "year_end_score": 500,
            "weeks_at_no1": 2,
            "peak_position": 2,
            "weeks_top10": 2,
            "chart_plays": 70,
        },
        {
            "name": "C",
            "year_end_score": 500,
            "weeks_at_no1": 2,
            "peak_position": 1,
            "weeks_top10": 1,
            "chart_plays": 60,
        },
        {
            "name": "D",
            "year_end_score": 500,
            "weeks_at_no1": 2,
            "peak_position": 1,
            "weeks_top10": 4,
            "chart_plays": 50,
        },
    ]

    sorted_rows = sort_year_end_rows(rows)

    assert [row["name"] for row in sorted_rows] == ["D", "C", "B", "A"]
    assert [row["year_end_rank"] for row in sorted_rows] == [1, 2, 3, 4]


def test_year_end_honors_are_derived_from_annual_rows():
    weekly = pd.DataFrame(
        [
            _track_row("2025-01-03", 1, "Winner", "Artist A", 120, 1),
            _track_row("2025-01-10", 1, "Winner", "Artist A", 110, 1),
            _track_row("2025-01-10", 2, "Runner", "Artist B", 60, 2),
        ]
    )
    weekly_album = pd.DataFrame(
        [
            _album_row("2025-01-03", "Album A", "Artist A", 120, 1),
            _album_row("2025-01-10", "Album A", "Artist A", 110, 1),
            _album_row("2025-01-10", "Album B", "Artist B", 60, 2),
        ]
    )
    weekly_artist = pd.DataFrame(
        [
            _artist_row("2025-01-03", "Artist A", 120, 1),
            _artist_row("2025-01-10", "Artist A", 110, 1),
            _artist_row("2025-01-10", "Artist B", 60, 2),
        ]
    )

    response = build_year_end_response(
        weekly=weekly,
        weekly_album=weekly_album,
        weekly_artist=weekly_artist,
        year=2025,
        top_n=30,
        album_top_n=20,
        artist_top_n=20,
        week_start_dow=4,
        week_start_hour=0,
    )

    honors = response["honors"]

    assert honors["year_end_no1_track"]["track_name"] == "Winner"
    assert honors["year_end_no1_album"]["album_name"] == "Album A"
    assert honors["year_end_no1_artist"]["artist_name"] == "Artist A"
    assert honors["longest_charting_track"]["track_name"] == "Winner"
    assert honors["biggest_no1_run_track"]["weeks_at_no1"] == 2
    assert honors["top_new_entry_track"]["track_name"] == "Winner"
    assert honors["breakthrough_artist"]["artist_name"] == "Artist A"
    assert honors["album_era_of_the_year"]["album_name"] == "Album A"


def test_no1_run_honor_ties_use_year_end_score_before_rank():
    honors = build_honors(
        tracks=[
            {
                "track_name": "Lower Score",
                "weeks_at_no1": 3,
                "year_end_score": 900,
                "year_end_rank": 1,
            },
            {
                "track_name": "Higher Score",
                "weeks_at_no1": 3,
                "year_end_score": 1200,
                "year_end_rank": 2,
            },
        ],
        albums=[],
        artists=[],
    )

    assert honors["biggest_no1_run_track"]["track_name"] == "Higher Score"
