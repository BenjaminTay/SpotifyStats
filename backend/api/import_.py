"""Import API — async import jobs for streaming and account data."""

import threading
import uuid

from fastapi import APIRouter, Depends

from backend.core.auth import require_auth
from backend.core.import_account_data import import_all
from backend.core.import_data import import_data
from backend.models.common import ImportJobCreateResponse, ImportJobStatus

router = APIRouter(prefix="/import", tags=["Import"])

# In-memory job store (single-user local app, no persistence needed)
_jobs = {}


def _make_job():
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "progress_pct": 0.0,
        "message": "初始化...",
        "result": None,
    }
    return job_id


def _progress_cb(job_id):
    def cb(message: str, pct: float):
        _jobs[job_id]["message"] = message
        _jobs[job_id]["progress_pct"] = pct

    return cb


@router.post("/streaming", response_model=ImportJobCreateResponse)
def start_streaming_import(auth: None = Depends(require_auth)):
    """Trigger streaming data import in the background."""
    job_id = _make_job()
    cb = _progress_cb(job_id)

    def _run():
        try:
            result = import_data(progress_callback=cb)
            from backend.core.cache_manager import invalidate_all

            invalidate_all()
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress_pct"] = 1.0
            _jobs[job_id]["message"] = "导入完成"
            _jobs[job_id]["result"] = {
                "files": result.get("files", 0),
                "records": result.get("records", 0),
                "artists": result.get("artists", 0),
                "albums": result.get("albums", 0),
                "tracks": result.get("tracks", 0),
            }
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["message"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@router.post("/account", response_model=ImportJobCreateResponse)
def start_account_import(auth: None = Depends(require_auth)):
    """Trigger account data import in the background."""
    job_id = _make_job()
    cb = _progress_cb(job_id)

    def _run():
        try:
            result = import_all(progress_callback=cb)
            from backend.core.cache_manager import invalidate_all

            invalidate_all()
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress_pct"] = 1.0
            _jobs[job_id]["message"] = "导入完成"
            # Simplify results: only keep summary keys, skip nested dicts
            summary = {}
            for k, v in result.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        if isinstance(sv, int) or isinstance(sv, str):
                            summary[f"{k}.{sk}"] = sv
                else:
                    summary[k] = str(v)
            _jobs[job_id]["result"] = summary
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["message"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@router.get("/status/{job_id}", response_model=ImportJobStatus)
def get_import_status(job_id: str):
    """Query the status of an import job."""
    job = _jobs.get(job_id)
    if not job:
        return {
            "job_id": job_id,
            "status": "not_found",
            "progress_pct": 0,
            "message": "Job not found",
        }
    return job
