from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from backend.core.migrations import MIGRATIONS
from backend.domains.music_search.context import (
    MUSIC_SEARCH_CHART_BUILDER_VERSION,
    MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION,
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
)
from scripts import rebuild_music_search_derived_data as rebuild_script

pytestmark = pytest.mark.unit


def _raw_variants(*, failed_key: tuple[int, bool] | None = None) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for merge_level in (1, 2, 3):
        for dynamic_threshold in (False, True):
            key = (merge_level, dynamic_threshold)
            variants.append(
                {
                    "merge_level": merge_level,
                    "dynamic_threshold": dynamic_threshold,
                    "status": "failed" if key == failed_key else "ready",
                    "filter_fingerprint": f"fingerprint-{merge_level}-{int(dynamic_threshold)}",
                    "entity_count": merge_level * 10 + int(dynamic_threshold),
                    "duration_ms": merge_level + 0.125,
                    "error_type": "PrivateEntityMustNotLeak" if key == failed_key else None,
                    "raw_query": "private-query",
                    "entities": ["Private Artist", "Private Track"],
                }
            )
    return variants


def _raw_report(
    *,
    variants: list[dict[str, Any]] | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "ready",
        "index": index,
        "debug": {"raw_query": "private-query", "entity": "Private Artist"},
        "snapshot_set": {
            "status": "ready",
            "semantic_base_key": "semantic-base-test",
            "ready_count": 6,
            "failed_count": 0,
            "duration_ms": 42.75,
            "variants": variants if variants is not None else _raw_variants(),
        },
    }


