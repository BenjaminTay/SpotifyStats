from __future__ import annotations

import sqlite3
from copy import deepcopy

import pandas as pd

from backend.domains.playback.logical_timeline import (
    LISTENING_INTERVALS_COLUMN,
    attach_listening_duration_frame,
    get_listening_duration_frame,
)
from backend.domains.playback.records_helpers import (
    attach_scoped_records_duration,
    records_duration_frame,
)
from backend.domains.playback.records_obsession import (
    _consecutive_marathon,
    _daily_binge,
    _daily_total_record,
)
from backend.services import analysis_records_service


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "play_id": 1,
                "ts": "2026-01-01T00:03:00Z",
                "ts_date": "2026-01-01",
                "track_id": "a",
                "track_name": "A",
                "album_name": "Album A",
                "artist_name": "Artist",
                "ms_played": 180_000,
            },
            {
                "play_id": 2,
                "ts": "2026-01-01T00:06:00Z",
                "ts_date": "2026-01-01",
                "track_id": "a",
                "track_name": "A",
                "album_name": "Album A",
                "artist_name": "Artist",
                "ms_played": 180_000,
            },
            {
                "play_id": 3,
                "ts": "2026-01-01T00:09:00Z",
                "ts_date": "2026-01-01",
                "track_id": "b",
                "track_name": "B",
                "album_name": "Album B",
                "artist_name": "Artist",
                "ms_played": 200_000,
            },
            {
                "play_id": 4,
                "ts": "2026-01-01T00:12:00Z",
                "ts_date": "2026-01-01",
                "track_id": "b",
                "track_name": "B",
                "album_name": "Album B",
                "artist_name": "Artist",
                "ms_played": 200_000,
            },
        ]
    )


def test_attached_duration_reference_survives_frame_copy_without_copying_payload() -> None:
    events = _events()
    duration = events.copy()
    attach_listening_duration_frame(events, duration)

    copied = deepcopy(events)

    assert get_listening_duration_frame(copied) is duration


