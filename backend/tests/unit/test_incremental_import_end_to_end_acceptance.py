from __future__ import annotations

from datetime import datetime

import pytest

from backend.domains.imports.incremental import FingerprintRecord, build_import_plan
from backend.domains.imports.source_inspector import record_fingerprint
from scripts import incremental_import_end_to_end_acceptance as acceptance

pytestmark = pytest.mark.unit


def _fingerprints(records: list[dict]) -> list[FingerprintRecord]:
    return [
        FingerprintRecord(
            source_type="audio",
            fingerprint=record_fingerprint(record),
            timestamp=datetime.fromisoformat(str(record["ts"]).replace("Z", "+00:00")),
        )
        for record in records
    ]


def test_synthetic_matrix_proves_cross_week_same_week_and_reconcile_relations() -> None:
    baseline, first_append, second_append, reconciled = acceptance.synthetic_datasets()
    account_hash = "same-account"

    assert [len(rows) for rows in (baseline, first_append, second_append, reconciled)] == [
        37,
        40,
        41,
        41,
    ]
    first_plan = build_import_plan(
        _fingerprints(first_append),
        existing_records=_fingerprints(baseline),
        existing_account_identity_hash=account_hash,
        incoming_account_identity_hash=account_hash,
    )
    second_plan = build_import_plan(
        _fingerprints(second_append),
        existing_records=_fingerprints(first_append),
        existing_account_identity_hash=account_hash,
        incoming_account_identity_hash=account_hash,
    )
    reconcile_plan = build_import_plan(
        _fingerprints(reconciled),
        existing_records=_fingerprints(second_append),
        existing_account_identity_hash=account_hash,
        incoming_account_identity_hash=account_hash,
    )

    assert first_plan.relation.value == "snapshot_superset"
    assert first_plan.added_count == 3
    assert second_plan.relation.value == "snapshot_superset"
    assert second_plan.added_count == 1
    assert reconcile_plan.relation.value == "reconciled_snapshot"
    assert reconcile_plan.added_count == reconcile_plan.removed_count == 1
    corrected = next(
        record
        for record in reconciled
        if record["spotify_track_uri"] == "spotify:track:acceptance-track-corrected"
    )
    assert corrected["master_metadata_album_album_name"] == "Acceptance Corrected Album"


def test_workdir_guard_rejects_repository_and_source_sibling(tmp_path) -> None:
    source = tmp_path / "data" / "spotify_stats.db"
    source.parent.mkdir()
    source.touch()

    with pytest.raises(acceptance.AcceptanceError, match="repository"):
        acceptance.validate_workdir(acceptance.PROJECT_ROOT / "acceptance", source)
    with pytest.raises(acceptance.AcceptanceError, match="source database directory"):
        acceptance.validate_workdir(source.parent / "acceptance", source)


def test_public_projection_does_not_emit_semantic_rows() -> None:
    projection = {
        "facts": {"row_count": 1, "digest": "facts", "rows": [["private"]]},
        "credits": {"row_count": 1, "digest": "credits", "rows": [["private"]]},
        "active_track_albums": {
            "row_count": 1,
            "digest": "active-track-albums",
            "rows": [["private"]],
        },
        "album_projects": {
            name: {"row_count": 1, "digest": name, "rows": [["private"]]}
            for name in acceptance.ALBUM_PROJECT_PROJECTIONS
        },
        "track_groups": {
            name: {"row_count": 1, "digest": name, "rows": [["private"]]}
            for name in acceptance.TRACK_GROUP_PROJECTIONS
        },
        "aggregates": {
            name: {"row_count": 1, "digest": name, "rows": [["private"]]}
            for name in acceptance.AGGREGATE_TABLES
        },
        "candidates": {"row_count": 1, "digest": "candidates", "rows": [["private"]]},
        "search": {
            "variant_count": 6,
            "row_count": 6,
            "digest": "search",
            "rows": {"private": [["private"]]},
        },
        "year_partition": {
            "fact_row_count": 1,
            "fact_digest": "year",
            "audit_digest": "audit",
            "fact_rows": [["private"]],
        },
        "billboard": {},
        "year_end": {"digest": "year-end", "payload": {"private": True}},
        "yearly_artifact": {},
        "home": {},
        "timings": {},
    }

    public = acceptance._public_projection(projection)

    assert "rows" not in str(public)
    assert "private" not in str(public)


def test_yearly_invalidation_contract_requires_fact_revision_and_key_change() -> None:
    before = {"direct_digest": "facts-a", "impact_revision": 3, "cache_key": "key-a"}

    assert acceptance._accepted_change_invalidated(
        before,
        {"direct_digest": "facts-b", "impact_revision": 4, "cache_key": "key-b"},
    )
    assert not acceptance._accepted_change_invalidated(
        before,
        {"direct_digest": "facts-b", "impact_revision": 3, "cache_key": "key-b"},
    )
    assert not acceptance._accepted_change_invalidated(
        before,
        {"direct_digest": "facts-b", "impact_revision": 4, "cache_key": "key-a"},
    )
