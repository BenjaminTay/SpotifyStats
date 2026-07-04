from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.domains.metadata.artist_genres import (
    canonicalize_genres_for_statistics,
    resolve_artist_genres,
)

pytestmark = pytest.mark.unit


def _genre_conn() -> sqlite3.Connection:
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


class _TrackingConnection:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.closed = False

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def close(self) -> None:
        self.closed = True
        self._conn.close()


def _seed_file(tmp_path: Path) -> Path:
    seed_path = tmp_path / "artist_genre_overrides.seed.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "artist_name": "Taylor Swift",
                    "spotify_artist_id": None,
                    "source": "curated_seed",
                    "source_key": "seed:taylor-swift",
                    "genres": ["pop", "country pop", "singer-songwriter"],
                    "primary_genre": "pop",
                    "language": "english",
                    "region": "美国",
                    "confidence": 0.95,
                    "evidence_url": "https://en.wikipedia.org/wiki/Taylor_Swift",
                    "evidence_summary": "Reviewed seed row.",
                    "status": "approved",
                },
                {
                    "artist_name": "Olivia Rodrigo",
                    "spotify_artist_id": None,
                    "source": "curated_seed",
                    "source_key": "seed:olivia-rodrigo",
                    "genres": ["pop", "pop rock", "alt z"],
                    "primary_genre": "pop",
                    "language": "english",
                    "region": "美国",
                    "confidence": 0.90,
                    "evidence_url": "https://en.wikipedia.org/wiki/Olivia_Rodrigo",
                    "evidence_summary": "Reviewed seed row.",
                    "status": "approved",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return seed_path


def test_seed_import_dry_run_writes_report_without_db_changes(monkeypatch, tmp_path):
    from scripts import import_artist_genre_overrides

    conn = _genre_conn()
    monkeypatch.setattr(import_artist_genre_overrides, "get_db", lambda readonly=False: conn)

    output_path = tmp_path / "seed-import.json"
    exit_code = import_artist_genre_overrides.main(
        [
            "--seed",
            str(_seed_file(tmp_path)),
            "--dry-run",
            "--json-output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert conn.execute("SELECT COUNT(*) FROM artist_genre_sources").fetchone()[0] == 0

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["loaded"] == 2
    assert report["approved"] == 2
    assert report["suggested"] == 0
    assert report["dry_run"] is True


def test_seed_import_commits_rows_that_resolver_can_use(monkeypatch, tmp_path):
    from scripts import import_artist_genre_overrides

    conn = _genre_conn()
    rows = import_artist_genre_overrides.load_seed(_seed_file(tmp_path))

    output_path = tmp_path / "seed-import.json"
    report = import_artist_genre_overrides.import_seed(rows, dry_run=False, conn=conn)
    import_artist_genre_overrides.write_json_report(report, output_path)

    assert conn.execute("SELECT COUNT(*) FROM artist_genre_sources").fetchone()[0] == 2

    resolved = resolve_artist_genres(conn, "Olivia Rodrigo")
    assert resolved.source == "curated_seed"
    assert resolved.genres == ["pop", "pop rock", "alt z"]
    assert resolved.confidence == 0.90

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["loaded"] == 2
    assert report["approved"] == 2
    assert report["dry_run"] is False


def test_seed_import_rolls_back_when_a_row_is_invalid(monkeypatch, tmp_path):
    from scripts import import_artist_genre_overrides

    conn = _genre_conn()
    monkeypatch.setattr(import_artist_genre_overrides, "get_db", lambda readonly=False: conn)
    seed_path = tmp_path / "bad-seed.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "artist_name": "Taylor Swift",
                    "source": "curated_seed",
                    "source_key": "seed:taylor-swift",
                    "genres": ["pop"],
                    "primary_genre": "pop",
                    "confidence": 0.95,
                    "status": "approved",
                },
                {
                    "artist_name": "Bad Row",
                    "source": "curated_seed",
                    "source_key": "seed:bad-row",
                    "genres": [],
                    "primary_genre": "pop",
                    "confidence": 0.95,
                    "status": "approved",
                },
            ]
        ),
        encoding="utf-8",
    )

    exit_code = import_artist_genre_overrides.main(["--seed", str(seed_path)])

    assert exit_code == 1
    assert conn.execute("SELECT COUNT(*) FROM artist_genre_sources").fetchone()[0] == 0


