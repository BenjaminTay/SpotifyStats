from __future__ import annotations

import pandas as pd

from backend.domains.yearly_review.season import build_monthly_fact_table, build_season
from backend.models.yearly_review import YearlyFactSemantics, YearlyHighlightCandidate, YearlyMetric


def _stats(*, empty_month: int | None = None) -> dict:
    return {
        "monthly_distribution": [
            {
                "month": month,
                "plays": 0 if month == empty_month else 100 + month * 10,
                "hours": 0.0 if month == empty_month else float(20 + month * 3),
                "active_days": 0 if month == empty_month else 20,
            }
            for month in range(1, 13)
        ]
    }


def _artist_frame(*, empty_month: int | None = None) -> pd.DataFrame:
    rows = []
    champions = {**{m: "A" for m in range(1, 4)}, **{m: "B" for m in range(4, 7)}}
    champions.update({m: "C" for m in range(7, 10)})
    champions.update({m: "D" for m in range(10, 13)})
    play_id = 1
    for month, artist in champions.items():
        if month == empty_month:
            continue
        for day in range(1, 4):
            rows.append(
                {
                    "play_id": play_id,
                    "track_id": play_id,
                    "artist_name": artist,
                    "album_name": "Album",
                    "ms_played": 180_000,
                    "ts_date": f"2025-{month:02d}-{day:02d}",
                    "ts_month": month,
                }
            )
            play_id += 1
    return pd.DataFrame(rows)


def test_single_month_table_has_deterministic_stages_and_turning_points() -> None:
    artist = _artist_frame()
    result = build_season(
        2025,
        _stats(),
        entity_frames=(pd.DataFrame(), pd.DataFrame(), artist),
    )

    assert [month.month for month in result.months] == list(range(1, 13))
    assert len(result.stages) == 4
    assert all(stage.end_month - stage.start_month + 1 >= 2 for stage in result.stages)
    assert 6 <= len(result.turning_points) <= 10
    assert len({point.month for point in result.turning_points}) == len(result.turning_points)
    assert len({point.event_type for point in result.turning_points}) >= 2
    assert sum(len(month.event_ids) for month in result.months) == len(result.turning_points)


def test_empty_month_is_preserved_without_false_turning_point() -> None:
    result = build_season(
        2025,
        _stats(empty_month=2),
        entity_frames=(pd.DataFrame(), pd.DataFrame(), _artist_frame(empty_month=2)),
    )

    february = result.months[1]
    assert february.plays == 0
    assert february.leaders == {}
    assert february.event_ids == []


def test_partial_current_month_compares_the_same_day_window() -> None:
    stats = _stats()
    stats["year"] = 2026
    stats["monthly_distribution"][6]["hours"] = 66.0
    stats["monthly_distribution"][7]["hours"] = 61.4
    stats["daily_trend"] = [
        {"date": "2026-07-01", "plays": 10, "hours": 66.0},
        {"date": "2026-08-01", "plays": 10, "hours": 61.4},
    ]

    months = build_monthly_fact_table(
        stats,
        baseline_monthly=[
            {"month": month, "hours": 50.0 if month == 8 else 1.0} for month in range(1, 13)
        ],
        complete=False,
        observed_end="2026-08-21",
    )
    metric = next(
        item for item in months[7].comparisons if item.key == "hours_vs_previous_period_pct"
    )

    assert metric.value == -7.0
    assert metric.comparison_label == "上月同期小时数"
    assert metric.observed_start == "2026-08-01"
    assert metric.observed_end == "2026-08-21"
    assert metric.comparison_start == "2026-07-01"
    assert metric.comparison_end == "2026-07-21"

    prior_year = next(
        item for item in months[7].comparisons if item.key == "hours_vs_prior_year_period_pct"
    )
    assert prior_year.value == 22.8
    assert prior_year.comparison_label == "上年同期小时数"
    assert prior_year.observed_start == "2026-08-01"
    assert prior_year.observed_end == "2026-08-21"
    assert prior_year.comparison_start == "2025-08-01"
    assert prior_year.comparison_end == "2025-08-21"
    assert all(item.key != "hours_vs_prior_year_month_pct" for item in months[7].comparisons)


def test_timeline_does_not_promote_a_ranked_runner_up_to_yearly_maximum() -> None:
    runner_up = YearlyHighlightCandidate(
        candidate_id="daily-rank-4",
        source="playback_records",
        source_family="obsession",
        record_key="obsession.daily_total_plays",
        category="obsession",
        fact_type="daily_total_plays",
        primary_metric=YearlyMetric(key="value", label="2025-06-13", value=130, unit="次"),
        raw_values={"rank": 4, "date": "2025-06-13", "year": 2025},
        semantics=YearlyFactSemantics(
            scope="annual",
            rank=4,
            rank_basis="total_plays",
            is_top=False,
        ),
    )

    result = build_season(2025, _stats(), record_candidates=[runner_up])

    assert all("2025-06-13" not in point.statement for point in result.turning_points)
