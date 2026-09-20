"""Default lifetime analysis publications, built only by controlled maintenance."""

from __future__ import annotations

import json
import logging
from datetime import date

from backend.core.access_surface import public_readonly_db_guard_active, snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.domains.settings.repository import SettingsRepository
from backend.services import analysis_snapshot_store as store
from backend.services.analysis_snapshot_revision import database_identity, source_revision

logger = logging.getLogger(__name__)
JOB_TYPE = "analysis_snapshot_rebuild"
VERSIONS = {"analysis_stats": "analysis_stats_taste_v1", "analysis_records": "analysis_records_v1"}
AUTOMATIC_PERIODS = ("lifetime", "last_4_weeks", "last_6_months")


def default_params(conn, family):
    settings = SettingsRepository(conn).load_all()
    params = {
        k: settings[k] for k in ("min_ms", "music_only", "merge_enabled", "max_merge_gap_minutes")
    }
    params.update(period="lifetime", start_date=None, end_date=None, dynamic_threshold=True)
    if family == "analysis_records":
        params.update(merge_level=2, include_compilations=False)
    return params


def request_context(conn, family, params):
    from backend.services.analysis_records_service import PLAYBACK_RECORDS_SORT_CONTRACT_VERSION
    from backend.services.analysis_stats_service import PERIOD_LABELS

    version = VERSIONS[family]
    resolved = default_params(conn, family)
    resolved.update(params)
    if resolved["period"] not in PERIOD_LABELS:
        resolved["period"] = "lifetime"
    if resolved["max_merge_gap_minutes"] is None:
        resolved["max_merge_gap_minutes"] = default_params(conn, family)["max_merge_gap_minutes"]
    if resolved["period"] == "lifetime":
        resolved["start_date"] = resolved["end_date"] = None
    elif resolved["period"] == "custom":
        if not resolved.get("start_date") or not resolved.get("end_date"):
            raise ValueError("Custom analysis publications require both dates")
        start = date.fromisoformat(str(resolved["start_date"]))
        end = date.fromisoformat(str(resolved["end_date"]))
        if start > end:
            raise ValueError("Custom analysis publication start date is after end date")
        resolved["start_date"], resolved["end_date"] = start.isoformat(), end.isoformat()
    else:
        resolved["start_date"] = resolved["end_date"] = None
    for k in ("min_ms", "max_merge_gap_minutes", "merge_level"):
        if k in resolved:
            resolved[k] = int(resolved[k])
    for k in ("music_only", "merge_enabled", "dynamic_threshold", "include_compilations"):
        if k in resolved:
            resolved[k] = bool(resolved[k])
    key = store.digest(
        {
            "family": family,
            "identity": database_identity(conn),
            "params": resolved,
            "scope": {
                "period": resolved["period"],
                "start": resolved["start_date"],
                "end": resolved["end_date"],
            },
            "builder": version,
            "sort": PLAYBACK_RECORDS_SORT_CONTRACT_VERSION
            if family == "analysis_records"
            else None,
        }
    )
    return resolved, key, source_revision(conn, family), version


def read_snapshot(conn, family, **params):
    from backend.services.analysis_stats_service import PERIOD_LABELS

    if params.get("period", "lifetime") not in PERIOD_LABELS:
        params["period"] = "lifetime"
    if not store.path().is_file():
        raise snapshot_unavailable(family)
    revision = None
    try:
        _, key, revision, version = request_context(conn, family, params)
        found = store.read(family, key, revision, version)
        if found:
            payload, row = found
            exact = row["source_revision"] == revision
            return {
                **payload,
                "snapshot": {
                    "status": "ready" if exact else "warming",
                    "freshness": "current" if exact else "last_known_good",
                    "source_revision": row["source_revision"],
                    "target_revision": revision,
                    "builder_version": version,
                    "request_key": key,
                },
            }
    except Exception:
        logger.exception("Analysis publication cannot be read: %s", family)
    unavailable = snapshot_unavailable(family, revision)
    unavailable.detail["message"] = "当前范围的数据正在准备，请稍后再试。"
    raise unavailable


