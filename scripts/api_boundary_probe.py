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
LONG_STRING = "x" * 512

DEFAULT_BOUNDARY_CASES: tuple[BoundaryCase, ...] = (
    BoundaryCase("analysis_overview_min_ms_negative", "/api/analysis/overview", {"min_ms": -1}),
    BoundaryCase(
        "analysis_overview_max_merge_gap_low",
        "/api/analysis/overview",
        {"max_merge_gap_minutes": 0},
    ),
    BoundaryCase(
        "analysis_overview_max_merge_gap_high",
        "/api/analysis/overview",
        {"max_merge_gap_minutes": 241},
    ),
    BoundaryCase("dashboard_top_tracks_n_nonint", "/api/dashboard/top-tracks", {"n": "many"}),
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
    BoundaryCase("analysis_charts_merge_level_low", "/api/analysis/charts", {"merge_level": 0}),
    BoundaryCase("analysis_charts_merge_level_high", "/api/analysis/charts", {"merge_level": 4}),
    BoundaryCase(
        "analysis_charts_entity_empty",
        "/api/analysis/charts",
        {"entity": ""},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "analysis_charts_entity_long",
        "/api/analysis/charts",
        {"entity": LONG_STRING},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "analysis_charts_metric_empty",
        "/api/analysis/charts",
        {"metric": ""},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "analysis_charts_metric_long",
        "/api/analysis/charts",
        {"metric": LONG_STRING},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "analysis_stats_period_empty",
        "/api/analysis/stats",
        {"period": ""},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "analysis_stats_period_long",
        "/api/analysis/stats",
        {"period": LONG_STRING},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "analysis_records_merge_level_low",
        "/api/analysis/records",
        {"merge_level": 0},
    ),
    BoundaryCase(
        "analysis_records_merge_level_high",
        "/api/analysis/records",
        {"merge_level": 4},
    ),
    BoundaryCase(
        "analysis_records_period_empty",
        "/api/analysis/records",
        {"period": ""},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase("leaderboard_invalid_entity", "/api/leaderboard", {"entity": "invalid"}),
    BoundaryCase("leaderboard_empty_entity", "/api/leaderboard", {"entity": ""}),
    BoundaryCase("leaderboard_invalid_metric", "/api/leaderboard", {"metric": "minutes"}),
    BoundaryCase("leaderboard_invalid_time_range", "/api/leaderboard", {"time_range": "forever"}),
    BoundaryCase("leaderboard_top_n_low", "/api/leaderboard", {"top_n": 4}),
    BoundaryCase("leaderboard_top_n_high", "/api/leaderboard", {"top_n": 101}),
    BoundaryCase("billboard_top_n_low", "/api/billboard/data", {"bb_top_n": 4}),
    BoundaryCase("billboard_top_n_high", "/api/billboard/data", {"bb_top_n": 101}),
    BoundaryCase("billboard_album_top_n_low", "/api/billboard/data", {"bb_album_top_n": 4}),
    BoundaryCase("billboard_album_top_n_high", "/api/billboard/data", {"bb_album_top_n": 101}),
    BoundaryCase("billboard_artist_top_n_low", "/api/billboard/data", {"bb_artist_top_n": 4}),
    BoundaryCase("billboard_artist_top_n_high", "/api/billboard/data", {"bb_artist_top_n": 101}),
    BoundaryCase("billboard_week_start_dow_low", "/api/billboard/data", {"bb_week_start_dow": -1}),
    BoundaryCase("billboard_week_start_dow_high", "/api/billboard/data", {"bb_week_start_dow": 7}),
    BoundaryCase(
        "billboard_week_start_hour_low", "/api/billboard/data", {"bb_week_start_hour": -1}
    ),
    BoundaryCase(
        "billboard_week_start_hour_high", "/api/billboard/data", {"bb_week_start_hour": 24}
    ),
    BoundaryCase("community_significance_low", "/api/community/feed", {"significance_min": -0.1}),
    BoundaryCase("community_significance_high", "/api/community/feed", {"significance_min": 1.5}),
    BoundaryCase("community_limit_high", "/api/community/feed", {"limit": 201}),
    BoundaryCase(
        "community_special_search",
        "/api/community/feed",
        {"search": SPECIAL_SEARCH, "limit": 5},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "community_trending_artist_limit_low", "/api/community/trending", {"artist_limit": 0}
    ),
    BoundaryCase(
        "community_trending_artist_limit_high", "/api/community/trending", {"artist_limit": 21}
    ),
    BoundaryCase(
        "community_trending_track_limit_low", "/api/community/trending", {"track_limit": 0}
    ),
    BoundaryCase(
        "community_trending_track_limit_high", "/api/community/trending", {"track_limit": 21}
    ),
    BoundaryCase(
        "community_post_long_missing",
        f"/api/community/post/{LONG_STRING}",
        expected_statuses=(404,),
        expect_validation_detail=False,
    ),
    BoundaryCase("covers_entity_id_nonint", "/covers/albums/not-an-int.jpg"),
    BoundaryCase(
        "cover_type_long",
        f"/covers/{LONG_STRING}/1.jpg",
        expected_statuses=(404,),
        expect_validation_detail=False,
    ),
    BoundaryCase("library_playlist_path_nonint", "/api/library/playlists/not-an-int/tracks"),
    BoundaryCase(
        "library_saved_tracks_page_nonint", "/api/library/saved-tracks", {"page": "first"}
    ),
    BoundaryCase(
        "library_saved_tracks_limit_nonint", "/api/library/saved-tracks", {"limit": "many"}
    ),
    BoundaryCase(
        "library_saved_tracks_search_empty",
        "/api/library/saved-tracks",
        {"search": "", "limit": 5},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "library_saved_tracks_search_long",
        "/api/library/saved-tracks",
        {"search": LONG_STRING, "limit": 5},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase("wrapped_year_path_nonint", "/api/wrapped/not-an-int"),
    BoundaryCase("settings_llm_profile_path_nonint", "/api/settings/llm-profiles/not-an-int"),
    BoundaryCase("chat_session_path_nonint", "/api/chat/sessions/not-an-int"),
    BoundaryCase("version_group_path_nonint", "/api/version-merge/groups/not-an-int/members"),
    BoundaryCase("music_track_path_nonint", "/api/music/tracks/not-an-int/stats"),
    BoundaryCase("music_search_q_too_long", "/api/music/search", {"q": LONG_STRING}),
    BoundaryCase(
        "music_search_kind_invalid", "/api/music/search", {"q": "Fixture", "kind": "playlist"}
    ),
    BoundaryCase(
        "music_search_limit_low", "/api/music/search", {"q": "Fixture", "limit_per_type": 0}
    ),
    BoundaryCase(
        "music_search_limit_high", "/api/music/search", {"q": "Fixture", "limit_per_type": 11}
    ),
    BoundaryCase("billboard_track_path_nonint", "/api/billboard/track/not-an-int"),
    BoundaryCase(
        "music_album_long_name",
        f"/api/music/albums/{LONG_STRING}/stats",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "music_artist_long_name",
        f"/api/music/artists/{LONG_STRING}/stats",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "artist_deep_dive_long_name",
        f"/api/artist/{LONG_STRING}/deep-dive",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_album_long_name",
        f"/api/billboard/album/{LONG_STRING}",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_artist_long_name",
        f"/api/billboard/artist/{LONG_STRING}",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_album_artist_name_empty",
        "/api/billboard/album/Fixture Future LP",
        {"artist_name": ""},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_album_artist_name_long",
        "/api/billboard/album/Fixture Future LP",
        {"artist_name": LONG_STRING},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "version_compare_album_id_a_nonint",
        "/api/version-merge/compare",
        {"album_id_a": "left", "album_id_b": 925},
    ),
    BoundaryCase(
        "version_compare_album_id_b_nonint",
        "/api/version-merge/compare",
        {"album_id_a": 921, "album_id_b": "right"},
    ),
    BoundaryCase(
        "version_album_types_album_ids_empty",
        "/api/version-merge/album-types",
        {"album_ids": ""},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "version_album_types_album_ids_long",
        "/api/version-merge/album-types",
        {"album_ids": ",".join(["1"] * 300)},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_versus_track_id_a_nonint",
        "/api/billboard/versus/track",
        {"track_id_a": "left", "track_id_b": 906},
    ),
    BoundaryCase(
        "billboard_versus_track_id_b_nonint",
        "/api/billboard/versus/track",
        {"track_id_a": 905, "track_id_b": "right"},
    ),
    BoundaryCase(
        "billboard_versus_album_a_empty",
        "/api/billboard/versus/album",
        {
            "album_a": "",
            "artist_a": "Fixture Artist Alpha",
            "album_b": "Fixture Future LP",
            "artist_b": "Fixture Artist Alpha",
        },
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_versus_album_a_long",
        "/api/billboard/versus/album",
        {
            "album_a": LONG_STRING,
            "artist_a": "Fixture Artist Alpha",
            "album_b": "Fixture Future LP",
            "artist_b": "Fixture Artist Alpha",
        },
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_versus_album_b_empty",
        "/api/billboard/versus/album",
        {
            "album_a": "Fixture Future LP",
            "artist_a": "Fixture Artist Alpha",
            "album_b": "",
            "artist_b": "Fixture Artist Alpha",
        },
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_versus_artist_a_empty",
        "/api/billboard/versus/artist",
        {"artist_a": "", "artist_b": "Fixture Artist Beta"},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "billboard_versus_artist_a_long",
        "/api/billboard/versus/artist",
        {"artist_a": LONG_STRING, "artist_b": "Fixture Artist Beta"},
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "job_status_long_missing",
        f"/api/jobs/{LONG_STRING}/status",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "import_status_long_missing",
        f"/api/import/status/{LONG_STRING}",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase(
        "ai_task_long_missing",
        f"/api/ai/tasks/{LONG_STRING}",
        expected_statuses=(200,),
        expect_validation_detail=False,
    ),
    BoundaryCase("ai_insights_year_nonint", "/api/ai-insights/yearly-story", {"year": "twenty"}),
    BoundaryCase(
        "release_cycle_artist_weeks_before_low",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha",
        {"weeks_before": 0},
    ),
    BoundaryCase(
        "release_cycle_artist_weeks_before_high",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha",
        {"weeks_before": 25},
    ),
    BoundaryCase(
        "release_cycle_artist_weeks_after_low",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha",
        {"weeks_after": 3},
    ),
    BoundaryCase(
        "release_cycle_artist_weeks_after_high",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha",
        {"weeks_after": 53},
    ),
    BoundaryCase(
        "release_cycle_weeks_before_low",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha/album/Fixture Future LP",
        {"weeks_before": 0},
    ),
    BoundaryCase(
        "release_cycle_album_weeks_before_high",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha/album/Fixture Future LP",
        {"weeks_before": 53},
    ),
    BoundaryCase(
        "release_cycle_album_weeks_after_low",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha/album/Fixture Future LP",
        {"weeks_after": 3},
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
