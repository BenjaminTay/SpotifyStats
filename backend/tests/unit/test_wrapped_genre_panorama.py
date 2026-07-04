from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from backend.services.wrapped_service import _build_genre_panorama

pytestmark = pytest.mark.unit


def _genre_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        )"""
    )
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
            "artist_name": ["C-Pop Overlap Artist"],
            "ts_month": [1],
            "ms_played": [3_600_000],
        }
    )

    panorama = _build_genre_panorama(conn, year_df, artist_agg)

    assert panorama["top_genres"] == [{"name": "c-pop", "play_share": 100.0}]
    assert panorama["monthly_genres"][0]["genres"] == {"c-pop": 100.0}
    assert "原始标签" in panorama["caveat"]
