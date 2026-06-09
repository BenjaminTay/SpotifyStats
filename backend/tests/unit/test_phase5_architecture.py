"""Phase 5 architecture guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        "backend/services/wikipedia_service.py",
        "backend/services/release_cycle_service.py",
    ],
)
def test_business_services_do_not_create_urllib_requests(path):
    source = _read(path)

    assert "urllib.request.Request" not in source
    assert "urllib.request.urlopen" not in source
    assert "urlopen(" not in source


@pytest.mark.parametrize(
    "path",
    [
        "backend/core/spotify_utils.py",
        "backend/core/version_merge.py",
    ],
)
def test_core_spotify_paths_do_not_create_urllib_requests(path):
    source = _read(path)

    assert "urllib.request.Request" not in source
    assert "urllib.request.urlopen" not in source
    assert "urlopen(" not in source


def test_billboard_records_output_helpers_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    output_source = _read("backend/domains/billboard/records_output.py")

    assert len(records_source.splitlines()) <= 1150
    assert "def _enrich_records_artist_names" not in records_source
    assert "def _add_cover_urls" not in records_source
    assert "def _serialize_records" not in records_source
    assert "def _enrich_records_artist_names" in output_source
    assert "def _add_cover_urls" in output_source
    assert "def _serialize_records" in output_source


def test_billboard_championship_records_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    championship_source = _read("backend/domains/billboard/records_championship.py")

    assert len(records_source.splitlines()) <= 1050
    assert 'records["artist_most_no1"]' not in records_source
    assert 'records["return_to_no1"]' not in records_source
    assert 'records["debut_no1"]' not in records_source
    assert "def compute_championship_records" in championship_source
    assert 'records["artist_most_no1"]' in championship_source
    assert 'records["return_to_no1"]' in championship_source
    assert 'records["debut_no1"]' in championship_source


def test_billboard_longevity_records_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    longevity_source = _read("backend/domains/billboard/records_longevity.py")

    assert len(records_source.splitlines()) <= 800
    assert 'records["longest_charting"]' not in records_source
    assert 'records["longest_streak"]' not in records_source
    assert 'records["longest_artist_span"]' not in records_source
    assert "def compute_longevity_records" in longevity_source
    assert 'records["longest_charting"]' in longevity_source
    assert 'records["longest_streak"]' in longevity_source
    assert 'records["longest_artist_span"]' in longevity_source
    assert len(longevity_source.splitlines()) <= 200


def test_billboard_endurance_records_are_split_from_records_and_longevity():
    records_source = _read("backend/domains/billboard/records.py")
    longevity_source = _read("backend/domains/billboard/records_longevity.py")
    endurance_source = _read("backend/domains/billboard/records_endurance.py")

    assert len(records_source.splitlines()) <= 200
    assert 'records["most_reentries"]' not in records_source
    assert 'records["longest_consecutive_same_rank"]' not in records_source
    assert 'records["most_weeks_no2_no_no1"]' not in records_source
    assert 'records["most_reentries"]' not in longevity_source
    assert 'records["longest_consecutive_same_rank"]' not in longevity_source
    assert 'records["most_weeks_no2_no_no1"]' not in longevity_source
    assert "def compute_endurance_records" in endurance_source
    assert 'records["most_reentries"]' in endurance_source
    assert 'records["longest_consecutive_same_rank"]' in endurance_source
    assert 'records["most_weeks_no2_no_no1"]' in endurance_source
    assert len(endurance_source.splitlines()) <= 220


def test_billboard_self_replacement_blocker_records_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    blocker_source = _read("backend/domains/billboard/records_self_replacement_blocker.py")

    assert len(records_source.splitlines()) <= 110
    assert 'records["self_replacement_no1"]' not in records_source
    assert 'records["blocker_king"]' not in records_source
    assert 'records["blocked_tracks_map"]' not in records_source
    assert "def compute_self_replacement_blocker_records" in blocker_source
    assert 'records["self_replacement_no1"]' in blocker_source
    assert 'records["blocker_king"]' in blocker_source
    assert 'records["blocked_tracks_map"]' in blocker_source
    assert len(blocker_source.splitlines()) <= 220


def test_billboard_movement_records_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    movement_source = _read("backend/domains/billboard/records_movement.py")

    assert len(records_source.splitlines()) <= 560
    assert 'records["biggest_jump"]' not in records_source
    assert 'records["biggest_drop"]' not in records_source
    assert 'records["album_simul"]' not in records_source
    assert 'records["longest_to_no1"]' not in records_source
    assert 'records["most_top10_simul"]' not in records_source
    assert "def compute_movement_records" in movement_source
    assert 'records["biggest_jump"]' in movement_source
    assert 'records["biggest_drop"]' in movement_source
    assert 'records["album_simul"]' in movement_source
    assert 'records["longest_to_no1"]' in movement_source
    assert 'records["most_top10_simul"]' in movement_source


def test_billboard_hall_of_fame_records_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    hall_source = _read("backend/domains/billboard/records_hall_of_fame.py")

    assert len(records_source.splitlines()) <= 460
    assert 'records["all_time_greatest"]' not in records_source
    assert 'records["year_end_no1"]' not in records_source
    assert 'records["album_power_ranking"]' not in records_source
    assert 'records["artist_power_ranking"]' not in records_source
    assert 'records["decade_best"]' not in records_source
    assert "def compute_hall_of_fame_records" in hall_source
    assert 'records["all_time_greatest"]' in hall_source
    assert 'records["year_end_no1"]' in hall_source
    assert 'records["album_power_ranking"]' in hall_source
    assert 'records["artist_power_ranking"]' in hall_source
    assert 'records["decade_best"]' in hall_source


def test_billboard_quirky_and_market_records_are_split_from_records_facade():
    records_source = _read("backend/domains/billboard/records.py")
    quirky_source = _read("backend/domains/billboard/records_quirky.py")
    market_source = _read("backend/domains/billboard/records_market.py")

    assert len(records_source.splitlines()) <= 320
    assert 'records["double_debut"]' not in records_source
    assert 'records["triple_no1"]' not in records_source
    assert 'records["week_total_plays"]' not in records_source
    assert 'records["strongest_week"]' not in records_source
    assert 'records["closest_no1_vs_no2"]' not in records_source
    assert 'records["new_entry_ratio"]' not in records_source
    assert "def compute_quirky_records" in quirky_source
    assert 'records["double_debut"]' in quirky_source
    assert 'records["triple_no1"]' in quirky_source
    assert "def compute_market_records" in market_source
    assert 'records["week_total_plays"]' in market_source
    assert 'records["strongest_week"]' in market_source
    assert 'records["closest_no1_vs_no2"]' in market_source
    assert 'records["new_entry_ratio"]' in market_source


def test_chart_compute_ranking_and_power_score_are_split():
    compute_source = _read("backend/domains/billboard/chart_compute.py")
    ranking_source = _read("backend/domains/billboard/chart_ranking.py")
    power_score_source = _read("backend/domains/billboard/chart_power_score.py")
    summaries_source = _read("backend/domains/billboard/chart_summaries.py")

    assert len(compute_source.splitlines()) <= 430
    assert "def compute_weekly_rankings" not in compute_source
    assert "_RANK1_BASE" not in compute_source
    assert "def compute_power_scores(" not in compute_source
    assert "def compute_track_summary" not in compute_source
    assert "def _add_running_metrics" not in compute_source
    assert "def compute_weekly_rankings" in ranking_source
    assert "def _add_running_metrics" in ranking_source
    assert "def compute_power_scores(" in power_score_source
    assert "_RANK1_BASE" in power_score_source
    assert "def compute_track_summary" in summaries_source


def test_chart_staged_cache_is_split_from_chart_compute_facade():
    compute_source = _read("backend/domains/billboard/chart_compute.py")
    staged_cache_source = _read("backend/domains/billboard/chart_staged_cache.py")

    assert "def _load_and_rank" not in compute_source
    assert "def _compute_weekly_data_cached" not in compute_source
    assert "def _compute_power_scores_cached" not in compute_source
    assert "def _compute_summaries_cached" not in compute_source
    assert "def _compute_records_cached" not in compute_source
    assert "def _load_and_rank" in staged_cache_source
    assert "def _compute_weekly_data_cached" in staged_cache_source
    assert "def _compute_power_scores_cached" in staged_cache_source
    assert "def _compute_summaries_cached" in staged_cache_source
    assert "def _compute_records_cached" in staged_cache_source
    assert len(staged_cache_source.splitlines()) <= 360


def test_chart_staged_public_api_is_split_from_chart_compute_facade():
    compute_source = _read("backend/domains/billboard/chart_compute.py")
    staged_api_source = _read("backend/domains/billboard/chart_staged_api.py")

    assert len(compute_source.splitlines()) <= 240
    assert "def compute_weekly_data" not in compute_source
    assert "def compute_power_scores_staged" not in compute_source
    assert "def compute_summaries_staged" not in compute_source
    assert "def compute_records_staged" not in compute_source
    assert "def compute_billboard_data" in compute_source
    assert "register_lru(" in compute_source
    assert "def compute_weekly_data" in staged_api_source
    assert "def compute_power_scores_staged" in staged_api_source
    assert "def compute_summaries_staged" in staged_api_source
    assert "def compute_records_staged" in staged_api_source
    assert len(staged_api_source.splitlines()) <= 140
