from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pandas as pd
import pytest

from backend.core.migrations import migrate_024
from backend.domains.metadata.artist_languages import (
    _compute_language_bucket_ms,
    build_primary_artist_ms,
    compute_artist_language_distribution,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def language_conn() -> Iterator[sqlite3.Connection]:
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
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            role TEXT NOT NULL DEFAULT 'primary',
            UNIQUE(track_id, artist_id)
        );
        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'English Artist'),
            (2, 'Missing Artist'),
            (3, 'Multilingual Artist');
        INSERT INTO tracks(track_id, track_name, artist_id) VALUES
            (10, 'Collaboration', 1),
            (20, 'Second Track', 2),
            (30, 'Third Track', 3),
            (40, 'No Primary Artist', NULL);
        INSERT INTO track_artists(track_id, artist_id, role) VALUES
            (10, 1, 'primary'),
            (10, 2, 'featured'),
            (20, 2, 'primary'),
            (30, 3, 'primary');
        """
    )
    migrate_024(conn)
    conn.executescript(
        """
        INSERT INTO artist_language_sources(
            artist_id, classification, primary_language_code,
            origin, source_key, status
        ) VALUES
            (1, 'single_language', 'english', 'manual', 'approved-en', 'approved'),
            (2, 'single_language', 'zh', 'legacy_import', 'draft-zh', 'suggested'),
            (3, 'multilingual', NULL, 'curated_seed', 'approved-multi', 'approved');
        """
    )
    yield conn
    conn.close()


def test_primary_artist_hours_do_not_fan_out_collaborations(
    language_conn: sqlite3.Connection,
) -> None:
    plays = pd.DataFrame(
        [
            {"track_id": 10, "ms_played": 3_600_000},
            {"track_id": 20, "ms_played": 1_800_000},
            {"track_id": None, "ms_played": 600_000},
            {"track_id": 40, "ms_played": 300_000},
            {"track_id": 999, "ms_played": 100_000},
        ]
    )

    artist_ms, excluded_ms = build_primary_artist_ms(language_conn, plays)

    assert artist_ms == {1: 3_600_000, 2: 1_800_000}
    assert excluded_ms == 1_000_000


def test_primary_artist_hours_apply_identity_aliases_and_exclusions(
    language_conn: sqlite3.Connection,
) -> None:
    language_conn.executescript(
        """
        CREATE TABLE artist_identity_aliases (
            alias_artist_id INTEGER PRIMARY KEY,
            canonical_artist_id INTEGER NOT NULL,
            reason TEXT NOT NULL
        );
        CREATE TABLE artist_metadata_attribution_overrides (
            track_id INTEGER PRIMARY KEY,
            artist_id INTEGER,
            reason TEXT NOT NULL,
            evidence_url TEXT
        );
        INSERT INTO artist_identity_aliases(alias_artist_id, canonical_artist_id, reason)
        VALUES (2, 1, 'test alias');
        INSERT INTO artist_metadata_attribution_overrides(track_id, artist_id, reason)
        VALUES (30, NULL, 'invalid primary artist attribution');
        """
    )
    plays = pd.DataFrame(
        {
            "track_id": [10, 20, 30],
            "ms_played": [1_000, 2_000, 3_000],
        }
    )

    artist_ms, excluded_ms = build_primary_artist_ms(language_conn, plays)

    assert artist_ms == {1: 3_000}
    assert excluded_ms == 3_000


def test_distribution_conserves_integer_ms_and_returns_public_dynamic_buckets(
    language_conn: sqlite3.Connection,
) -> None:
    artist_ms = {1: 3_600_001, 2: 1_800_002, 3: 900_003}

    bucket_ms = _compute_language_bucket_ms(language_conn, artist_ms)
    result = compute_artist_language_distribution(
        language_conn,
        artist_ms,
        excluded_ms=600_000,
    )

    assert sum(bucket_ms.values()) == sum(artist_ms.values())
    assert bucket_ms == {"en": 3_600_001, "unknown": 1_800_002, "multilingual": 900_003}
    assert result["eligible_hours"] == pytest.approx(sum(artist_ms.values()) / 3_600_000)
    assert result["excluded_unattributed_hours"] == pytest.approx(1 / 6)
    assert result["classified_hours"] + result["unknown_hours"] == pytest.approx(
        result["eligible_hours"]
    )
    assert {bucket["key"] for bucket in result["buckets"]} == {
        "en",
        "multilingual",
        "unknown",
    }
    assert all(bucket["hours"] > 0 for bucket in result["buckets"])
    assert result["source_hours"] == {
        "manual": pytest.approx(3_600_001 / 3_600_000),
        "curated_seed": pytest.approx(900_003 / 3_600_000),
    }
    assert result["top_missing"] == [
        {
            "artist_id": 2,
            "artist_name": "Missing Artist",
            "hours": pytest.approx(1_800_002 / 3_600_000),
        }
    ]
    assert "_raw_buckets" not in result
    assert "bucket_ms" not in result


def test_distribution_normalizes_registry_aliases(
    language_conn: sqlite3.Connection,
) -> None:
    result = compute_artist_language_distribution(language_conn, {1: 3_600_000})

    assert result["buckets"] == [
        {
            "key": "en",
            "label": "英文",
            "classification": "single_language",
            "hours": 1.0,
            "share_pct": 100.0,
            "artist_count": 1,
        }
    ]
