from __future__ import annotations

import pandas as pd

from backend.domains.yearly_review.season import build_season


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
