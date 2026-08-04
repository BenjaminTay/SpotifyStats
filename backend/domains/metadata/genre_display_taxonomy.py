"""User-facing genre buckets derived from the governed four-axis taxonomy.

This module deliberately does not alter approved genre facts.  It only maps
resolved axis labels to stable consumer labels and keeps a version that can be
included in caches whenever display semantics change.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

import pandas as pd

from backend.domains.metadata.artist_genres import (
    ResolvedArtistGenres,
    normalize_genres,
    resolve_artist_genres_map,
)
from backend.domains.metadata.artist_languages import (
    build_primary_artist_ms,
    compute_artist_language_distribution,
)

GENRE_DISPLAY_TAXONOMY_VERSION = "consumer_v1"

STYLE_DISPLAY_LABELS: dict[str, str] = {
    "pop": "Pop",
    "rock/alternative": "Rock",
    "indie/alternative": "Indie",
    "r&b/soul": "R&B / Soul",
    "hip hop/rap": "Hip Hop / Rap",
    "folk": "Folk",
    "country": "Country",
    "americana/roots": "Americana / Roots",
    "jazz/blues": "Jazz / Blues",
    "classical/instrumental": "Classical / Instrumental",
    "traditional/folk": "Traditional / Folk",
    "world/traditional": "World / Traditional",
}

SCENE_DISPLAY_LABELS: dict[str, str] = {
    "c-pop": "C-Pop",
    "j-pop": "J-Pop",
    "k-pop": "K-Pop",
    "latin": "Latin",
    "afrobeats/afropop": "Afrobeats / Afropop",
    "southeast asian pop": "Southeast Asian Pop",
    "brazilian": "Brazilian",
    "caribbean": "Caribbean",
}

ELECTRONIC_LABELS = {
    "electronic",
    "electropop",
    "electro",
    "synth pop",
    "synth-pop",
    "synthpop",
    "hyperpop",
    "idm",
    "future bass",
    "trip hop",
}
AMBIENT_LABELS = {
    "ambient",
    "ambient pop",
    "ambient techno",
    "dark ambient",
    "drone",
}
DANCE_MARKERS = (
    "dance",
    "edm",
    "house",
    "techno",
    "trance",
    "club",
    "disco",
    "hi-nrg",
)


def _electronic_display_keys(raw_genres: list[str]) -> list[str]:
    normalized = normalize_genres(raw_genres)
    result: list[str] = []
    if any(label in AMBIENT_LABELS or "ambient" in label for label in normalized):
        result.append("ambient")
    if any(any(marker in label for marker in DANCE_MARKERS) for label in normalized):
        result.append("dance")
    if any(label in ELECTRONIC_LABELS or "electronic" in label for label in normalized):
        result.append("electronic")
    return result or ["electronic"]


def display_style_keys(item: ResolvedArtistGenres | None) -> list[str]:
    """Return non-exclusive user-facing style keys for one resolved artist."""
    if item is None:
        return []
    result: list[str] = []
    for canonical in item.axis_genres.get("style", []):
        mapped = (
            _electronic_display_keys(item.genres)
            if canonical == "electronic/dance"
            else [canonical]
        )
        for key in mapped:
            if key not in result:
                result.append(key)
    return result


def display_scene_keys(item: ResolvedArtistGenres | None) -> list[str]:
    if item is None:
        return []
    return list(dict.fromkeys(item.axis_genres.get("scene", [])))


def _label_for(axis: str, key: str) -> str:
    if axis == "style":
        if key == "electronic":
            return "Electronic"
        if key == "dance":
            return "Dance"
        if key == "ambient":
            return "Ambient"
        return STYLE_DISPLAY_LABELS.get(key, key.replace("/", " / ").title())
    return SCENE_DISPLAY_LABELS.get(key, key.replace("/", " / ").title())


def build_consumer_axis_distribution(
    resolved: Mapping[str, ResolvedArtistGenres],
    artist_hours: Mapping[str, float],
    *,
    axis: str,
) -> dict[str, Any]:
    """Aggregate display buckets against all attributable listening time.

    An artist can retain multiple labels.  Its listening time is split evenly
    across labels within this display axis, matching the existing same-axis
    allocation rule without forcing a false single-label classification.
    """
    if axis not in {"style", "scene"}:
        raise ValueError(f"unsupported consumer genre axis: {axis}")

    total_hours = sum(max(float(hours), 0.0) for hours in artist_hours.values())
    bucket_hours: dict[str, float] = defaultdict(float)
    bucket_artists: Counter[str] = Counter()
    known_hours = 0.0
    key_resolver = display_style_keys if axis == "style" else display_scene_keys

    for artist_name, hours_value in artist_hours.items():
        hours = max(float(hours_value), 0.0)
        keys = key_resolver(resolved.get(artist_name))
        if not keys or hours <= 0:
            continue
        known_hours += hours
        share = hours / len(keys)
        for key in keys:
            bucket_hours[key] += share
            bucket_artists[key] += 1

    buckets = [
        {
            "key": key,
            "label": _label_for(axis, key),
            "hours": round(hours, 2),
            "share_pct": round(hours / total_hours * 100, 1) if total_hours else 0.0,
            "artist_count": int(bucket_artists[key]),
        }
        for key, hours in sorted(bucket_hours.items(), key=lambda row: (-row[1], row[0]))
    ]
    unknown_hours = max(total_hours - known_hours, 0.0)
    if unknown_hours > 0:
        buckets.append(
            {
                "key": "unknown",
                "label": "尚未归类",
                "hours": round(unknown_hours, 2),
                "share_pct": round(unknown_hours / total_hours * 100, 1) if total_hours else 0.0,
                "artist_count": sum(
                    1
                    for artist_name, hours in artist_hours.items()
                    if float(hours) > 0 and not key_resolver(resolved.get(artist_name))
                ),
            }
        )

    return {
        "axis": axis,
        "label": "主曲风" if axis == "style" else "地区流行",
        "total_hours": round(total_hours, 2),
        "known_hours": round(known_hours, 2),
        "unknown_hours": round(unknown_hours, 2),
        "allows_multiple": True,
        "buckets": buckets,
    }


def build_consumer_taste_profile(
    conn: sqlite3.Connection,
    plays: pd.DataFrame,
) -> dict[str, Any]:
    """Build the shared consumer style, scene, and language view for a play set."""
    if plays.empty or not {"track_id", "ms_played"}.issubset(plays.columns):
        artist_ms: dict[int, int] = {}
        excluded_ms = 0
    else:
        artist_ms, excluded_ms = build_primary_artist_ms(
            conn,
            plays.loc[:, ["track_id", "ms_played"]],
        )

    language_dist = compute_artist_language_distribution(
        conn,
        artist_ms,
        excluded_ms=excluded_ms,
    )
    artist_names_by_id: dict[int, str] = {}
    artist_ids = list(artist_ms)
    for offset in range(0, len(artist_ids), 500):
        chunk = artist_ids[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT artist_id, artist_name FROM artists WHERE artist_id IN ({placeholders})",
            chunk,
        ).fetchall()
        artist_names_by_id.update({int(row[0]): str(row[1]) for row in rows})

    artist_hours = {
        artist_names_by_id[artist_id]: ms / 3_600_000
        for artist_id, ms in artist_ms.items()
        if artist_id in artist_names_by_id
    }
    resolved = resolve_artist_genres_map(conn, list(artist_hours)) if artist_hours else {}
    return {
        "display_taxonomy_version": GENRE_DISPLAY_TAXONOMY_VERSION,
        "primary_styles": build_consumer_axis_distribution(resolved, artist_hours, axis="style"),
        "regional_pop": build_consumer_axis_distribution(resolved, artist_hours, axis="scene"),
        "language_dist": language_dist,
    }
