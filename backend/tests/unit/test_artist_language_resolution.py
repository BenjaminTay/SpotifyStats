from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from backend.core.migrations import migrate_024
from backend.domains.metadata.artist_languages import (
    ArtistLanguageValidationError,
    artist_language_fact_revision,
    resolve_artist_languages_map,
    validate_approved_language_source,
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
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id)
        );
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            role TEXT NOT NULL DEFAULT 'primary',
            UNIQUE(track_id, artist_id)
        );
        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'Approved Artist'),
            (2, 'Suggested Artist'),
            (3, 'Multilingual Artist');
        INSERT INTO tracks(track_id, track_name, artist_id) VALUES
            (10, 'Primary Track', 1),
            (20, 'Suggested Track', 2);
        INSERT INTO track_artists(track_id, artist_id, role) VALUES
            (10, 1, 'primary'),
            (10, 2, 'featured'),
            (20, 2, 'primary');
        """
    )
    migrate_024(conn)
    conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (1, 'single_language', 'en', 'manual', 'approved-en', 'approved')"""
    )
    conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (2, 'single_language', 'zh', 'manual', 'suggested-zh', 'suggested')"""
    )
    conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, origin, source_key, status
           ) VALUES (3, 'multilingual', 'curated_seed', 'approved-multi', 'approved')"""
    )
    yield conn
    conn.close()


def test_resolver_only_reads_approved_sources(language_conn: sqlite3.Connection) -> None:
    resolved = resolve_artist_languages_map(language_conn, [1, 2, 999])

    assert resolved[1].classification == "single_language"
    assert resolved[1].primary_language_code == "en"
    assert resolved[2].classification == "unknown"
    assert resolved[999].classification == "unknown"


def test_fact_revision_ignores_suggested_edits(language_conn: sqlite3.Connection) -> None:
    first = artist_language_fact_revision(language_conn)

    language_conn.execute(
        "UPDATE artist_language_sources SET raw_language='draft edit' WHERE status='suggested'"
    )

    assert artist_language_fact_revision(language_conn) == first


def test_fact_revision_changes_when_approved_fact_changes(
    language_conn: sqlite3.Connection,
) -> None:
    first = artist_language_fact_revision(language_conn)

    language_conn.execute("UPDATE artist_language_sources SET status='approved' WHERE artist_id=2")

    assert artist_language_fact_revision(language_conn) != first


def _source(
    classification: str,
    *,
    code: str | None = None,
    variant: str | None = None,
) -> dict[str, object]:
    return {
        "classification": classification,
        "primary_language_code": code,
        "language_variant": variant,
        "origin": "manual",
        "source_key": "test-source",
    }


def _evidence(
    *,
    code: str | None = None,
    variant: str | None = None,
    kind: str = "artist_profile",
    attribution: str = "artist_vocal_confirmed",
    track_id: int | None = None,
) -> dict[str, object]:
    return {
        "local_track_id": track_id,
        "claimed_language_code": code,
        "claimed_language_variant": variant,
        "evidence_kind": kind,
        "performer_attribution": attribution,
        "evidence_url": "https://example.com/source",
        "evidence_title": "Source",
        "evidence_accessed_at": "2026-07-11T00:00:00Z",
        "evidence_summary": "Evidence summary",
    }


def test_single_language_accepts_normalized_artist_level_evidence(
    language_conn: sqlite3.Connection,
) -> None:
    source, evidence = validate_approved_language_source(
        language_conn,
        1,
        _source("single_language", code="English"),
        [_evidence(code="english")],
    )

    assert source["primary_language_code"] == "en"
    assert evidence[0]["claimed_language_code"] == "en"


def test_single_language_rejects_track_language_only(
    language_conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ArtistLanguageValidationError, match="single_language"):
        validate_approved_language_source(
            language_conn,
            1,
            _source("single_language", code="en"),
            [
                _evidence(
                    code="en",
                    kind="track_language",
                    attribution="track_language_only",
                    track_id=10,
                )
            ],
        )


def test_multilingual_accepts_two_distinct_canonical_claims(
    language_conn: sqlite3.Connection,
) -> None:
    _, evidence = validate_approved_language_source(
        language_conn,
        3,
        _source("multilingual"),
        [
            _evidence(code="en"),
            _evidence(code="Chinese", variant="Mandarin", kind="editorial_source"),
        ],
    )

    assert {
        (item["claimed_language_code"], item["claimed_language_variant"]) for item in evidence
    } == {("en", None), ("zh", "mandarin")}


def test_multilingual_does_not_double_count_broad_and_specific_claims(
    language_conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ArtistLanguageValidationError, match="multilingual"):
        validate_approved_language_source(
            language_conn,
            3,
            _source("multilingual"),
            [_evidence(code="zh"), _evidence(code="zh", variant="mandarin")],
        )


def test_multilingual_deduplicates_repeated_claim_rows(
    language_conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ArtistLanguageValidationError, match="multilingual"):
        validate_approved_language_source(
            language_conn,
            3,
            _source("multilingual"),
            [_evidence(code="en"), _evidence(code="English")],
        )


def test_instrumental_accepts_artist_level_confirmation(
    language_conn: sqlite3.Connection,
) -> None:
    source, _ = validate_approved_language_source(
        language_conn,
        1,
        _source("instrumental"),
        [
            _evidence(
                kind="artist_repertoire",
                attribution="artist_instrumental_confirmed",
            )
        ],
    )

    assert source["classification"] == "instrumental"


def test_instrumental_rejects_track_only_confirmation(
    language_conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ArtistLanguageValidationError, match="instrumental"):
        validate_approved_language_source(
            language_conn,
            1,
            _source("instrumental"),
            [
                _evidence(
                    kind="track_credit",
                    attribution="artist_instrumental_confirmed",
                    track_id=10,
                )
            ],
        )


def test_track_evidence_requires_artist_credit(
    language_conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ArtistLanguageValidationError, match="track_artists"):
        validate_approved_language_source(
            language_conn,
            1,
            _source("single_language", code="en"),
            [
                _evidence(code="en"),
                _evidence(
                    code="zh",
                    kind="track_language",
                    attribution="track_language_only",
                    track_id=20,
                ),
            ],
        )
