"""API response models for import preflight and data health."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ImportStatus = Literal["healthy", "partial", "blocked", "stale", "failed"]
ImportHealthIssueCategory = Literal["database", "relationship", "metadata", "derived"]
ImportHealthIssueSeverity = Literal["critical", "high", "medium", "low"]
ImportHealthImpactScope = Literal[
    "current_stats", "source_exclusion", "historical_only", "non_music"
]
ImportHealthUserStatus = Literal["blocking", "action_required", "maintenance", "info"]
ImportAccountIdentityStatus = Literal["unknown", "not_provided", "matched", "mismatched"]
ImportFingerprintBaselineStatus = Literal["missing", "ready", "incompatible"]
ImportDetectedRelation = Literal[
    "unknown",
    "baseline_required",
    "identical",
    "snapshot_superset",
    "delta_tail",
    "reconciled_snapshot",
    "truncated_or_regressive",
    "different_account",
    "ambiguous",
]
ImportRequestedMode = Literal["auto", "append", "replace"]
ImportEstimatedStrategy = Literal["noop", "incremental", "mixed", "full"]


class ImportFileReport(BaseModel):
    source_key: str
    label: str
    file_name: str
    required: bool
    status: Literal["missing", "ok", "empty", "invalid"]
    size_bytes: int = 0
    record_count: int = 0
    duplicate_record_count: int = 0
    first_date: str | None = None
    last_date: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImportDuplicateFileGroup(BaseModel):
    file_names: list[str]
    sha256: str


class ImportDateOverlap(BaseModel):
    left_file: str
    right_file: str
    overlap_start: str
    overlap_end: str
    overlap_days: int
    shared_record_count: int = 0
    classification: Literal["duplicate_records", "boundary_only", "review_required"] = (
        "review_required"
    )


class ImportDatasetDateRange(BaseModel):
    first_date: str | None = None
    last_date: str | None = None


class ImportPreflightResponse(BaseModel):
    status: ImportStatus
    streaming_files: list[ImportFileReport] = Field(default_factory=list)
    account_files: list[ImportFileReport] = Field(default_factory=list)
    duplicate_file_groups: list[ImportDuplicateFileGroup] = Field(default_factory=list)
    date_overlaps: list[ImportDateOverlap] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    account_identity_status: ImportAccountIdentityStatus = "unknown"
    fingerprint_baseline_status: ImportFingerprintBaselineStatus = "missing"
    detected_relation: ImportDetectedRelation = "unknown"
    requested_mode: ImportRequestedMode = "auto"
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    existing_record_count: int = Field(default=0, ge=0)
    incoming_record_count: int = Field(default=0, ge=0)
    unchanged_record_count: int = Field(default=0, ge=0)
    added_record_count: int = Field(default=0, ge=0)
    removed_record_count: int = Field(default=0, ge=0)
    existing_date_range: ImportDatasetDateRange | None = None
    incoming_date_range: ImportDatasetDateRange | None = None
    affected_weeks_count: int = Field(default=0, ge=0)
    affected_years_count: int = Field(default=0, ge=0)
    planned_actions: list[str] = Field(default_factory=list)
    estimated_strategy: ImportEstimatedStrategy = "full"
    comparison_status: Literal["comparable", "baseline_missing", "incompatible"] = (
        "baseline_missing"
    )
    record_delta_comparable: bool = False


class ImportHealthIssue(BaseModel):
    code: str
    category: ImportHealthIssueCategory
    severity: ImportHealthIssueSeverity
    title: str
    count: int = 0
    affected_play_count: int = 0
    impact: str
    recommended_action: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    impact_scope: ImportHealthImpactScope = "historical_only"
    user_status: ImportHealthUserStatus = "maintenance"
    user_title: str | None = None
    user_explanation: str | None = None
    action: Literal["retry", "review", "preview_cleanup", "no_action"] = "review"


class ImportHealthResponse(BaseModel):
    status: ImportStatus
    checked_at: str
    database: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    derived: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    issues: list[ImportHealthIssue] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImportCleanupPreviewGroup(BaseModel):
    issue_code: str
    title: str
    count: int = 0
    affected_play_count: int = 0
    proposed_action: str
    automatic_cleanup_allowed: bool = False
    samples: list[dict[str, Any]] = Field(default_factory=list)


class ImportCleanupPreviewResponse(BaseModel):
    status: Literal["ready"] = "ready"
    generated_at: str
    database_revision: str
    preview_token: str
    writes_performed: bool = False
    groups: list[ImportCleanupPreviewGroup] = Field(default_factory=list)
    excluded_issue_codes: list[str] = Field(default_factory=list)
