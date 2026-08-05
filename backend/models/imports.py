"""API response models for import preflight and data health."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ImportStatus = Literal["healthy", "partial", "blocked", "stale", "failed"]
ImportHealthIssueCategory = Literal["database", "relationship", "metadata", "derived"]
ImportHealthIssueSeverity = Literal["critical", "high", "medium", "low"]


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


class ImportPreflightResponse(BaseModel):
    status: ImportStatus
    streaming_files: list[ImportFileReport] = Field(default_factory=list)
    account_files: list[ImportFileReport] = Field(default_factory=list)
    duplicate_file_groups: list[ImportDuplicateFileGroup] = Field(default_factory=list)
    date_overlaps: list[ImportDateOverlap] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


class ImportHealthResponse(BaseModel):
    status: ImportStatus
    checked_at: str
    database: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    derived: dict[str, Any] = Field(default_factory=dict)
    issues: list[ImportHealthIssue] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
