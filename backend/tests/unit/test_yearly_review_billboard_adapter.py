from __future__ import annotations

import sqlite3

from backend.domains.yearly_review import billboard_adapter
from backend.domains.yearly_review.billboard_adapter import build_billboard_source
from backend.models.yearly_review import YearlyReviewFilterContext


def _context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=12,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="a",
        artist_identity_revision=1,
        track_credit_revision=1,
        track_group_revision="t",
        album_project_revision="p",
        filter_fingerprint="f",
    )


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        CREATE TABLE album_projects (
            project_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            artist_id INTEGER,
            include_in_charts INTEGER
        );
        INSERT INTO artists VALUES (3, 'Singer');
        INSERT INTO album_projects VALUES (91, 'Album', 3, 1);
        """
    )
    return conn


def test_preserves_year_end_semantics_coverage_honors_and_album_identity() -> None:
    year_end = {
        "meta": {
            "year": 2025,
            "semantics_version": "year_end_v3",
            "coverage_status": "complete",
            "observed_weeks": 52,
            "expected_weeks": 52,
            "has_internal_gaps": False,
        },
        "tracks": [{"track_id": 8, "track_name": "Song", "year_end_rank": 1}],
        "albums": [{"album_name": "Album", "artist_name": "Singer", "year_end_rank": 1}],
        "artists": [{"artist_name": "Singer", "year_end_rank": 1}],
        "honors": {"year_end_no1_artist": {"artist_name": "Singer"}},
    }
    records = {
        "records": {"debut_no1": [{"artist_name": "Singer", "weeks_at_no1": 8, "year": 2025}]}
    }
    result = build_billboard_source(
        _conn(),
        2025,
        _context(),
        year_end_payload=year_end,
        records_payload=records,
    )

    assert result["semantics_version"] == "year_end_v3"
    assert result["coverage"].status == "complete"
    assert result["honors"]["year_end_no1_artist"]["artist_name"] == "Singer"
    assert result["charts"]["album"][0]["album_project_id"] == 91
    assert result["charts"]["album"][0]["identity_key"] == "album-project:91"
    assert result["record_candidates"][0].source == "billboard_records"
    assert result["record_candidates"][0].source_family == "championship"
    assert result["record_semantics"]["aligned_with_requested_context"] is True


def test_unknown_album_keeps_explicit_fallback_identity() -> None:
    payload = {
        "meta": {"coverage_status": "empty", "semantics_version": "year_end_v3"},
        "tracks": [],
        "albums": [{"album_name": "Unknown", "artist_name": "Nobody"}],
        "artists": [],
        "honors": {},
    }
    result = build_billboard_source(
        _conn(),
        2025,
        _context(),
        year_end_payload=payload,
        records_payload={"records": {}},
    )

    album = result["charts"]["album"][0]
    assert album["album_project_id"] is None
    assert album["identity_key"] == "album:nobody\u241funknown"
    assert result["coverage"].status == "empty"


def test_ambiguous_album_project_name_does_not_invent_identity() -> None:
    conn = _conn()
    conn.execute("INSERT INTO album_projects VALUES (92, 'Album', 3, 1)")
    payload = {
        "meta": {"coverage_status": "empty", "semantics_version": "year_end_v3"},
        "tracks": [],
        "albums": [{"album_name": "Album", "artist_name": "Singer"}],
        "artists": [],
        "honors": {},
    }
    result = build_billboard_source(
        conn,
        2025,
        _context(),
        year_end_payload=payload,
        records_payload={"records": {}},
    )

    assert result["charts"]["album"][0]["album_project_id"] is None


def test_live_adapter_passes_integer_annual_range_to_billboard_records(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        billboard_adapter,
        "compute_year_end_staged",
        lambda **_kwargs: {
            "meta": {"coverage_status": "empty", "semantics_version": "year_end_v3"},
            "tracks": [],
            "albums": [],
            "artists": [],
            "honors": {},
        },
    )

    def fake_records(**kwargs):
        captured.update(kwargs)
        return {"records": {}}

    monkeypatch.setattr(billboard_adapter, "compute_records_staged", fake_records)
    build_billboard_source(_conn(), 2025, _context())

    assert captured["year_start"] == 2025
    assert captured["year_end"] == 2025
