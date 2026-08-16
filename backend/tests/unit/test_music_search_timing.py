from __future__ import annotations

import pytest

from backend.domains.music_search.timing import MusicSearchTiming, measure_search_phase

pytestmark = pytest.mark.unit


def test_music_search_timing_collects_repeatable_phases() -> None:
    values = iter([1.0, 1.025, 2.0, 2.01])
    timing = MusicSearchTiming(clock=lambda: next(values))

    with timing.measure("candidate_query"):
        pass
    with measure_search_phase(timing, "candidate_query"):
        pass

    assert timing.as_dict() == {"candidate_query": 35.0}
    assert timing.server_timing_header() == "candidate_query;dur=35.000"


def test_measure_search_phase_accepts_disabled_timing() -> None:
    with measure_search_phase(None, "candidate_query"):
        pass
