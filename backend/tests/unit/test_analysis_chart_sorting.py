from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.billboard.details import _stable_detail_track_sort
from backend.services.analysis_stats_service import _sort_chart_rows

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("entity", "rows", "expected"),
    [
        (
            "track",
            [
                {"track_id": 3, "track_name": "Zulu", "artist_name": "A", "plays": 8, "hours": 1.0},
                {
                    "track_id": 2,
                    "track_name": "Alpha",
                    "artist_name": "A",
                    "plays": 8,
                    "hours": 2.0,
                },
                {"track_id": 1, "track_name": "Beta", "artist_name": "A", "plays": 8, "hours": 2.0},
            ],
            [1, 2, 3],
        ),
        (
            "artist",
            [
                {"artist_name": "Zulu", "plays": 8, "hours": 1.0},
                {"artist_name": "beta", "plays": 8, "hours": 2.0},
                {"artist_name": "Alpha", "plays": 8, "hours": 2.0},
            ],
            ["Alpha", "beta", "Zulu"],
        ),
        (
            "album",
            [
                {
                    "album_project_id": 30,
                    "album_name": "Zulu",
                    "artist_name": "A",
                    "plays": 8,
                    "hours": 1.0,
                },
                {
                    "album_project_id": 20,
                    "album_name": "Alpha",
                    "artist_name": "A",
                    "plays": 8,
                    "hours": 2.0,
                },
                {
                    "album_project_id": 10,
                    "album_name": "Beta",
                    "artist_name": "A",
                    "plays": 8,
                    "hours": 2.0,
                },
            ],
            [10, 20, 30],
        ),
    ],
)
def test_play_chart_ties_use_hours_then_stable_entity_key(entity, rows, expected):
    outputs = []
    for frame in (pd.DataFrame(rows), pd.DataFrame(list(reversed(rows)))):
        sorted_rows = _sort_chart_rows(frame, entity, "plays")
        key = {
            "track": "track_id",
            "artist": "artist_name",
            "album": "album_project_id",
        }[entity]
        outputs.append(sorted_rows[key].tolist())
    assert outputs == [expected, expected]


def test_play_chart_tie_pagination_is_stable_across_input_order():
    rows = [
        {"track_id": track_id, "track_name": f"Track {track_id}", "plays": 8, "hours": 2.0}
        for track_id in (5, 1, 4, 2, 3)
    ]
    pages = []
    for frame in (pd.DataFrame(rows), pd.DataFrame(list(reversed(rows)))):
        sorted_rows = _sort_chart_rows(frame, "track", "plays")
        pages.append(sorted_rows.iloc[1:4]["track_id"].tolist())
    assert pages == [[2, 3, 4], [2, 3, 4]]


def test_hours_chart_keeps_plays_as_second_key_then_stable_id():
    frame = pd.DataFrame(
        [
            {"track_id": 2, "track_name": "B", "artist_name": "A", "plays": 7, "hours": 2.0},
            {"track_id": 1, "track_name": "A", "artist_name": "A", "plays": 8, "hours": 2.0},
        ]
    )
    assert _sort_chart_rows(frame, "track", "hours")["track_id"].tolist() == [1, 2]


def test_detail_track_sort_appends_track_identity_after_business_keys():
    frame = pd.DataFrame(
        [
            {"track_id": 9, "track_name": "Zulu", "peak_position": 1, "weeks_on_chart": 5},
            {"track_id": 2, "track_name": "Alpha", "peak_position": 1, "weeks_on_chart": 5},
            {"track_id": 1, "track_name": "Beta", "peak_position": 2, "weeks_on_chart": 20},
        ]
    )
    sorted_rows = _stable_detail_track_sort(
        frame.sample(frac=1, random_state=4),
        primary_columns=("peak_position", "weeks_on_chart"),
        primary_ascending=(True, False),
    )
    assert sorted_rows["track_id"].tolist() == [2, 9, 1]
