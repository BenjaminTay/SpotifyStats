from __future__ import annotations

import pytest

from scripts.api_boundary_probe import DEFAULT_BOUNDARY_CASES, assert_results, run_cases

pytestmark = pytest.mark.contract


def test_api_boundary_probe(client):
    results = run_cases(client)

    assert len(DEFAULT_BOUNDARY_CASES) >= 15
    assert_results(results)
    assert {result.case.name for result in results} >= {
        "analysis_plays_limit_zero",
        "leaderboard_invalid_entity",
        "community_special_search",
        "music_track_path_nonint",
    }
