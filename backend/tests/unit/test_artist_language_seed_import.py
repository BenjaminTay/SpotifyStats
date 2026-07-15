from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from backend.core.migrations import migrate_023, migrate_024
from backend.domains.metadata.artist_languages import ArtistLanguageValidationError
from scripts import import_artist_language_sources

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
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        );
        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'Seed Artist'),
            (2, 'Legacy Artist'),
            (3, 'Conflict Artist'),
            (4, 'Second Seed Artist'),
            (5, 'Spotify Resolved Artist');
        INSERT INTO tracks(track_id, track_name, artist_id) VALUES
            (10, 'Seed Track', 1),
            (20, 'Second Track', 4);
        INSERT INTO track_artists(track_id, artist_id, role) VALUES
            (10, 1, 'primary'),
            (20, 4, 'primary');
        INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name)
        VALUES ('spotify-resolved', 'Spotify Resolved Artist');
        """
    )
    migrate_023(conn)
    migrate_024(conn)
    conn.commit()
    yield conn
    conn.close()


def _approved_row(
    artist_name: str = "Seed Artist",
    *,
    source_key: str = "seed:seed-artist:v1",
    spotify_artist_id: str | None = None,
) -> dict[str, Any]:
    return {
        "artist_name": artist_name,
        "spotify_artist_id": spotify_artist_id,
        "classification": "single_language",
        "primary_language_code": "english",
        "language_variant": None,
        "raw_language": "English",
        "origin": "curated_seed",
        "source_key": source_key,
        "status": "approved",
        "reviewed_by": "metadata-reviewer",
        "resolution_note": "Official profile explicitly identifies the vocal language.",
        "evidence": [
            {
                "local_track_id": None,
                "claimed_language_code": "english",
                "claimed_language_variant": None,
                "evidence_kind": "artist_profile",
                "performer_attribution": "artist_vocal_confirmed",
                "evidence_url": "https://example.com/official-profile",
                "evidence_title": "Official artist profile",
                "evidence_accessed_at": "2026-07-11T00:00:00Z",
                "evidence_summary": "The profile documents the artist's English vocals.",
            }
        ],
    }


def _write_seed(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "artist-language-seed.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class _TrackingConnection:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.closed = False

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def close(self) -> None:
        self.closed = True


def test_cli_contract_and_repository_seed_is_empty() -> None:
    args = import_artist_language_sources.parse_args(
        ["--legacy-suggestions", "--dry-run", "--json-output", "/tmp/report.json"]
    )
    assert args.seed == import_artist_language_sources.DEFAULT_SEED
    assert args.legacy_suggestions is True
    assert args.dry_run is True
    assert args.json_output == Path("/tmp/report.json")

    assert json.loads(import_artist_language_sources.DEFAULT_SEED.read_text()) == []


def test_approved_seed_requires_reviewer_and_resolution_note(tmp_path: Path) -> None:
    row = _approved_row()
    row["reviewed_by"] = ""
    with pytest.raises(ValueError, match="reviewed_by"):
        import_artist_language_sources.load_seed(_write_seed(tmp_path, [row]))

    row = _approved_row()
    row["resolution_note"] = None
    with pytest.raises(ValueError, match="resolution_note"):
        import_artist_language_sources.load_seed(_write_seed(tmp_path, [row]))


def test_seed_dry_run_resolves_validates_and_writes_nothing(
    language_conn: sqlite3.Connection,
) -> None:
    report = import_artist_language_sources.import_seed(
        [_approved_row()], dry_run=True, conn=language_conn
    )

    assert report == {
        "mode": "seed",
        "dry_run": True,
        "loaded": 1,
        "approved": 1,
        "suggested": 0,
        "skipped": 0,
        "conflicted": 0,
        "unresolved": 0,
        "details": [],
    }
    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0


def test_seed_dry_run_matches_real_batch_outcomes_for_duplicate_approved_artist(
    language_conn: sqlite3.Connection,
) -> None:
    rows = [
        _approved_row(),
        _approved_row(source_key="seed:seed-artist:v2"),
    ]

    dry_run_report = import_artist_language_sources.import_seed(
        rows,
        dry_run=True,
        conn=language_conn,
    )

    assert dry_run_report["approved"] == 1
    assert dry_run_report["conflicted"] == 1
    assert dry_run_report["details"] == [{"artist_name": "Seed Artist", "outcome": "conflicted"}]
    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_evidence") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0

    real_report = import_artist_language_sources.import_seed(
        rows,
        dry_run=False,
        conn=language_conn,
    )

    assert {**dry_run_report, "dry_run": False} == real_report
    assert _count(language_conn, "artist_language_sources") == 1
    assert _count(language_conn, "artist_language_review_queue") == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_url", "http://example.com/not-https", "evidence_url must use https://"),
        ("evidence_title", "", "evidence_title must not be empty"),
        ("evidence_summary", " ", "evidence_summary must not be empty"),
    ],
)
@pytest.mark.parametrize("dry_run", [True, False])
def test_invalid_approved_seed_fails_identically_in_dry_run_and_import(
    language_conn: sqlite3.Connection,
    field: str,
    value: str,
    message: str,
    dry_run: bool,
) -> None:
    row = _approved_row()
    row["evidence"][0][field] = value

    with pytest.raises(ArtistLanguageValidationError, match=message):
        import_artist_language_sources.import_seed([row], dry_run=dry_run, conn=language_conn)

    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0


@pytest.mark.parametrize("status", ["suggested", "approved"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_seed_rejects_unknown_local_track_identically_without_partial_writes(
    language_conn: sqlite3.Connection,
    status: str,
    dry_run: bool,
) -> None:
    row = _approved_row()
    row["status"] = status
    if status == "suggested":
        row["reviewed_by"] = None
        row["resolution_note"] = None
    row["evidence"][0]["local_track_id"] = 999_999

    with pytest.raises(
        ArtistLanguageValidationError,
        match="local_track_id 999999 does not exist",
    ):
        import_artist_language_sources.import_seed([row], dry_run=dry_run, conn=language_conn)

    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_evidence") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0


@pytest.mark.parametrize("dry_run", [True, False])
def test_seed_batch_rolls_back_earlier_valid_row_when_later_track_is_unknown(
    language_conn: sqlite3.Connection,
    dry_run: bool,
) -> None:
    valid = _approved_row()
    invalid = _approved_row(
        "Second Seed Artist",
        source_key="seed:second-seed-artist:v1",
    )
    invalid["evidence"][0]["local_track_id"] = 999_999

    with pytest.raises(ArtistLanguageValidationError, match="local_track_id 999999 does not exist"):
        import_artist_language_sources.import_seed(
            [valid, invalid],
            dry_run=dry_run,
            conn=language_conn,
        )

    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_evidence") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0


def test_approved_seed_uses_review_services_and_validator(
    language_conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real_get = import_artist_language_sources.get_or_create_review
    real_save = import_artist_language_sources.save_review_source
    real_decide = import_artist_language_sources.decide_review

    def tracked_get(*args, **kwargs):
        calls.append("get")
        return real_get(*args, **kwargs)

    def tracked_save(*args, **kwargs):
        calls.append("save")
        return real_save(*args, **kwargs)

    def tracked_decide(*args, **kwargs):
        calls.append("decide")
        return real_decide(*args, **kwargs)

    monkeypatch.setattr(import_artist_language_sources, "get_or_create_review", tracked_get)
    monkeypatch.setattr(import_artist_language_sources, "save_review_source", tracked_save)
    monkeypatch.setattr(import_artist_language_sources, "decide_review", tracked_decide)

    report = import_artist_language_sources.import_seed(
        [_approved_row()], dry_run=False, conn=language_conn
    )

    assert calls == ["get", "save", "decide"]
    assert report["approved"] == 1
    source = language_conn.execute("SELECT * FROM artist_language_sources").fetchone()
    assert tuple(source[key] for key in ("artist_id", "primary_language_code", "status")) == (
        1,
        "en",
        "approved",
    )
    review = language_conn.execute(
        "SELECT status, reviewed_by, resolution_note FROM artist_language_review_queue"
    ).fetchone()
    assert tuple(review) == (
        "approved",
        "metadata-reviewer",
        "Official profile explicitly identifies the vocal language.",
    )


def test_seed_resolves_optional_spotify_id_and_leaves_unknown_unwritten(
    language_conn: sqlite3.Connection,
) -> None:
    mapped = _approved_row(
        "Historical Display Name",
        source_key="seed:spotify-resolved:v1",
        spotify_artist_id="spotify-resolved",
    )
    missing = _approved_row("Unknown Artist", source_key="seed:unknown:v1")

    report = import_artist_language_sources.import_seed(
        [mapped, missing], dry_run=False, conn=language_conn
    )

    assert report["approved"] == 1
    assert report["unresolved"] == 1
    assert report["details"] == [{"artist_name": "Unknown Artist", "outcome": "unresolved"}]
    assert language_conn.execute("SELECT artist_id FROM artist_language_sources").fetchone()[0] == 5


def test_existing_approved_fact_is_reported_and_never_replaced(
    language_conn: sqlite3.Connection,
) -> None:
    language_conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code,
               origin, source_key, status
           ) VALUES (1, 'single_language', 'ja', 'manual', 'manual:existing', 'approved')"""
    )
    language_conn.commit()

    report = import_artist_language_sources.import_seed(
        [_approved_row()], dry_run=False, conn=language_conn
    )

    assert report["conflicted"] == 1
    assert report["approved"] == 0
    assert tuple(
        language_conn.execute(
            "SELECT primary_language_code, origin, status FROM artist_language_sources"
        ).fetchone()
    ) == ("ja", "manual", "approved")
    assert _count(language_conn, "artist_language_review_queue") == 0


