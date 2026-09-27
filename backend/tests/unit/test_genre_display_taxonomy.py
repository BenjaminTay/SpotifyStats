from __future__ import annotations

import sqlite3
from typing import cast

import pandas as pd
import pytest

from backend.domains.metadata.artist_genres import ResolvedArtistGenres
from backend.domains.metadata.genre_display_taxonomy import (
    GENRE_DISPLAY_TAXONOMY_VERSION,
    build_consumer_axis_distribution,
    build_consumer_taste_profile,
    display_style_keys,
)

pytestmark = pytest.mark.unit


def _resolved(
    *,
    raw: list[str],
    style: list[str] | None = None,
    scene: list[str] | None = None,
    role: list[str] | None = None,
) -> ResolvedArtistGenres:
    axes = {}
    if style is not None:
        axes["style"] = style
    if scene is not None:
        axes["scene"] = scene
    if role is not None:
        axes["role"] = role
    return ResolvedArtistGenres(
        artist_name="Fixture Artist",
        genres=raw,
        primary_genre=raw[0] if raw else None,
        language=None,
        region=None,
        source="spotify",
        confidence=1.0,
        axis_genres=axes,
    )


def test_display_styles_use_clear_names_without_changing_axis_facts() -> None:
    item = _resolved(
        raw=["indie rock", "dance pop", "ambient"],
        style=["rock/alternative", "indie/alternative", "electronic/dance"],
    )

    assert display_style_keys(item) == ["rock/alternative", "indie/alternative", "ambient", "dance"]
    assert item.axis_genres["style"] == [
        "rock/alternative",
        "indie/alternative",
        "electronic/dance",
    ]


def test_consumer_axes_keep_cpop_and_rnb_as_independent_views() -> None:
    item = _resolved(raw=["chinese r&b"], style=["r&b/soul"], scene=["c-pop"])
    resolved = {"Fixture Artist": item}
    hours = {"Fixture Artist": 10.0, "Unknown Artist": 5.0}

    styles = build_consumer_axis_distribution(resolved, hours, axis="style")
    scenes = build_consumer_axis_distribution(resolved, hours, axis="scene")

    assert styles["buckets"][0] == {
        "key": "r&b/soul",
        "label": "R&B / Soul",
        "hours": 10.0,
        "share_pct": 66.7,
        "artist_count": 1,
    }
    assert scenes["buckets"][0]["key"] == "c-pop"
    assert scenes["buckets"][0]["share_pct"] == 66.7
    assert styles["buckets"][-1]["label"] == "尚未归类"
    assert styles["buckets"][-1]["share_pct"] == 33.3


def test_role_never_enters_primary_style_distribution() -> None:
    item = _resolved(raw=["singer-songwriter"], style=[], role=["singer-songwriter"])
    result = build_consumer_axis_distribution(
        {"Fixture Artist": item}, {"Fixture Artist": 4.0}, axis="style"
    )

    assert [bucket["key"] for bucket in result["buckets"]] == ["unknown"]
    assert GENRE_DISPLAY_TAXONOMY_VERSION == "consumer_v1"


def test_taste_profile_prefers_scoped_duration_slices(monkeypatch) -> None:
    events = pd.DataFrame([{"track_id": 1, "ms_played": 9_999_000}])
    events.attrs["listening_duration_slices"] = pd.DataFrame(
        [{"track_id": 2, "ms_played": 120_000}]
    )
    captured: dict[str, list[int]] = {}

    def fake_primary_artist_ms(_conn, frame):
        captured["track_ids"] = frame["track_id"].astype(int).tolist()
        captured["milliseconds"] = frame["ms_played"].astype(int).tolist()
        return {}, 120_000

    monkeypatch.setattr(
        "backend.domains.metadata.genre_display_taxonomy.build_primary_artist_ms",
        fake_primary_artist_ms,
    )
    monkeypatch.setattr(
        "backend.domains.metadata.genre_display_taxonomy.compute_artist_language_distribution",
        lambda _conn, _artist_ms, *, excluded_ms: {
            "eligible_hours": excluded_ms / 3_600_000,
            "buckets": [],
        },
    )

    profile = build_consumer_taste_profile(cast(sqlite3.Connection, object()), events)

    assert captured == {"track_ids": [2], "milliseconds": [120_000]}
    assert profile["language_dist"]["eligible_hours"] == pytest.approx(1 / 30)
