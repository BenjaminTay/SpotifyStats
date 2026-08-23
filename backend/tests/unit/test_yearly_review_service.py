from __future__ import annotations

import sqlite3

import pytest

from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services import yearly_review_service
from backend.services.yearly_review_service import build_yearly_review_cache_key


def _context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
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
    changed = context.model_copy(update={"min_ms": 45_000, "filter_fingerprint": "other"})
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


def test_cache_key_ignores_unrelated_global_metadata_when_scoped_dependency_is_stable() -> None:
    context = _context()
    changed_global = context.model_copy(
        update={
            "artist_metadata_revision": "new-artist-outside-year",
            "track_group_revision": "new-group-outside-year",
            "album_project_revision": "new-project-outside-year",
            "filter_fingerprint": "global-context-changed",
        }
    )
    first = build_yearly_review_cache_key(
        2025,
        context,
        language_revision="lang-a",
        db_revision="prefix-2025",
        scoped_dependency_revision="scope-2025",
    )
    second = build_yearly_review_cache_key(
        2025,
        changed_global,
        language_revision="lang-a",
        db_revision="prefix-2025",
        scoped_dependency_revision="scope-2025",
    )

    assert second == first
    assert first != build_yearly_review_cache_key(
        2025,
        changed_global,
        language_revision="lang-a",
        db_revision="prefix-2025",
        scoped_dependency_revision="scope-2025-updated",
    )


def test_batch_preparation_reuses_shared_source_revisions(monkeypatch) -> None:
    calls = {"database": 0, "language": 0}

    def database(year):
        calls["database"] += 1
        return f"db-{year}"

    def language():
        calls["language"] += 1
        return "lang-a"

    monkeypatch.setattr(yearly_review_service, "database_revision", database)
    monkeypatch.setattr(yearly_review_service, "_language_revision", language)
    monkeypatch.setattr(
        yearly_review_service,
        "_year_scoped_dependency_revision",
        lambda year, context: f"scope-{year}",
    )

    prepared = yearly_review_service._prepare_artifacts([2023, 2024, 2025], _context())

    assert list(prepared) == [2023, 2024, 2025]
    assert calls == {"database": 3, "language": 1}


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


