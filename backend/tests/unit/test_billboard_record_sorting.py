import pandas as pd
import pytest

from backend.domains.billboard.record_sorting import stable_record_sort

pytestmark = pytest.mark.unit


def test_stable_record_sort_orders_before_top_n_and_ignores_input_permutation():
    frame = pd.DataFrame(
        [
            {"track_id": 3, "track_name": "Zeta", "score": 10, "weeks": 4},
            {"track_id": 1, "track_name": "Alpha", "score": 10, "weeks": 5},
            {"track_id": 2, "track_name": "Beta", "score": 10, "weeks": 5},
            {"track_id": 4, "track_name": "Delta", "score": 9, "weeks": 99},
        ]
    )
    expected = [
        {"track_id": 1, "track_name": "Alpha", "score": 10, "weeks": 5},
        {"track_id": 2, "track_name": "Beta", "score": 10, "weeks": 5},
    ]

    for candidate in (frame, frame.sample(frac=1, random_state=23)):
        result = stable_record_sort(
            candidate,
            [("score", False), ("weeks", False)],
            stable_columns=("track_id", "track_name"),
            limit=2,
        )
        assert result[["track_id", "track_name", "score", "weeks"]].to_dict("records") == expected
