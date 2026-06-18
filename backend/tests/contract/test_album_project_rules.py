"""Contract tests for album project playback semantics."""

from __future__ import annotations

import pytest

from backend.core.db import load_plays
from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings
from backend.domains.playback.album_projects import (
    compute_album_project_plays,
    compute_album_source_breakdown,
    load_album_project_membership,
)

pytestmark = pytest.mark.contract


def test_l2_album_project_counts_lead_single_and_deluxe_once(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(
        df,
        seed_conn,
        merge_level=2,
        include_compilations=False,
        billboard_mode=False,
    )
    row = result[result["album_project_name"] == "Fixture Future LP"].iloc[0]
    assert int(row["play_count"]) == 9
    assert int(row["unique_canonical_songs"]) == 3


def test_source_breakdown_sums_to_album_project_total(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    totals = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=False)
    breakdown = compute_album_source_breakdown(df, seed_conn, merge_level=2)
    total = int(totals[totals["album_project_name"] == "Fixture Future LP"].iloc[0]["play_count"])
    rows = breakdown[breakdown["album_project_name"] == "Fixture Future LP"]
    assert int(rows["play_count"].sum()) == total
    assert rows.set_index("source_bucket")["play_count"].to_dict() == {
        "single": 2,
        "original_album": 4,
        "deluxe": 2,
        "compilation": 1,
    }


def test_billboard_album_project_excludes_pre_release_single_week(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    weekly = compute_album_weekly_rankings(
        df,
        top_n=50,
        merge_level=2,
        include_compilations=False,
    )
    future_lp = weekly[weekly["album_name"] == "Fixture Future LP"]
    assert not future_lp.empty
    assert future_lp["billboard_week"].min() >= "2026-02-01"


def test_pure_compilation_does_not_become_album_project_at_l2(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=False)
    assert "Fixture Pure Compilation" not in set(result["album_project_name"])


def test_compilation_exclusive_track_forms_project(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=True)
    row = result[result["album_project_name"] == "Fixture Compilation Plus"].iloc[0]
    assert int(row["play_count"]) == 4
    assert int(row["unique_canonical_songs"]) == 1


def test_l3_rerecord_and_collab_versions_join_project(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=3, include_compilations=True)
    row = result[result["album_project_name"] == "Fixture Future LP"].iloc[0]
    assert int(row["play_count"]) == 12
    assert int(row["unique_canonical_songs"]) == 4


def test_album_membership_has_one_default_project_per_canonical_song(seed_conn):
    membership = load_album_project_membership(seed_conn, merge_level=2, include_compilations=True)
    duplicated = membership[membership.duplicated(["canonical_song_key"], keep=False)]
    assert duplicated.empty


def test_album_detail_includes_album_project_payload(use_seed_db):
    from backend.services.billboard_service import get_album_chart_detail

    detail = get_album_chart_detail(
        album_name="Fixture Future LP",
        artist_name="Fixture Artist Alpha",
        min_ms=30_000,
        music_only=True,
        bb_top_n=50,
        bb_album_top_n=50,
        bb_artist_top_n=50,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
        dynamic_threshold=False,
        max_merge_gap_minutes=None,
        merge_level=2,
    )

    project = detail["album_project"]
    assert project["album_project_name"] == "Fixture Future LP"
    assert project["artist_name"] == "Fixture Artist Alpha"
    assert project["play_count"] == 9
    assert sum(item["play_count"] for item in project["source_breakdown"]) == 9


def test_collaboration_candidate_detector_finds_primary_artist_remix(use_seed_db):
    from backend.core.version_merge import detect_collaboration_track_group_candidates

    candidates = detect_collaboration_track_group_candidates()
    match = candidates[
        (candidates["original_track_id"] == 920) & (candidates["candidate_track_id"] == 926)
    ]
    assert not match.empty
