from __future__ import annotations

import pandas as pd
import pytest

from scripts.audit_yearly_review_v2 import (
    _profile_entities,
    history_transition_candidates,
    inventory_records,
    parse_years,
    ranking_billboard_gap,
    taste_delta,
)


def test_parse_years_deduplicates_and_sorts() -> None:
    assert parse_years("2025, 2023,2025,2024") == [2023, 2024, 2025]


def test_parse_years_rejects_invalid_input() -> None:
    with pytest.raises(Exception):
        parse_years("2025,nope")


def test_profile_entities_exposes_persistence_and_burst_distributions() -> None:
    frame = pd.DataFrame(
        [
            {
                "play_id": index,
                "track_id": 1,
                "canonical_track_id": 1,
                "canonical_track_name": "Long Run",
                "artist_name": "Artist A",
                "ts_date": date,
                "ms_played": 180_000,
            }
            for index, date in enumerate(
                ["2025-01-01", "2025-02-02", "2025-03-03", "2025-04-04"], start=1
            )
        ]
        + [
            {
                "play_id": 100 + index,
                "track_id": 2,
                "canonical_track_id": 2,
                "canonical_track_name": "One Month",
                "artist_name": "Artist B",
                "ts_date": "2025-06-15",
                "ms_played": 180_000,
            }
            for index in range(4)
        ]
    )

    result = _profile_entities(
        frame,
        entity_type="track",
        id_column="canonical_track_id",
        name_column="canonical_track_name",
        artist_column="artist_name",
        min_sample_plays=4,
        top_sample=2,
    )

    assert result["eligible_count"] == 2
    assert result["scenario_counts"]["concentrated_burst"] == 1
    assert result["top_by_persistence"][0]["name"] == "Long Run"
    assert result["top_by_persistence"][0]["consecutive_active_months"] == 4
    assert result["top_by_burst"][0]["name"] == "One Month"
    assert result["top_by_burst"][0]["peak_month_share"] == 1.0


def test_inventory_records_counts_leaves_and_exact_cross_leaf_duplicates() -> None:
    duplicate = {"track_id": 1, "track_name": "Song", "plays": 20, "cover_url": "/a"}
    records = {
        "obsession": {"daily": [duplicate]},
        "reigns": {
            "weekly": [
                {"track_id": 1, "track_name": "Song", "plays": 20, "cover_url": "/b"},
                {"track_id": 2, "track_name": "Else", "plays": 12},
            ]
        },
        "empty": [],
    }

    result = inventory_records(records)

    assert result["nonempty_leaf_count"] == 2
    assert result["total_candidate_rows"] == 3
    assert result["exact_duplicate_group_count"] == 1
    assert result["exact_duplicate_appearance_count"] == 2


def test_taste_delta_keeps_unknown_and_sorts_by_absolute_change() -> None:
    q1 = {
        "primary_styles": {
            "buckets": [
                {"key": "rock", "share_pct": 60},
                {"key": "unknown", "share_pct": 40},
            ]
        },
        "regional_pop": {"buckets": []},
        "language_dist": {"buckets": [{"key": "en", "share_pct": 80}]},
    }
    q4 = {
        "primary_styles": {
            "buckets": [
                {"key": "rock", "share_pct": 20},
                {"key": "indie", "share_pct": 50},
                {"key": "unknown", "share_pct": 30},
            ]
        },
        "regional_pop": {"buckets": []},
        "language_dist": {"buckets": [{"key": "en", "share_pct": 55}]},
    }

    result = taste_delta(q1, q4)

    assert result["primary_styles"][0] == {
        "key": "indie",
        "q1_share_pct": 0.0,
        "q4_share_pct": 50.0,
        "delta_pp": 50.0,
    }
    assert any(row["key"] == "unknown" for row in result["primary_styles"])


def test_ranking_billboard_gap_matches_stable_track_identity() -> None:
    result = ranking_billboard_gap(
        [
            {"track_id": 1, "track_name": "A", "artist_name": "Artist", "rank": 8},
            {"track_id": 2, "track_name": "B", "artist_name": "Artist", "rank": 2},
        ],
        [
            {"track_id": 1, "year_end_rank": 1},
            {"track_id": 2, "year_end_rank": 5},
        ],
        entity_type="track",
    )

    assert result["matched_count"] == 2
    assert result["gap_at_least_5_count"] == 1
    assert result["largest_gaps"][0]["name"] == "A"
    assert result["largest_gaps"][0]["rank_gap"] == 7


def test_history_transition_candidates_distinguishes_new_and_true_comeback() -> None:
    frame = pd.DataFrame(
        [
            {
                "play_id": index,
                "artist_name": "New Artist",
                "ts_date": date,
                "ms_played": 180_000,
            }
            for index, date in enumerate(["2025-01-01", "2025-02-10", "2025-03-15"] * 4, start=1)
        ]
        + [
            {
                "play_id": 100,
                "artist_name": "Returning Artist",
                "ts_date": "2023-01-01",
                "ms_played": 180_000,
            }
        ]
        + [
            {
                "play_id": 200 + index,
                "artist_name": "Returning Artist",
                "ts_date": date,
                "ms_played": 180_000,
            }
            for index, date in enumerate(
                ["2025-07-01", "2025-07-02", "2025-07-03", "2025-07-04"] * 3
            )
        ]
    )

    result = history_transition_candidates(
        frame,
        year=2025,
        entity_type="artist",
        id_column="artist_name",
        name_column="artist_name",
    )

    assert result["new_count"] == 1
    assert result["new_relationships"][0]["name"] == "New Artist"
    assert result["comeback_count"] == 1
    assert result["true_comebacks"][0]["inactivity_gap_days"] >= 180
