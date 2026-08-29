from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.billboard.chart_movement import build_home_billboard_movement

pytestmark = pytest.mark.unit


def test_artist_falling_out_of_top_n_then_returning_is_reentry():
    movement = build_home_billboard_movement(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(
            [
                {
                    "billboard_week": "2026-08-14",
                    "artist_id": 159,
                    "artist_name": "Phoebe Bridgers",
                    "rank": 1,
                },
                {
                    "billboard_week": "2026-07-24",
                    "artist_id": 159,
                    "artist_name": "Phoebe Bridgers",
                    "rank": 17,
                },
            ]
        ),
        ["2026-08-14", "2026-08-07", "2026-07-24"],
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
    )

    assert movement["artist"] == {
        "movement": "re",
        "previous_rank": None,
        "rank_change": None,
    }


@pytest.mark.parametrize(
    ("previous_rank", "expected"),
    [
        (4, {"movement": "up", "previous_rank": 4, "rank_change": 3}),
        (1, {"movement": "same", "previous_rank": 1, "rank_change": 0}),
    ],
)
def test_top_n_champion_movement_keeps_previous_rank(previous_rank, expected):
    movement = build_home_billboard_movement(
        pd.DataFrame(
            [
                {
                    "billboard_week": "2026-08-14",
                    "track_id": 7,
                    "track_name": "歌曲",
                    "artist_name": "艺人",
                    "rank": 1,
                },
                {
                    "billboard_week": "2026-08-07",
                    "track_id": 7,
                    "track_name": "歌曲",
                    "artist_name": "艺人",
                    "rank": previous_rank,
                },
            ]
        ),
        pd.DataFrame(),
        pd.DataFrame(),
        ["2026-08-14", "2026-08-07"],
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
    )

    assert movement["track"] == expected


def test_entity_without_any_historical_top_n_entry_is_new():
    movement = build_home_billboard_movement(
        pd.DataFrame(
            [
                {
                    "billboard_week": "2026-08-14",
                    "track_id": 8,
                    "track_name": "新歌",
                    "artist_name": "艺人",
                    "rank": 1,
                },
                {
                    "billboard_week": "2026-08-07",
                    "track_id": 7,
                    "track_name": "旧歌",
                    "artist_name": "艺人",
                    "rank": 1,
                },
            ]
        ),
        pd.DataFrame(),
        pd.DataFrame(),
        ["2026-08-14", "2026-08-07"],
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
    )

    assert movement["track"] == {
        "movement": "new",
        "previous_rank": None,
        "rank_change": None,
    }
