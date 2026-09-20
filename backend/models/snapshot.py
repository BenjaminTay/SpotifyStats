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
    message: str = "当前筛选的数据尚未发布，请稍后重试。"


class SnapshotUnavailableResponse(BaseModel):
    detail: SnapshotUnavailableDetail
