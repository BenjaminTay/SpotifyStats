from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.domains.imports.execution import (
    ImportExecutionAction,
    resolve_import_execution,
)
from backend.domains.imports.incremental import (
    FingerprintRecord,
    ImportCoverage,
    build_import_plan,
)

pytestmark = pytest.mark.unit


def _record(name: str, day: int = 1) -> FingerprintRecord:
    return FingerprintRecord(
        source_type="audio",
        fingerprint=name * 64,
        timestamp=datetime(2026, 8, day, tzinfo=timezone.utc),
    )


def test_auto_baseline_uses_replace_and_identical_uses_noop() -> None:
    incoming = [_record("a")]

    baseline = resolve_import_execution(build_import_plan(incoming))
    identical = resolve_import_execution(build_import_plan(incoming, existing_records=incoming))

    assert baseline.action is ImportExecutionAction.REPLACE
    assert identical.action is ImportExecutionAction.NOOP


def test_auto_snapshot_superset_uses_append() -> None:
    existing = [_record("a")]
    incoming = [*existing, _record("b", 2)]

    decision = resolve_import_execution(build_import_plan(incoming, existing_records=existing))

    assert decision.action is ImportExecutionAction.APPEND
    assert decision.writes_playback is True


def test_proven_same_account_tail_delta_uses_append() -> None:
    plan = build_import_plan(
        [_record("b", 2)],
        existing_records=[_record("a")],
        existing_account_identity_hash="same",
        incoming_account_identity_hash="same",
        coverage=ImportCoverage.DELTA,
    )

    assert (
        resolve_import_execution(plan, requested_mode="append").action
        is ImportExecutionAction.APPEND
    )


def test_append_cannot_override_missing_baseline_or_account_mismatch() -> None:
    missing = build_import_plan([_record("a")])
    mismatch = build_import_plan(
        [_record("b", 2)],
        existing_records=[_record("a")],
        existing_account_identity_hash="first",
        incoming_account_identity_hash="second",
        coverage=ImportCoverage.DELTA,
    )

    assert (
        resolve_import_execution(
            missing,
            requested_mode="append",
            confirm_plan=True,
        ).action
        is ImportExecutionAction.BLOCKED
    )
    assert (
        resolve_import_execution(
            mismatch,
            requested_mode="append",
            confirm_plan=True,
        ).action
        is ImportExecutionAction.BLOCKED
    )


def test_auto_ambiguous_requires_explicit_replace() -> None:
    plan = build_import_plan(
        [_record("b", 2)],
        existing_records=[_record("a")],
    )

    assert (
        resolve_import_execution(plan, confirm_plan=True).action
        is ImportExecutionAction.NEEDS_CONFIRMATION
    )
    assert (
        resolve_import_execution(plan, requested_mode="replace").action
        is ImportExecutionAction.NEEDS_CONFIRMATION
    )
    assert (
        resolve_import_execution(
            plan,
            requested_mode="replace",
            confirm_plan=True,
        ).action
        is ImportExecutionAction.REPLACE
    )


def test_legacy_baseline_with_existing_rows_requires_confirmed_replace() -> None:
    plan = build_import_plan([_record("a")], existing_records=None)
    plan = replace(plan, existing_count=10, requires_confirmation=True)

    assert resolve_import_execution(plan).action is ImportExecutionAction.NEEDS_CONFIRMATION
    assert (
        resolve_import_execution(plan, requested_mode="replace").action
        is ImportExecutionAction.NEEDS_CONFIRMATION
    )
    assert resolve_import_execution(plan, confirm_plan=True).action is ImportExecutionAction.REPLACE


def test_explicit_replace_is_not_silently_optimised_to_noop() -> None:
    records = [_record("a")]
    plan = build_import_plan(records, existing_records=records)

    assert (
        resolve_import_execution(plan, requested_mode="replace").action
        is ImportExecutionAction.REPLACE
    )