def test_records_duration_scope_does_not_leak_global_attached_rows() -> None:
    events = _events().iloc[:1].copy()
    duration = pd.DataFrame(
        [
            {**events.iloc[0].to_dict(), "ms_played": 20_000},
            {
                **events.iloc[0].to_dict(),
                "ts_date": "2026-02-01",
                "ms_played": 25_000,
            },
        ]
    )
    attach_listening_duration_frame(events, duration)

    attach_scoped_records_duration(
        events,
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    scoped = records_duration_frame(events)
    assert scoped["ts_date"].tolist() == ["2026-01-01"]
    assert scoped["ms_played"].sum() == 20_000


def test_records_duration_scope_replaces_yearly_bare_slices_with_safe_reference() -> None:
    events = _events().iloc[:1].copy()
    global_duration = pd.DataFrame(
        [
            {**events.iloc[0].to_dict(), "ms_played": 20_000},
            {
                **events.iloc[0].to_dict(),
                "ts_date": "2026-02-01",
                "ms_played": 25_000,
            },
        ]
    )
    attach_listening_duration_frame(events, global_duration)
    events.attrs["listening_duration_slices"] = global_duration.iloc[:1].copy()

    attach_scoped_records_duration(
        events,
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    assert "listening_duration_slices" not in events.attrs
    scoped = get_listening_duration_frame(events)
    assert scoped is not None
    assert scoped["ts_date"].tolist() == ["2026-01-01"]
    assert scoped["ms_played"].sum() == 20_000


def test_records_duration_scope_slices_cross_midnight_interval_before_filtering() -> None:
    events = _events().iloc[:1].copy()
    start = pd.Timestamp("2025-12-31T15:59:00Z")
    end = pd.Timestamp("2025-12-31T16:01:00Z")
    duration = events.assign(
        ts="2025-12-31T16:01:00Z",
        ts_date="2026-01-01",
        ms_played=120_000,
    )
    duration[LISTENING_INTERVALS_COLUMN] = [[(int(start.value), int(end.value))]]
    attach_listening_duration_frame(events, duration)

    attach_scoped_records_duration(
        events,
        start_date="2026-01-01",
        end_date="2026-01-01",
    )

    scoped = records_duration_frame(events)
    assert scoped["ts_date"].astype(str).tolist() == ["2026-01-01"]
    assert scoped["ms_played"].sum() == 60_000


def test_count_record_uses_all_duration_only_as_tie_breaker() -> None:
    events = _events()
    duration = events.copy()
    duration = pd.concat(
        [
            duration,
            pd.DataFrame(
                [
                    {
                        **events.iloc[0].to_dict(),
                        "play_id": 99,
                        "ms_played": 25_000,
                    },
                    {
                        **events.iloc[0].to_dict(),
                        "play_id": 100,
                        "ms_played": 25_000,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    attach_listening_duration_frame(events, duration)

    result = _daily_binge(events, "track_id", "track_name", "artist_name")

    assert result.iloc[0]["entity_id"] == "a"
    assert result.iloc[0]["plays"] == 2
    assert result.iloc[0]["total_ms"] == 410_000


def test_daily_total_uses_all_duration_but_keeps_qualified_play_count() -> None:
    events = _events().iloc[:1].copy()
    duration = pd.concat(
        [events, events.assign(play_id=99, ms_played=20_000)],
        ignore_index=True,
    )
    attach_listening_duration_frame(events, duration)

    result = _daily_total_record(events, events, events, events).iloc[0]

    assert result["total_plays"] == 1
    assert result["total_ms"] == 200_000


def test_consecutive_marathon_remains_on_qualified_event_sequence() -> None:
    events = _events().iloc[:2].copy()
    duration = pd.concat(
        [
            events,
            pd.DataFrame(
                [
                    {
                        **events.iloc[0].to_dict(),
                        "play_id": 99,
                        "track_id": "b",
                        "track_name": "B",
                        "ms_played": 25_000,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    attach_listening_duration_frame(events, duration)

    result = _consecutive_marathon(
        events,
        "track_id",
        "track_name",
        "artist_name",
    ).iloc[0]

    assert result["entity_id"] == "a"
    assert result["value"] == 2
    assert result["total_ms"] == 360_000


def test_records_meta_uses_scoped_all_duration_without_changing_counts(monkeypatch) -> None:
    event = _events().iloc[:1].copy()
    event["ms_played"] = 3_400_000
    short_rows = pd.concat(
        [event.assign(play_id=100 + index, ms_played=20_000) for index in range(10)],
        ignore_index=True,
    )
    duration = pd.concat(
        [
            event,
            short_rows,
            event.assign(play_id=999, ts_date="2026-02-01", ms_played=3_600_000),
        ],
        ignore_index=True,
    )
    attach_listening_duration_frame(event, duration)
    monkeypatch.setattr(analysis_records_service, "compute_playback_records", lambda **_: {})
    monkeypatch.setattr(analysis_records_service, "_add_cover_urls_to_records", lambda _: None)
    monkeypatch.setattr(analysis_records_service, "_serialize_records", lambda _: {})

    payload = analysis_records_service._get_analysis_records_uncached(
        conn=sqlite3.connect(":memory:"),
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        period="custom",
        start_date="2026-01-01",
        end_date="2026-01-31",
        merge_level=2,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
        include_compilations=False,
        preloaded_event_frame=event,
        preloaded_entity_frames=(event, event, event),
    )

    assert payload["meta"]["total_plays"] == 1
    assert payload["meta"]["total_hours"] == 1.0
    assert payload["meta"]["active_days"] == 1


def test_records_event_keys_assigned_before_custom_scope_preserve_duplicate_ordinals(
    monkeypatch,
) -> None:
    events = _events().iloc[:2].copy()
    events["play_id"] = 7
    events.loc[events.index[0], "ts_date"] = "2025-12-31"
    captured = {}

    def capture_records(**kwargs):
        captured.update(kwargs)
        return {}

    def entities(frame, *args, **kwargs):
        return frame.copy(), frame.copy(), frame.copy()

    monkeypatch.setattr(analysis_records_service, "load_plays", lambda *a, **kw: events)
    monkeypatch.setattr(analysis_records_service, "_build_entity_frames", entities)
    monkeypatch.setattr(analysis_records_service, "compute_playback_records", capture_records)
    monkeypatch.setattr(analysis_records_service, "_add_cover_urls_to_records", lambda _: None)
    payload = analysis_records_service._get_analysis_records_uncached(
        conn=sqlite3.connect(":memory:"),
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        period="custom",
        start_date="2026-01-01",
        end_date="2026-01-31",
        merge_level=2,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
        include_compilations=False,
    )
    assert payload["meta"]["total_plays"] == 1
    for field in ("event_frame", "track_frame", "album_frame", "artist_frame"):
        assert captured[field]["_logical_event_id"].tolist() == ["raw_play_v1:7:1"]


def test_yearly_entity_builder_keeps_preexisting_logical_keys_and_track_identity(
    monkeypatch,
) -> None:
    events = _events().iloc[:2].copy()
    events["_logical_event_id"] = ["annual-key-1", "annual-key-2"]
    events["representative_track_id"] = [101, 102]
    artists = events.assign(artist_id=1)
    monkeypatch.setattr(
        analysis_records_service, "load_plays_for_artists", lambda *a, **kw: artists
    )
    monkeypatch.setattr(
        analysis_records_service, "_load_reliable_album_release_dates", lambda _: pd.DataFrame()
    )
    frames = analysis_records_service._build_entity_frames(events, sqlite3.connect(":memory:"), 1)
    for frame in frames:
        assert frame["_logical_event_id"].tolist() == ["annual-key-1", "annual-key-2"]
        assert frame["representative_track_id"].tolist() == [101, 102]


def test_entity_builder_keeps_played_credit_key_when_group_projection_has_its_own_representative(
    monkeypatch,
) -> None:
    events = _events().iloc[:2].copy()
    events["representative_track_id"] = [101, 102]
    duration = events.assign(ms_played=90000)
    attach_listening_duration_frame(events, duration)
    groups = pd.DataFrame(
        {
            "track_id": ["a", "b"],
            "track_agg_id": [999, 999],
            "track_agg_name": ["Song", "Song"],
            "representative_track_id": [201, 202],
            "representative_track_agg_id": [301, 301],
        }
    )
    monkeypatch.setattr(analysis_records_service, "load_track_group_keys", lambda *a: groups)
    monkeypatch.setattr(
        analysis_records_service, "load_plays_for_artists", lambda *a, **kw: events.copy()
    )
    monkeypatch.setattr(
        analysis_records_service, "_load_reliable_album_release_dates", lambda _: pd.DataFrame()
    )
    for level in (2, 3):
        track, _, _ = analysis_records_service._build_entity_frames(
            events, sqlite3.connect(":memory:"), level
        )
        assert track["canonical_track_id"].tolist() == [999, 999]
        assert track["representative_track_id"].tolist() == [101, 102]
        track_duration = records_duration_frame(track)
        assert track_duration["canonical_track_id"].tolist() == [999, 999]
        assert track_duration["representative_track_id"].tolist() == [101, 102]
        assert not {"representative_track_id_x", "representative_track_id_y"} & set(track.columns)
