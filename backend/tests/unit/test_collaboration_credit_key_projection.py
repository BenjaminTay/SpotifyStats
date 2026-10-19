"""Credit-ID collection preserves identity rules without copying source frames."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.playback import records_collaboration as collaboration
from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.tests.unit.test_playback_records_collaboration import (
    _frames,
)
from backend.tests.unit.test_playback_records_collaboration import (
    credit_conn as _credit_conn_fixture,
)

credit_conn = _credit_conn_fixture

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("legacy_raw", [False, True])
@pytest.mark.parametrize(
    "columns,expected_modern,expected_legacy",
    [
        ({"representative_track_id": [101, 102]}, [101, 102], [101, 102]),
        (
            {"representative_track_id": ["101", "bad"], "track_id": [201, 202]},
            [101, None],
            [101, None],
        ),
        (
            {"representative_track_id": [None, None], "track_id": [201, 202]},
            [None, None],
            [None, None],
        ),
        ({"track_id": [201, "202"]}, [None, None], [201, 202]),
        ({"track_id": [201, 202], "l1_id": [301, 302]}, [None, None], [None, None]),
        ({"unrelated": [1, 2]}, [None, None], [None, None]),
        (
            {"representative_track_id": pd.array([101, None], dtype="Int64")},
            [101, None],
            [101, None],
        ),
        ({"representative_track_id": [101.5, -2]}, [101.5, -2], [101.5, -2]),
        ({"representative_track_id": []}, [], []),
    ],
)
def test_credit_key_keeps_precedence_coercion_and_legacy_boundary(
    columns, expected_modern, expected_legacy, legacy_raw
):
    frame = pd.DataFrame(columns)
    frame.index = pd.Index([4] * len(frame), name="source_row")
    original = frame.copy()
    frame.attrs["sentinel"] = "unchanged"
    ids = collaboration._credit_track_ids(frame, legacy_raw=legacy_raw)
    expected = expected_legacy if legacy_raw else expected_modern
    assert ids.where(ids.notna(), None).astype(object).where(ids.notna(), None).tolist() == expected
    assert ids.index.equals(frame.index)
    keyed = collaboration._credit_key(frame, legacy_raw=legacy_raw)
    pd.testing.assert_series_equal(ids, keyed["_credit_track_id"], check_names=False)
    pd.testing.assert_frame_equal(frame, original)
    assert frame.attrs == {"sentinel": "unchanged"}
    assert keyed.attrs == {}


def _duration_frames():
    events, tracks, albums = _frames([101, 102])
    extra = _frames([104])[0].assign(ms_played=9000, play_id=9)
    duration = pd.concat([events, extra], ignore_index=True)
    duration["slice_start_at"] = ["2026-01-01T01:00Z", "2026-01-01T02:00Z", "2026-01-01T03:00Z"]
    track_duration = duration.assign(
        canonical_track_id=duration.track_id, canonical_track_name=duration.track_name
    )
    album_duration = duration.assign(album_project_id=50, album_project_name="Album Project")
    for frame, slices in zip((events, tracks, albums), (duration, track_duration, album_duration)):
        frame["unused_wide_payload"] = "retain this source column"
        slices["unused_wide_payload"] = "retain this duration column"
        attach_listening_duration_frame(frame, slices)
    return (events, tracks, albums), (duration, track_duration, album_duration)


def test_collecting_credit_ids_does_not_copy_track_album_or_duration_sources(
    monkeypatch, credit_conn
):
    frames, durations = _duration_frames()
    sources = dict(
        zip(
            ["events", "tracks", "albums", "duration", "track_duration", "album_duration"],
            [*frames, *durations],
        )
    )
    originals = {name: frame.copy() for name, frame in sources.items()}
    copied_sources = []
    at_lookup = []
    native_copy = pd.DataFrame.copy
    native_lookup = collaboration.get_effective_track_credit_frame

    def observe_copy(frame, *args, **kwargs):
        copied_sources.extend(name for name, source in sources.items() if frame is source)
        return native_copy(frame, *args, **kwargs)

    def observe_lookup(conn, ids):
        at_lookup.append((list(ids), list(copied_sources)))
        return native_lookup(conn, ids)

    monkeypatch.setattr(pd.DataFrame, "copy", observe_copy)
    monkeypatch.setattr(collaboration, "get_effective_track_credit_frame", observe_lookup)
    facts = collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    # One event copy establishes logical identity. ID discovery itself copies
    # none of the six original wide frames, including duration-only track 104.
    assert at_lookup == [([101, 102, 104], ["events"])]
    assert facts.total_events == 2
    assert "unused_wide_payload" in facts.tracks.columns
    assert 104 in set(facts.artist_duration["_credit_track_id"])
    for name, frame in sources.items():
        pd.testing.assert_frame_equal(frame, originals[name])
