"""Portable rank installation touches only its bounded Analysis sidecar."""

from __future__ import annotations

import copy
import sqlite3
from contextlib import closing

import pytest

from backend.core import config, db
from backend.services import analysis_snapshot_store as store
from backend.services import versus_rank_context_service as ranks
from backend.services import versus_rank_publication as publication
from backend.tests.unit import test_versus_rank_context

isolated = test_versus_rank_context.isolated
base_isolated = test_versus_rank_context.base_isolated
pytestmark = pytest.mark.unit


@pytest.fixture
def portable(isolated, monkeypatch):
    source = db.get_db(readonly=True)
    try:
        for params in ranks.default_configurations(source):
            ranks.ensure(source, params)
        bundle = publication.export_bundle(source)
        copied = isolated[1] / "target.db"
        with closing(sqlite3.connect(copied)) as target:
            source.backup(target)
            # A standalone Online Backup has no live WAL writer. Make this
            # test-owned copy readable through SQLite's strict mode=ro URI.
            target.execute("PRAGMA journal_mode=DELETE")
    finally:
        source.close()
    monkeypatch.setattr(
        config, "SPOTIFY_STATS_ANALYSIS_CACHE_PATH", str(isolated[1] / "target-analysis.db")
    )
    target = sqlite3.connect(f"{copied.as_uri()}?mode=ro", uri=True)
    target.row_factory = sqlite3.Row
    try:
        yield target, bundle, copied
    finally:
        target.close()
        ranks._read_cached.cache_clear()


def test_install_four_default_contexts_rebases_only_lineage_keys(portable):
    conn, bundle, copied = portable
    before = copied.read_bytes()
    result = publication.install_bundle(conn, bundle)
    assert result["installed"] == 4
    assert copied.read_bytes() == before
    for item in bundle["publications"]:
        params, key, metadata, family = ranks.request_context(conn, item["filters"])
        assert key != item["origin_request_key"]
        assert metadata["source_revision"] == item["source_revision"]
        payload, snapshot = ranks.read(conn, params)
        assert payload == item["payload"]
        assert snapshot["request_key"] == key
    with sqlite3.connect(store.path()) as cache:
        assert cache.execute(
            "SELECT family,COUNT(*) FROM analysis_snapshots GROUP BY family"
        ).fetchall() == [(ranks.FAMILY, 4)]


@pytest.mark.parametrize(
    "mutation",
    ["version", "family", "revision", "filters", "digest", "shape", "dates", "duplicate", "extra"],
)
def test_install_rejects_invalid_manifest_before_any_sidecar_write(portable, mutation):
    conn, original, _ = portable
    bundle = copy.deepcopy(original)
    item = bundle["publications"][0]
    if mutation == "version":
        item["builder_version"] = "unknown"
    elif mutation == "family":
        item["family"] = "analysis_records"
    elif mutation == "revision":
        item["source_revision"] = "stale"
    elif mutation == "filters":
        item["filters"]["min_ms"] = str(item["filters"]["min_ms"])
    elif mutation == "digest":
        item["payload_digest"] = "bad"
    elif mutation == "shape":
        item["payload"]["ranks"]["track"].pop("last_4_weeks")
        item["payload_digest"] = store.digest(item["payload"])
    elif mutation == "dates":
        item["payload"]["periods"]["lifetime"]["start_date"] = "2099-99-99"
        item["payload_digest"] = store.digest(item["payload"])
    elif mutation == "duplicate":
        bundle["publications"][1] = copy.deepcopy(item)
    elif mutation == "extra":
        item["payload"]["unexpected"] = 1
        item["payload_digest"] = store.digest(item["payload"])
    with pytest.raises(ValueError):
        publication.install_bundle(conn, bundle)
    assert not store.path().exists()


def test_install_rolls_back_entire_batch_if_source_changes_before_commit(portable, monkeypatch):
    conn, bundle, copied = portable
    store.publish("analysis_stats", "existing", "old", "v", {"preserve": True})
    before = store.path().read_bytes()
    original = store.publish_many

    def drifting(entries, *, before_commit):
        def mutate_then_check():
            with sqlite3.connect(copied) as writer:
                writer.execute(
                    "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
                )
            before_commit()

        return original(entries, before_commit=mutate_then_check)

    monkeypatch.setattr(store, "publish_many", drifting)
    with pytest.raises(ValueError, match="source or filters"):
        publication.install_bundle(conn, bundle)
    assert store.path().read_bytes() == before
    with sqlite3.connect(store.path()) as cache:
        assert cache.execute("SELECT family FROM analysis_snapshots").fetchall() == [
            ("analysis_stats",)
        ]


def test_install_never_calls_builder_and_public_guard_refuses(portable, monkeypatch):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )

    conn, bundle, _ = portable
    monkeypatch.setattr(
        ranks, "build_payload", lambda *a: pytest.fail("installation built full ranks")
    )
    monkeypatch.setattr(
        ranks, "enqueue_defaults", lambda *a, **kw: pytest.fail("installation queued work")
    )
    token = set_public_readonly_db_guard(True)
    try:
        with pytest.raises(PermissionError):
            publication.install_bundle(conn, bundle)
    finally:
        reset_public_readonly_db_guard(token)
    assert publication.install_bundle(conn, bundle)["installed"] == 4


