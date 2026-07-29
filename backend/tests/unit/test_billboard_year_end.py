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


def test_track_year_end_score_keeps_true_debut_as_fact_only():
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


def test_v3_year_end_score_is_weekly_score_sum_without_annual_bonuses():
    response = build_year_end_response(
        weekly=pd.DataFrame([_track_row("2025-01-03", 1, "Track A", "Artist A", 100, 1)]),
        weekly_album=pd.DataFrame([_album_row("2025-01-03", "Album A", "Artist A", 100, 1)]),
        weekly_artist=pd.DataFrame([_artist_row("2025-01-03", "Artist A", 100, 1)]),
        year=2025,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
    )

    assert response["meta"]["semantics_version"] == "year_end_v3"
    for family in ("tracks", "albums", "artists"):
        row = response[family][0]
        assert row["year_end_score"] == 400
        assert row["peak_position"] == 1
        assert row["weeks_on_chart"] == 1
        assert row["weeks_at_no1"] == 1


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


def test_year_end_separates_chart_plays_from_all_eligible_annual_plays():
    chart_weekly = pd.DataFrame(
        [
            _track_row("2025-01-03", 1, "Winner", "Artist A", 100, 1),
            _track_row("2025-01-10", 1, "Winner", "Artist A", 80, 2),
        ]
    )
    all_weekly = pd.concat(
        [
            chart_weekly,
            pd.DataFrame(
                [
                    _track_row("2025-01-17", 1, "Winner", "Artist A", 7, 45),
                ]
            ),
        ],
        ignore_index=True,
    )

    response = build_year_end_response(
        weekly=chart_weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
        weekly_top_n=30,
        weekly_album_top_n=20,
        weekly_artist_top_n=20,
        all_weekly=all_weekly,
    )

    row = response["tracks"][0]
    assert row["weeks_on_chart"] == 2
    assert row["chart_plays"] == 180
    assert row["annual_plays"] == 187
    assert response["meta"]["weekly_top_n"] == 30
    assert response["meta"]["year_end_top_n"] == 50


def test_year_end_output_limit_does_not_change_common_row_scores():
    weekly = pd.DataFrame(
        [
            _track_row("2025-01-03", 1, "Winner", "Artist A", 100, 1),
            _track_row("2025-01-03", 2, "Runner", "Artist B", 80, 2),
            _track_row("2025-01-10", 1, "Winner", "Artist A", 90, 1),
            _track_row("2025-01-10", 2, "Runner", "Artist B", 70, 2),
        ]
    )

    top_one = build_year_end_response(
        weekly=weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=1,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
        weekly_top_n=30,
    )
    top_two = build_year_end_response(
        weekly=weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=2,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
        weekly_top_n=30,
    )

    assert top_one["tracks"][0]["track_name"] == "Winner"
    assert top_one["tracks"][0]["year_end_score"] == top_two["tracks"][0]["year_end_score"]


def test_year_end_coverage_distinguishes_complete_and_partial_years():
    complete_weeks = pd.date_range("2025-01-03", "2025-12-26", freq="7D")
    complete_weekly = pd.DataFrame(
        [_track_row(week.isoformat(), 1, "Winner", "Artist A", 10, 1) for week in complete_weeks]
    )
    partial_weekly = complete_weekly[
        complete_weekly["billboard_week"] >= pd.Timestamp("2025-06-27")
    ].copy()

    complete = build_year_end_response(
        weekly=complete_weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
    )
    partial = build_year_end_response(
        weekly=partial_weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2025,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
    )

    assert complete["meta"]["coverage_status"] == "complete"
    assert complete["meta"]["is_complete_year"] is True
    assert complete["meta"]["observed_weeks"] == complete["meta"]["expected_weeks"] == 52
    assert partial["meta"]["coverage_status"] == "partial_start"
    assert partial["meta"]["is_complete_year"] is False
    assert partial["meta"]["has_internal_gaps"] is False


def test_year_end_coverage_uses_source_play_dates_without_losing_week_boundaries():
    weekly = pd.DataFrame(
        [
            _track_row("2026-01-02", 1, "Winner", "Artist A", 10, 1),
            _track_row("2026-01-09", 1, "Winner", "Artist A", 10, 1),
        ]
    )
    coverage_source = pd.DataFrame(
        [
            {"billboard_week": _week("2026-01-02"), "ts_date": "2026-01-04"},
            {"billboard_week": _week("2026-01-09"), "ts_date": "2026-01-15"},
        ]
    )

    response = build_year_end_response(
        weekly=weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2026,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
        coverage_source=coverage_source,
    )

    meta = response["meta"]
    assert meta["period_start"].startswith("2026-01-04")
    assert meta["period_end"].startswith("2026-01-15")
    assert meta["first_billboard_week"].startswith("2026-01-02")
    assert meta["last_billboard_week"].startswith("2026-01-09")


def test_year_end_coverage_uses_preaggregated_source_date_metadata():
    weekly = pd.DataFrame(
        [
            _track_row("2026-01-02", 1, "Winner", "Artist A", 10, 1),
            _track_row("2026-01-09", 1, "Winner", "Artist A", 10, 1),
        ]
    )
    coverage_source = weekly[["billboard_week", "track_id"]].copy()
    coverage_source.attrs["coverage_periods"] = {
        2026: (pd.Timestamp("2026-01-04", tz="UTC"), pd.Timestamp("2026-01-15", tz="UTC"))
    }

    response = build_year_end_response(
        weekly=weekly,
        weekly_album=_empty_album(),
        weekly_artist=_empty_artist(),
        year=2026,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
        coverage_source=coverage_source,
    )

    assert response["meta"]["period_start"].startswith("2026-01-04")
    assert response["meta"]["period_end"].startswith("2026-01-15")
