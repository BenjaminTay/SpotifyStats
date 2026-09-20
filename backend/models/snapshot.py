"""Read status for published Home and Billboard snapshots."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SnapshotReadState(BaseModel):
    status: Literal["ready", "warming"]
    freshness: Literal["current", "last_known_good"]
    source_revision: str | None = None
    target_revision: str


class SnapshotUnavailableDetail(BaseModel):
    error: Literal["snapshot_unavailable"] = "snapshot_unavailable"
    status: Literal["unavailable"] = "unavailable"
    family: str
    target_revision: str | None = None
    message: str = "当前范围的数据暂时不可用。"


class SnapshotUnavailableResponse(BaseModel):
    detail: SnapshotUnavailableDetail


class SnapshotPrepareResponse(BaseModel):
    status: Literal["ready", "queued"]
    family: str
    request_key: str
    target_revision: str
    job_id: str | None = None