def rebuild(family: str, params_json: str, request_key: str, target_revision: str):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build analysis snapshots")
    conn = get_db(readonly=True)
    try:
        params, key, revision, _ = request_context(conn, family, json.loads(params_json))
        if (key, revision) != (request_key, target_revision):
            raise ValueError("Analysis source fence changed before build")
    finally:
        conn.close()
    return _rebuild_once(family, json.dumps(params, sort_keys=True), key, revision)


@singleflight
def _rebuild_once(family: str, params_json: str, request_key: str, target_revision: str):
    """Primitive per-key singleflight; followers recheck exact after the lock."""
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build analysis snapshots")
    conn = get_db(readonly=True)
    try:
        params, key, revision, version = request_context(conn, family, json.loads(params_json))
        if (key, revision) != (request_key, target_revision):
            raise ValueError("Analysis source fence changed before build")
        found = store.read(family, key, revision, version)
        if found and found[1]["source_revision"] == revision:
            return {"published": False, "exact": True}
        if family == "analysis_stats":
            from backend.services.analysis_stats_service import _build_analysis_stats

            payload = _build_analysis_stats(conn, **params)
        else:
            from backend.services.analysis_records_service import _get_analysis_records_uncached

            payload = _get_analysis_records_uncached(conn, **params)
        # Validate the complete API contract before any publication transaction.
        from backend.models.analysis import AnalysisStatsResponse, PlaybackRecordsResponse

        model = AnalysisStatsResponse if family == "analysis_stats" else PlaybackRecordsResponse
        model.model_validate(payload)
        if source_revision(conn, family) != revision:
            raise ValueError("Analysis source fence changed during build")
        store.publish(family, key, revision, version, payload)
        return {"published": True, "exact": True}
    finally:
        conn.close()


def prepare_snapshot(family: str, params: dict, *, queue=None):
    """Explicit private maintenance entrypoint for one normalized range."""
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot prepare analysis snapshots")
    if family not in VERSIONS:
        raise ValueError("Unknown analysis snapshot family")
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            raise ValueError("Analysis queue database does not match the request database")
        resolved, key, revision, version = request_context(conn, family, params)
        found = store.read(family, key, revision, version)
        if found and found[1]["source_revision"] == revision:
            return {
                "status": "ready",
                "family": family,
                "request_key": key,
                "target_revision": revision,
                "job_id": None,
            }
        job_id = _enqueue(family, key, json.dumps(resolved, sort_keys=True), queue)
        return {
            "status": "queued",
            "family": family,
            "request_key": key,
            "target_revision": revision,
            "job_id": job_id,
        }
    finally:
        conn.close()


def enqueue_defaults(reason: str, *, queue=None):
    if public_readonly_db_guard_active():
        return []
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            return []
        jobs = []
        for family in VERSIONS:
            for period in AUTOMATIC_PERIODS:
                params, key, revision, version = request_context(conn, family, {"period": period})
                found = store.read(family, key, revision, version)
                if found and found[1]["source_revision"] == revision:
                    continue
                job_id = _enqueue(family, key, json.dumps(params, sort_keys=True), queue)
                if job_id:
                    jobs.append(job_id)
                    logger.info(
                        "Analysis maintenance queued: family=%s period=%s reason=%s",
                        family,
                        period,
                        reason,
                    )
        return jobs
    finally:
        conn.close()


@singleflight
def _enqueue(family, key, params_json, queue):
    # The queue check+insert needs serialization among caller threads. The
    # lock covers only this normalized key, never the computation itself.
    return queue.enqueue_if_not_pending(Job.create(JOB_TYPE, family, key, params_json=params_json))


def handle_rebuild(job):
    conn = get_db(readonly=True)
    try:
        params, key, revision, _ = request_context(
            conn, job.entity_type, json.loads(job.payload["params_json"])
        )
    finally:
        conn.close()
    rebuild(job.entity_type, json.dumps(params, sort_keys=True), key, revision)
