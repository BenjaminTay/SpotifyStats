from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_api_boundary_probe_exposes_reusable_boundary_cases():
    from scripts.api_boundary_probe import DEFAULT_BOUNDARY_CASES, run_cases

    assert callable(run_cases)
    assert len(DEFAULT_BOUNDARY_CASES) >= 55
    names = {case.name for case in DEFAULT_BOUNDARY_CASES}
    assert "analysis_plays_limit_zero" in names
    assert "analysis_charts_merge_level_low" in names
    assert "billboard_week_start_hour_high" in names
    assert "leaderboard_invalid_entity" in names
    assert "community_special_search" in names
    assert "community_trending_artist_limit_high" in names
    assert "chat_session_path_nonint" in names
    assert "ai_insights_year_nonint" in names
    assert "music_track_path_nonint" in names


def test_api_boundary_probe_cases_cover_validation_and_safe_special_chars():
    from scripts.api_boundary_probe import DEFAULT_BOUNDARY_CASES

    validation_cases = [case for case in DEFAULT_BOUNDARY_CASES if case.expected_statuses == (422,)]
    safe_search_cases = [case for case in DEFAULT_BOUNDARY_CASES if "special" in case.name]

    assert len(validation_cases) >= 10
    assert safe_search_cases
    assert all(case.expect_validation_detail for case in validation_cases)