def test_seed_import_rolls_back_when_write_fails_after_partial_insert(monkeypatch, tmp_path):
    from scripts import import_artist_genre_overrides

    conn = _genre_conn()
    rows = import_artist_genre_overrides.load_seed(_seed_file(tmp_path))
    original_upsert = import_artist_genre_overrides.upsert_genre_source
    calls = 0

    def flaky_upsert(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated write failure")
        return original_upsert(*args, **kwargs)

    monkeypatch.setattr(import_artist_genre_overrides, "upsert_genre_source", flaky_upsert)

    with pytest.raises(RuntimeError, match="simulated write failure"):
        import_artist_genre_overrides.import_seed(rows, dry_run=False, conn=conn)

    assert conn.execute("SELECT COUNT(*) FROM artist_genre_sources").fetchone()[0] == 0


def test_seed_import_closes_only_connections_it_opens(monkeypatch, tmp_path):
    from scripts import import_artist_genre_overrides

    caller_owned = _TrackingConnection(_genre_conn())
    rows = import_artist_genre_overrides.load_seed(_seed_file(tmp_path))

    import_artist_genre_overrides.import_seed(rows, dry_run=False, conn=caller_owned)

    assert caller_owned.closed is False

    script_owned = _TrackingConnection(_genre_conn())
    monkeypatch.setattr(
        import_artist_genre_overrides, "get_db", lambda readonly=False: script_owned
    )

    import_artist_genre_overrides.import_seed(rows, dry_run=False)

    assert script_owned.closed is True


def test_repository_seed_includes_missing_completion_batch():
    from scripts import import_artist_genre_overrides

    seed_path = Path(__file__).resolve().parents[3] / "data" / "artist_genre_overrides.seed.json"
    rows = import_artist_genre_overrides.load_seed(seed_path)
    batch_rows = [
        row
        for row in rows
        if row["source"] == "curated_seed"
        and row["source_key"] == "missing_completion_2026-07-05_v1"
    ]

    assert len(batch_rows) == 310
    assert len({row["artist_name"] for row in batch_rows}) == 310
    assert {
        "Elias",
        "Sebastian Croft",
        "Auli'i Cravalho",
        "安沐凡",
        "Maggie Rogers",
        "Saja Boys",
    }.issubset({row["artist_name"] for row in batch_rows})

    for row in batch_rows:
        assert row["status"] == "approved"
        assert row["confidence"] >= 0.6
        assert canonicalize_genres_for_statistics(row["genres"])


def _coverage_conn() -> sqlite3.Connection:
    conn = _genre_conn()
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id)
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ms_played INTEGER NOT NULL,
            track_id INTEGER REFERENCES tracks(track_id),
            content_type TEXT NOT NULL DEFAULT 'audio'
        );

        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'Known Artist'),
            (2, 'Missing Artist');
        INSERT INTO tracks(track_id, track_name, artist_id) VALUES
            (10, 'Known Song', 1),
            (20, 'Missing Song', 2);
        INSERT INTO plays(ts, ms_played, track_id, content_type) VALUES
            ('2026-01-01T00:00:00Z', 3600000, 10, 'audio'),
            ('2026-01-01T01:00:00Z', 10800000, 20, 'audio');
        INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES
            ('sp-known', 'Known Artist', '["rock"]'),
            ('sp-missing', 'Missing Artist', '');
        """
    )
    return conn


def test_coverage_probe_reports_unknown_play_hours_and_threshold(monkeypatch, tmp_path):
    from scripts import artist_genre_coverage_probe

    conn = _coverage_conn()

    output_path = tmp_path / "coverage.json"
    report = artist_genre_coverage_probe.build_report(max_unknown_pct=80, conn=conn)
    artist_genre_coverage_probe.write_json_report(report, output_path)

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["known_pct"] == 25.0
    assert report["unknown_pct"] == 75.0
    assert report["source_hours"] == {"spotify": 1.0}
    assert report["top_missing"][0] == {"artist_name": "Missing Artist", "hours": 3.0}

    failed_report = artist_genre_coverage_probe.build_report(max_unknown_pct=70, conn=conn)
    assert failed_report["threshold_exceeded"] is True


def test_coverage_probe_closes_only_connections_it_opens(monkeypatch):
    from scripts import artist_genre_coverage_probe

    caller_owned = _TrackingConnection(_coverage_conn())

    artist_genre_coverage_probe.build_report(conn=caller_owned)

    assert caller_owned.closed is False

    script_owned = _TrackingConnection(_coverage_conn())
    monkeypatch.setattr(artist_genre_coverage_probe, "get_db", lambda readonly=True: script_owned)

    artist_genre_coverage_probe.build_report()

    assert script_owned.closed is True
