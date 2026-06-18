#!/usr/bin/env python3
"""Reusable non-mutating API boundary probe.

This complements ``api_smoke_probe.py``: smoke covers happy-path GETs, while
this probe checks representative invalid params, invalid path values, and safe
special-character searches. The probe must never mutate local app state.
"""

# ruff: noqa: UP045

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class BoundaryCase:
    name: str
    path: str
    params: Optional[dict[str, Any]] = None
    expected_statuses: tuple[int, ...] = (422,)
    expect_validation_detail: bool = True


@dataclass(frozen=True)
class BoundaryResult:
    case: BoundaryCase
    status_code: int
    request_id: Optional[str]
    ok: bool
    detail: str


SPECIAL_SEARCH = "%_🎧/../"

DEFAULT_BOUNDARY_CASES: tuple[BoundaryCase, ...] = (
    BoundaryCase("analysis_plays_limit_zero", "/api/analysis/plays", {"limit": 0}),
    BoundaryCase("analysis_plays_limit_too_high", "/api/analysis/plays", {"limit": 201}),
    BoundaryCase("analysis_plays_offset_negative", "/api/analysis/plays", {"offset": -1}),
    BoundaryCase(
        "analysis_plays_special_search",
        "/api/analysis/plays",
        {"search": SPECIAL_SEARCH, "limit": 5},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase("analysis_charts_limit_zero", "/api/analysis/charts", {"limit": 0}),
    BoundaryCase("analysis_charts_limit_too_high", "/api/analysis/charts", {"limit": 5001}),
    BoundaryCase("leaderboard_invalid_entity", "/api/leaderboard", {"entity": "invalid"}),
    BoundaryCase("leaderboard_empty_entity", "/api/leaderboard", {"entity": ""}),
    BoundaryCase("leaderboard_top_n_low", "/api/leaderboard", {"top_n": 4}),
    BoundaryCase("leaderboard_top_n_high", "/api/leaderboard", {"top_n": 101}),
    BoundaryCase("community_significance_high", "/api/community/feed", {"significance_min": 1.5}),
    BoundaryCase("community_limit_high", "/api/community/feed", {"limit": 201}),
    BoundaryCase(
        "community_special_search",
        "/api/community/feed",
        {"search": SPECIAL_SEARCH, "limit": 5},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase("music_track_path_nonint", "/api/music/tracks/not-an-int/stats"),
    BoundaryCase("billboard_track_path_nonint", "/api/billboard/track/not-an-int"),
    BoundaryCase(
        "release_cycle_weeks_before_low",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha/album/Fixture Future LP",
        {"weeks_before": 0},
    ),
    BoundaryCase(
        "release_cycle_weeks_after_high",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha/album/Fixture Future LP",
        {"weeks_after": 999},
    ),
    BoundaryCase("lyrics_path_nonint", "/api/lyrics/not-an-int"),
    BoundaryCase("chat_sessions_limit_high", "/api/chat/sessions", {"limit": 201}),
)


def _has_validation_detail(response) -> bool:
    try:
        payload = response.json()
    except ValueError:
        return False
    return isinstance(payload.get("detail"), list) and bool(payload["detail"])


def run_cases(
    client, cases: tuple[BoundaryCase, ...] = DEFAULT_BOUNDARY_CASES
) -> list[BoundaryResult]:
    results = []
    for case in cases:
        response = client.get(case.path, params=case.params or {})
        request_id = response.headers.get("X-Request-ID")
        status_ok = response.status_code in case.expected_statuses
        no_server_error = response.status_code < 500
        request_id_ok = bool(request_id)
        validation_detail_ok = not case.expect_validation_detail or _has_validation_detail(response)
        ok = status_ok and no_server_error and request_id_ok and validation_detail_ok
        detail = ""
        if not status_ok:
            detail = f"expected {case.expected_statuses}, got {response.status_code}"
        elif not no_server_error:
            detail = f"server error {response.status_code}"
        elif not request_id_ok:
            detail = "missing X-Request-ID"
        elif not validation_detail_ok:
            detail = "missing FastAPI validation detail"

        results.append(
            BoundaryResult(
                case=case,
                status_code=response.status_code,
                request_id=request_id,
                ok=ok,
                detail=detail,
            )
        )
    return results


def assert_results(results: list[BoundaryResult]) -> None:
    failures = [result for result in results if not result.ok]
    if failures:
        lines = [
            f"{result.case.name}: GET {result.case.path} -> {result.status_code} ({result.detail})"
            for result in failures
        ]
        raise AssertionError("API boundary probe failures:\n" + "\n".join(lines))


def main() -> int:
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        results = run_cases(client)

    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed
    print(f"API boundary probe: {passed}/{len(results)} passed")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status} {result.case.name} {result.status_code} {result.case.path}")

    assert_results(results)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
