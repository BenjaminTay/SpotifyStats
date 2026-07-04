from __future__ import annotations

import json
import sqlite3

import pytest

from backend.domains.metadata import artist_genres
from backend.domains.metadata.artist_genres import (
    canonicalize_genres_for_statistics,
    compute_genre_coverage,
    compute_genre_taxonomy_audit,
    normalize_genres,
    resolve_artist_genres,
    resolve_artist_genres_map,
    upsert_genre_source,
)

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        );
        CREATE TABLE artist_genre_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            spotify_artist_id TEXT,
            source TEXT NOT NULL,
            source_key TEXT NOT NULL,
            raw_genres_json TEXT,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            evidence_url TEXT,
            evidence_summary TEXT,
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_name, source, source_key)
        );
        CREATE TABLE artist_genre_overrides (
            artist_name TEXT PRIMARY KEY,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    return conn


def test_normalize_genres_dedupes_and_keeps_order() -> None:
    assert normalize_genres(["Pop", "pop", "Singer-Songwriter", "", None]) == [
        "pop",
        "singer-songwriter",
    ]


def test_canonicalize_genres_for_statistics_collapses_overlapping_cpop_tags() -> None:
    assert canonicalize_genres_for_statistics(
        ["mandopop", "c-pop", "Taiwanese Pop", "cantopop"]
    ) == ["c-pop"]


def test_canonicalize_genres_for_statistics_preserves_audit_level_display_tags() -> None:
    assert canonicalize_genres_for_statistics(
        ["synth-pop", "synthpop", "musical theatre", "musicals"]
    ) == ["electronic/dance", "soundtrack/stage"]


def test_canonicalize_genres_for_statistics_splits_market_and_style_tags() -> None:
    assert canonicalize_genres_for_statistics(
        ["mandopop", "chinese r&b", "chinese rock", "gufeng"]
    ) == ["c-pop", "r&b/soul", "rock/alternative", "traditional/folk"]


def test_canonicalize_genres_for_statistics_collapses_pop_substyles_but_keeps_hybrids() -> None:
    assert canonicalize_genres_for_statistics(
        ["pop", "alt z", "art pop", "pop rock", "country pop", "singer-songwriter"]
    ) == ["pop", "rock/alternative", "country", "singer-songwriter"]


def test_statistical_genres_split_songwriter_folk_country_and_roots() -> None:
    assert canonicalize_genres_for_statistics(["singer-songwriter"]) == ["singer-songwriter"]
    assert canonicalize_genres_for_statistics(["folk"]) == ["folk"]
    assert canonicalize_genres_for_statistics(["folk pop"]) == ["pop", "folk"]
    assert canonicalize_genres_for_statistics(["folk rock"]) == ["rock/alternative", "folk"]
    assert canonicalize_genres_for_statistics(["country"]) == ["country"]
    assert canonicalize_genres_for_statistics(["country pop"]) == ["pop", "country"]
    assert canonicalize_genres_for_statistics(["americana"]) == ["americana/roots"]
    assert canonicalize_genres_for_statistics(["red dirt"]) == ["americana/roots", "country"]


def test_statistical_genre_label_metadata_axes() -> None:
    assert hasattr(artist_genres, "statistical_genre_label_metadata")
    metadata = artist_genres.statistical_genre_label_metadata()

    assert metadata["pop"]["axis"] == "style"
    assert metadata["singer-songwriter"]["axis"] == "role"
    assert metadata["folk"]["axis"] == "style"
    assert metadata["country"]["axis"] == "style"
    assert metadata["americana/roots"]["axis"] == "style"
    assert metadata["c-pop"]["axis"] == "scene"
    assert metadata["soundtrack/stage"]["axis"] == "context"
    assert metadata["holiday"]["axis"] == "context"


def test_canonicalize_genres_for_statistics_covers_major_long_tail_families() -> None:
    assert canonicalize_genres_for_statistics(
        [
            "hip hop",
            "rap",
            "latin pop",
            "reggaeton",
            "k-pop",
            "j-r&b",
            "christmas",
            "score",
        ]
    ) == [
        "hip hop/rap",
        "latin",
        "pop",
        "k-pop",
        "j-pop",
        "r&b/soul",
        "holiday",
        "soundtrack/stage",
    ]


def test_canonicalize_genres_for_statistics_maps_audited_passthrough_long_tail() -> None:
    assert canonicalize_genres_for_statistics(
        [
            "southern gothic",
            "adult standards",
            "variété française",
            "enka",
            "kayōkyoku",
            "slowcore",
            "soca",
        ]
    ) == [
        "folk",
        "jazz/blues",
        "pop",
        "j-pop",
        "traditional/folk",
        "indie/alternative",
        "caribbean",
    ]


def test_resolver_prefers_non_empty_spotify_over_manual_override() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Taylor Swift", json.dumps(["pop"], ensure_ascii=False)),
    )
    conn.execute(
        """INSERT INTO artist_genre_overrides
           (artist_name, normalized_genres_json, primary_genre, language, region, confidence, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "Taylor Swift",
            json.dumps(["pop", "country pop"], ensure_ascii=False),
            "pop",
            "english",
            "美国",
            1.0,
            "manual seed",
        ),
    )
    conn.commit()

    resolved = resolve_artist_genres(conn, "Taylor Swift")

    assert resolved.genres == ["pop"]
    assert resolved.source == "spotify"
    assert resolved.confidence == 1.0


def test_resolver_uses_manual_override_when_spotify_empty() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Taylor Swift", json.dumps([], ensure_ascii=False)),
    )
    conn.execute(
        """INSERT INTO artist_genre_overrides
           (artist_name, normalized_genres_json, primary_genre, language, region, confidence, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "Taylor Swift",
            json.dumps(["pop", "country pop"], ensure_ascii=False),
            "pop",
            "english",
            "美国",
            1.0,
            "manual seed",
        ),
    )
    conn.commit()

    resolved = resolve_artist_genres(conn, "Taylor Swift")

    assert resolved.genres == ["pop", "country pop"]
    assert resolved.source == "manual_override"
    assert resolved.confidence == 1.0
    assert resolved.is_fallback is True


