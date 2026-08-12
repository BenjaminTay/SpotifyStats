from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from backend import dependencies
from backend.domains.settings.repository import SETTINGS_DEFAULTS
from backend.domains.yearly_review.context import (
    FILTER_FIELDS,
    build_yearly_review_context,
    fingerprint_filter_context,
    fingerprint_filter_values,
)

REVISIONS: dict[str, str | int] = {
    "display_taxonomy_version": "consumer_v1",
    "artist_metadata_revision": "artist-rev",
    "artist_identity_revision": 3,
    "track_credit_revision": 4,
    "track_group_revision": "track-groups",
    "album_project_revision": "album-projects",
}


def _filters(**overrides):
    values = {
        "min_ms": 30_000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": None,
        "merge_level": 2,
        "include_compilations": False,
        "bb_top_n": 30,
        "bb_album_top_n": 20,
        "bb_artist_top_n": 20,
        "bb_week_start_dow": 4,
        "bb_week_start_hour": 12,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_context_fingerprint_is_stable_across_mapping_order() -> None:
    original = {**vars(_filters()), **REVISIONS}
    reversed_order = dict(reversed(list(original.items())))

    assert fingerprint_filter_values(original) == fingerprint_filter_values(reversed_order)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("min_ms", 45_000),
        ("music_only", False),
        ("merge_enabled", False),
        ("dynamic_threshold", False),
        ("max_merge_gap_minutes", 45),
        ("merge_level", 3),
        ("include_compilations", True),
        ("bb_top_n", 50),
        ("bb_album_top_n", 30),
        ("bb_artist_top_n", 30),
        ("bb_week_start_dow", 0),
        ("bb_week_start_hour", 0),
    ],
)
def test_every_filter_change_changes_fingerprint(field: str, changed) -> None:
    conn = sqlite3.connect(":memory:")
    try:
        baseline = build_yearly_review_context(
            conn,
            _filters(),
            revision_overrides=REVISIONS,
        )
        modified = build_yearly_review_context(
            conn,
            _filters(**{field: changed}),
            revision_overrides=REVISIONS,
        )
    finally:
        conn.close()

    assert baseline.filter_fingerprint != modified.filter_fingerprint


def test_revision_change_changes_fingerprint() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        baseline = build_yearly_review_context(
            conn,
            _filters(),
            revision_overrides=REVISIONS,
        )
        modified = build_yearly_review_context(
            conn,
            _filters(),
            revision_overrides={**REVISIONS, "album_project_revision": "changed"},
        )
    finally:
        conn.close()

    assert fingerprint_filter_context(baseline) == baseline.filter_fingerprint
    assert baseline.filter_fingerprint != modified.filter_fingerprint


def test_yearly_filter_defaults_match_persisted_settings_defaults(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "_load_filter_settings", lambda: dict(SETTINGS_DEFAULTS))

    filters = dependencies.YearlyReviewFilters()

    for field in (
        "min_ms",
        "music_only",
        "merge_enabled",
        "include_compilations",
        "bb_top_n",
        "bb_album_top_n",
        "bb_artist_top_n",
        "bb_week_start_dow",
        "bb_week_start_hour",
    ):
        assert getattr(filters, field) == SETTINGS_DEFAULTS[field]
    assert filters.dynamic_threshold is True
    assert filters.merge_level == 2
    assert set(FILTER_FIELDS) == set(vars(filters))


def test_v1_play_filters_remain_independent() -> None:
    filters = dependencies.PlayFilters(
        min_ms=10_000,
        music_only=False,
        merge_enabled=False,
        dynamic_threshold=False,
        max_merge_gap_minutes=30,
    )

    assert filters.min_ms == 10_000
    assert filters.music_only is False
    assert filters.merge_enabled is False
    assert filters.dynamic_threshold is False
    assert filters.max_merge_gap_minutes == 30
