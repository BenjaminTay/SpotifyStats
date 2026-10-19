"""Completed date processing must not pin album duration through track merge."""

from __future__ import annotations

import sqlite3
import weakref

import pandas as pd
import pytest

from backend.domains.playback.logical_timeline import get_listening_duration_frame
from backend.services import analysis_records_service as service
from backend.tests.unit.test_records_projection_lifetime import (
    records_sources as _records_sources_fixture,
)

records_sources = _records_sources_fixture

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("has_fallback", [True, False])
def test_album_duration_follows_result_owner_after_date_processing(
    monkeypatch, records_sources, level, has_fallback
):
    events, duration, *_ = records_sources("success")
    before, dbefore = events.copy(), duration.copy()
    lookup = pd.DataFrame(
        {
            "album_name": ["Album"],
            "artist_name": ["Artist"],
            "source_album_release_date": ["2025-12-31"],
        }
    )
    monkeypatch.setattr(
        service,
        "_load_reliable_album_release_dates",
        lambda _: lookup if has_fallback else lookup.iloc[:0],
    )
    native_album, native_track = (
        service._build_records_album_frame,
        service._build_records_track_frame,
    )
    duration_refs, observed = [], []

    def albums(*args, **kwargs):
        result = native_album(*args, **kwargs)
        if kwargs.get("duration"):
            duration_refs.append(weakref.ref(result[0]))
        return result

    def tracks(*args, **kwargs):
        observed.append(duration_refs[0]() is not None)
        assert observed[-1] is (not has_fallback)
        return native_track(*args, **kwargs)

    monkeypatch.setattr(service, "_build_records_album_frame", albums)
    monkeypatch.setattr(service, "_build_records_track_frame", tracks)
    with sqlite3.connect(":memory:") as conn:
        track, album, artist = service._build_entity_frames(events, conn, level)
    assert observed == [not has_fallback]
    if not has_fallback:
        assert get_listening_duration_frame(album) is duration_refs[0]()
    else:
        assert get_listening_duration_frame(album) is None
    pd.testing.assert_frame_equal(events, before)
    pd.testing.assert_frame_equal(duration, dbefore)
    assert all(frame is not events for frame in [track, album, artist])