def test_cli_build_export_install_opens_source_readonly(isolated, monkeypatch, capsys):
    from scripts.versus_rank_publication import main

    copied = isolated[1] / "cli-copy.db"
    with closing(db.get_db(readonly=True)) as source, closing(sqlite3.connect(copied)) as target:
        source.backup(target)
    cache = isolated[1] / "cli-analysis.db"
    manifest = isolated[1] / "manifest.json"
    before = copied.read_bytes()
    assert (
        main(
            [
                "build",
                "--closed-source",
                "--source-db",
                str(copied),
                "--analysis-cache",
                str(cache),
                "--manifest",
                str(manifest),
            ]
        )
        == 0
    )
    assert copied.read_bytes() == before
    assert '"exported": 4' in capsys.readouterr().out
    assert (
        main(
            [
                "export",
                "--closed-source",
                "--source-db",
                str(copied),
                "--analysis-cache",
                str(cache),
                "--manifest",
                str(manifest),
            ]
        )
        == 0
    )
    target_cache = isolated[1] / "install-analysis.db"
    assert (
        main(
            [
                "install",
                "--source-db",
                str(isolated[0]),
                "--analysis-cache",
                str(target_cache),
                "--manifest",
                str(manifest),
            ]
        )
        == 0
    )
    assert '"installed": 4' in capsys.readouterr().out


def test_entity_rank_status_matches_api_contract(isolated):
    conn = db.get_db(readonly=True)
    try:
        ranks.ensure(conn)
        track = conn.execute(
            "SELECT l1_id FROM track_l1_identities ORDER BY l1_id LIMIT 1"
        ).fetchone()[0]
        entities = ranks.read_personal_ranks(conn, "track", [track, 999999999], {})["entities"]
        assert entities[0]["status"] in ("found", "empty")
        assert entities[1]["status"] == "unavailable"
        assert entities[1]["found"] is False
        assert entities[1]["ranks"] is None
    finally:
        conn.close()


def test_install_refuses_source_database_as_sidecar_including_symlink(portable, monkeypatch):
    conn, bundle, copied = portable
    before = copied.read_bytes()
    alias = copied.with_name("source-symlink.db")
    alias.symlink_to(copied)
    monkeypatch.setattr(config, "SPOTIFY_STATS_ANALYSIS_CACHE_PATH", str(alias))
    with pytest.raises(ValueError, match="separate from"):
        publication.install_bundle(conn, bundle)
    assert copied.read_bytes() == before


def test_release_sha_binding_and_four_default_inventory_are_required(portable):
    conn, original, _ = portable
    bundle = copy.deepcopy(original)
    bundle["release_sha"] = "abcdef12"
    with pytest.raises(ValueError, match="target release SHA"):
        publication.install_bundle(
            conn, bundle, expected_release_sha="1234abcd", require_defaults=True
        )
    subset = {**bundle, "publications": bundle["publications"][:1]}
    with pytest.raises(ValueError, match="all four"):
        publication.install_bundle(
            conn, subset, expected_release_sha="abcdef12", require_defaults=True
        )
    assert not store.path().exists()
    assert (
        publication.install_bundle(
            conn, bundle, expected_release_sha="abcdef12", require_defaults=True
        )["installed"]
        == 4
    )


def test_cli_closed_wal_header_exports_and_installs_without_source_writes(isolated, monkeypatch):
    from scripts.versus_rank_publication import main

    source = isolated[1] / "closed-source.db"
    with closing(db.get_db(readonly=True)) as origin, closing(sqlite3.connect(source)) as copied:
        origin.backup(copied)
    # The source retains a WAL journal header but is now closed and has no WAL.
    assert not source.with_name(source.name + "-wal").exists()
    original_source = source.read_bytes()
    original_cache = isolated[1] / "closed-built-analysis.db"
    manifest = isolated[1] / "closed-export.json"
    assert (
        main(
            [
                "build",
                "--closed-source",
                "--source-db",
                str(source),
                "--analysis-cache",
                str(original_cache),
                "--manifest",
                str(manifest),
                "--release-sha",
                "abcdef12",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "export",
                "--closed-source",
                "--source-db",
                str(source),
                "--analysis-cache",
                str(original_cache),
                "--manifest",
                str(manifest),
                "--release-sha",
                "abcdef12",
            ]
        )
        == 0
    )
    output = isolated[1] / "closed-install.db"
    assert (
        main(
            [
                "install",
                "--closed-source",
                "--source-db",
                str(source),
                "--analysis-cache",
                str(output),
                "--manifest",
                str(manifest),
                "--release-sha",
                "abcdef12",
                "--require-defaults",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "verify",
                "--closed-source",
                "--source-db",
                str(source),
                "--analysis-cache",
                str(output),
            ]
        )
        == 0
    )
    assert source.read_bytes() == original_source
    assert not source.with_name(source.name + "-wal").exists()
    assert not source.with_name(source.name + "-shm").exists()


def test_cli_closed_source_rejects_wal_and_fences_file_change_before_commit(portable, monkeypatch):
    import json

    from scripts.versus_rank_publication import main

    conn, bundle, copied = portable
    conn.close()
    manifest = copied.with_name("closed-manifest.json")
    manifest.write_text(json.dumps(bundle))
    output = copied.with_name("closed-analysis.db")
    wal = copied.with_name(copied.name + "-wal")
    wal.write_bytes(b"")
    arguments = [
        "install",
        "--closed-source",
        "--source-db",
        str(copied),
        "--analysis-cache",
        str(output),
        "--manifest",
        str(manifest),
    ]
    with pytest.raises(ValueError, match="no WAL"):
        main(arguments)
    wal.unlink()
    original = store.publish_many

    def drifting(entries, *, before_commit):
        def mutate_then_check():
            with sqlite3.connect(copied) as writer:
                writer.execute(
                    "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
                )
            before_commit()

        return original(entries, before_commit=mutate_then_check)

    monkeypatch.setattr(store, "publish_many", drifting)
    with pytest.raises(ValueError, match="Closed personal rank source changed"):
        main(arguments)
    with sqlite3.connect(output) as cache:
        assert cache.execute("SELECT COUNT(*) FROM analysis_snapshots").fetchone()[0] == 0
