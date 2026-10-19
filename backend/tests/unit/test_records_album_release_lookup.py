"""Release-date fallback joins keys while keeping owned entity projections."""

from __future__ import annotations

import sqlite3
import warnings
import weakref

import pandas as pd
import pytest

from backend.domains.playback.logical_timeline import get_listening_duration_frame
from backend.domains.playback.records_helpers import records_duration_frame
from backend.services import analysis_records_service as service
from backend.tests.unit.test_records_projection_lifetime import (
    records_sources as _records_sources_fixture,
)

records_sources = _records_sources_fixture

pytestmark = pytest.mark.unit


def release_lookup(mode="normal"):
    if mode == "empty":
        return pd.DataFrame(columns=["album_name", "artist_name", "source_album_release_date"])
    if mode == "unmatched":
        return pd.DataFrame(
            {
                "album_name": ["Elsewhere"],
                "artist_name": ["Artist"],
                "source_album_release_date": ["2025-12-31"],
            }
        )
    if mode == "null_key":
        return pd.DataFrame(
            {
                "album_name": [None],
                "artist_name": ["Artist"],
                "source_album_release_date": ["2025-12-31"],
            }
        )
    return pd.DataFrame(
        {
            "album_name": ["Album"],
            "artist_name": ["Artist"],
            "source_album_release_date": ["2025-12-31"],
        }
    )


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("mode", ["normal", "empty", "unmatched", "null_key", "named_index"])
def test_release_lookup_preserves_source_results_and_metadata(
    monkeypatch, records_sources, level, mode
):
    events, duration, *_ = records_sources("success")
    if mode == "null_key":
        events["album_name"] = None
    if mode == "named_index":
        events.index.name = "source_row"
        events.columns.name = "source_field"
    before, before_duration = events.copy(), duration.copy()
    attrs = events.attrs.copy()
    lookup = release_lookup(mode)
    before_lookup = lookup.copy()
    monkeypatch.setattr(service, "_load_reliable_album_release_dates", lambda _: lookup)
    with sqlite3.connect(":memory:") as conn:
        track, album, artist = service._build_entity_frames(events, conn, level)
    assert album is not events and album is not track and album is not artist
    if not lookup.empty:
        assert album.attrs == {}
        assert isinstance(album.index, pd.RangeIndex) and album.index.name is None
        assert album.columns.name is None
        assert get_listening_duration_frame(album) is None
        pd.testing.assert_frame_equal(records_duration_frame(album), album)
    if mode in {"normal", "named_index"}:
        expected_dates = ["2026-01-01", "2025-12-31"] if level >= 2 else ["2025-12-31"]
        assert album["album_release_date"].iloc[:-1].tolist() == expected_dates
        assert pd.isna(album["album_release_date"].iloc[-1])
    album.iat[0, album.columns.get_loc("track_name")] = "changed"
    album.attrs["new_metadata"] = "owned"
    pd.testing.assert_frame_equal(events, before)
    pd.testing.assert_frame_equal(duration, before_duration)
    pd.testing.assert_frame_equal(lookup, before_lookup)
    assert events.attrs == attrs


@pytest.mark.parametrize("level", [1, 2, 3])
def test_release_join_uses_only_keys_and_temporary_expires(monkeypatch, records_sources, level):
    events, *_ = records_sources("success")
    lookup = release_lookup()
    monkeypatch.setattr(service, "_load_reliable_album_release_dates", lambda _: lookup)
    native_merge, native_track = pd.DataFrame.merge, service._build_records_track_frame
    calls, temporary, states = [], [], []

    def merge(frame, right, *args, **kwargs):
        result = native_merge(frame, right, *args, **kwargs)
        if right is lookup:
            calls.append(list(frame.columns))
            assert list(frame.columns) == ["album_name", "artist_name"]
            temporary.append(weakref.ref(frame))
            temporary.append(weakref.ref(result))
        return result

    def tracks(*args, **kwargs):
        states.append([ref() is not None for ref in temporary])
        return native_track(*args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", merge)
    monkeypatch.setattr(service, "_build_records_track_frame", tracks)
    with sqlite3.connect(":memory:") as conn:
        service._build_entity_frames(events, conn, level)
    assert calls == [["album_name", "artist_name"]]
    assert states == [[False, False]]


def test_reliable_release_loader_groups_duplicate_and_null_keys():
    with sqlite3.connect(":memory:") as conn:
        conn.executescript("""
          CREATE TABLE artists (artist_id INTEGER, artist_name TEXT);
          CREATE TABLE albums (album_id INTEGER, album_name TEXT, artist_id INTEGER);
          CREATE TABLE album_spotify_links (album_id INTEGER, spotify_album_id TEXT, confidence REAL);
          CREATE TABLE spotify_album_meta (spotify_album_id TEXT, release_date TEXT,
              release_date_precision TEXT, album_type TEXT);
          INSERT INTO artists VALUES(1,'Artist'),(2,'Other artist');
          INSERT INTO albums VALUES(1,'Album',1),(2,'Album',1),(3,'Album',2),(4,NULL,1),
             (5,NULL,1),(6,'Conflict',1),(7,'Conflict',1),(8,'Partial',1);
          INSERT INTO album_spotify_links VALUES(1,'a',1),(2,'b',1),(3,'c',1),(4,'d',1),
             (5,'d',1),(6,'a',1),(7,'e',1),(8,'f',1);
          INSERT INTO spotify_album_meta VALUES('a','2026-01-01','day','album'),
             ('b','2026-01-01','day','album'),('c','2025-12-31','day','ep'),
             ('d','2024-01-01','day','album'),('e','2026-01-02','day','album'),
             ('f','2026','year','album');
        """)
        result = service._load_reliable_album_release_dates(conn)
    assert len(result) == 3
    assert not result.duplicated(["album_name", "artist_name"]).any()
    assert result["artist_name"].tolist() == ["Artist", "Other artist", "Artist"]
    assert result["source_album_release_date"].tolist() == [
        "2026-01-01",
        "2025-12-31",
        "2024-01-01",
    ]


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("mode", ["normal", "unmatched", "null_key"])
def test_release_fallback_keeps_legacy_dtype_without_downcast_warning(
    monkeypatch, records_sources, level, mode
):
    events, duration, *_ = records_sources("success")
    before_events, before_duration = events.copy(), duration.copy()
    lookup = release_lookup(mode)
    before_lookup = lookup.copy()
    monkeypatch.setattr(service, "_load_reliable_album_release_dates", lambda _: lookup)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always", FutureWarning)
        with sqlite3.connect(":memory:") as conn:
            _, album, _ = service._build_entity_frames(events, conn, level)
    assert not any("Downcasting object dtype arrays" in str(item.message) for item in emitted)
    fallback = album[["album_name", "artist_name"]].merge(
        lookup, on=["album_name", "artist_name"], how="left", validate="many_to_one"
    )["source_album_release_date"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        expected = album["album_project_release_day"].fillna(fallback)
    expected.name = "album_release_date"
    pd.testing.assert_series_equal(album["album_release_date"], expected)
    pd.testing.assert_frame_equal(events, before_events)
    pd.testing.assert_frame_equal(duration, before_duration)
    pd.testing.assert_frame_equal(lookup, before_lookup)
