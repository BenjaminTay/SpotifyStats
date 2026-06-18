"""Background job status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.core.db import get_db
from backend.models.common import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """Return the status of a background job."""
    conn = get_db()
    row = conn.execute(
        "SELECT job_id, job_type, entity_type, entity_id, status, created_at, updated_at, error "
        "FROM background_jobs WHERE job_id = ?",
        [job_id],
    ).fetchone()
    conn.close()
    if not row:
        return {"found": False}
    return {
        "found": True,
        "job_id": row["job_id"],
        "job_type": row["job_type"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "error": row["error"],
    }