def test_resolver_prefers_non_empty_spotify_over_local_source() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Spotify Artist", json.dumps(["spotify pop"], ensure_ascii=False)),
    )
    upsert_genre_source(
        conn,
        artist_name="Spotify Artist",
        spotify_artist_id="sp1",
        source="curated_seed",
        source_key="seed:spotify-artist",
        raw_genres=["curated pop"],
        normalized_genres=["curated pop"],
        primary_genre="curated pop",
        language="english",
        region="全球",
        confidence=1.0,
        evidence_url=None,
        evidence_summary="Curated fallback.",
        status="approved",
    )

    resolved = resolve_artist_genres(conn, "Spotify Artist")

    assert resolved.genres == ["spotify pop"]
    assert resolved.source == "spotify"
    assert resolved.is_fallback is False


def test_resolver_uses_approved_local_source_when_spotify_empty() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp2", "Olivia Rodrigo", ""),
    )
    upsert_genre_source(
        conn,
        artist_name="Olivia Rodrigo",
        spotify_artist_id="sp2",
        source="curated_seed",
        source_key="seed:olivia-rodrigo",
        raw_genres=["pop", "alt z"],
        normalized_genres=["pop", "alt z"],
        primary_genre="pop",
        language="english",
        region="美国",
        confidence=0.95,
        evidence_url="https://example.test/olivia",
        evidence_summary="Curated from artist profile.",
        status="approved",
    )

    resolved = resolve_artist_genres(conn, "Olivia Rodrigo")

    assert resolved.genres == ["pop", "alt z"]
    assert resolved.source == "curated_seed"
    assert resolved.is_fallback is True


def test_local_source_resolution_uses_source_priority_before_confidence() -> None:
    conn = _conn()
    upsert_genre_source(
        conn,
        artist_name="Priority Artist",
        spotify_artist_id=None,
        source="lastfm",
        source_key="lastfm:priority",
        raw_genres=["indie pop"],
        normalized_genres=["indie pop"],
        primary_genre="indie pop",
        language="english",
        region="全球",
        confidence=0.99,
        evidence_url=None,
        evidence_summary="External tag.",
        status="approved",
    )
    upsert_genre_source(
        conn,
        artist_name="Priority Artist",
        spotify_artist_id=None,
        source="curated_seed",
        source_key="seed:priority",
        raw_genres=["pop"],
        normalized_genres=["pop"],
        primary_genre="pop",
        language="english",
        region="全球",
        confidence=0.75,
        evidence_url=None,
        evidence_summary="Manual curated seed.",
        status="approved",
    )

    resolved = resolve_artist_genres(conn, "Priority Artist")

    assert resolved.genres == ["pop"]
    assert resolved.source == "curated_seed"


