from __future__ import annotations

import json
import sqlite3

import pytest

from backend.core.access_surface import reset_public_readonly_db_guard, set_public_readonly_db_guard
from scripts import prepare_billboard_publications as maintenance

pytestmark = pytest.mark.unit


def test_factual_dependencies_normalize_nested_revision_tuples(monkeypatch):
    monkeypatch.setattr(
        maintenance.cache,
        "_dependency_state",
        lambda *_: {"database_path": "copy", "credits": (("albums", "revision", 3),)},
    )
    assert maintenance._dependencies("weekly", {}) == {"credits": [["albums", "revision", 3]]}


def test_portable_analysis_revision_retains_facts_while_rebinding_file_namespace(monkeypatch):
    state = {"database_path": "source", "billboard_revision_state": [3, "opaque-source-inode"]}
    monkeypatch.setattr(maintenance.cache, "_dependency_state", lambda *_: dict(state))
    vector = {"plays": ["stable-epoch", 7], "release_date_policy": "date-v2"}
    monkeypatch.setattr(maintenance, "_analysis_dependencies", lambda: dict(vector))
    before = maintenance._dependencies("weekly", {})
    state.update(database_path="target", billboard_revision_state=[3, "opaque-target-inode"])
    assert maintenance._dependencies("weekly", {}) == before
    vector["plays"] = ["stable-epoch", 8]
    assert maintenance._dependencies("weekly", {}) != before


@pytest.mark.parametrize("corrupt", [False, True])
def test_exact_verification_does_not_create_missing_sidecar_or_delete_corruption(
    tmp_path, monkeypatch, corrupt
):
    path = tmp_path / "cache.db"
    monkeypatch.setattr(maintenance.cache, "BILLBOARD_CACHE_PATH", str(path))
    context = {
        "family": "full_data",
        "cache_key": "exact",
        "request_key": "request",
        "source_revision": "source",
        "builder_version": maintenance.cache.BILLBOARD_CACHE_BUILDER_VERSION,
    }
    monkeypatch.setattr(maintenance.cache, "build_cache_context", lambda *_: context)
    if corrupt:
        maintenance.cache.store_persisted_snapshot(context, {"value": 1})
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE billboard_snapshots SET payload=?", (b"corrupt",))
    with pytest.raises(RuntimeError, match="unavailable"):
        maintenance._read_exact("full_data", {})
    if corrupt:
        with sqlite3.connect(path) as conn:
            assert (
                conn.execute("SELECT payload FROM billboard_snapshots").fetchone()[0] == b"corrupt"
            )
    else:
        assert not path.exists()


@pytest.fixture
def publication(tmp_path, monkeypatch):
    filters = {"merge_level": 2, "dynamic_threshold": True, "min_ms": 30000}
    fence = {"lineage": "source-a", "governance": "g1"}
    monkeypatch.setattr(maintenance, "configured_billboard_filters", lambda _: dict(filters))
    monkeypatch.setattr(maintenance, "source_fence", lambda _: dict(fence))
    monkeypatch.setattr(maintenance, "_dependencies", lambda *_: {"revision": "source-a"})
    monkeypatch.setattr(
        maintenance,
        "_read_exact",
        lambda family, params: {"meta": {"available_years": [2026, 2024]}, "family": family},
    )
    monkeypatch.setattr(maintenance.cache, "BILLBOARD_CACHE_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(
        maintenance.cache,
        "build_cache_context",
        lambda family, params: {
            "family": family,
            "cache_key": maintenance._digest(["target-path", family, params]),
            "request_key": maintenance._digest([family, params]),
            "source_revision": "target-path-source-a",
            "builder_version": maintenance.cache.BILLBOARD_CACHE_BUILDER_VERSION,
        },
    )
    path = tmp_path / "manifest.json"
    result = maintenance.export_manifest(None, path)
    assert result["targets"] == 36
    return path, fence


def test_transfer_rebinds_target_namespace_and_preserves_factual_fence(publication, monkeypatch):
    path, _ = publication
    maintenance.cache.store_persisted_snapshot(
        {
            "family": "full_data",
            "cache_key": "old-v3",
            "request_key": "old-v3-request",
            "source_revision": "old-v3-source",
            "builder_version": "billboard_persistent_snapshot_release_precision_v3_legacy_year",
        },
        {"old": "preserved"},
    )
    # Verify using real exact sidecar reads after import, not the export fixture.
    monkeypatch.setattr(
        maintenance,
        "_read_exact",
        lambda family, params: maintenance.cache.load_persisted_snapshot(
            maintenance.cache.build_cache_context(family, params), allow_lkg=False
        ),
    )
    result = maintenance.import_manifest(None, path)
    assert result["status"] == "imported" and result["targets"] == 36
    conn = maintenance.cache._connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM billboard_snapshots").fetchone()[0] == 37
        assert {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT source_revision FROM billboard_snapshots WHERE cache_key!='old-v3'"
            )
        } == {"target-path-source-a"}
        assert (
            conn.execute(
                "SELECT source_revision FROM billboard_snapshots WHERE cache_key='old-v3'"
            ).fetchone()[0]
            == "old-v3-source"
        )
    finally:
        conn.close()


def test_transfer_rejects_source_drift_before_sidecar_creation(publication):
    path, fence = publication
    fence["lineage"] = "source-b"
    with pytest.raises(RuntimeError, match="source/governance"):
        maintenance.import_manifest(None, path)
    assert not maintenance.Path(maintenance.cache.BILLBOARD_CACHE_PATH).exists()


@pytest.mark.parametrize("corruption", ["digest", "payload", "target"])
def test_transfer_rejects_corrupt_or_incomplete_manifest(publication, corruption):
    path, _ = publication
    manifest = json.loads(path.read_text())
    if corruption == "digest":
        manifest["digest"] = "invalid"
    elif corruption == "payload":
        manifest["payload"]["entries"][0]["payload"]["unexpected"] = True
        manifest["digest"] = maintenance._digest(manifest["payload"])
    else:
        manifest["payload"]["entries"].pop()
        manifest["digest"] = maintenance._digest(manifest["payload"])
    path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError):
        maintenance.import_manifest(None, path)
    assert not maintenance.Path(maintenance.cache.BILLBOARD_CACHE_PATH).exists()


def test_transfer_rolls_back_all_rows_if_source_changes_before_commit(publication, monkeypatch):
    path, _ = publication
    original = maintenance.validate_manifest
    checks = []

    def changed(conn, path):
        checks.append(True)
        if len(checks) == 2:
            raise RuntimeError("source changed")
        return original(conn, path)

    monkeypatch.setattr(maintenance, "validate_manifest", changed)
    with pytest.raises(RuntimeError, match="source changed"):
        maintenance.import_manifest(None, path)
    conn = maintenance.cache._connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM billboard_snapshots").fetchone()[0] == 0
    finally:
        conn.close()


def test_public_guard_rejects_maintenance_without_opening_files(monkeypatch):
    def forbidden(*args):
        pytest.fail("public maintenance opened files or built facts")

    monkeypatch.setattr(maintenance.cache, "_connect", forbidden)
    token = set_public_readonly_db_guard(True)
    try:
        for operation in (
            lambda: maintenance.prepare_publications(None),
            lambda: maintenance.export_manifest(None, "absent"),
            lambda: maintenance.import_manifest(None, "absent"),
            lambda: maintenance.validate_manifest(None, "absent"),
            lambda: maintenance.verify_publications(None),
        ):
            with pytest.raises(RuntimeError, match="public requests"):
                operation()
    finally:
        reset_public_readonly_db_guard(token)
