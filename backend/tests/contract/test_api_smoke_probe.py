from __future__ import annotations

import pytest

from scripts.api_smoke_probe import DEFAULT_SAFE_GET_CASES, assert_results, run_cases

pytestmark = pytest.mark.contract


def test_safe_readonly_api_smoke_probe(client):
    results = run_cases(client)

    assert len(DEFAULT_SAFE_GET_CASES) >= 50
    assert_results(results)
    assert {result.case.path for result in results} >= {
        "/api/dashboard/full",
        "/api/billboard/summaries",
        "/api/community/post/nonexistent-smoke-post",
        "/api/lyrics/-1",
        "/api/lyrics/-1/url",
        "/api/settings/llm-profiles/999999",
        "/api/spotify/auth/status",
        "/covers/albums/999999999.jpg",
    }
