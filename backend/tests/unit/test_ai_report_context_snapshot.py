from __future__ import annotations

import hashlib
import sqlite3

import pytest

from backend.core.access_surface import (
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
)
from backend.domains.ai_reports import context_snapshot


def _snapshot(value: int) -> dict:
    return {
        "schema_version": "yearly_agent_context_v1",
        "reporting_period": {"year": 2025},
        "facts": {"top_track": "good 4 u", "plays": value},
        "limitations": [],
    }


def _store(cache_path, cache_key: str, value: int, *, max_entries: int = 32) -> None:
    context_snapshot.store_context_snapshot(
        cache_key,
        _snapshot(value),
        year=2025,
        filter_fingerprint=f"filters-{value}",
        source_db_revision=f"db-{value}",
        builder_version="context-v1",
        build_elapsed_ms=1234 + value,
        cache_path=cache_path,
        max_entries=max_entries,
    )


def test_context_snapshot_round_trip_persists_ready_metadata_and_checksum(tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    _store(cache_path, "exact-key", 7)

    assert context_snapshot.load_context_snapshot("exact-key", cache_path=cache_path) == _snapshot(
        7
    )
    assert context_snapshot.has_context_snapshot("exact-key", cache_path=cache_path)

    conn = sqlite3.connect(cache_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM yearly_agent_context_snapshots WHERE cache_key='exact-key'"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["report_year"] == 2025
    assert row["filter_fingerprint"] == "filters-7"
    assert row["source_db_revision"] == "db-7"
    assert row["builder_version"] == "context-v1"
    assert row["status"] == "ready"
    assert row["build_elapsed_ms"] == 1241
    assert row["created_at"]
    assert row["updated_at"]
    assert row["uncompressed_bytes"] > 0
    assert len(row["payload"]) < row["uncompressed_bytes"]
    assert len(row["payload_checksum"]) == hashlib.sha256().digest_size * 2


def test_store_prunes_oldest_ready_snapshots_and_delete_is_exact(tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    for index in range(3):
        _store(cache_path, f"key-{index}", index, max_entries=2)

    assert context_snapshot.load_context_snapshot("key-0", cache_path=cache_path) is None
    assert context_snapshot.has_context_snapshot("key-1", cache_path=cache_path)
    assert context_snapshot.has_context_snapshot("key-2", cache_path=cache_path)
    assert context_snapshot.delete_context_snapshot("key-1", cache_path=cache_path)
    assert not context_snapshot.delete_context_snapshot("key-1", cache_path=cache_path)
    assert context_snapshot.load_context_snapshot("key-2", cache_path=cache_path) == _snapshot(2)


def test_explicit_prune_preserves_newest_ready_snapshot(tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    for index in range(3):
        _store(cache_path, f"key-{index}", index)

    assert context_snapshot.prune_context_snapshots(max_entries=1, cache_path=cache_path) == 2
    assert context_snapshot.has_context_snapshot("key-2", cache_path=cache_path)
    assert not context_snapshot.has_context_snapshot("key-1", cache_path=cache_path)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("payload", b"not-zlib"),
        ("payload_checksum", "0" * 64),
        ("uncompressed_bytes", -1),
    ],
)
def test_corrupt_context_snapshot_is_deleted_and_treated_as_miss(
    tmp_path, column: str, value: object
) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    _store(cache_path, "broken", 1)
    conn = sqlite3.connect(cache_path)
    conn.execute(
        f"UPDATE yearly_agent_context_snapshots SET {column}=? WHERE cache_key='broken'",
        (value,),
    )
    conn.commit()
    conn.close()

    assert context_snapshot.load_context_snapshot("broken", cache_path=cache_path) is None
    conn = sqlite3.connect(cache_path)
    remaining = conn.execute(
        "SELECT COUNT(*) FROM yearly_agent_context_snapshots WHERE cache_key='broken'"
    ).fetchone()[0]
    conn.close()
    assert remaining == 0


def test_only_ready_snapshot_is_visible(tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    _store(cache_path, "building", 1)
    conn = sqlite3.connect(cache_path)
    conn.execute(
        "UPDATE yearly_agent_context_snapshots SET status='building' WHERE cache_key='building'"
    )
    conn.commit()
    conn.close()

    assert not context_snapshot.has_context_snapshot("building", cache_path=cache_path)
    assert context_snapshot.load_context_snapshot("building", cache_path=cache_path) is None


def test_failed_ready_publication_rolls_back_to_previous_snapshot(tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    _store(cache_path, "same-key", 1)
    conn = sqlite3.connect(cache_path)
    conn.execute(
        """CREATE TRIGGER reject_ready_publication
           BEFORE UPDATE OF status ON yearly_agent_context_snapshots
           WHEN NEW.status = 'ready'
           BEGIN
               SELECT RAISE(ABORT, 'injected publication failure');
           END"""
    )
    conn.commit()
    conn.close()

    with pytest.raises(sqlite3.IntegrityError, match="injected publication failure"):
        _store(cache_path, "same-key", 2)

    conn = sqlite3.connect(cache_path)
    conn.execute("DROP TRIGGER reject_ready_publication")
    conn.commit()
    conn.close()
    assert context_snapshot.load_context_snapshot("same-key", cache_path=cache_path) == _snapshot(1)


def test_public_readonly_guard_missing_and_corrupt_sidecars_are_safe_misses(tmp_path) -> None:
    missing_path = tmp_path / "missing.db"
    corrupt_path = tmp_path / "corrupt.db"
    corrupt_path.write_bytes(b"not a sqlite database")
    token = set_public_readonly_db_guard(True)
    try:
        assert context_snapshot.load_context_snapshot("missing", cache_path=missing_path) is None
        assert not context_snapshot.has_context_snapshot("missing", cache_path=missing_path)
        assert context_snapshot.load_context_snapshot("broken", cache_path=corrupt_path) is None
        assert not context_snapshot.has_context_snapshot("broken", cache_path=corrupt_path)
        assert not context_snapshot.delete_context_snapshot("broken", cache_path=corrupt_path)
        assert context_snapshot.prune_context_snapshots(cache_path=corrupt_path) == 0
        with pytest.raises(PermissionError, match="public read-only"):
            context_snapshot.store_context_snapshot(
                "blocked",
                _snapshot(1),
                year=2025,
                filter_fingerprint="filters",
                source_db_revision="db",
                builder_version="context-v1",
                build_elapsed_ms=1,
                cache_path=missing_path,
            )
    finally:
        reset_public_readonly_db_guard(token)

    assert not missing_path.exists()
    assert corrupt_path.read_bytes() == b"not a sqlite database"


def test_public_readonly_guard_does_not_delete_corrupt_snapshot(tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    _store(cache_path, "broken-public", 1)
    conn = sqlite3.connect(cache_path)
    conn.execute(
        """UPDATE yearly_agent_context_snapshots
           SET payload_checksum=? WHERE cache_key='broken-public'""",
        ("0" * 64,),
    )
    conn.commit()
    conn.close()

    token = set_public_readonly_db_guard(True)
    try:
        assert (
            context_snapshot.load_context_snapshot("broken-public", cache_path=cache_path) is None
        )
    finally:
        reset_public_readonly_db_guard(token)

    conn = sqlite3.connect(cache_path)
    remaining = conn.execute(
        """SELECT COUNT(*) FROM yearly_agent_context_snapshots
           WHERE cache_key='broken-public'"""
    ).fetchone()[0]
    conn.close()
    assert remaining == 1


def test_store_rejects_empty_key_and_oversized_payload(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "yearly_review_cache.db"
    with pytest.raises(ValueError, match="cache key"):
        _store(cache_path, "", 1)

    monkeypatch.setattr(context_snapshot, "MAX_UNCOMPRESSED_BYTES", 8)
    with pytest.raises(ValueError, match="size limit"):
        _store(cache_path, "too-large", 1)
    assert not cache_path.exists()
