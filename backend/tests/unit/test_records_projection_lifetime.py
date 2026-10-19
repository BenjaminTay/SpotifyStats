"""Full Records/Yearly frame contracts and transient projection ownership."""

from __future__ import annotations

import sqlite3
import weakref

import pandas as pd
import pytest

from backend.domains.playback import album_projects
from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.domains.playback.records_helpers import records_duration_frame
from backend.services import analysis_records_service as service

pytestmark = pytest.mark.unit


@pytest.fixture
def records_sources(monkeypatch):
    def configure(mode):
        events = pd.DataFrame(
            {
                "play_id": [7, 8],
                "track_id": [1, 2],
                "track_name": ["Song A", "Song B"],
                "album_name": ["Album", "Other"],
                "artist_name": ["Artist", "Artist"],
                "ts_date": ["2026-01-01", "2026-01-02"],
                "ms_played": [40000, 50000],
                "representative_track_id": [101, 102],
                "platform": ["phone", "desktop"],
                "shuffle": [True, False],
                "reason_start": ["clickrow", "trackdone"],
                "reason_end": ["trackdone", "endplay"],
                "skipped": [False, True],
                "offline": [False, False],
            },
            index=[4, 4],
        )
        duration = pd.concat(
            [events, events.iloc[:1].assign(play_id=9, ms_played=9000)], ignore_index=True
        )
        duration["slice_start_at"] = ["2026-01-01T10:00:00"] * 3
        if mode in {"events_empty", "both_empty"}:
            events = events.iloc[:0].copy()
        if mode in {"duration_empty", "both_empty"}:
            duration = duration.iloc[:0].copy()
        attach_listening_duration_frame(events, duration)
        events.attrs["sentinel"] = "preserve source metadata"
        original = events.copy()
        original_duration = duration.copy()
        membership = pd.DataFrame(
            {
                "canonical_song_key": ["k1", "k1"],
                "project_id": [10, 11],
                "album_project_name": ["Project", "Extra"],
                "release_date": ["2026-01-01", "2026"],
                "release_date_precision": ["day", "year"],
            }
        )
        calls = []

        def keys(frame, *args):
            calls.append("keys")
            if mode == "key_error":
                raise RuntimeError("canonical keys unavailable")
            return frame.assign(
                canonical_song_key=frame.track_id.map({1: "k1", 2: "k2"}),
                canonical_song_name=frame.track_name,
            )

        def memberships(*args):
            calls.append("membership")
            if mode == "load_error":
                raise RuntimeError("membership unavailable")
            if mode == "fill_error":
                return membership.astype({"project_id": "Int64"})
            if mode == "empty_membership":
                return membership.iloc[:0].copy()
            if mode == "join_error":
                return membership.drop(columns="release_date_precision")
            return membership.copy()

        def artists(*args, **kwargs):
            if mode == "artist_error":
                raise RuntimeError("artist unavailable")
            return events.copy()

        monkeypatch.setattr(album_projects, "apply_canonical_song_keys", keys)
        monkeypatch.setattr(album_projects, "load_album_project_membership", memberships)
        monkeypatch.setattr(service, "load_plays_for_artists", artists)
        monkeypatch.setattr(
            service,
            "load_track_group_keys",
            lambda *args: pd.DataFrame(
                {
                    "track_id": [1, 2],
                    "track_agg_id": [100, 100],
                    "track_agg_name": ["Song", "Song"],
                }
            ),
        )
        monkeypatch.setattr(
            service, "_load_reliable_album_release_dates", lambda *args: pd.DataFrame()
        )
        return events, duration, original, original_duration, calls

    return configure


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "empty_membership",
        "key_error",
        "load_error",
        "join_error",
        "fill_error",
        "events_empty",
        "duration_empty",
        "both_empty",
        "artist_error",
        "period",
    ],
)
def test_records_projections_preserve_full_frames(records_sources, level, mode):
    events, duration, original, original_duration, calls = records_sources(mode)
    with sqlite3.connect(":memory:") as conn:
        track, album, artist = service._build_entity_frames(
            events,
            conn,
            level,
            period_start="2026-01-02" if mode == "period" else None,
        )
    pd.testing.assert_frame_equal(events, original)
    pd.testing.assert_frame_equal(duration, original_duration)
    successful_join = level >= 2 and mode in {
        "success",
        "events_empty",
        "duration_empty",
        "artist_error",
        "period",
    }
    for frame in (track, album):
        assert set(events.columns) <= set(frame.columns)
        assert frame["representative_track_id"].isin([101, 102]).all()
        assert frame["_logical_event_id"].nunique() == len(events)
        attached = records_duration_frame(frame)
        assert set(duration.columns) <= set(attached.columns)
        expected_rows = len(duration) + (
            int((duration.track_id == 1).sum())
            if frame is album and (successful_join or (level >= 2 and mode == "fill_error"))
            else 0
        )
        assert len(attached) == expected_rows
        if len(duration):
            assert 9 in set(attached.play_id)  # Duration below the play threshold survives.
        frame.loc[:, "track_name"] = "changed"
    assert original.track_name.tolist() == events.track_name.tolist()
    if successful_join and not album.empty:
        assert album.album_project_name.tolist() == ["Project", "Extra", "Other"]
        assert album.album_release_date.tolist() == ["2026-01-01", None, None]
    if level >= 2 and mode not in {"key_error", "both_empty"}:
        assert calls.count("membership") == (
            2 if mode == "load_error" and len(events) and len(duration) else 1
        )
    if mode == "period":
        assert artist.ts_date.tolist() == ["2026-01-02"]


def test_album_join_intermediates_expire_before_next_projection(monkeypatch, records_sources):
    events, *_ = records_sources("success")
    native_keys = album_projects.apply_canonical_song_keys
    native_groups = service.load_track_group_keys
    intermediates = []
    observations = []

    def keys(frame, *args):
        observations.append(("album", sum(ref() is not None for ref in intermediates)))
        result = native_keys(frame, *args)
        intermediates.append(weakref.ref(result))
        return result

    def groups(*args):
        observations.append(("track", sum(ref() is not None for ref in intermediates)))
        return native_groups(*args)

    monkeypatch.setattr(album_projects, "apply_canonical_song_keys", keys)
    monkeypatch.setattr(service, "load_track_group_keys", groups)
    with sqlite3.connect(":memory:") as conn:
        service._build_entity_frames(events, conn, 2)
    assert observations == [("album", 0), ("album", 0), ("track", 0)]


def test_source_release_fallback_keeps_project_day_priority(monkeypatch, records_sources):
    events, *_ = records_sources("success")
    monkeypatch.setattr(
        service,
        "_load_reliable_album_release_dates",
        lambda *args: pd.DataFrame(
            {
                "album_name": ["Album"],
                "artist_name": ["Artist"],
                "source_album_release_date": ["2025-12-31"],
            }
        ),
    )
    with sqlite3.connect(":memory:") as conn:
        _, album, _ = service._build_entity_frames(events, conn, 2)
    assert album.album_release_date.iloc[:2].tolist() == ["2026-01-01", "2025-12-31"]
    assert pd.isna(album.album_release_date.iloc[2])
