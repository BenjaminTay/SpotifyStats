from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.music_search_performance_probe import (
    CONTEXT_UNAVAILABLE_REASON,
    DEFAULT_QUERY_CASES,
    evaluate_budgets,
    open_readonly_database,
    sqlite_capabilities,
    summarize_samples,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "music_search_performance_probe.py"


def _create_search_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE artists (
                artist_id INTEGER PRIMARY KEY,
                artist_name TEXT NOT NULL
            );
            CREATE TABLE albums (
                album_id INTEGER PRIMARY KEY,
                album_name TEXT NOT NULL,
                artist_id INTEGER NOT NULL
            );
            CREATE TABLE tracks (
                track_id INTEGER PRIMARY KEY,
                track_name TEXT NOT NULL,
                artist_id INTEGER NOT NULL,
                album_id INTEGER
            );
            CREATE TABLE plays (
                play_id INTEGER PRIMARY KEY,
                track_id INTEGER NOT NULL,
                ms_played INTEGER NOT NULL,
                source_album_id INTEGER
            );
            INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Example Artist');
            INSERT INTO albums(album_id, album_name, artist_id)
            VALUES (10, 'Example Album', 1);
            INSERT INTO tracks(track_id, track_name, artist_id, album_id)
            VALUES (100, 'vampire', 1, 10);
            INSERT INTO plays(play_id, track_id, ms_played, source_album_id)
            VALUES (1000, 100, 180000, 10);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _run_probe(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_music_search_performance_probe_exposes_reusable_cli() -> None:
    result = _run_probe("--help")

    assert result.returncode == 0, result.stderr
    assert "music_search_performance_probe.py" in result.stdout
    assert "--db-path" in result.stdout
    assert "--mode" in result.stdout
    assert "--query" in result.stdout
    assert "--cold" in result.stdout
    assert "--cold-repeat" in result.stdout
    assert "--warm-repeat" in result.stdout
    assert "--json-output" in result.stdout
    assert "--max-p95-ms" in result.stdout
    assert "--require-available" in result.stdout


def test_default_probe_matrix_covers_required_query_classes() -> None:
    assert {case["query_class"] for case in DEFAULT_QUERY_CASES} == {
        "exact",
        "prefix",
        "multi_token_cross_field",
        "high_hit_three_char",
        "unicode_nfkc",
        "single_cjk",
        "single_kind_page_2",
    }
    second_page = next(
        case for case in DEFAULT_QUERY_CASES if case["query_class"] == "single_kind_page_2"
    )
    assert second_page["kind"] == "track"
    assert second_page["page"] == 2


def test_probe_connection_is_uri_read_only_and_query_only(tmp_path: Path) -> None:
    database = tmp_path / "search.db"
    _create_search_database(database)
    before = database.read_bytes()

    conn = open_readonly_database(database)
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (2, 'No Write')")
    finally:
        conn.close()

    assert database.read_bytes() == before


def test_probe_records_sqlite_and_fts_runtime_capabilities() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        capabilities = sqlite_capabilities(conn)
    finally:
        conn.close()

    assert capabilities["sqlite_version"] == sqlite3.sqlite_version
    assert isinstance(capabilities["fts5_compile_option"], bool)
    assert isinstance(capabilities["fts5_runtime"], bool)
    assert isinstance(capabilities["fts5_trigram_runtime"], bool)
    assert isinstance(capabilities["capability_errors"], dict)


def test_candidate_probe_writes_aggregate_json_without_query_or_results(
    tmp_path: Path,
) -> None:
    database = tmp_path / "search.db"
    json_output = tmp_path / "report.json"
    _create_search_database(database)

    result = _run_probe(
        "--db-path",
        str(database),
        "--mode",
        "candidate",
        "--query",
        "vampire",
        "--warm-repeat",
        "1",
        "--json-output",
        str(json_output),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(json_output.read_text(encoding="utf-8"))
    serialized = json.dumps(report, ensure_ascii=False)
    assert report["status"] == "ok"
    assert report["database"]["open_mode"] == "ro"
    assert report["database"]["query_only"] is True
    assert report["database"]["table_counts"] == {
        "plays": 1,
        "tracks": 1,
        "albums": 1,
        "artists": 1,
    }
    assert report["queries"] == {
        "source": "explicit",
        "count": 1,
        "raw_text_included": False,
        "descriptors": [
            {
                "query_id": "q1",
                "length": 7,
                "source": "explicit",
                "query_class": "explicit",
                "kind": "all",
                "page": 1,
            }
        ],
    }
    sample = report["profiles"][0]["samples"][0]
    assert sample["status"] == "ok"
    assert sample["result_count"] == 1
    assert sample["result_counts"] == {"tracks": 1, "albums": 0, "artists": 0}
    assert "vampire" not in result.stdout.lower()
    assert "vampire" not in serialized.lower()
    assert "example artist" not in serialized.lower()
    assert report["privacy"] == {
        "raw_query_emitted": False,
        "result_content_emitted": False,
        "listening_history_rows_emitted": False,
    }


def test_context_mode_is_explicitly_unavailable_instead_of_faking_measurements(
    tmp_path: Path,
) -> None:
    database = tmp_path / "search.db"
    json_output = tmp_path / "context.json"
    _create_search_database(database)

    result = _run_probe(
        "--db-path",
        str(database),
        "--mode",
        "context",
        "--query",
        "private-query",
        "--warm-repeat",
        "2",
        "--json-output",
        str(json_output),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(json_output.read_text(encoding="utf-8"))
    assert report["status"] == "unavailable"
    assert report["profiles"][0]["status"] == "unavailable"
    assert report["profiles"][0]["samples"] == []
    assert report["profiles"][0]["unavailable_reason"] == CONTEXT_UNAVAILABLE_REASON
    assert "private-query" not in result.stdout
    assert "private-query" not in json.dumps(report)

    required = _run_probe(
        "--db-path",
        str(database),
        "--mode",
        "context",
        "--warm-repeat",
        "1",
        "--require-available",
    )
    assert required.returncode == 1


def test_cold_mode_uses_fresh_process_and_does_not_add_warm_samples(tmp_path: Path) -> None:
    database = tmp_path / "search.db"
    json_output = tmp_path / "cold.json"
    _create_search_database(database)

    result = _run_probe(
        "--db-path",
        str(database),
        "--mode",
        "candidate",
        "--query",
        "vampire",
        "--cold",
        "--json-output",
        str(json_output),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(json_output.read_text(encoding="utf-8"))
    assert report["configuration"]["warm_repeat"] == 0
    assert report["configuration"]["cold_repeat"] == 1
    assert len(report["profiles"]) == 1
    assert report["profiles"][0]["condition"] == "cold"
    assert report["profiles"][0]["strategy"] == "fresh_python_process_per_sample"
    assert report["profiles"][0]["os_page_cache_cleared"] is False
    assert report["profiles"][0]["samples"][0]["status"] == "ok"


def test_probe_summarizes_nearest_rank_percentile_and_fails_budgets() -> None:
    samples = [
        {"status": "ok", "elapsed_ms": value, "response_bytes": 1024}
        for value in (1.0, 2.0, 3.0, 100.0)
    ]
    summary = summarize_samples(samples)
    profile = {"condition": "warm", "status": "ok", "summary": summary}

    assert summary["p50_ms"] == 2.5
    assert summary["p95_ms"] == 100.0
    failures = evaluate_budgets(
        [profile],
        max_p50_ms=2.0,
        max_p95_ms=99.0,
        max_warm_p95_ms=90.0,
        max_cold_p95_ms=None,
        max_response_kib=0.5,
    )

    assert len(failures) == 4
    assert any("warm p50" in failure for failure in failures)
    assert any("warm p95" in failure for failure in failures)
    assert any("condition budget" in failure for failure in failures)
    assert any("response" in failure for failure in failures)


def test_probe_exits_nonzero_when_configured_budget_is_exceeded(tmp_path: Path) -> None:
    database = tmp_path / "search.db"
    _create_search_database(database)

    result = _run_probe(
        "--db-path",
        str(database),
        "--mode",
        "candidate",
        "--query",
        "vampire",
        "--warm-repeat",
        "1",
        "--max-p95-ms",
        "0",
    )

    assert result.returncode == 1
    assert "Budget failures:" in result.stdout
