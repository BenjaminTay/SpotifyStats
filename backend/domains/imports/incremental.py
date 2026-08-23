"""Pure helpers for planning an incremental streaming-history import.

The functions in this module deliberately do not open or mutate the database.
Callers provide the persisted active fingerprint baseline (or ``None`` when a
baseline does not exist yet) and the fingerprints found by the import
preflight.  The resulting :class:`ImportPlan` is evidence only; executing the
plan belongs to the import service.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

FINGERPRINT_VERSION = 1


class ImportRelation(str, Enum):
    """Proven relationship between the active and incoming record sets."""

    BASELINE_REQUIRED = "baseline_required"
    IDENTICAL = "identical"
    SNAPSHOT_SUPERSET = "snapshot_superset"
    DELTA_TAIL = "delta_tail"
    RECONCILED_SNAPSHOT = "reconciled_snapshot"
    TRUNCATED_OR_REGRESSIVE = "truncated_or_regressive"
    DIFFERENT_ACCOUNT = "different_account"
    AMBIGUOUS = "ambiguous"


class ImportCoverage(str, Enum):
    """Meaning explicitly attached to the incoming export bundle."""

    UNKNOWN = "unknown"
    SNAPSHOT = "snapshot"
    DELTA = "delta"


class ImportStrategy(str, Enum):
    """Coarse execution strategy suggested by the read-only plan."""

    NOOP = "noop"
    INCREMENTAL = "incremental"
    MIXED = "mixed"
    FULL = "full"


@dataclass(frozen=True, order=True)
class RecordIdentity:
    """Identity of one exact source record, isolated by source type."""

    source_type: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.source_type.strip():
            raise ValueError("source_type must not be empty")
        if not self.fingerprint.strip():
            raise ValueError("fingerprint must not be empty")


@dataclass(frozen=True)
class FingerprintRecord:
    """One record fingerprint plus optional time evidence for tail detection."""

    source_type: str
    fingerprint: str
    timestamp: datetime | None = None

    @property
    def identity(self) -> RecordIdentity:
        return RecordIdentity(self.source_type, self.fingerprint)


@dataclass(frozen=True)
class ImportPlan:
    """Read-only comparison result consumed by API and import orchestration."""

    relation: ImportRelation
    estimated_strategy: ImportStrategy
    incoming_digest: str
    previous_digest: str | None
    incoming_count: int
    existing_count: int
    unchanged_count: int
    added: frozenset[RecordIdentity]
    removed: frozenset[RecordIdentity]
    incoming_first_ts: datetime | None
    incoming_latest_ts: datetime | None
    existing_first_ts: datetime | None
    existing_latest_ts: datetime | None
    requires_confirmation: bool

    @property
    def added_count(self) -> int:
        return len(self.added)

    @property
    def removed_count(self) -> int:
        return len(self.removed)

    def to_dict(self) -> dict[str, Any]:
        """Return the compact, JSON-compatible representation used by APIs."""

        return {
            "detected_relation": self.relation.value,
            "estimated_strategy": self.estimated_strategy.value,
            "requires_confirmation": self.requires_confirmation,
            "incoming_digest": self.incoming_digest,
            "previous_digest": self.previous_digest,
            "incoming_count": self.incoming_count,
            "existing_count": self.existing_count,
            "unchanged_count": self.unchanged_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "incoming_first_ts": _isoformat(self.incoming_first_ts),
            "incoming_latest_ts": _isoformat(self.incoming_latest_ts),
            "existing_first_ts": _isoformat(self.existing_first_ts),
            "existing_latest_ts": _isoformat(self.existing_latest_ts),
        }


def dataset_digest(records: Iterable[FingerprintRecord]) -> str:
    """Hash a record set independently of files, ordering, and repartitioning.

    Exact duplicate records are intentionally collapsed, matching the current
    importer's record-level deduplication.  Length-prefixed fields keep the
    encoding unambiguous without relying on a reserved delimiter.
    """

    identities = sorted({record.identity for record in records})
    digest = hashlib.sha256(b"spotifystats-streaming-dataset-v1\0")
    for identity in identities:
        source = identity.source_type.encode("utf-8")
        fingerprint = identity.fingerprint.encode("ascii")
        digest.update(len(source).to_bytes(4, "big"))
        digest.update(source)
        digest.update(len(fingerprint).to_bytes(4, "big"))
        digest.update(fingerprint)
    return digest.hexdigest()


def build_import_plan(
    incoming_records: Iterable[FingerprintRecord],
    *,
    existing_records: Iterable[FingerprintRecord] | None = None,
    existing_account_identity_hash: str | None = None,
    incoming_account_identity_hash: str | None = None,
    coverage: ImportCoverage = ImportCoverage.UNKNOWN,
) -> ImportPlan:
    """Compare incoming evidence with the active fingerprint baseline.

    ``existing_records=None`` means the active database has no persisted
    fingerprint baseline.  An empty iterable is a valid, already-established
    empty baseline and is therefore intentionally different from ``None``.
    """

    coverage = ImportCoverage(coverage)
    incoming = _index_records(incoming_records)
    incoming_keys = frozenset(incoming)
    incoming_range = _timestamp_range(incoming.values())
    incoming_hash = dataset_digest(incoming.values())

    if existing_records is None:
        return ImportPlan(
            relation=ImportRelation.BASELINE_REQUIRED,
            estimated_strategy=ImportStrategy.FULL,
            incoming_digest=incoming_hash,
            previous_digest=None,
            incoming_count=len(incoming_keys),
            existing_count=0,
            unchanged_count=0,
            added=incoming_keys,
            removed=frozenset(),
            incoming_first_ts=incoming_range[0],
            incoming_latest_ts=incoming_range[1],
            existing_first_ts=None,
            existing_latest_ts=None,
            requires_confirmation=False,
        )

    existing = _index_records(existing_records)
    existing_keys = frozenset(existing)
    existing_range = _timestamp_range(existing.values())
    previous_hash = dataset_digest(existing.values())
    unchanged = incoming_keys & existing_keys
    added = incoming_keys - existing_keys
    removed = existing_keys - incoming_keys

    accounts_differ = (
        existing_account_identity_hash is not None
        and incoming_account_identity_hash is not None
        and existing_account_identity_hash != incoming_account_identity_hash
    )
    accounts_match = (
        existing_account_identity_hash is not None
        and incoming_account_identity_hash is not None
        and existing_account_identity_hash == incoming_account_identity_hash
    )

    if accounts_differ:
        relation = ImportRelation.DIFFERENT_ACCOUNT
    elif not added and not removed:
        relation = ImportRelation.IDENTICAL
    elif coverage is ImportCoverage.DELTA and accounts_match and not added:
        # A declared delta is additive: omitted active records are not
        # deletions.  If every supplied fact already exists, applying the
        # delta leaves the active dataset unchanged.
        relation = ImportRelation.IDENTICAL
    elif not removed:
        relation = ImportRelation.SNAPSHOT_SUPERSET
    elif not unchanged and not accounts_match:
        # With no shared facts and no proven account identity, set algebra
        # cannot distinguish a later delta from another account's history.
        relation = ImportRelation.AMBIGUOUS
    elif (
        added
        and removed
        and accounts_match
        and coverage is ImportCoverage.UNKNOWN
        and _range_covers_existing(
            incoming_range=incoming_range,
            existing_range=existing_range,
        )
    ):
        # Auto mode may offer (but never silently execute) an exact reconcile
        # only when the same-account input looks like an authoritative history
        # snapshot: it contains both sides of a correction and its timestamp
        # envelope covers the complete active range.  Anything weaker stays
        # ambiguous so omitted rows cannot be mistaken for deletions.
        relation = ImportRelation.RECONCILED_SNAPSHOT
    elif (
        unchanged
        and accounts_match
        and coverage is ImportCoverage.UNKNOWN
        and _is_tail_addition(
            added=added,
            incoming=incoming,
            existing=existing,
        )
    ):
        # Auto mode may safely treat a same-account package as a tail delta
        # when every genuinely new identity is at or beyond the active tail.
        # Missing historical identities are ignored rather than interpreted as
        # deletions, which is the conservative no-data-loss action.
        relation = ImportRelation.DELTA_TAIL
    elif coverage is ImportCoverage.DELTA:
        relation = _classify_declared_delta(
            added=added,
            incoming=incoming,
            existing=existing,
            accounts_match=accounts_match,
        )
    elif incoming_keys < existing_keys:
        relation = ImportRelation.TRUNCATED_OR_REGRESSIVE
    elif coverage is ImportCoverage.SNAPSHOT:
        relation = ImportRelation.RECONCILED_SNAPSHOT
    else:
        relation = ImportRelation.AMBIGUOUS

    strategy, requires_confirmation = _execution_hint(relation)
    effective_removed = (
        frozenset()
        if relation is ImportRelation.DELTA_TAIL
        or (coverage is ImportCoverage.DELTA and relation is ImportRelation.IDENTICAL)
        else frozenset(removed)
    )
    return ImportPlan(
        relation=relation,
        estimated_strategy=strategy,
        incoming_digest=incoming_hash,
        previous_digest=previous_hash,
        incoming_count=len(incoming_keys),
        existing_count=len(existing_keys),
        unchanged_count=len(unchanged),
        added=frozenset(added),
        removed=effective_removed,
        incoming_first_ts=incoming_range[0],
        incoming_latest_ts=incoming_range[1],
        existing_first_ts=existing_range[0],
        existing_latest_ts=existing_range[1],
        requires_confirmation=requires_confirmation,
    )


def _index_records(records: Iterable[FingerprintRecord]) -> dict[RecordIdentity, FingerprintRecord]:
    indexed: dict[RecordIdentity, FingerprintRecord] = {}
    for record in records:
        identity = record.identity
        previous = indexed.get(identity)
        if previous is not None and _normalise_timestamp(
            previous.timestamp
        ) != _normalise_timestamp(record.timestamp):
            raise ValueError(
                f"conflicting timestamps for {identity.source_type}:{identity.fingerprint}"
            )
        indexed[identity] = record
    return indexed


def _classify_declared_delta(
    *,
    added: frozenset[RecordIdentity],
    incoming: dict[RecordIdentity, FingerprintRecord],
    existing: dict[RecordIdentity, FingerprintRecord],
    accounts_match: bool,
) -> ImportRelation:
    if not accounts_match:
        return ImportRelation.AMBIGUOUS
    if _is_tail_addition(added=added, incoming=incoming, existing=existing):
        return ImportRelation.DELTA_TAIL
    return ImportRelation.TRUNCATED_OR_REGRESSIVE


def _is_tail_addition(
    *,
    added: frozenset[RecordIdentity],
    incoming: dict[RecordIdentity, FingerprintRecord],
    existing: dict[RecordIdentity, FingerprintRecord],
) -> bool:
    existing_latest = _timestamp_range(existing.values())[1]
    added_timestamps = [_normalise_timestamp(incoming[key].timestamp) for key in added]
    return bool(
        added_timestamps
        and existing_latest is not None
        and all(timestamp is not None for timestamp in added_timestamps)
        and min(timestamp for timestamp in added_timestamps if timestamp is not None)
        >= _normalise_timestamp(existing_latest)
    )


def _range_covers_existing(
    *,
    incoming_range: tuple[datetime | None, datetime | None],
    existing_range: tuple[datetime | None, datetime | None],
) -> bool:
    incoming_first, incoming_latest = incoming_range
    existing_first, existing_latest = existing_range
    return bool(
        incoming_first is not None
        and incoming_latest is not None
        and existing_first is not None
        and existing_latest is not None
        and incoming_first <= existing_first
        and incoming_latest >= existing_latest
    )


def _execution_hint(relation: ImportRelation) -> tuple[ImportStrategy, bool]:
    if relation is ImportRelation.IDENTICAL:
        return ImportStrategy.NOOP, False
    if relation in {ImportRelation.SNAPSHOT_SUPERSET, ImportRelation.DELTA_TAIL}:
        return ImportStrategy.INCREMENTAL, False
    if relation is ImportRelation.RECONCILED_SNAPSHOT:
        return ImportStrategy.MIXED, True
    if relation in {
        ImportRelation.TRUNCATED_OR_REGRESSIVE,
        ImportRelation.DIFFERENT_ACCOUNT,
        ImportRelation.AMBIGUOUS,
    }:
        return ImportStrategy.FULL, True
    return ImportStrategy.FULL, False


def _timestamp_range(
    records: Iterable[FingerprintRecord],
) -> tuple[datetime | None, datetime | None]:
    timestamps = [
        timestamp
        for record in records
        if (timestamp := _normalise_timestamp(record.timestamp)) is not None
    ]
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


def _normalise_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    normalised = _normalise_timestamp(value)
    return normalised.isoformat() if normalised is not None else None
