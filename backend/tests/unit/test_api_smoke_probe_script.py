from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_api_smoke_probe_exposes_reusable_readonly_cases():
    from scripts.api_smoke_probe import DEFAULT_SAFE_GET_CASES, run_cases

    assert callable(run_cases)
    assert len(DEFAULT_SAFE_GET_CASES) >= 50
    paths = {case.path for case in DEFAULT_SAFE_GET_CASES}
    assert "/api/dashboard/full" in paths
    assert "/api/billboard/summaries" in paths
    assert "/api/spotify/auth/status" in paths
    assert "/api/lyrics/901" not in paths
    assert "/api/spotify/auth/playing" not in paths


def test_api_smoke_probe_accounts_for_openapi_get_paths():
    from backend.main import app
    from scripts.api_smoke_probe import get_openapi_get_coverage

    coverage = get_openapi_get_coverage(app)

    assert coverage.unaccounted_paths == ()
    assert "/api/spotify/auth/playing" in coverage.excluded_paths
    assert "/api/music/tracks/{track_id}/stats" in coverage.covered_paths
