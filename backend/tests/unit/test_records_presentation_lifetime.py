"""Presentation retains record results, rather than completed working frames."""

from __future__ import annotations

import sqlite3
import weakref

import pandas as pd
import pytest

from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.domains.playback.records_helpers import records_duration_frame
from backend.services import analysis_records_service as service

pytestmark = pytest.mark.unit


@pytest.fixture
def presentation_case(monkeypatch):
    def configure(preloaded, bounds, mode, *, return_input=False):
        events = pd.DataFrame(
            {
                "play_id": [7, 8, 9],
                "track_id": [1, 2, 3],
                "track_name": ["Before", "Inside", "After"],
                "album_name": ["Album"] * 3,
                "artist_name": ["Artist"] * 3,
                "ts_date": ["2025-12-31", "2026-01-02", "2026-02-01"],
                "ms_played": [40000, 50000, 60000],
                "_logical_event_id": ["annual-A", "annual-B", "annual-C"],
            }
        )
        duration = events.assign(slice_start_at="2026-01-01T00:00:00", ms_played=20000)
        if mode in {"events_empty", "both_empty"}:
            events = events.iloc[:0].copy()
        if mode in {"duration_empty", "both_empty"}:
            duration = duration.iloc[:0].copy()
        attach_listening_duration_frame(events, duration)
        events.attrs["sentinel"] = "unchanged"
        originals = [events.copy(), duration.copy()]
        entities = tuple(events.copy() for _ in range(3)) if preloaded else None
        refs = {}
        stages = []

        def build(frame, *args, **kwargs):
            return tuple(frame.copy() for _ in range(3))

        def compute(**kwargs):
            stages.append("compute")
            for name in ["event_frame", "track_frame", "album_frame", "artist_frame"]:
                frame = kwargs[name]
                assert frame is not events
                refs[name] = weakref.ref(frame)
                refs[name + "_duration"] = weakref.ref(records_duration_frame(frame, copy=False))
            lifetime = kwargs["milestone_event_frame"]
            assert (lifetime is None) is preloaded
            if lifetime is not None:
                pd.testing.assert_frame_equal(lifetime, events)
                refs["lifetime"] = weakref.ref(lifetime)
            if return_input:
                return {"obsession_daily_binge_track": kwargs["track_frame"]}
            return {"obsession_daily_binge_track": pd.DataFrame({"value": [123]})}

        def covers(records):
            stages.append("covers")
            if not return_input:
                assert refs and all(ref() is None for ref in refs.values())
                assert records["obsession_daily_binge_track"]["value"].tolist() == [123]
            else:
                # Results may retain an input or its buffers. Dropping local
                # working references must never invalidate a result owner.
                assert refs["track_frame"]() is records["obsession_daily_binge_track"]
                pd.testing.assert_frame_equal(
                    records["obsession_daily_binge_track"],
                    originals[0],
                )
            pd.testing.assert_frame_equal(events, originals[0])
            pd.testing.assert_frame_equal(duration, originals[1])
            if entities is not None:
                for frame in entities:
                    pd.testing.assert_frame_equal(frame, originals[0])

        monkeypatch.setattr(service, "load_plays", lambda *a, **kw: events)
        monkeypatch.setattr(service, "_build_entity_frames", build)
        monkeypatch.setattr(service, "compute_playback_records", compute)
        monkeypatch.setattr(service, "_add_cover_urls_to_records", covers)
        period = "lifetime" if bounds == (None, None) else "custom"
        with sqlite3.connect(":memory:") as conn:
            payload = service._get_analysis_records_uncached(
                conn,
                30000,
                True,
                True,
                period,
                *bounds,
                2,
                False,
                5,
                False,
                preloaded_event_frame=events if preloaded else None,
                preloaded_entity_frames=entities,
            )
        pd.testing.assert_frame_equal(events, originals[0])
        pd.testing.assert_frame_equal(duration, originals[1])
        return payload, stages

    return configure


@pytest.mark.parametrize("preloaded", [False, True], ids=["standalone", "yearly"])
@pytest.mark.parametrize(
    "bounds",
    [(None, None), ("2026-01-01", None), (None, "2026-01-31"), ("2026-01-01", "2026-01-31")],
)
@pytest.mark.parametrize("mode", ["success", "events_empty", "duration_empty"])
def test_working_frames_released_before_presentation(presentation_case, preloaded, bounds, mode):
    payload, stages = presentation_case(preloaded, bounds, mode)
    assert stages == ["compute", "covers"]
    assert payload["records"]["obsession"]["daily_binge"]["track"][0]["value"] == 123


@pytest.mark.parametrize("preloaded", [False, True])
def test_empty_history_keeps_early_response(presentation_case, preloaded):
    payload, stages = presentation_case(preloaded, (None, None), "both_empty")
    assert stages == []
    assert payload["records"] == {}
    assert payload["meta"]["total_plays"] == 0


@pytest.mark.parametrize("preloaded", [False, True])
def test_returned_record_keeps_its_owner(presentation_case, preloaded):
    payload, stages = presentation_case(preloaded, (None, None), "success", return_input=True)
    assert stages == ["compute", "covers"]
    assert [
        row["track_name"] for row in payload["records"]["obsession"]["daily_binge"]["track"]
    ] == ["Before", "Inside", "After"]
