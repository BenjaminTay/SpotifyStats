"""Release the complete collaboration identity table after its final consumer."""

from __future__ import annotations

import weakref

import pandas as pd
import pytest

from backend.domains.playback import records_collaboration as collaboration
from backend.tests.unit.test_collaboration_select_projection import select_sources
from backend.tests.unit.test_playback_records_collaboration import (
    credit_conn as _credit_conn_fixture,
)

credit_conn = _credit_conn_fixture

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("mode", ["integer", "all", "none"])
@pytest.mark.parametrize("attached_duration", [False, True])
def test_identity_projection_released_before_credit_fanout(
    monkeypatch, credit_conn, mode, attached_duration
):
    frames, _ = select_sources(mode, True)
    if not attached_duration:
        for frame in frames:
            frame.attrs.pop("listening_duration_frame", None)
    source_ids = {id(frame) for frame in frames}
    expected_total = frames[0]["_logical_event_id"].nunique()
    native_projection = collaboration._event_projection
    native_merge = pd.DataFrame.merge
    projected = []
    observed = []

    def project(frame, events):
        assert id(events) not in source_ids
        projected.append(weakref.ref(events))
        return native_projection(frame, events)

    def merge(frame, *args, **kwargs):
        if len(projected) == 2 and not observed:
            observed.append(True)
            assert projected[-1]() is None
        return native_merge(frame, *args, **kwargs)

    monkeypatch.setattr(collaboration, "_event_projection", project)
    monkeypatch.setattr(pd.DataFrame, "merge", merge)
    facts = collaboration.build_collaboration_facts(*frames, pd.DataFrame(), credit_conn)
    assert observed == [True]
    assert facts.total_events == expected_total
    assert (
        facts.events.play_id.tolist()
        == {
            "integer": [1, 3, 4],
            "all": [1, 2, 3, 4],
            "none": [],
        }[mode]
    )
