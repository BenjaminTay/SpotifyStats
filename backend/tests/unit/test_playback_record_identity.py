from copy import deepcopy

import pandas as pd
import pytest

from backend.domains.playback.record_identity import record_track_id
from backend.domains.playback.records_obsession import _daily_binge
from backend.domains.playback.records_output import _serialize_records
from backend.models.analysis import PlaybackRecordRow

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", [1493, 1493.0, "1493", "1493.0", "001493.000"])
def test_integral_track_ids_have_one_decimal_representation(value):
    assert record_track_id(value) == "1493"


@pytest.mark.parametrize(
    "value", [None, True, 0, -1, "1493.5", "1493oops", "1e3", "NaN", float("inf")]
)
def test_invalid_ids_do_not_point_at_another_song(value):
    assert record_track_id(value) is None


def test_large_integer_identity_is_not_rounded_through_float():
    assert record_track_id("9007199254740993.0") == "9007199254740993"


def test_float_groupby_identity_is_normalized_without_changing_record_facts():
    frame = pd.DataFrame(
        [
            {
                "track_id": 1493.0,
                "track_name": "vampire",
                "artist_name": "Olivia Rodrigo",
                "ts_date": "2023-07-01",
                "play_id": i,
                "ms_played": 180000,
            }
            for i in range(43)
        ]
    )
    raw = _daily_binge(frame, "track_id", "track_name", "artist_name")
    before = raw.copy(deep=True)
    row = _serialize_records({"daily_binge_track": raw})["daily_binge_track"][0]
    assert row["entity_id"] == "1493"
    assert row["name"] == "vampire"
    assert row["value"] == 43
    assert row["total_ms"] == 43 * 180000
    pd.testing.assert_frame_equal(raw, before)


def test_snapshot_model_and_new_serialization_share_identity_rules():
    rows = [
        {
            "rank": 1,
            "entity_type": "track",
            "entity_id": "1493.0",
            "name": "vampire",
            "value": 43,
            "unit": "次",
            "top_track_entity_id": "1493.000",
        },
        {
            "rank": 1,
            "entity_type": "artist",
            "entity_id": "1493.0",
            "name": "1493.0",
            "value": 1,
            "unit": "次",
        },
        {
            "rank": 1,
            "entity_type": "album",
            "entity_id": "569.0",
            "name": "vampire",
            "value": 1,
            "unit": "次",
        },
    ]
    before = deepcopy(rows)
    serialized = _serialize_records({"rows": rows})["rows"]
    for source, output in zip(rows, serialized):
        model = PlaybackRecordRow.model_validate(source)
        assert model.entity_id == output["entity_id"]
        assert model.top_track_entity_id == output.get("top_track_entity_id")
    assert serialized[0]["entity_id"] == "1493"
    assert serialized[1]["entity_id"] == "1493.0"
    assert serialized[2]["entity_id"] == "569.0"
    assert rows == before
