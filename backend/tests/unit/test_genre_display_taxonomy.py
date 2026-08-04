from __future__ import annotations

import pytest

from backend.domains.metadata.artist_genres import ResolvedArtistGenres
from backend.domains.metadata.genre_display_taxonomy import (
    GENRE_DISPLAY_TAXONOMY_VERSION,
    build_consumer_axis_distribution,
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
