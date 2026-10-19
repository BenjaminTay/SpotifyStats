"""Records projections must not overlap the cold artist reconstruction peak."""

from __future__ import annotations

import sqlite3
import weakref

import pandas as pd
import pytest

from backend.domains.playback.records_helpers import records_duration_frame
from backend.services import analysis_records_service as service

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("artist_failure", [False, True])
def test_artist_reconstruction_does_not_hold_entity_projection_copies(
    monkeypatch, artist_failure
) -> None:
    events = pd.DataFrame(
        {
            "play_id": [7, 8],
            "track_id": [1, 2],
            "track_name": ["Song A", "Song B"],
            "album_name": ["Album", "Album"],
            "artist_name": ["Artist", "Artist"],
            "ts_date": ["2026-01-01", "2026-01-02"],
            "ms_played": [40000, 50000],
        }
    )
    original = events.copy()
    copies = []
    live_during_artist = []
    native_copy = pd.DataFrame.copy

    def observe_copy(frame, *args, **kwargs):
        result = native_copy(frame, *args, **kwargs)
        if "play_id" in result.columns:
            copies.append(weakref.ref(result))
        return result

    def load_artists(*args, **kwargs):
        live_during_artist.append(sum(ref() is not None for ref in copies))
        if artist_failure:
            raise RuntimeError("artist history unavailable")
        return original.copy()

    monkeypatch.setattr(pd.DataFrame, "copy", observe_copy)
    monkeypatch.setattr(service, "load_plays_for_artists", load_artists)
    monkeypatch.setattr(service, "_load_reliable_album_release_dates", lambda _: pd.DataFrame())
    with sqlite3.connect(":memory:") as conn:
        track, album, artist = service._build_entity_frames(events, conn, 1)

    # Check outside the builder: artist exceptions deliberately use its fallback.
    assert live_during_artist == [1]
    pd.testing.assert_frame_equal(events, original)
    assert track["canonical_track_id"].tolist() == [1, 2]
    assert album["album_project_name"].tolist() == ["Album", "Album"]
    assert artist["play_id"].tolist() == [7, 8]
    assert records_duration_frame(track)["ms_played"].sum() == 90000
    assert records_duration_frame(album)["ms_played"].sum() == 90000
    track.loc[0, "track_name"] = "Changed"
    album.loc[0, "album_name"] = "Changed"
    assert events.loc[0, "track_name"] == "Song A"
    assert artist.loc[0, "track_name"] == "Song A"
