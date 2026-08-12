from __future__ import annotations

import sqlite3
import threading
from types import SimpleNamespace

from backend.domains.yearly_review.artifact_cache import (
    has_persisted_artifact,
    load_persisted_artifact,
    store_persisted_artifact,
)
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services import yearly_review_service


def _artifact(value: int) -> dict:
    return {
        "report": {"schema_version": "yearly_review_v2", "value": value},
        "record_catalog": [{"value": value}],
    }


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


def test_persistent_artifact_round_trip_and_prunes_old_entries(tmp_path) -> None:
    cache_path = tmp_path / "yearly.db"
    for index in range(3):
        store_persisted_artifact(
            f"key-{index}",
            _artifact(index),
            year=2023 + index,
            filter_fingerprint="filters",
            source_db_revision=f"db-{index}",
            cache_path=cache_path,
            max_entries=2,
        )

    assert load_persisted_artifact("key-2", cache_path=cache_path) == _artifact(2)
    assert load_persisted_artifact("key-1", cache_path=cache_path) == _artifact(1)
    assert load_persisted_artifact("key-0", cache_path=cache_path) is None
    assert has_persisted_artifact("key-2", cache_path=cache_path)
    assert not has_persisted_artifact("key-0", cache_path=cache_path)


def test_corrupt_persistent_artifact_is_deleted_and_treated_as_miss(tmp_path) -> None:
    cache_path = tmp_path / "yearly.db"
    store_persisted_artifact(
        "broken",
        _artifact(1),
        year=2025,
        filter_fingerprint="filters",
        source_db_revision="db",
        cache_path=cache_path,
    )
    conn = sqlite3.connect(cache_path)
    conn.execute(
        "UPDATE yearly_review_artifacts SET payload=?, uncompressed_bytes=10 WHERE cache_key=?",
        (b"not-zlib", "broken"),
    )
    conn.commit()
    conn.close()

    assert load_persisted_artifact("broken", cache_path=cache_path) is None
    conn = sqlite3.connect(cache_path)
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM yearly_review_artifacts WHERE cache_key='broken'"
        ).fetchone()[0]
        == 0
    )
    conn.close()


def test_service_uses_persistent_hit_without_rebuilding(monkeypatch) -> None:
    yearly_review_service._build_cached_artifact.cache_clear()
    expected = _artifact(7)
    monkeypatch.setattr(
        yearly_review_service,
        "load_persisted_artifact",
        lambda _key: expected,
    )
    monkeypatch.setattr(
        yearly_review_service,
        "build_yearly_review_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not rebuild")),
    )

    result = yearly_review_service._build_cached_artifact(
        2025,
        _context().model_dump_json(),
        "cache-key",
        "db-revision",
    )

    assert result == expected
    yearly_review_service._build_cached_artifact.cache_clear()


def test_recompute_bypass_refreshes_persistent_artifact(monkeypatch) -> None:
    yearly_review_service._build_cached_artifact.cache_clear()
    stored = []

    class Report:
        def model_dump(self, *, mode):
            assert mode == "json"
            return {"schema_version": "yearly_review_v2", "value": 9}

    monkeypatch.setattr(
        yearly_review_service,
        "load_persisted_artifact",
        lambda _key: _artifact(1),
    )
    monkeypatch.setattr(
        yearly_review_service,
        "get_db",
        lambda readonly=True: SimpleNamespace(close=lambda: None),
    )
    monkeypatch.setattr(
        yearly_review_service,
        "build_yearly_review_artifact",
        lambda *_args, **_kwargs: SimpleNamespace(
            report=Report(),
            record_catalog=[{"value": 9}],
        ),
    )
    monkeypatch.setattr(
        yearly_review_service,
        "store_persisted_artifact",
        lambda *args, **kwargs: stored.append((args, kwargs)),
    )

    with yearly_review_service.bypass_yearly_review_persistent_cache():
        result = yearly_review_service._build_cached_artifact(
            2025,
            _context().model_dump_json(),
            "cache-key",
            "db-revision",
        )

    assert result["report"]["value"] == 9
    assert stored[0][1]["source_db_revision"] == "db-revision"
    yearly_review_service._build_cached_artifact.cache_clear()


def test_background_prewarm_is_deduplicated(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def blocking_prewarm():
        nonlocal calls
        calls += 1
        started.set()
        release.wait(timeout=2)
        return 2026

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        yearly_review_service,
        "prewarm_latest_yearly_review",
        blocking_prewarm,
    )
    yearly_review_service._prewarm_thread = None

    first = yearly_review_service.start_yearly_review_prewarm_thread()
    assert started.wait(timeout=1)
    second = yearly_review_service.start_yearly_review_prewarm_thread()

    assert first is second
    assert calls == 1
    release.set()
    first.join(timeout=2)
