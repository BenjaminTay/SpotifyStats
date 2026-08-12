"""Versioned deterministic policies for Yearly Review V2 content selection."""

from __future__ import annotations

RELATIONSHIP_POLICY_VERSION = "relationship_policy_v1"
HIGHLIGHT_POLICY_VERSION = "highlight_policy_v1"
SEASON_STAGE_POLICY_VERSION = "season_stage_v1"

MIN_RELATIONSHIP_SPAN_DAYS = 90
RELATIONSHIP_ENTITY_CAP = 2
RELATIONSHIP_PER_TYPE_CAP = 2

RELATIONSHIP_THRESHOLDS: dict[str, dict[str, float]] = {
    "long_companion": {
        "plays": 10,
        "active_months": 9,
        "consecutive_months": 6,
        "span_days": 240,
    },
    "full_year_companion": {
        "active_months": 11,
        "consecutive_months": 9,
        "span_days": 300,
    },
    "short_obsession": {
        "plays": 10,
        "peak_month_share_pct": 70.0,
        "max_active_months": 4,
    },
    "deep_album": {
        "plays": 20,
        "unique_tracks": 8,
        "active_days": 10,
    },
    "broad_artist": {
        "plays": 30,
        "unique_tracks": 15,
        "active_months": 4,
    },
    "new_relationship": {
        "plays": 10,
        "active_days": 3,
        "span_days": 30,
    },
    "return": {
        "sleep_days": 180,
        "plays": 10,
        "active_days": 3,
    },
}

DIVERGENCE_RANK_GAPS = {"track": 10, "album": 5, "artist": 5}

HIGHLIGHT_MIN_COUNT = 8
HIGHLIGHT_MAX_COUNT = 12
HIGHLIGHT_CATEGORY_CAP = 2
HIGHLIGHT_RELAXED_CATEGORY_CAP = 3
HIGHLIGHT_ENTITY_CAP = 2

HIGHLIGHT_WEIGHTS = {
    "magnitude": 0.30,
    "duration": 0.20,
    "historical_rarity": 0.20,
    "comparison": 0.15,
    "specificity": 0.10,
    "evidence": 0.05,
}

TASTE_CORE_COVERAGE_PCT = 70.0
TASTE_SECONDARY_COVERAGE_PCT = 40.0
TASTE_CHANGE_MIN_PCT = 5.0

SEASON_MIN_STAGES = 3
SEASON_MAX_STAGES = 5
SEASON_MIN_STAGE_MONTHS = 2
SEASON_MIN_TURNING_POINTS = 6
SEASON_MAX_TURNING_POINTS = 10
SEASON_LEADER_CHANGE_CAP = 3