def _create_scoped_dependency_fixture(db_path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """CREATE TABLE plays (
               play_id INTEGER PRIMARY KEY, ts_year INTEGER NOT NULL,
               track_id INTEGER
           );
           CREATE TABLE artists (
               artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL,
               spotify_artist_id TEXT, genres TEXT, popularity INTEGER,
               followers INTEGER, image_url TEXT
           );
           CREATE TABLE tracks (
               track_id INTEGER PRIMARY KEY, track_name TEXT NOT NULL,
               artist_id INTEGER, album_id INTEGER, spotify_track_uri TEXT,
               spotify_track_id TEXT
           );
           CREATE TABLE track_artists (
               track_id INTEGER, artist_id INTEGER, role TEXT
           );
           CREATE TABLE spotify_artist_meta (
               spotify_artist_id TEXT PRIMARY KEY, artist_name TEXT NOT NULL,
               popularity INTEGER, followers INTEGER, genres TEXT, image_url TEXT
           );
           CREATE TABLE artist_genre_overrides (
               artist_name TEXT PRIMARY KEY, normalized_genres_json TEXT NOT NULL,
               primary_genre TEXT, language TEXT, region TEXT,
               confidence REAL, note TEXT
           );
           CREATE TABLE artist_genre_sources (
               source_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL,
               spotify_artist_id TEXT, source TEXT, source_key TEXT,
               normalized_genres_json TEXT, primary_genre TEXT, language TEXT,
               region TEXT, confidence REAL, evidence_url TEXT,
               evidence_summary TEXT, status TEXT
           );
           CREATE TABLE artist_metadata_attribution_overrides (
               track_id INTEGER PRIMARY KEY, artist_id INTEGER,
               reason TEXT, evidence_url TEXT
           );
           CREATE TABLE spotify_track_meta (
               spotify_track_id TEXT PRIMARY KEY, track_name TEXT,
               duration_ms INTEGER, popularity INTEGER, explicit INTEGER,
               track_number INTEGER, disc_number INTEGER, isrc TEXT,
               spotify_album_id TEXT
           );
           CREATE TABLE spotify_album_meta (
               spotify_album_id TEXT PRIMARY KEY, album_name TEXT,
               album_type TEXT, release_date TEXT, popularity INTEGER,
               label TEXT, genres TEXT, image_url TEXT, album_artists TEXT,
               total_tracks INTEGER, track_list TEXT
           );
           CREATE TABLE track_groups (
               group_id INTEGER PRIMARY KEY, scope TEXT, canonical_name TEXT,
               primary_track_id INTEGER, is_manual INTEGER
           );
           CREATE TABLE track_group_members (group_id INTEGER, track_id INTEGER);
           CREATE TABLE album_projects (
               project_id INTEGER PRIMARY KEY, canonical_name TEXT,
               artist_id INTEGER, primary_album_id INTEGER, release_date TEXT,
               scope TEXT, project_type TEXT, include_in_charts INTEGER,
               is_manual INTEGER
           );
           CREATE TABLE album_project_tracks (
               project_id INTEGER, track_id INTEGER, membership_role TEXT,
               min_merge_level INTEGER, source_album_id INTEGER,
               is_exclusive INTEGER, inferred INTEGER
           );
           CREATE TABLE album_project_albums (
               project_id INTEGER, album_id INTEGER, role TEXT,
               source_bucket TEXT, inferred INTEGER
           );
           CREATE TABLE agg_weekly_tracks (billboard_week TEXT);
           CREATE TABLE agg_weekly_albums (billboard_week TEXT);
           CREATE TABLE agg_weekly_artists (billboard_week TEXT);

           INSERT INTO artists VALUES
               (1, 'Scoped Artist', 'artist-1', '[]', 50, 100, 'artist.jpg'),
               (2, 'Outside Artist', 'artist-2', '[]', 40, 80, 'outside.jpg');
           INSERT INTO tracks VALUES
               (10, 'Scoped Track', 1, 100, 'spotify:track:track-1', 'track-1'),
               (20, 'Outside Track', 2, 200, 'spotify:track:track-2', 'track-2');
           INSERT INTO track_artists VALUES (10, 1, 'primary'), (20, 2, 'primary');
           INSERT INTO plays VALUES (1, 2025, 10);
           INSERT INTO spotify_artist_meta VALUES
               ('artist-1', 'Scoped Artist', 50, 100, '["pop"]', 'artist.jpg'),
               ('artist-2', 'Outside Artist', 40, 80, '["rock"]', 'outside.jpg');
           INSERT INTO artist_genre_overrides VALUES
               ('Scoped Artist', '["pop"]', 'pop', 'en', 'US', 1.0, 'manual');
           INSERT INTO artist_genre_sources VALUES
               (1, 'Scoped Artist', 'artist-1', 'wikidata', 'scope', '["pop"]',
                'pop', 'en', 'US', 0.9, 'https://example.test', 'evidence', 'approved');
           INSERT INTO artist_metadata_attribution_overrides VALUES
               (10, 1, 'confirmed', 'https://example.test');
           INSERT INTO spotify_track_meta VALUES
               ('track-1', 'Scoped Track', 180000, 60, 0, 1, 1, 'ISRC1', 'album-1'),
               ('track-2', 'Outside Track', 200000, 40, 0, 1, 1, 'ISRC2', 'album-2');
           INSERT INTO spotify_album_meta VALUES
               ('album-1', 'Scoped Album', 'album', '2025-01-01', 60, 'Label',
                '[]', 'album.jpg', '["Scoped Artist"]', 10, '["track-1"]'),
               ('album-2', 'Outside Album', 'album', '2024-01-01', 40, 'Label',
                '[]', 'outside-album.jpg', '["Outside Artist"]', 8, '["track-2"]');
           INSERT INTO track_groups VALUES (1, 'recording', 'Scoped Song', 10, 1);
           INSERT INTO track_group_members VALUES (1, 10);
           INSERT INTO album_projects VALUES
               (1, 'Scoped Project', 1, 100, '2025-01-01', 'release', 'album', 1, 1);
           INSERT INTO album_project_tracks VALUES
               (1, 10, 'standard', 2, 100, 1, 0);
           INSERT INTO album_project_albums VALUES
               (1, 100, 'member', 'primary', 0);
           INSERT INTO agg_weekly_tracks VALUES ('2025-01-03');"""
    )
    conn.commit()
    conn.close()


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE spotify_artist_meta SET genres='[\"indie\"]' WHERE spotify_artist_id='artist-1'",
        "UPDATE artist_genre_overrides SET normalized_genres_json='[\"indie\"]' WHERE artist_name='Scoped Artist'",
        "UPDATE artist_genre_sources SET normalized_genres_json='[\"indie\"]' WHERE source_id=1",
        "UPDATE tracks SET artist_id=2 WHERE track_id=10",
        "UPDATE artist_metadata_attribution_overrides SET artist_id=2 WHERE track_id=10",
        "UPDATE spotify_track_meta SET duration_ms=181000 WHERE spotify_track_id='track-1'",
        "UPDATE spotify_album_meta SET release_date='2024-12-31' WHERE spotify_album_id='album-1'",
        "UPDATE album_project_albums SET source_bucket='deluxe' WHERE project_id=1 AND album_id=100",
        "INSERT INTO plays VALUES (2, 2026, 20)",
        "INSERT INTO agg_weekly_tracks VALUES ('2026-01-02')",
    ],
)
def test_scoped_dependency_revision_tracks_reachable_facts_and_available_years(
    monkeypatch, tmp_path, mutation
) -> None:
    db_path = tmp_path / "scoped-dependencies.db"
    _create_scoped_dependency_fixture(db_path)

    def connect(*, readonly=True):
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(yearly_review_service, "get_db", connect)
    base = yearly_review_service._year_scoped_dependency_revision(2025, _context())
    conn = sqlite3.connect(db_path)
    conn.execute(mutation)
    conn.commit()
    conn.close()

    assert yearly_review_service._year_scoped_dependency_revision(2025, _context()) != base


def test_scoped_dependency_revision_ignores_unreachable_metadata(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "unreachable-dependencies.db"
    _create_scoped_dependency_fixture(db_path)

    def connect(*, readonly=True):
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(yearly_review_service, "get_db", connect)
    base = yearly_review_service._year_scoped_dependency_revision(2025, _context())
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE spotify_artist_meta SET genres='[\"jazz\"]' WHERE spotify_artist_id='artist-2'"
    )
    conn.execute(
        "UPDATE spotify_album_meta SET release_date='1999-01-01' WHERE spotify_album_id='album-2'"
    )
    conn.commit()
    conn.close()

    assert yearly_review_service._year_scoped_dependency_revision(2025, _context()) == base
