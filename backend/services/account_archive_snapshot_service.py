"""Private Archive maintenance and side-effect-free published family reads."""

from __future__ import annotations

import fcntl
import json
import logging

from backend.core.access_surface import public_readonly_db_guard_active, snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.domains.account_archive import snapshot_store as store
from backend.domains.account_archive.context import (
    _fingerprint,
    build_archive_filter_context,
    resolve_archive_filters,
)
from backend.domains.account_archive.snapshot_revision import FAMILIES, family_revision
from backend.services.analysis_snapshot_revision import database_identity
from backend.services.analysis_snapshot_store import digest

logger = logging.getLogger(__name__)
JOB_TYPE = "account_archive_snapshot_rebuild"
BUILDER_VERSION = "archive_shared_events_v1"
PUBLICATION_VERSION = "archive_result_v1"


def request_key(conn, family, params):
    return digest(
        {
            "namespace": database_identity(conn),
            "family": family,
            "filter_fingerprint": _fingerprint({} if family == "overview" else params),
            "builder": BUILDER_VERSION,
            "publication": PUBLICATION_VERSION,
        }
    )


def read(conn, family, filters=None):
    revision = None
    try:
        if not store.path().is_file():
            raise snapshot_unavailable("account_archive")
        params = resolve_archive_filters(conn, filters or {})
        key = request_key(conn, family, params)
        revision = family_revision(conn, family)
        loaded = store.read(family, key)
        if loaded is None:
            error = snapshot_unavailable("account_archive", revision)
            if store.failed_revision(family, key) == revision:
                error.detail["message"] = "音乐档案构建失败，请检查本地重建任务后重新读取。"
            raise error
        payload, row = loaded
        exact = row["revision"] == revision and not row["fallback"]
        return {
            **payload,
            "snapshot": {
                "status": "ready" if exact else "warming",
                "freshness": "current" if exact else "last_known_good",
                "source_revision": row["revision"],
                "target_revision": revision,
                "request_key": key,
                "builder_version": BUILDER_VERSION,
                "build_status": "failed"
                if row["failed_revision"] == revision
                else ("ready" if exact else "pending"),
            },
        }
    except (OSError, ValueError, store.sqlite3.Error):
        logger.exception("Archive publication unavailable")
        raise snapshot_unavailable("account_archive", revision) from None


def _targets(conn, params, families):
    return [(f, request_key(conn, f, params), family_revision(conn, f)) for f in families]


def _pending(targets):
    result = []
    for family, key, revision in targets:
        loaded = store.read(family, key)
        if loaded is None or loaded[1]["revision"] != revision or loaded[1]["fallback"]:
            result.append((family, key, revision))
    return result


def ensure(conn, filters=None, families=None):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build Archive")
    params = resolve_archive_filters(conn, filters or {})
    families = tuple(families or FAMILIES)
    if not set(families).issubset(FAMILIES):
        raise ValueError("Unknown Archive family")
    namespace = database_identity(conn)
    lock_path = store.path().with_suffix(".build.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _ensure_once(digest(namespace), json.dumps(params, sort_keys=True), families)


@singleflight
def _ensure_once(namespace, params_json, families):
    conn = get_db(readonly=True)
    try:
        if digest(database_identity(conn)) != namespace:
            raise ValueError("Archive database namespace changed")
        params = json.loads(params_json)
        targets = _pending(_targets(conn, params, families))
        if not targets:
            return {"published": [], "event_builds": 0}
        from backend.domains.account_archive.cohorts import build_collection_cohorts
        from backend.domains.account_archive.discovery import build_archive_discovery
        from backend.domains.account_archive.event_facts import ArchiveEventFacts
        from backend.domains.account_archive.journey import build_collection_journey
        from backend.domains.account_archive.other_media import build_archive_other_media
        from backend.domains.account_archive.overview import build_archive_overview
        from backend.domains.account_archive.returns import build_archive_returns

        builders = {
            "cohorts": build_collection_cohorts,
            "returns": build_archive_returns,
            "discovery": build_archive_discovery,
            "journey": build_collection_journey,
            "other_media": build_archive_other_media,
        }
        settings = resolve_archive_filters(conn, {})
        facts = None
        results = []
        try:
            for family, key, revision in targets:
                if family == "overview":
                    payload = build_archive_overview(conn, data_revision=revision)
                else:
                    context = build_archive_filter_context(conn, params, family=family)
                    if family in {"cohorts", "returns", "discovery"}:
                        if facts is None:
                            facts = ArchiveEventFacts(conn, context)
                        payload = builders[family](conn, context, facts=facts)
                    else:
                        payload = builders[family](conn, context)
                results.append((family, key, revision, payload))

            def fence():
                if (
                    _targets(conn, params, [r[0] for r in targets]) != targets
                    or resolve_archive_filters(conn, {}) != settings
                ):
                    raise ValueError("Archive source/config changed during build")

            store.publish(results, fence)
            return {
                "published": [t[0] for t in targets],
                "event_builds": int(facts is not None and "frame" in facts.__dict__),
            }
        except Exception:
            store.mark_failed(targets)
            raise
    finally:
        conn.close()


def enqueue_defaults(reason, *, queue=None):
    if public_readonly_db_guard_active():
        return []
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            return []
        params = resolve_archive_filters(conn, {})
        targets = _pending(_targets(conn, params, FAMILIES))
        if not targets:
            return []
        # A retry re-resolves desired state; no stale revision is frozen into the job.
        key = digest({"namespace": database_identity(conn), "params": params})
        job = queue.enqueue_if_not_pending(
            Job.create(JOB_TYPE, "account_archive", key, reason=reason)
        )
        return [job] if job else []
    finally:
        conn.close()


def handle_rebuild(job):
    conn = get_db(readonly=True)
    try:
        return ensure(conn)
    finally:
        conn.close()
