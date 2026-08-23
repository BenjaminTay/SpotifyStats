from datetime import datetime, timezone

import pytest

from backend.domains.imports.incremental import (
    FingerprintRecord,
    ImportCoverage,
    ImportRelation,
    ImportStrategy,
    build_import_plan,
    dataset_digest,
)
from backend.domains.imports.source_inspector import record_fingerprint

pytestmark = pytest.mark.unit


def _record(
    value: str,
    *,
    source_type: str = "streaming_audio",
    timestamp: str = "2026-08-01T00:00:00+00:00",
) -> FingerprintRecord:
    raw = {"ts": timestamp, "spotify_track_uri": value, "ms_played": 180_000}
    return FingerprintRecord(
        source_type=source_type,
        fingerprint=record_fingerprint(raw),
        timestamp=datetime.fromisoformat(timestamp),
    )


def test_dataset_digest_ignores_order_duplicates_and_file_repartitioning() -> None:
    first = _record("spotify:track:first")
    second = _record("spotify:track:second")

    one_file = [first, second]
    repartitioned_and_reordered = [second, first, second]

    assert dataset_digest(one_file) == dataset_digest(repartitioned_and_reordered)


def test_dataset_digest_keeps_audio_and_video_identities_separate() -> None:
    audio = _record("spotify:track:same", source_type="streaming_audio")
    video = FingerprintRecord(
        source_type="streaming_video",
        fingerprint=audio.fingerprint,
        timestamp=audio.timestamp,
    )

    plan = build_import_plan([audio, video], existing_records=[])

    assert plan.incoming_count == 2
    assert dataset_digest([audio]) != dataset_digest([video])


def test_missing_persisted_baseline_requires_full_baseline_import() -> None:
    incoming = [_record("spotify:track:new")]

    plan = build_import_plan(incoming)

    assert plan.relation is ImportRelation.BASELINE_REQUIRED
    assert plan.estimated_strategy is ImportStrategy.FULL
    assert plan.added_count == 1
    assert plan.previous_digest is None
    assert plan.requires_confirmation is False


def test_identical_record_sets_are_noop() -> None:
    records = [_record("spotify:track:a"), _record("spotify:track:b")]

    plan = build_import_plan(reversed(records), existing_records=records)

    assert plan.relation is ImportRelation.IDENTICAL
    assert plan.estimated_strategy is ImportStrategy.NOOP
    assert plan.incoming_digest == plan.previous_digest
    assert plan.unchanged_count == 2
    assert plan.added_count == 0
    assert plan.removed_count == 0


def test_strict_superset_is_safe_snapshot_increment() -> None:
    existing = [_record("spotify:track:a")]
    incoming = [*existing, _record("spotify:track:b", timestamp="2026-08-02T00:00:00+00:00")]

    plan = build_import_plan(incoming, existing_records=existing)

    assert plan.relation is ImportRelation.SNAPSHOT_SUPERSET
    assert plan.estimated_strategy is ImportStrategy.INCREMENTAL
    assert plan.added_count == 1
    assert plan.removed_count == 0


def test_declared_same_account_tail_delta_is_incremental() -> None:
    existing = [_record("spotify:track:old")]
    incoming = [_record("spotify:track:new", timestamp="2026-08-02T00:00:00+00:00")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        existing_account_identity_hash="same-account",
        incoming_account_identity_hash="same-account",
        coverage=ImportCoverage.DELTA,
    )

    assert plan.relation is ImportRelation.DELTA_TAIL
    assert plan.estimated_strategy is ImportStrategy.INCREMENTAL
    assert plan.added_count == 1
    assert plan.removed_count == 0
    assert plan.requires_confirmation is False


def test_auto_same_account_tail_package_is_incremental() -> None:
    boundary = _record("spotify:track:boundary", timestamp="2026-08-01T00:00:00+00:00")
    existing = [_record("spotify:track:old"), boundary]
    incoming = [boundary, _record("spotify:track:new", timestamp="2026-08-02T00:00:00+00:00")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        existing_account_identity_hash="same-account",
        incoming_account_identity_hash="same-account",
    )

    assert plan.relation is ImportRelation.DELTA_TAIL
    assert plan.estimated_strategy is ImportStrategy.INCREMENTAL
    assert plan.added_count == 1
    assert plan.removed_count == 0
    assert plan.requires_confirmation is False


