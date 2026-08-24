from __future__ import annotations

import argparse

import pytest

from scripts.yearly_review_v2_probe import (
    _consumer_issues,
    _editorial_issues,
    _identity_issues,
    _semantic_fingerprint,
    _semantic_issues,
    _taste_issues,
    parse_years,
)


def test_parse_years_is_sorted_unique_and_bounded() -> None:
    assert parse_years("2025,2023,2025") == [2023, 2025]
    with pytest.raises(argparse.ArgumentTypeError):
        parse_years("1999")


def test_probe_detects_unknown_loss_and_duplicate_identities() -> None:
    payload = {
        "coverage": {
            "taste": {
                axis: {"unknown_hours": 1.0 if axis == "style" else 0.0}
                for axis in ("style", "scene", "language", "release_era")
            }
        },
        "taste_migration": {
            "distributions": {
                "style": [{"key": "pop", "share_pct": 80}],
                "scene": [],
                "language": [],
                "release_era": [],
            }
        },
        "appendix": {
            "play_charts": {
                "track_by_plays": [
                    {"identity_key": "track:1"},
                    {"identity_key": "track:1"},
                ]
            },
            "billboard_charts": {"track": [], "artist": [], "album": [{}]},
        },
    }

    taste = _taste_issues(payload)
    identities = _identity_issues(payload)

    assert "taste_share_not_conserved:style:80.00" in taste
    assert "unknown_bucket_missing:style" in taste
    assert "duplicate_play_identity:track_by_plays" in identities
    assert "billboard_album_identity_missing" in identities


def test_semantic_fingerprint_is_key_order_independent_and_value_sensitive() -> None:
    assert _semantic_fingerprint({"a": 1, "b": [2]}) == _semantic_fingerprint({"b": [2], "a": 1})
    assert _semantic_fingerprint({"a": 1}) != _semantic_fingerprint({"a": 2})


def test_editorial_probe_rejects_internal_copy_and_repeated_epilogue() -> None:
    payload = {
        "headlines": [{"statement": "same"}],
        "records": {
            "featured": [
                {
                    "record_id": "bad",
                    "title": "internal",
                    "statement": "记录到 championship / triple_no1 的年度事实。",
                    "metrics": [],
                }
            ]
        },
        "season": {"stage_status": "no_stable_phase", "stages": [], "turning_points": []},
        "epilogue": {"conclusions": [{"statement": "same"}]},
    }

    issues = _editorial_issues(payload)

    assert "featured_internal_copy:bad" in issues
    assert "featured_missing_evidence:bad" in issues
    assert "epilogue_duplicates_opening" in issues


def test_consumer_probe_rejects_audit_copy_ytd_full_year_and_missing_artwork() -> None:
    payload = {
        "status": "year_to_date",
        "passport": {"metrics": [{"key": "plays", "label": "有效播放"}]},
        "headlines": [{"title": "全年主角", "statement": "可比基线减少。", "entity_refs": []}],
        "honors": {"annual_honors": []},
        "season": {"turning_points": [], "stage_note": None},
        "relationships": [],
        "listening_life": {"observations": []},
        "records": {"featured": []},
        "taste_migration": {"observations": []},
        "epilogue": {
            "conclusions": [
                {
                    "title": "结语",
                    "statement": "变化 3.0pp",
                    "entity_refs": [
                        {
                            "entity_type": "artist",
                            "name": "Artist",
                            "deep_link": "/music/artists/Artist",
                            "cover_url": None,
                        }
                    ],
                }
            ]
        },
    }

    issues = _consumer_issues(payload)

    assert any(issue.endswith(":有效播放") for issue in issues)
    assert any(issue.startswith("ytd_full_year_copy:") for issue in issues)
    assert any(issue.startswith("consumer_pp_copy:") for issue in issues)
    assert "consumer_entity_cover_missing" in issues


def test_semantic_probe_rejects_cross_chapter_denominators_and_conflicting_maxima() -> None:
    payload = {
        "status": "year_to_date",
        "passport": {
            "observed_end": "2026-08-21",
            "metrics": [
                {"key": "total_plays", "value": 100},
                {"key": "unique_tracks", "value": 40},
            ],
        },
        "listening_life": {
            "metrics": [
                {"key": "unique_tracks", "value": 39},
                {"key": "top_artist_plays", "value": 20},
                {"key": "top_artist_share_pct", "value": 25.0},
            ]
        },
        "season": {
            "months": [
                {
                    "month": 8,
                    "comparisons": [
                        {"key": "hours_vs_previous_month_pct", "value": -10.0},
                        {"key": "hours_vs_prior_year_month_pct", "value": 20.0},
                    ],
                }
            ],
            "turning_points": [
                {
                    "point_id": "june",
                    "title": "听歌次数最多的一天",
                    "statement": "6 月 13 日是今年听歌最多的一天。",
                },
                {
                    "point_id": "july",
                    "title": "听歌次数最多的一天",
                    "statement": "7 月 25 日是今年听歌最多的一天。",
                },
            ],
        },
        "records": {"featured": []},
    }

    issues = _semantic_issues(payload)

    assert any(issue.startswith("unique_track_identity_mismatch:") for issue in issues)
    assert any(issue.startswith("artist_share_denominator_mismatch:") for issue in issues)
    assert "partial_month_uses_full_month_baseline" in issues
    assert "partial_month_uses_full_prior_year_baseline" in issues
    assert "conflicting_unique_claim:daily_plays_max:2" in issues


def test_semantic_probe_accepts_aligned_partial_month_window() -> None:
    payload = {
        "status": "year_to_date",
        "passport": {
            "observed_end": "2026-08-21",
            "metrics": [
                {"key": "total_plays", "value": 200},
                {"key": "unique_tracks", "value": 40},
            ],
        },
        "listening_life": {
            "metrics": [
                {"key": "unique_tracks", "value": 40},
                {"key": "top_artist_plays", "value": 20},
                {"key": "top_artist_share_pct", "value": 10.0},
            ]
        },
        "season": {
            "months": [
                {
                    "month": 8,
                    "comparisons": [
                        {
                            "key": "hours_vs_previous_period_pct",
                            "value": -7.0,
                            "observed_start": "2026-08-01",
                            "observed_end": "2026-08-21",
                            "comparison_start": "2026-07-01",
                            "comparison_end": "2026-07-21",
                        },
                        {
                            "key": "hours_vs_prior_year_period_pct",
                            "value": 10.0,
                            "observed_start": "2026-08-01",
                            "observed_end": "2026-08-21",
                            "comparison_start": "2025-08-01",
                            "comparison_end": "2025-08-21",
                        },
                    ],
                }
            ],
            "turning_points": [
                {
                    "point_id": "july",
                    "title": "听歌次数最多的一天",
                    "statement": "7 月 25 日是今年听歌次数最多的一天。",
                }
            ],
        },
        "records": {"featured": []},
    }

    assert _semantic_issues(payload) == []