def test_source_key_makes_seed_import_idempotent(
    language_conn: sqlite3.Connection,
) -> None:
    first = import_artist_language_sources.import_seed(
        [_approved_row()], dry_run=False, conn=language_conn
    )
    second = import_artist_language_sources.import_seed(
        [_approved_row()], dry_run=False, conn=language_conn
    )

    assert first["approved"] == 1
    assert second["skipped"] == 1
    assert second["conflicted"] == 0
    assert _count(language_conn, "artist_language_sources") == 1
    assert _count(language_conn, "artist_language_review_queue") == 1


def test_legacy_aliases_merge_to_one_suggestion_without_evidence(
    language_conn: sqlite3.Connection,
) -> None:
    language_conn.execute(
        """INSERT INTO artist_genre_sources(
               artist_name, source, source_key, normalized_genres_json,
               language, status
           ) VALUES ('Legacy Artist', 'spotify', 'spotify:legacy', '[]',
                     'English', 'approved')"""
    )
    language_conn.execute(
        """INSERT INTO artist_genre_overrides(
               artist_name, normalized_genres_json, language
           ) VALUES ('Legacy Artist', '[]', 'en')"""
    )
    language_conn.commit()

    report = import_artist_language_sources.import_legacy_suggestions(language_conn, dry_run=False)

    assert report["approved"] == 0
    assert report["suggested"] == 1
    source = language_conn.execute(
        "SELECT primary_language_code, raw_language, origin, status FROM artist_language_sources"
    ).fetchone()
    assert tuple(source) == ("en", "English | en", "legacy_import", "suggested")
    assert _count(language_conn, "artist_language_evidence") == 0
    assert (
        language_conn.execute("SELECT status FROM artist_language_review_queue").fetchone()[0]
        == "open"
    )


