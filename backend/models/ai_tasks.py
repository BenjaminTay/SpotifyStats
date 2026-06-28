"""Pydantic models for observable AI task orchestration endpoints."""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field, model_validator

JsonPayload = Union[dict[str, Any], list[Any]]
AiTaskStatus = Literal["queued", "running", "done", "error", "cancelled"]


class AiTaskRun(BaseModel):
    task_id: str
    task_type: str
    status: AiTaskStatus
    stage: str
    progress_pct: float = Field(ge=0.0, le=1.0)
    message: str = ""
    request: JsonPayload | None = None
    result: JsonPayload | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class AiTaskEvent(BaseModel):
    event_id: int
    task_id: str
    event_type: str
    stage: str
    message: str = ""
    payload: JsonPayload | None = None
    created_at: str


class AiToolCall(BaseModel):
    tool_call_id: int
    task_id: str
    tool_name: str
    status: str
    params_summary: str = ""
    result_summary: str = ""
    source_range: str = ""
    error: str | None = None
    started_at: str
    completed_at: str | None = None


class AiTaskStatusResponse(BaseModel):
    found: bool
    task_id: str | None = None
    task_type: str | None = None
    status: AiTaskStatus | None = None
    stage: str | None = None
    progress_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    message: str | None = None
    request: JsonPayload | None = None
    result: JsonPayload | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AiTaskEventsResponse(BaseModel):
    found: bool
    events: list[AiTaskEvent]
    tool_calls: list[AiToolCall]


class AiTaskCreateResponse(BaseModel):
    task_id: str
    status: AiTaskStatus
    stage: str
    progress_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = ""
    result: JsonPayload | None = None


class AiTaskCreateRequest(BaseModel):
    task_type: str = Field(..., min_length=1, max_length=80)
    stage: str = Field(..., min_length=1, max_length=80)
    message: str = ""
    request: JsonPayload = Field(default_factory=dict)


class ReportTaskRequest(BaseModel):
    report_type: Literal["weekly", "monthly", "yearly"]
    action: Literal["cache_only", "generate"] = "cache_only"
    force: bool = False
    week_start: str | None = None
    week_end: str | None = None
    month: str | None = None
    year: int | None = None
    min_ms: int = Field(default=30000, ge=0)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)

    @model_validator(mode="after")
    def validate_report_period(self) -> ReportTaskRequest:
        if self.report_type == "weekly" and (not self.week_start or not self.week_end):
            raise ValueError("weekly report requires week_start and week_end")
        if self.report_type == "monthly" and (not self.month or self.year is None):
            raise ValueError("monthly report requires month and year")
        if self.report_type == "yearly" and self.year is None:
            raise ValueError("yearly report requires year")
        return self


class ChatAgentTaskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    conversation_history: list[dict[str, str]] | None = None
    thinking_mode: bool = False
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=1, ge=1, le=3)


class ArtistEnrichmentTaskRequest(BaseModel):
    artist_name: str = Field(..., min_length=1, max_length=300)


class AlbumEnrichmentTaskRequest(BaseModel):
    album_name: str = Field(..., min_length=1, max_length=300)
    artist_name: str = Field(..., min_length=1, max_length=300)
