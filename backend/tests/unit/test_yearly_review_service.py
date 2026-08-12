from __future__ import annotations

import sqlite3

from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services import yearly_review_service
from backend.services.yearly_review_service import build_yearly_review_cache_key


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
        bb_week_start_hour=0,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="artist-rev",
        artist_identity_revision=1,
        track_credit_revision=2,
        track_group_revision="track-rev",
        album_project_revision="album-rev",
        filter_fingerprint="fingerprint",
    )


def test_cache_key_changes_with_language_database_and_filter_revisions() -> None:
    context = _context()
    base = build_yearly_review_cache_key(
        2025, context, language_revision="lang-a", db_revision="db-a"
    )

    assert base != build_yearly_review_cache_key(
        2025, context, language_revision="lang-b", db_revision="db-a"
    )
    assert base != build_yearly_review_cache_key(
        2025, context, language_revision="lang-a", db_revision="db-b"
    )
    changed = context.model_copy(update={"filter_fingerprint": "other"})
    assert base != build_yearly_review_cache_key(
        2025, changed, language_revision="lang-a", db_revision="db-a"
    )


def test_cache_key_changes_with_content_version(monkeypatch) -> None:
    context = _context()
    base = build_yearly_review_cache_key(
        2025, context, language_revision="lang-a", db_revision="db-a"
    )
    monkeypatch.setattr(yearly_review_service, "YEARLY_REVIEW_CONTENT_VERSION", "next")

    assert base != build_yearly_review_cache_key(
        2025, context, language_revision="lang-a", db_revision="db-a"
    )


def test_batch_preparation_reuses_shared_source_revisions(monkeypatch) -> None:
    calls = {"database": 0, "language": 0}

    def database():
        calls["database"] += 1
        return "db-a"

    def language():
        calls["language"] += 1
        return "lang-a"

    monkeypatch.setattr(yearly_review_service, "database_revision", database)
    monkeypatch.setattr(yearly_review_service, "_language_revision", language)

    prepared = yearly_review_service._prepare_artifacts([2023, 2024, 2025], _context())

    assert list(prepared) == [2023, 2024, 2025]
    assert calls == {"database": 1, "language": 1}


def test_prewarm_rejects_years_not_present_in_playback_data(monkeypatch) -> None:
    monkeypatch.setattr(
        yearly_review_service,
        "get_yearly_review_available_years",
        lambda: yearly_review_service.YearlyReviewAvailableYearsResponse(
            years=[2024, 2025], latest_year=2025
        ),
    )

    try:
        yearly_review_service.prewarm_yearly_reviews([2024, 2099], _context(), foreground_year=2099)
    except ValueError as exc:
        assert str(exc) == "unavailable_years:2099"
    else:
        raise AssertionError("unavailable years must be rejected")


def test_database_revision_ignores_unrelated_writes_but_tracks_imports(
    monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "revision.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """CREATE TABLE plays (
               play_id INTEGER PRIMARY KEY, ts TEXT NOT NULL, ms_played INTEGER NOT NULL
           );
           CREATE TABLE tracks (track_id INTEGER PRIMARY KEY);
           CREATE TABLE albums (album_id INTEGER PRIMARY KEY);
           CREATE TABLE artists (artist_id INTEGER PRIMARY KEY);
           CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY);
           CREATE TABLE task_logs (id INTEGER PRIMARY KEY, message TEXT);
           INSERT INTO tracks VALUES (1);
           INSERT INTO albums VALUES (1);
           INSERT INTO artists VALUES (1);
           INSERT INTO schema_migrations VALUES (30);
           INSERT INTO plays VALUES (1, '2025-01-01T00:00:00Z', 60000);"""
    )
    conn.commit()
    conn.close()

    def connect(*, readonly=True):
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(yearly_review_service, "get_db", connect)
    base = yearly_review_service.database_revision()
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO task_logs(message) VALUES ('unrelated')")
    conn.commit()
    conn.close()
    assert yearly_review_service.database_revision() == base

    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO plays VALUES (2, '2025-01-02T00:00:00Z', 70000)")
    conn.commit()
    conn.close()
    assert yearly_review_service.database_revision() != base