def test_auto_zero_overlap_tail_stays_ambiguous_without_bound_provenance() -> None:
    existing = [_record("spotify:track:old")]
    incoming = [_record("spotify:track:new", timestamp="2026-08-02T00:00:00+00:00")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        existing_account_identity_hash="same-account",
        incoming_account_identity_hash="same-account",
    )

    assert plan.relation is ImportRelation.AMBIGUOUS
    assert plan.requires_confirmation is True


def test_declared_same_account_delta_with_only_existing_records_is_noop() -> None:
    duplicate = _record("spotify:track:duplicate", timestamp="2026-08-02T00:00:00+00:00")
    existing = [_record("spotify:track:old"), duplicate]

    plan = build_import_plan(
        [duplicate],
        existing_records=existing,
        existing_account_identity_hash="same-account",
        incoming_account_identity_hash="same-account",
        coverage=ImportCoverage.DELTA,
    )

    assert plan.relation is ImportRelation.IDENTICAL
    assert plan.estimated_strategy is ImportStrategy.NOOP
    assert plan.added_count == 0
    assert plan.removed_count == 0


def test_confirmed_snapshot_with_additions_and_removals_is_reconciled() -> None:
    shared = _record("spotify:track:shared")
    existing = [shared, _record("spotify:track:removed")]
    incoming = [shared, _record("spotify:track:added", timestamp="2026-08-02T00:00:00+00:00")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        coverage=ImportCoverage.SNAPSHOT,
    )

    assert plan.relation is ImportRelation.RECONCILED_SNAPSHOT
    assert plan.estimated_strategy is ImportStrategy.MIXED
    assert plan.unchanged_count == 1
    assert plan.added_count == 1
    assert plan.removed_count == 1


def test_snapshot_subset_is_truncated_or_regressive() -> None:
    incoming = [_record("spotify:track:a")]
    existing = [*incoming, _record("spotify:track:b")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        coverage=ImportCoverage.SNAPSHOT,
    )

    assert plan.relation is ImportRelation.TRUNCATED_OR_REGRESSIVE
    assert plan.requires_confirmation is True


def test_explicit_account_mismatch_takes_precedence_over_set_relation() -> None:
    records = [_record("spotify:track:a")]

    plan = build_import_plan(
        records,
        existing_records=records,
        existing_account_identity_hash="account-a",
        incoming_account_identity_hash="account-b",
    )

    assert plan.relation is ImportRelation.DIFFERENT_ACCOUNT
    assert plan.requires_confirmation is True


def test_unknown_account_without_overlap_is_ambiguous_even_for_declared_delta() -> None:
    existing = [_record("spotify:track:old")]
    incoming = [_record("spotify:track:new", timestamp="2026-08-02T00:00:00+00:00")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        coverage=ImportCoverage.DELTA,
    )

    assert plan.relation is ImportRelation.AMBIGUOUS
    assert plan.requires_confirmation is True


def test_unknown_mixed_bundle_is_ambiguous_without_snapshot_evidence() -> None:
    shared = _record("spotify:track:shared")
    existing = [shared, _record("spotify:track:old")]
    incoming = [shared, _record("spotify:track:new")]

    plan = build_import_plan(incoming, existing_records=existing)

    assert plan.relation is ImportRelation.AMBIGUOUS


def test_same_account_delta_with_historical_addition_is_regressive() -> None:
    existing = [_record("spotify:track:current", timestamp="2026-08-02T00:00:00+00:00")]
    incoming = [_record("spotify:track:historical", timestamp="2026-07-01T00:00:00+00:00")]

    plan = build_import_plan(
        incoming,
        existing_records=existing,
        existing_account_identity_hash="same-account",
        incoming_account_identity_hash="same-account",
        coverage=ImportCoverage.DELTA,
    )

    assert plan.relation is ImportRelation.TRUNCATED_OR_REGRESSIVE
    assert plan.requires_confirmation is True


def test_plan_serialisation_is_compact_and_json_compatible() -> None:
    record = _record("spotify:track:a")

    payload = build_import_plan([record], existing_records=[record]).to_dict()

    assert payload["detected_relation"] == "identical"
    assert payload["incoming_first_ts"] == "2026-08-01T00:00:00+00:00"
    assert payload["added_count"] == 0
    assert "added" not in payload


def test_duplicate_identity_with_conflicting_time_evidence_is_rejected() -> None:
    first = _record("spotify:track:a")
    conflicting = FingerprintRecord(
        source_type=first.source_type,
        fingerprint=first.fingerprint,
        timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="conflicting timestamps"):
        build_import_plan([first, conflicting], existing_records=[])
