#!/usr/bin/env python3
"""Reusable read-only API smoke probe.

The default case list intentionally avoids mutating endpoints, OAuth callback
exchange, and LLM-generating requests. It is safe to run against the contract
seed database or a local development database.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class SmokeCase:
    name: str
    path: str
    params: dict[str, Any] | None = None
    expected_statuses: tuple[int, ...] = (200,)
    expected_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class SmokeResult:
    case: SmokeCase
    status_code: int
    request_id: str | None
    ok: bool
    detail: str


@dataclass(frozen=True)
class CoverageSummary:
    get_path_count: int
    covered_paths: frozenset[str]
    excluded_paths: frozenset[str]
    unaccounted_paths: tuple[str, ...]


DEFAULT_FILTERS = {
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "dynamic_threshold": True,
}

DEFAULT_BILLBOARD = {
    **DEFAULT_FILTERS,
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "merge_level": 2,
}

DEFAULT_EXCLUDED_GET_PATHS: frozenset[str] = frozenset(
    {
        # LLM or external enrichment calls are intentionally outside the
        # default local-only smoke probe.
        "/api/ai-insights/monthly-personality",
        "/api/ai-insights/weekly-digest",
        "/api/ai-insights/yearly-story",
        "/api/billboard/enrichment/album/{album_name}",
        "/api/billboard/enrichment/artist/{artist_name}",
        "/api/billboard/enrichment/track/{track_name}",
        # OAuth and live playback depend on a real browser/session or Spotify's
        # live API; they are covered by dedicated targeted tests where possible.
        "/api/spotify/auth/callback",
        "/api/spotify/auth/login",
        "/api/spotify/auth/playing",
        # Artist genre metadata endpoints — read-only review/coverage/taxonomy
        # and per-axis gaps are covered by dedicated metadata tests.
        "/api/metadata/artist-genres/axis-gaps",
        "/api/metadata/artist-genres/coverage",
        "/api/metadata/artist-genres/reviews",
        "/api/metadata/artist-genres/taxonomy",
    }
)

DEFAULT_SAFE_GET_CASES: tuple[SmokeCase, ...] = (
    SmokeCase("health", "/api/health"),
    SmokeCase("openapi", "/openapi.json"),
    SmokeCase("cover_missing", "/covers/albums/999999999.jpg", expected_statuses=(404,)),
    SmokeCase("analysis_overview", "/api/analysis/overview", DEFAULT_FILTERS),
    SmokeCase("analysis_stats", "/api/analysis/stats", {**DEFAULT_FILTERS, "period": "lifetime"}),
    SmokeCase(
        "analysis_charts",
        "/api/analysis/charts",
        {**DEFAULT_FILTERS, "entity": "track", "metric": "plays", "limit": 25},
    ),
    SmokeCase("analysis_plays", "/api/analysis/plays", {**DEFAULT_FILTERS, "limit": 5}),
    SmokeCase("analysis_play_dates", "/api/analysis/play-dates", DEFAULT_FILTERS),
    SmokeCase(
        "analysis_records",
        "/api/analysis/records",
        {**DEFAULT_FILTERS, "period": "lifetime", "merge_level": 2},
    ),
    SmokeCase("dashboard_summary", "/api/dashboard/summary", DEFAULT_FILTERS),
    SmokeCase("dashboard_full", "/api/dashboard/full", DEFAULT_FILTERS),
    SmokeCase("dashboard_top_tracks", "/api/dashboard/top-tracks", {**DEFAULT_FILTERS, "n": 5}),
    SmokeCase("dashboard_platform", "/api/dashboard/platform-dist", DEFAULT_FILTERS),
    SmokeCase("dashboard_dow", "/api/dashboard/dow-dist", DEFAULT_FILTERS),
    SmokeCase("dashboard_random", "/api/dashboard/random-track", DEFAULT_FILTERS),
    SmokeCase("timeline_annual", "/api/timeline/annual", DEFAULT_FILTERS),
    SmokeCase("timeline_monthly", "/api/timeline/monthly", DEFAULT_FILTERS),
    SmokeCase("timeline_weekly", "/api/timeline/weekly", DEFAULT_FILTERS),
    SmokeCase(
        "leaderboard_track",
        "/api/leaderboard",
        {**DEFAULT_FILTERS, "entity": "track", "metric": "plays", "top_n": 10},
    ),
    SmokeCase("behavior", "/api/behavior", {"music_only": True}),
    SmokeCase("listening_heatmap", "/api/listening-hours/heatmap", DEFAULT_FILTERS),
    SmokeCase("listening_yearly", "/api/listening-hours/yearly", DEFAULT_FILTERS),
    SmokeCase("listening_late_night", "/api/listening-hours/late-night", DEFAULT_FILTERS),
    SmokeCase("listening_weekday_weekend", "/api/listening-hours/weekday-weekend", DEFAULT_FILTERS),
    SmokeCase("listening_platform_hourly", "/api/listening-hours/platform-hourly", DEFAULT_FILTERS),
    SmokeCase("artist_list", "/api/artist/list", DEFAULT_FILTERS),
    SmokeCase("artist_deep_dive", "/api/artist/Fixture Artist Alpha/deep-dive", DEFAULT_FILTERS),
    SmokeCase(
        "artist-language-coverage",
        "/api/metadata/artist-languages/coverage",
        DEFAULT_FILTERS,
    ),
    SmokeCase("artist-language-reviews", "/api/metadata/artist-languages/reviews"),
    SmokeCase("wrapped_years", "/api/wrapped/available-years"),
    SmokeCase("wrapped_2024", "/api/wrapped/2024", DEFAULT_FILTERS),
    SmokeCase("wrapped_2024_full", "/api/wrapped/2024/full", DEFAULT_FILTERS),
    SmokeCase("library", "/api/library"),
    SmokeCase("library_playlists", "/api/library/playlists"),
    SmokeCase("library_playlist_tracks", "/api/library/playlists/1/tracks"),
    SmokeCase("library_saved_tracks", "/api/library/saved-tracks", {"page": 1, "limit": 5}),
    SmokeCase("library_playlist_overlap", "/api/library/playlist-overlap"),
    SmokeCase("search_history", "/api/search-history"),
    SmokeCase("insights_tiers", "/api/insights/tiers"),
    SmokeCase("insights_marquee", "/api/insights/marquee"),
    SmokeCase("podcast", "/api/podcast"),
    SmokeCase("podcast_interactions", "/api/podcast/interactions"),
    SmokeCase("podcast_saved_shows", "/api/podcast/saved-shows"),
    SmokeCase("video", "/api/video"),
    SmokeCase("profile", "/api/profile"),
    SmokeCase("profile_inferences", "/api/profile/inferences"),
    SmokeCase("sound_capsule", "/api/profile/sound-capsule"),
    SmokeCase("wrapped_hub_years", "/api/wrapped-hub/available-years"),
    SmokeCase("wrapped_hub", "/api/wrapped-hub"),
    SmokeCase("settings", "/api/settings"),
    SmokeCase("settings_llm_profiles", "/api/settings/llm-profiles"),
    SmokeCase(
        "settings_llm_profile_missing",
        "/api/settings/llm-profiles/999999",
        expected_statuses=(404,),
    ),
    SmokeCase("billboard_data", "/api/billboard/data", DEFAULT_BILLBOARD),
    SmokeCase("billboard_weekly", "/api/billboard/weekly", DEFAULT_BILLBOARD),
    SmokeCase("billboard_records", "/api/billboard/records", DEFAULT_BILLBOARD),
    SmokeCase("billboard_power", "/api/billboard/power-scores", DEFAULT_BILLBOARD),
    SmokeCase("billboard_summaries", "/api/billboard/summaries", DEFAULT_BILLBOARD),
    SmokeCase("billboard_all_time", "/api/billboard/all-time", DEFAULT_BILLBOARD),
    SmokeCase("billboard_year_end", "/api/billboard/year-end", DEFAULT_BILLBOARD),
    SmokeCase(
        "release_cycle_artist_list", "/api/billboard/release-cycle/artist-list", DEFAULT_BILLBOARD
    ),
    SmokeCase(
        "release_cycle_artist",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha",
        DEFAULT_BILLBOARD,
    ),
    SmokeCase(
        "release_cycle_album",
        "/api/billboard/release-cycle/artist/Fixture Artist Alpha/album/Fixture Future LP",
        DEFAULT_BILLBOARD,
    ),
    SmokeCase("billboard_track_detail", "/api/billboard/track/901", DEFAULT_BILLBOARD),
    SmokeCase(
        "billboard_artist_detail", "/api/billboard/artist/Fixture Artist Alpha", DEFAULT_BILLBOARD
    ),
    SmokeCase(
        "billboard_album_detail", "/api/billboard/album/Fixture Future LP", DEFAULT_BILLBOARD
    ),
    SmokeCase("billboard_entity_lists", "/api/billboard/entity-lists", DEFAULT_BILLBOARD),
    SmokeCase(
        "billboard_versus_track",
        "/api/billboard/versus/track",
        {**DEFAULT_BILLBOARD, "track_id_a": 905, "track_id_b": 906},
    ),
    SmokeCase(
        "billboard_versus_album",
        "/api/billboard/versus/album",
        {
            **DEFAULT_BILLBOARD,
            "album_a": "Fixture Future LP",
            "artist_a": "Fixture Artist Alpha",
            "album_b": "Fixture Future LP Deluxe",
            "artist_b": "Fixture Artist Alpha",
        },
    ),
    SmokeCase(
        "billboard_versus_artist",
        "/api/billboard/versus/artist",
        {
            **DEFAULT_BILLBOARD,
            "artist_a": "Fixture Artist Alpha",
            "artist_b": "Fixture Artist Beta",
        },
    ),
    SmokeCase("community_feed", "/api/community/feed", {"limit": 5}),
    SmokeCase("community_trending", "/api/community/trending"),
    SmokeCase(
        "community_post_missing",
        "/api/community/post/nonexistent-smoke-post",
        expected_statuses=(404,),
    ),
    SmokeCase("version_groups", "/api/version-merge/groups"),
    SmokeCase("version_group_members", "/api/version-merge/groups/2/members"),
    SmokeCase("version_artist_groups", "/api/version-merge/groups/artist/Fixture Artist Alpha"),
    SmokeCase("version_ungrouped", "/api/version-merge/ungrouped"),
    SmokeCase(
        "version_compare", "/api/version-merge/compare", {"album_id_a": 921, "album_id_b": 925}
    ),
    SmokeCase("version_album_types", "/api/version-merge/album-types", {"album_ids": "921,925"}),
    SmokeCase(
        "version_collab_candidates", "/api/version-merge/track-group-candidates/collaboration"
    ),
    SmokeCase("import_status_missing", "/api/import/status/nonexistent"),
    SmokeCase("music_search", "/api/music/search", {"q": "Fixture", "limit_per_type": 3}),
    SmokeCase("music_track_stats", "/api/music/tracks/901/stats", DEFAULT_FILTERS),
    SmokeCase("music_album_stats", "/api/music/albums/Fixture Future LP/stats", DEFAULT_FILTERS),
    SmokeCase(
        "music_artist_stats", "/api/music/artists/Fixture Artist Alpha/stats", DEFAULT_FILTERS
    ),
    SmokeCase("music_track_plays", "/api/music/tracks/901/plays", {**DEFAULT_FILTERS, "limit": 5}),
    SmokeCase(
        "music_album_plays",
        "/api/music/albums/Fixture Future LP/plays",
        {**DEFAULT_FILTERS, "limit": 5},
    ),
    SmokeCase(
        "music_artist_plays",
        "/api/music/artists/Fixture Artist Alpha/plays",
        {**DEFAULT_FILTERS, "limit": 5},
    ),
    SmokeCase("music_track_dates", "/api/music/tracks/901/play-dates", DEFAULT_FILTERS),
    SmokeCase(
        "music_album_dates", "/api/music/albums/Fixture Future LP/play-dates", DEFAULT_FILTERS
    ),
    SmokeCase(
        "music_artist_dates", "/api/music/artists/Fixture Artist Alpha/play-dates", DEFAULT_FILTERS
    ),
    SmokeCase("lyrics_missing", "/api/lyrics/-1"),
    SmokeCase("lyrics_url_missing", "/api/lyrics/-1/url"),
    SmokeCase("account", "/api/account"),
    SmokeCase("account_collection", "/api/account/collection-insights"),
    SmokeCase(
        "ai_task_missing",
        "/api/ai/tasks/nonexistent-smoke-task",
        expected_json={"found": False},
    ),
    SmokeCase(
        "ai_task_events_missing",
        "/api/ai/tasks/nonexistent-smoke-task/events",
        expected_json={"found": False, "events": [], "tool_calls": []},
    ),
    SmokeCase(
        "ai_suggested_questions", "/api/ai-insights/suggested-questions", {"context": "chat"}
    ),
    SmokeCase("chat_sessions", "/api/chat/sessions", {"limit": 5}),
    SmokeCase("chat_session_missing", "/api/chat/sessions/999999"),
    SmokeCase("admin_cache_stats", "/api/admin/cache-stats"),
    SmokeCase("job_missing", "/api/jobs/nonexistent/status"),
    SmokeCase("spotify_status", "/api/spotify/auth/status"),
    SmokeCase("spotify_data", "/api/spotify/auth/data"),
)


def run_cases(client, cases: tuple[SmokeCase, ...] = DEFAULT_SAFE_GET_CASES) -> list[SmokeResult]:
    results = []
    for case in cases:
        response = client.get(case.path, params=case.params or {})
        request_id = response.headers.get("X-Request-ID")
        status_ok = response.status_code in case.expected_statuses
        no_server_error = response.status_code < 500
        request_id_ok = bool(request_id)
        expected_json_ok = True
        if case.expected_json is not None:
            try:
                expected_json_ok = response.json() == case.expected_json
            except ValueError:
                expected_json_ok = False
        ok = status_ok and no_server_error and request_id_ok and expected_json_ok
        detail = ""
        if not status_ok:
            detail = f"expected {case.expected_statuses}, got {response.status_code}"
        elif not no_server_error:
            detail = f"server error {response.status_code}"
        elif not request_id_ok:
            detail = "missing X-Request-ID"
        elif not expected_json_ok:
            detail = f"expected JSON {case.expected_json}, got {response.text[:200]}"
        results.append(
            SmokeResult(
                case=case,
                status_code=response.status_code,
                request_id=request_id,
                ok=ok,
                detail=detail,
            )
        )
    return results


def assert_results(results: list[SmokeResult]) -> None:
    failures = [r for r in results if not r.ok]
    if failures:
        lines = [
            f"{r.case.name}: GET {r.case.path} -> {r.status_code} ({r.detail})" for r in failures
        ]
        raise AssertionError("API smoke failures:\n" + "\n".join(lines))


def _compile_openapi_path_template(path: str) -> Pattern[str]:
    pattern = ""
    cursor = 0
    for match in re.finditer(r"\{[^{}]+\}", path):
        pattern += re.escape(path[cursor : match.start()])
        pattern += r"[^/]+"
        cursor = match.end()
    pattern += re.escape(path[cursor:])
    return re.compile(r"^" + pattern + r"$")


def _covered_openapi_get_paths(cases: tuple[SmokeCase, ...], get_paths: set[str]) -> set[str]:
    template_patterns = {
        path: _compile_openapi_path_template(path) for path in get_paths if "{" in path
    }
    covered = set()
    for case in cases:
        if case.path in get_paths:
            covered.add(case.path)
            continue
        for template_path, pattern in template_patterns.items():
            if pattern.match(case.path):
                covered.add(template_path)
                break
    return covered


def get_openapi_get_coverage(
    app, cases: tuple[SmokeCase, ...] = DEFAULT_SAFE_GET_CASES
) -> CoverageSummary:
    schema = app.openapi()
    get_paths = {path for path, operations in schema["paths"].items() if "get" in operations}
    covered_paths = _covered_openapi_get_paths(cases, get_paths)
    excluded_paths = DEFAULT_EXCLUDED_GET_PATHS & get_paths
    unaccounted_paths = tuple(sorted(get_paths - covered_paths - excluded_paths))
    return CoverageSummary(
        get_path_count=len(get_paths),
        covered_paths=frozenset(covered_paths),
        excluded_paths=frozenset(excluded_paths),
        unaccounted_paths=unaccounted_paths,
    )


def assert_openapi_get_coverage(coverage: CoverageSummary) -> None:
    if coverage.unaccounted_paths:
        lines = [f"- {path}" for path in coverage.unaccounted_paths]
        raise AssertionError("Unaccounted OpenAPI GET paths:\n" + "\n".join(lines))


def main() -> int:
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        results = run_cases(client)
    coverage = get_openapi_get_coverage(app)
    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed
    print(f"API smoke: {passed}/{len(results)} passed")
    print(
        "OpenAPI GET coverage: "
        f"{len(coverage.covered_paths)}/{coverage.get_path_count} covered, "
        f"{len(coverage.excluded_paths)} excluded, "
        f"{len(coverage.unaccounted_paths)} unaccounted"
    )
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status} {result.case.name} {result.status_code} {result.case.path}")
    assert_results(results)
    assert_openapi_get_coverage(coverage)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
