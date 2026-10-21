from __future__ import annotations

import json
import sqlite3
from contextlib import nullcontext

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
    filters = {
        "merge_level": 2,
        "dynamic_threshold": True,
        "min_ms": 30000,
        "include_compilations": False,
    }
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


def test_explicit_compilation_scope_builds_all_eight_contexts(publication, monkeypatch):
    from backend.core import cache_manager
    from backend.domains.billboard import build_context
    from backend.services import billboard_service

    calls = []

    def builder(**params):
        calls.append(params)
        return {"meta": {"available_years": [2026, 2024]}}

    monkeypatch.setattr(build_context, "BillboardBuildContext", lambda _: nullcontext("facts"))
    monkeypatch.setattr(cache_manager, "invalidate", lambda _: None)
    for name in (
        "compute_all_time_staged",
        "compute_billboard_data",
        "compute_power_scores_staged",
        "compute_records_staged",
        "compute_summaries_staged",
        "compute_weekly_data",
        "compute_year_end_staged",
    ):
        monkeypatch.setattr(billboard_service, name, builder)

    result = maintenance.prepare_publications(None, include_compilation_variants=True)

    assert result["targets"] == 72
    assert result["variant_scope"] == {"include_compilation_variants": True}
    assert len(calls) == 72
    assert {
        (row["merge_level"], row["dynamic_threshold"], row["include_compilations"])
        for row in result["prepared"]
    } == {
        (level, dynamic, compilation)
        for level in (2, 3)
        for dynamic in (False, True)
        for compilation in (False, True)
    }
    assert all(call["force_rebuild"] and call["_build_context"] == "facts" for call in calls)


@pytest.mark.parametrize("configured_compilations", [False, True])
def test_default_scope_preserves_configured_compilation_setting(
    monkeypatch, configured_compilations
):
    monkeypatch.setattr(
        maintenance,
        "configured_billboard_filters",
        lambda _: {"include_compilations": configured_compilations},
    )

    default = maintenance._variants(None)
    expanded = maintenance._variants(None, include_compilation_variants=True)

    assert len(default) == 4
    assert {item["include_compilations"] for item in default} == {configured_compilations}
    assert len(expanded) == 8
    assert {item["include_compilations"] for item in expanded} == {False, True}


def test_compilation_manifest_import_verifies_its_full_declared_scope(publication, monkeypatch):
    path, _ = publication
    monkeypatch.setattr(
        maintenance,
        "_read_exact",
        lambda family, params: {
            "meta": {"available_years": [2022, 2023, 2024, 2025, 2026]},
            "family": family,
        },
    )
    exported = maintenance.export_manifest(None, path, include_compilation_variants=True)
    assert exported["targets"] == 96
    manifest = json.loads(path.read_text())
    assert manifest["payload"]["variant_scope"] == {"include_compilation_variants": True}
    monkeypatch.setattr(
        maintenance,
        "_read_exact",
        lambda family, params: maintenance.cache.load_persisted_snapshot(
            maintenance.cache.build_cache_context(family, params), allow_lkg=False
        ),
    )

    result = maintenance.import_manifest(None, path)

    assert result["targets"] == 96
    assert result["variant_scope"] == {"include_compilation_variants": True}
    assert maintenance.verify_publications(None)["targets"] == 48
    assert maintenance.verify_publications(None, include_compilation_variants=True)["targets"] == 96


def test_historical_manifest_without_scope_remains_default_four_variants(publication):
    path, _ = publication
    manifest = json.loads(path.read_text())
    manifest["payload"].pop("variant_scope")
    manifest["digest"] = maintenance._digest(manifest["payload"])
    path.write_text(json.dumps(manifest))

    _, entries = maintenance.validate_manifest(None, path)

    assert len(entries) == 36


@pytest.mark.parametrize("declared_scope", [None, False, True, "true", {"unexpected": True}])
def test_manifest_scope_cannot_hide_extra_or_missing_compilation_targets(
    publication, declared_scope
):
    path, _ = publication
    # Only a complete eight-context set is legal when the manifest declares it.
    maintenance.export_manifest(None, path, include_compilation_variants=True)
    manifest = json.loads(path.read_text())
    payload = manifest["payload"]
    if declared_scope is None:
        payload.pop("variant_scope")
    elif declared_scope is True:
        payload["entries"] = [
            entry for entry in payload["entries"] if not entry["params"]["include_compilations"]
        ]
    elif isinstance(declared_scope, dict):
        payload["variant_scope"] = declared_scope
    else:
        payload["variant_scope"] = {"include_compilation_variants": declared_scope}
    manifest["digest"] = maintenance._digest(payload)
    path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="target|variant scope"):
        maintenance.import_manifest(None, path)
    assert not maintenance.Path(maintenance.cache.BILLBOARD_CACHE_PATH).exists()


