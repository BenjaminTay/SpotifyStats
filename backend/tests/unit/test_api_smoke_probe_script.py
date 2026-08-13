from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_api_smoke_probe_exposes_reusable_readonly_cases():
    from scripts.api_smoke_probe import DEFAULT_SAFE_GET_CASES, run_cases

    assert callable(run_cases)
    assert len(DEFAULT_SAFE_GET_CASES) >= 50
    cases_by_path = {case.path: case for case in DEFAULT_SAFE_GET_CASES}
    paths = set(cases_by_path)
    assert "/api/home/overview" in paths
    assert "/api/dashboard/full" in paths
    assert "/api/billboard/summaries" in paths
    assert "/api/spotify/auth/status" in paths
    assert "/api/lyrics/-1" in paths
    assert "/api/lyrics/-1/url" in paths
    assert "/api/community/post/nonexistent-smoke-post" in paths
    assert "/api/settings/llm-profiles/999999" in paths
    assert "/api/yearly-review/available-years" in paths
    assert "/api/yearly-review/2099" in paths
    assert "/api/yearly-review/2099/records" in paths
    assert "/covers/albums/999999999.jpg" in paths
    assert cases_by_path["/api/community/post/nonexistent-smoke-post"].expected_statuses == (404,)
    assert cases_by_path["/api/settings/llm-profiles/999999"].expected_statuses == (404,)
    assert cases_by_path["/covers/albums/999999999.jpg"].expected_statuses == (404,)
    assert cases_by_path["/api/billboard/artist/Fixture Artist Alpha"].expected_statuses == (
        200,
        404,
    )
    assert cases_by_path["/api/billboard/album/Fixture Future LP"].expected_statuses == (
        200,
        404,
    )
    assert "/api/spotify/auth/playing" not in paths


def test_api_smoke_probe_accounts_for_openapi_get_paths():
    from backend.main import app
    from scripts.api_smoke_probe import get_openapi_get_coverage

    coverage = get_openapi_get_coverage(app)

    assert coverage.unaccounted_paths == ()
    assert "/api/spotify/auth/playing" in coverage.excluded_paths
    assert "/api/community/post/{post_id}" in coverage.covered_paths
    assert "/api/settings/llm-profiles/{profile_id}" in coverage.covered_paths
    assert "/covers/{cover_type}/{entity_id}.jpg" in coverage.covered_paths
    assert "/api/lyrics/{track_id}" in coverage.covered_paths
    assert "/api/lyrics/{track_id}/url" in coverage.covered_paths
    assert "/api/music/tracks/{track_id}/stats" in coverage.covered_paths
    assert "/api/yearly-review/{year}" in coverage.covered_paths
    assert "/api/yearly-review/{year}/records" in coverage.covered_paths
    assert "/api/home/overview" in coverage.covered_paths
