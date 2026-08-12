from __future__ import annotations

import argparse

import pytest

from scripts.yearly_review_v2_probe import (
    _identity_issues,
    _semantic_fingerprint,
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