def test_local_source_resolution_uses_confidence_within_same_priority() -> None:
    conn = _conn()
    upsert_genre_source(
        conn,
        artist_name="Confidence Artist",
        spotify_artist_id=None,
        source="lastfm",
        source_key="lastfm:low",
        raw_genres=["rock"],
        normalized_genres=["rock"],
        primary_genre="rock",
        language="english",
        region="全球",
        confidence=0.60,
        evidence_url=None,
        evidence_summary="Low confidence tag.",
        status="approved",
    )
    upsert_genre_source(
        conn,
        artist_name="Confidence Artist",
        spotify_artist_id=None,
        source="lastfm",
        source_key="lastfm:high",
        raw_genres=["indie pop"],
        normalized_genres=["indie pop"],
        primary_genre="indie pop",
        language="english",
        region="全球",
        confidence=0.90,
        evidence_url=None,
        evidence_summary="High confidence tag.",
        status="approved",
    )

    resolved = resolve_artist_genres(conn, "Confidence Artist")

    assert resolved.genres == ["indie pop"]
    assert resolved.confidence == 0.90


def test_suggested_llm_rows_do_not_feed_statistics() -> None:
    conn = _conn()
    upsert_genre_source(
        conn,
        artist_name="Unknown Artist",
        spotify_artist_id=None,
        source="llm",
        source_key="llm:unknown",
        raw_genres=["pop"],
        normalized_genres=["pop"],
        primary_genre="pop",
        language="english",
        region="全球",
        confidence=0.70,
        evidence_url=None,
        evidence_summary="LLM suggestion only.",
        status="suggested",
    )

    resolved = resolve_artist_genres(conn, "Unknown Artist")
    coverage = compute_genre_coverage(conn, {"Unknown Artist": 4.0})

    assert resolved.genres == []
    assert resolved.source == "unknown"
    assert coverage["known_hours"] == 0.0
    assert coverage["unknown_hours"] == 4.0


def test_upsert_genre_source_leaves_transaction_control_to_caller() -> None:
    conn = _conn()

    upsert_genre_source(
        conn,
        artist_name="Rollback Artist",
        spotify_artist_id=None,
        source="curated_seed",
        source_key="seed:rollback",
        raw_genres=["pop"],
        normalized_genres=["pop"],
        primary_genre="pop",
        language="english",
        region="全球",
        confidence=0.90,
        evidence_url=None,
        evidence_summary="Rollback candidate.",
        status="approved",
    )
    conn.rollback()

    count = conn.execute("SELECT COUNT(*) FROM artist_genre_sources").fetchone()[0]
    assert count == 0


def test_resolver_falls_back_to_spotify_when_local_tables_are_missing() -> None:
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
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Legacy Artist", json.dumps(["legacy pop"], ensure_ascii=False)),
    )

    resolved = resolve_artist_genres(conn, "Legacy Artist")
    missing = resolve_artist_genres(conn, "Missing Artist")

    assert resolved.genres == ["legacy pop"]
    assert resolved.source == "spotify"
    assert missing.genres == []
    assert missing.source == "unknown"


def test_resolve_artist_genres_map_batches_names() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Known", json.dumps(["rock"], ensure_ascii=False)),
    )
    result = resolve_artist_genres_map(conn, ["Known", "Missing"])
    assert result["Known"].genres == ["rock"]
    assert result["Missing"].genres == []