def _success_report(
    raw_report: dict[str, Any],
    *,
    require_all_ready: bool = True,
    prior_inventory: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return rebuild_script._success_report(
        raw_report,
        require_all_ready=require_all_ready,
        prior_inventory=prior_inventory or {},
        base_counts={
            "row_count": 6,
            "unique_fingerprint_count": 6,
            "duplicate_fingerprint_count": 0,
        },
        migration={
            "applied_version": 34,
            "target_version": 34,
            "applied_count": 34,
            "expected_count": 34,
            "missing_count": 0,
            "up_to_date": True,
        },
        elapsed_ms=57.25,
        storage={
            "before": {
                "database_bytes": 100,
                "wal_bytes": 20,
                "combined_bytes": 120,
            },
            "after": {
                "database_bytes": 140,
                "wal_bytes": 30,
                "combined_bytes": 170,
            },
            "delta": {
                "database_bytes": 40,
                "wal_bytes": 10,
                "combined_bytes": 50,
            },
        },
    )


def _create_gate_database(path: Path) -> None:
    target_version = max(version for version, _name, _fn in MIGRATIONS)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE music_search_snapshot_meta (
                filter_fingerprint TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                builder_version TEXT,
                semantic_base_key TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
            [(version, name) for version, name, _fn in MIGRATIONS if version <= target_version],
        )
        conn.commit()
    finally:
        conn.close()


def _publish_fake_snapshot_set(conn: sqlite3.Connection) -> dict[str, Any]:
    variants = _raw_variants()
    conn.executemany(
        """INSERT OR REPLACE INTO music_search_snapshot_meta(
               filter_fingerprint, status, builder_version, semantic_base_key
           ) VALUES (?, ?, ?, ?)""",
        [
            (
                variant["filter_fingerprint"],
                variant["status"],
                MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                "semantic-base-test",
            )
            for variant in variants
        ],
    )
    conn.commit()
    return _raw_report(variants=variants)


def test_success_report_is_complete_and_privacy_safe(monkeypatch) -> None:
    monkeypatch.setattr(rebuild_script, "_peak_rss_bytes", lambda: 128 * 1024 * 1024)

    report = _success_report(_raw_report())
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "ready"
    assert report["semantic_base_key"] == "semantic-base-test"
    assert report["builder"] == {
        "filter_fingerprint_version": MUSIC_SEARCH_FILTER_FINGERPRINT_VERSION,
        "snapshot_builder_version": MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
        "chart_builder_version": MUSIC_SEARCH_CHART_BUILDER_VERSION,
    }
    assert report["migration"] == {
        "applied_version": 34,
        "target_version": 34,
        "applied_count": 34,
        "expected_count": 34,
        "missing_count": 0,
        "up_to_date": True,
    }
    assert report["snapshot_elapsed_ms"] == 42.75
    assert report["total_elapsed_ms"] == 57.25
    assert report["resources"]["peak_rss_bytes"] == 128 * 1024 * 1024
    assert report["resources"]["peak_rss_mib"] == 128.0
    assert report["storage"]["delta"]["combined_bytes"] == 50
    assert report["gate"]["all_six_ready"] is True
    assert report["gate"]["passed"] is True
    assert len(report["variants"]) == 6
    assert set(report["variants"][0]) == {
        "merge_level",
        "dynamic_threshold",
        "status",
        "fingerprint",
        "entity_count",
        "elapsed_ms",
    }
    assert "private-query" not in serialized
    assert "Private Artist" not in serialized
    assert "Private Track" not in serialized
    assert report["privacy"] == rebuild_script.PRIVACY_REPORT


def test_any_reported_non_ready_variant_fails_even_without_strict_flag() -> None:
    report = _success_report(
        _raw_report(variants=_raw_variants(failed_key=(3, False))),
        require_all_ready=False,
    )

    assert report["gate"]["reported_variant_count"] == 6
    assert report["gate"]["ready_variant_count"] == 5
    assert report["gate"]["all_reported_ready"] is False
    assert report["gate"]["passed"] is False
    assert report["variants"][4]["failure_type"] == "PrivateEntityMustNotLeak"


def test_require_all_ready_rejects_an_incomplete_variant_set() -> None:
    variants = [
        _raw_variant for _raw_variant in _raw_variants() if _raw_variant["merge_level"] != 3
    ]

    informational = _success_report(
        _raw_report(variants=variants),
        require_all_ready=False,
    )
    strict = _success_report(
        _raw_report(variants=variants),
        require_all_ready=True,
    )

    assert informational["gate"]["all_reported_ready"] is True
    assert informational["gate"]["exact_variant_set"] is False
    assert informational["gate"]["passed"] is True
    assert strict["gate"]["passed"] is False


def test_snapshot_only_second_run_is_reported_as_idempotent_revalidation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "production-copy.db"
    _create_gate_database(database)
    monkeypatch.setattr(rebuild_script.db_mod, "DB_PATH", str(database))
    monkeypatch.setattr(rebuild_script, "run_migrations", lambda: None)
    monkeypatch.setattr(
        rebuild_script,
        "get_db",
        lambda readonly=False: sqlite3.connect(database),
    )
    monkeypatch.setattr(rebuild_script, "_peak_rss_bytes", lambda: 96 * 1024 * 1024)
    monkeypatch.setattr(
        rebuild_script,
        "rebuild_current_music_search_derived_data",
        lambda conn, rebuild_documents=False: _publish_fake_snapshot_set(conn),
    )
    argv = [
        "--db-path",
        str(database),
        "--snapshot-only",
        "--json",
        "--require-all-ready",
    ]

    assert rebuild_script.main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["idempotency"]["classification"] == ("rebuilt_snapshot_set_on_existing_documents")
    assert first["idempotency"]["repeat_safe"] is True

    assert rebuild_script.main(argv) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["idempotency"] == {
        "classification": "revalidated_existing_snapshot_set",
        "documents_rebuilt": False,
        "documents_reused": True,
        "preexisting_ready_variant_count": 6,
        "all_variants_preexisting_ready": True,
        "snapshot_rows_for_semantic_base": 6,
        "unique_fingerprint_count": 6,
        "duplicate_fingerprint_count": 0,
        "repeat_safe": True,
    }
    assert second["gate"]["passed"] is True


def test_main_returns_nonzero_for_any_non_ready_variant_without_strict_flag(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "partial-copy.db"
    _create_gate_database(database)
    monkeypatch.setattr(rebuild_script.db_mod, "DB_PATH", str(database))
    monkeypatch.setattr(rebuild_script, "run_migrations", lambda: None)
    monkeypatch.setattr(
        rebuild_script,
        "get_db",
        lambda readonly=False: sqlite3.connect(database),
    )
    monkeypatch.setattr(rebuild_script, "_peak_rss_bytes", lambda: 64 * 1024 * 1024)

    def publish_partial(conn: sqlite3.Connection, rebuild_documents: bool) -> dict[str, Any]:
        variants = _raw_variants(failed_key=(2, True))
        conn.executemany(
            """INSERT OR REPLACE INTO music_search_snapshot_meta(
                   filter_fingerprint, status, builder_version, semantic_base_key
               ) VALUES (?, ?, ?, ?)""",
            [
                (
                    variant["filter_fingerprint"],
                    variant["status"],
                    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                    "semantic-base-test",
                )
                for variant in variants
            ],
        )
        conn.commit()
        return _raw_report(variants=variants)

    monkeypatch.setattr(
        rebuild_script,
        "rebuild_current_music_search_derived_data",
        publish_partial,
    )

    exit_code = rebuild_script.main(["--db-path", str(database), "--snapshot-only", "--json"])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert report["gate"]["require_all_ready"] is False
    assert report["gate"]["ready_variant_count"] == 5
    assert report["gate"]["passed"] is False


def test_json_failure_does_not_emit_exception_message_content(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "failed-copy.db"
    _create_gate_database(database)
    monkeypatch.setattr(rebuild_script.db_mod, "DB_PATH", str(database))
    monkeypatch.setattr(rebuild_script, "run_migrations", lambda: None)
    monkeypatch.setattr(
        rebuild_script,
        "get_db",
        lambda readonly=False: sqlite3.connect(database),
    )

    def fail_rebuild(conn: sqlite3.Connection, rebuild_documents: bool) -> dict[str, Any]:
        raise RuntimeError("private-query mentions Private Artist")

    monkeypatch.setattr(
        rebuild_script,
        "rebuild_current_music_search_derived_data",
        fail_rebuild,
    )

    exit_code = rebuild_script.main(["--db-path", str(database), "--json"])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert report["error"] == {
        "stage": "derived_rebuild",
        "type": "RuntimeError",
        "message_emitted": False,
    }
    assert "private-query" not in output
    assert "Private Artist" not in output


def test_storage_report_tracks_database_and_wal_deltas(tmp_path: Path) -> None:
    database = tmp_path / "copy.db"
    wal = Path(f"{database}-wal")
    database.write_bytes(b"d" * 10)
    wal.write_bytes(b"w" * 4)
    before = rebuild_script._storage_sizes(database)

    database.write_bytes(b"d" * 16)
    wal.unlink()
    after = rebuild_script._storage_sizes(database)

    assert rebuild_script._storage_report(before, after) == {
        "before": {"database_bytes": 10, "wal_bytes": 4, "combined_bytes": 14},
        "after": {"database_bytes": 16, "wal_bytes": 0, "combined_bytes": 16},
        "delta": {"database_bytes": 6, "wal_bytes": -4, "combined_bytes": 2},
    }