def test_conflicting_legacy_values_are_reported_not_chosen(
    language_conn: sqlite3.Connection,
) -> None:
    for source_key, language in (("one", "english"), ("two", "chinese")):
        language_conn.execute(
            """INSERT INTO artist_genre_sources(
                   artist_name, source, source_key, normalized_genres_json,
                   language, status
               ) VALUES ('Conflict Artist', 'curated_seed', ?, '[]', ?, 'approved')""",
            (source_key, language),
        )
    language_conn.commit()

    report = import_artist_language_sources.import_legacy_suggestions(language_conn, dry_run=False)

    assert report["conflicted"] == 1
    assert report["suggested"] == 0
    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0


def test_legacy_dry_run_reports_real_outcomes_with_zero_writes(
    language_conn: sqlite3.Connection,
) -> None:
    language_conn.execute(
        """INSERT INTO artist_genre_overrides(
               artist_name, normalized_genres_json, language
           ) VALUES ('Legacy Artist', '[]', 'english')"""
    )
    language_conn.execute(
        """INSERT INTO artist_genre_overrides(
               artist_name, normalized_genres_json, language
           ) VALUES ('Missing Legacy Artist', '[]', 'japanese')"""
    )
    language_conn.commit()

    report = import_artist_language_sources.import_legacy_suggestions(language_conn, dry_run=True)

    assert report["suggested"] == 1
    assert report["unresolved"] == 1
    assert report["dry_run"] is True
    assert _count(language_conn, "artist_language_sources") == 0