def test_resolve_artist_genres_map_uses_batch_queries() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Known", json.dumps(["rock"], ensure_ascii=False)),
    )
    upsert_genre_source(
        conn,
        artist_name="Fallback",
        spotify_artist_id=None,
        source="curated_seed",
        source_key="seed:fallback",
        raw_genres=["pop"],
        normalized_genres=["pop"],
        primary_genre="pop",
        language="english",
        region="全球",
        confidence=0.90,
        evidence_url=None,
        evidence_summary="Fallback tag.",
        status="approved",
    )
    conn.commit()
    traces: list[str] = []
    conn.set_trace_callback(traces.append)

    result = resolve_artist_genres_map(conn, ["Known", "Fallback", "Unknown"])

    selects = [sql for sql in traces if sql.lstrip().upper().startswith("SELECT")]
    assert result["Known"].source == "spotify"
    assert result["Fallback"].source == "curated_seed"
    assert result["Unknown"].source == "unknown"
    assert len(selects) <= 6


def test_compute_genre_coverage_by_play_hours() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Known", json.dumps(["rock"], ensure_ascii=False)),
    )
    coverage = compute_genre_coverage(conn, {"Known": 10.0, "Missing": 30.0})
    assert coverage["known_hours"] == 10.0
    assert coverage["unknown_hours"] == 30.0
    assert coverage["known_pct"] == 25.0
    assert coverage["top_missing"][0]["artist_name"] == "Missing"


def test_compute_genre_taxonomy_audit_groups_axes_and_flags_interpretation_risks() -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp-pop", "Spotify Pop Artist", json.dumps(["spotify pop"], ensure_ascii=False)),
    )
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp-cpop", "C-Pop Artist", json.dumps(["mandopop"], ensure_ascii=False)),
    )
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp-cpop-2", "Second C-Pop Artist", json.dumps(["taiwanese pop"], ensure_ascii=False)),
    )
    upsert_genre_source(
        conn,
        artist_name="Taylor Swift",
        spotify_artist_id=None,
        source="curated_seed",
        source_key="seed:taylor",
        raw_genres=["pop", "country pop", "singer-songwriter"],
        normalized_genres=["country pop", "singer-songwriter"],
        primary_genre="pop",
        language="english",
        region="美国",
        confidence=0.95,
        evidence_url=None,
        evidence_summary="Curated seed.",
        status="approved",
    )
    upsert_genre_source(
        conn,
        artist_name="LLM Electronic Artist",
        spotify_artist_id=None,
        source="llm",
        source_key="llm:electronic",
        raw_genres=["electropop"],
        normalized_genres=["electropop"],
        primary_genre="electropop",
        language="english",
        region="全球",
        confidence=0.72,
        evidence_url=None,
        evidence_summary="Approved LLM suggestion.",
        status="approved",
    )
    conn.commit()

    report = compute_genre_taxonomy_audit(
        conn,
        {
            "Spotify Pop Artist": 1.0,
            "C-Pop Artist": 2.0,
            "Second C-Pop Artist": 2.0,
            "Taylor Swift": 7.0,
            "LLM Electronic Artist": 8.0,
        },
    )

    axis_summary = {row["axis"]: row for row in report["axis_summary"]}
    assert axis_summary["style"]["label"] == "风格"
    assert axis_summary["scene"]["label"] == "场景"
    assert axis_summary["role"]["label"] == "身份"
    assert axis_summary["style"]["hours"] == pytest.approx(13.7)
    assert axis_summary["scene"]["hours"] == pytest.approx(4.0)
    assert axis_summary["role"]["hours"] == pytest.approx(2.3)
    assert "声音/风格偏好" in axis_summary["style"]["interpretation"]
    assert "不等同于声音风格" in axis_summary["scene"]["interpretation"]

    by_name = {row["name"]: row for row in report["top_canonical_genres"]}
    assert by_name["pop"]["confidence_tier"] == "medium"
    assert by_name["pop"]["interpretation"] == axis_summary["style"]["interpretation"]
    assert by_name["c-pop"]["axis"] == "scene"
    assert by_name["c-pop"]["confidence_tier"] == "high"
    assert by_name["c-pop"]["risk_flags"] == []

    country_flags = {flag["code"]: flag for flag in by_name["country"]["risk_flags"]}
    assert "single_artist_dominance" in country_flags
    assert "Taylor Swift" in country_flags["single_artist_dominance"]["message"]

    electronic_flags = {flag["code"]: flag for flag in by_name["electronic/dance"]["risk_flags"]}
    assert by_name["electronic/dance"]["confidence_tier"] == "low"
    assert "source_confidence" in electronic_flags
    assert "LLM" in electronic_flags["source_confidence"]["message"]
