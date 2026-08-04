from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from backend.core.migrations import migrate_023, migrate_024
from backend.services.wrapped_service import (
    _build_genre_panorama,
    _language_region_kind,
    _registry_language_code,
)

pytestmark = pytest.mark.unit


def _genre_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER REFERENCES artists(artist_id)
        );
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        );
        INSERT INTO artists(artist_id, artist_name)
        VALUES (1, 'C-Pop Overlap Artist');
        INSERT INTO tracks(track_id, track_name, artist_id)
        VALUES (10, 'C-Pop Track', 1);
        """
    )
    migrate_023(conn)
    migrate_024(conn)
    return conn


def test_genre_panorama_uses_statistical_genre_families_for_spotify_overlap() -> None:
    conn = _genre_conn()
    conn.execute(
        """INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres)
           VALUES (?, ?, ?)""",
        (
            "sp-cpop",
            "C-Pop Overlap Artist",
            json.dumps(["mandopop", "c-pop", "taiwanese pop", "cantopop"]),
        ),
    )

    artist_agg = pd.DataFrame(
        {"plays": [20], "hours": [1.0]},
        index=pd.Index(["C-Pop Overlap Artist"], name="artist_name"),
    )
    year_df = pd.DataFrame(
        {
            "track_id": [10],
            "artist_name": ["C-Pop Overlap Artist"],
            "ts_month": [1],
            "ms_played": [3_600_000],
        }
    )

    panorama = _build_genre_panorama(conn, year_df, artist_agg)

    assert panorama["top_genres"] == []
    axes = {axis["axis"]: axis for axis in panorama["axes"]}
    assert axes["style"]["coverage_pct"] == 0.0
    assert axes["scene"]["coverage_pct"] == 100.0
    assert axes["scene"]["buckets"][0]["name"] == "c-pop"
    assert axes["scene"]["buckets"][0]["share_pct"] == 100.0
    assert panorama["display_taxonomy_version"] == "consumer_v1"
    assert panorama["primary_styles"]["buckets"][0]["key"] == "unknown"
    assert panorama["regional_pop"]["buckets"][0]["key"] == "c-pop"
    assert panorama["regional_pop"]["buckets"][0]["share_pct"] == 100.0
    assert panorama["monthly_genres"][0]["genres"] == {}
    assert panorama["language_dist"]["unknown_hours"] == pytest.approx(1.0)
    assert "原始标签" in panorama["caveat"]


def test_genre_panorama_monthly_style_uses_approved_axis_fallback() -> None:
    conn = _genre_conn()
    conn.execute(
        """INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres)
           VALUES (?, ?, ?)""",
        ("sp-cpop", "C-Pop Overlap Artist", json.dumps(["mandopop"])),
    )
    conn.execute(
        """INSERT INTO artist_genre_sources(
               artist_name, spotify_artist_id, source, source_key,
               raw_genres_json, normalized_genres_json, primary_genre,
               confidence, evidence_url, status
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')""",
        (
            "C-Pop Overlap Artist",
            "sp-cpop",
            "external_consensus",
            "style-axis-unit",
            json.dumps(["pop"]),
            json.dumps(["pop"]),
            "pop",
            0.9,
            "https://example.test/c-pop-overlap-artist",
        ),
    )

    artist_agg = pd.DataFrame(
        {"plays": [20], "hours": [1.0]},
        index=pd.Index(["C-Pop Overlap Artist"], name="artist_name"),
    )
    year_df = pd.DataFrame(
        {
            "track_id": [10],
            "artist_name": ["C-Pop Overlap Artist"],
            "ts_month": [1],
            "ms_played": [3_600_000],
        }
    )

    panorama = _build_genre_panorama(conn, year_df, artist_agg)

    assert [row["name"] for row in panorama["top_genres"]] == ["pop"]
    assert panorama["primary_styles"]["buckets"][0]["label"] == "Pop"
    assert panorama["monthly_genres"][0]["genres"] == {"pop": 100.0}


def test_legacy_genre_language_values_use_canonical_registry() -> None:
    assert _registry_language_code("Mandarin") == "zh"
    assert _registry_language_code("Cantonese") == "zh"
    assert _registry_language_code("华语") == "zh"
    assert _registry_language_code("普通话") == "zh"
    assert _registry_language_code("粤语") == "zh"
    assert _registry_language_code("hokkien") == "zh"
    assert _language_region_kind("English") == "english"


@pytest.mark.parametrize(
    ("legacy_value", "expected_code", "expected_kind"),
    [
        ("英语", "en", "english"),
        ("Chinese (Mandarin)", "zh", "chinese"),
        ("Mandarin Chinese", "zh", "chinese"),
        ("Chinese / Cantonese", "zh", "chinese"),
    ],
)
def test_legacy_genre_language_compound_values_remain_compatible(
    legacy_value: str,
    expected_code: str,
    expected_kind: str,
) -> None:
    assert _registry_language_code(legacy_value) == expected_code
    assert _language_region_kind(legacy_value) == expected_kind