@pytest.mark.parametrize("dry_run", [True, False])
def test_seed_batch_rolls_back_when_second_save_fails(
    language_conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    dry_run: bool,
) -> None:
    rows = [
        _approved_row(),
        _approved_row("Second Seed Artist", source_key="seed:second:v1"),
    ]
    real_save = import_artist_language_sources.save_review_source
    calls = 0

    def flaky_save(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated second-row failure")
        return real_save(*args, **kwargs)

    monkeypatch.setattr(import_artist_language_sources, "save_review_source", flaky_save)

    with pytest.raises(RuntimeError, match="second-row"):
        import_artist_language_sources.import_seed(rows, dry_run=dry_run, conn=language_conn)

    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0


def test_script_owned_seed_dry_run_rolls_back_and_closes_on_error(
    language_conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _approved_row(),
        _approved_row("Second Seed Artist", source_key="seed:second:v1"),
    ]
    tracked = _TrackingConnection(language_conn)
    real_save = import_artist_language_sources.save_review_source
    calls = 0

    def flaky_save(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated script-owned failure")
        return real_save(*args, **kwargs)

    monkeypatch.setattr(import_artist_language_sources, "get_db", lambda readonly=False: tracked)
    monkeypatch.setattr(import_artist_language_sources, "save_review_source", flaky_save)

    with pytest.raises(RuntimeError, match="script-owned"):
        import_artist_language_sources.import_seed(rows, dry_run=True)

    assert _count(language_conn, "artist_language_sources") == 0
    assert _count(language_conn, "artist_language_evidence") == 0
    assert _count(language_conn, "artist_language_review_queue") == 0
    assert tracked.closed is True


def test_main_writes_json_report_for_seed_dry_run(
    language_conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed_path = _write_seed(tmp_path, [_approved_row()])
    output_path = tmp_path / "report.json"
    tracked = _TrackingConnection(language_conn)
    monkeypatch.setattr(import_artist_language_sources, "get_db", lambda readonly=False: tracked)

    exit_code = import_artist_language_sources.main(
        [
            "--seed",
            str(seed_path),
            "--dry-run",
            "--json-output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text())["approved"] == 1
    assert _count(language_conn, "artist_language_sources") == 0
    assert tracked.closed is True


@pytest.mark.parametrize("mode", ["seed", "legacy"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_import_never_closes_caller_owned_connection(
    language_conn: sqlite3.Connection,
    mode: str,
    dry_run: bool,
) -> None:
    tracked = _TrackingConnection(language_conn)

    if mode == "seed":
        import_artist_language_sources.import_seed(
            [], dry_run=dry_run, conn=cast(sqlite3.Connection, tracked)
        )
    else:
        import_artist_language_sources.import_legacy_suggestions(
            cast(sqlite3.Connection, tracked), dry_run=dry_run
        )

    assert tracked.closed is False


@pytest.mark.parametrize("mode", ["seed", "legacy"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_import_always_closes_script_owned_connection(
    language_conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    dry_run: bool,
) -> None:
    tracked = _TrackingConnection(language_conn)
    monkeypatch.setattr(import_artist_language_sources, "get_db", lambda readonly=False: tracked)

    if mode == "seed":
        import_artist_language_sources.import_seed([], dry_run=dry_run)
    else:
        import_artist_language_sources.import_legacy_suggestions(dry_run=dry_run)

    assert tracked.closed is True
