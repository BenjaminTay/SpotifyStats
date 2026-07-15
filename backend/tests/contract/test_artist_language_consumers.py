from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.core.migrations import migrate_024
from backend.services import wrapped_service

pytestmark = pytest.mark.contract


def _language_conn(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
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
            role TEXT NOT NULL,
            UNIQUE(track_id, artist_id)
        );
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            genres TEXT
        );
        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'English Primary'),
            (2, 'Unknown Collaborator');
        INSERT INTO tracks(track_id, track_name, artist_id) VALUES
            (10, 'Primary Collaboration', 1),
            (20, 'Unknown Solo', 2);
        INSERT INTO track_artists(track_id, artist_id, role) VALUES
            (10, 1, 'primary'),
            (10, 2, 'featured'),
            (20, 2, 'primary');
        """
    )
    migrate_024(conn)
    return conn


def test_wrapped_language_distribution_uses_primary_artist_and_unknown_bucket() -> None:
    conn = _language_conn()
    conn.executemany(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (1, "single_language", "en", "manual", "approved-en", "approved"),
            (2, "single_language", "zh", "legacy_import", "draft-zh", "suggested"),
        ],
    )
    year_df = pd.DataFrame(
        [
            {
                "track_id": 10,
                "artist_name": "English Primary",
                "ts_month": 1,
                "ms_played": 7_200_000,
            },
            {
                "track_id": 20,
                "artist_name": "Unknown Collaborator",
                "ts_month": 1,
                "ms_played": 3_600_000,
            },
            {
                "track_id": 999,
                "artist_name": "Missing Track",
                "ts_month": 1,
                "ms_played": 1_800_000,
            },
        ]
    )
    empty_genre_agg = pd.DataFrame(
        columns=["plays", "hours"],
        index=pd.Index([], name="artist_name"),
    )

    panorama = wrapped_service._build_genre_panorama(conn, year_df, empty_genre_agg)
    language = panorama["language_dist"]

    assert panorama["top_genres"] == []
    assert language is not None
    assert language["eligible_hours"] == pytest.approx(3.0)
    assert language["excluded_unattributed_hours"] == pytest.approx(0.5)
    assert language["classified_hours"] + language["unknown_hours"] == pytest.approx(3.0)
    assert {row["key"]: row["hours"] for row in language["buckets"]} == {
        "en": pytest.approx(2.0),
        "unknown": pytest.approx(1.0),
    }
    assert sum(row["hours"] for row in language["buckets"]) == pytest.approx(3.0)
    assert language["top_missing"] == [
        {
            "artist_id": 2,
            "artist_name": "Unknown Collaborator",
            "hours": pytest.approx(1.0),
        }
    ]
    conn.close()


def test_wrapped_cache_changes_only_for_approved_language_facts(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "wrapped-language-cache.db"
    conn = _language_conn(str(db_path))
    wrapped_service._get_wrapped_full_cached.cache_clear()
    build_calls = 0

    def fake_build(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        return {"build": build_calls}

    monkeypatch.setattr(wrapped_service, "_build_wrapped_full", fake_build)

    first = wrapped_service.get_wrapped_full(conn, 30_000, True, True, 2024)
    conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code, raw_language,
               origin, source_key, status
           ) VALUES (2, 'single_language', 'zh', 'draft',
                     'legacy_import', 'draft-zh', 'suggested')"""
    )
    conn.commit()
    after_suggestion = wrapped_service.get_wrapped_full(conn, 30_000, True, True, 2024)

    source_id = conn.execute(
        "SELECT source_id FROM artist_language_sources WHERE source_key='draft-zh'"
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO artist_language_evidence(
               source_id, claimed_language_code, evidence_kind,
               performer_attribution, evidence_url, evidence_title,
               evidence_accessed_at, evidence_summary
           ) VALUES (?, 'zh', 'artist_repertoire', 'artist_vocal_confirmed',
                     'https://example.test/language', 'Language profile',
                     '2026-07-11', 'Initial evidence')""",
        (source_id,),
    )
    conn.execute(
        """UPDATE artist_language_evidence
           SET evidence_summary='Edited evidence'
           WHERE source_id=?""",
        (source_id,),
    )
    conn.commit()
    after_evidence_edit = wrapped_service.get_wrapped_full(conn, 30_000, True, True, 2024)

    conn.execute(
        """UPDATE artist_language_sources
           SET status='approved', updated_at='2099-01-02 00:00:00'
           WHERE source_key='draft-zh'"""
    )
    conn.commit()
    after_approval = wrapped_service.get_wrapped_full(conn, 30_000, True, True, 2024)

    assert first == after_suggestion == after_evidence_edit == {"build": 1}
    assert after_approval == {"build": 2}
    assert build_calls == 2
    conn.close()
    wrapped_service._get_wrapped_full_cached.cache_clear()