def test_import_releases_parsed_payloads_before_revalidation_and_final_verification(
    publication, monkeypatch
):
    import gc
    import weakref

    path, _ = publication
    validate = maintenance.validate_manifest
    verify = maintenance.verify_publications
    parsed_references = []

    class ParsedDict(dict):
        pass

    class ParsedEntries(list):
        pass

    def assert_released(references):
        gc.collect()
        assert all(reference() is None for reference in references), (
            "an earlier complete manifest or payload tree is still retained"
        )

    def observed_validation(conn, manifest_path):
        if parsed_references:
            # Check before parsing the second complete manifest. In particular,
            # the final loop entry must not retain its potentially large payload.
            assert_released(parsed_references[-1])
        raw_manifest, raw_entries = validate(conn, manifest_path)
        references = []
        for entry in raw_entries:
            entry["payload"] = ParsedDict(entry["payload"])
            references.append(weakref.ref(entry["payload"]))
        entries = ParsedEntries(raw_entries)
        payload = ParsedDict(raw_manifest["payload"])
        payload["entries"] = entries
        manifest = ParsedDict(raw_manifest)
        manifest["payload"] = payload
        parsed_references.append(
            [weakref.ref(manifest), weakref.ref(payload), weakref.ref(entries), *references]
        )
        return manifest, entries

    def observed_verification(conn, **scope):
        assert len(parsed_references) == 2
        for references in parsed_references:
            assert_released(references)
        return verify(conn, **scope)

    monkeypatch.setattr(maintenance, "validate_manifest", observed_validation)
    monkeypatch.setattr(maintenance, "verify_publications", observed_verification)
    monkeypatch.setattr(
        maintenance,
        "_read_exact",
        lambda family, params: maintenance.cache.load_persisted_snapshot(
            maintenance.cache.build_cache_context(family, params), allow_lkg=False
        ),
    )

    result = maintenance.import_manifest(None, path)

    assert result["status"] == "imported" and result["targets"] == 36
    assert len(parsed_references) == 2


@pytest.mark.parametrize(
    "change,expected_error",
    [
        ("payload_checksum", "payload checksum"),
        ("valid_replacement", "manifest changed during import"),
        ("source", "source/governance"),
    ],
)
def test_revalidation_drift_rolls_back_new_publications_and_preserves_existing_snapshot(
    publication, monkeypatch, change, expected_error
):
    path, fence = publication
    prior = maintenance.cache.build_cache_context("full_data", {"unrelated": True})
    maintenance.cache.store_persisted_snapshot(prior, {"prior": "must remain unchanged"})
    conn = maintenance.cache._connect()
    try:
        before = [
            tuple(row)
            for row in conn.execute("SELECT * FROM billboard_snapshots ORDER BY cache_key")
        ]
    finally:
        conn.close()
    validate = maintenance.validate_manifest
    validations = []

    def changed_during_import(conn, manifest_path):
        validations.append(True)
        if len(validations) == 2:
            if change == "source":
                fence["lineage"] = "source-changed-before-commit"
            else:
                manifest = json.loads(path.read_text())
                entry = manifest["payload"]["entries"][0]
                entry["payload"]["changed_during_import"] = True
                if change == "valid_replacement":
                    # Both checksums validate, but a different valid manifest
                    # still cannot replace the one whose entries were installed.
                    entry["payload_digest"] = maintenance._digest(entry["payload"])
                manifest["digest"] = maintenance._digest(manifest["payload"])
                path.write_text(json.dumps(manifest))
        return validate(conn, manifest_path)

    monkeypatch.setattr(maintenance, "validate_manifest", changed_during_import)

    with pytest.raises(RuntimeError, match=expected_error):
        maintenance.import_manifest(None, path)

    assert len(validations) == 2
    conn = maintenance.cache._connect()
    try:
        after = [
            tuple(row)
            for row in conn.execute("SELECT * FROM billboard_snapshots ORDER BY cache_key")
        ]
        assert after == before
    finally:
        conn.close()
