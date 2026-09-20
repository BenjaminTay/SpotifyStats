"""Read-only Community projections and private, revision-fenced maintenance."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from backend.core.access_surface import public_readonly_db_guard_active, snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.domains.community import snapshot_store as store
from backend.domains.community.snapshot_revision import source_revision
from backend.services.analysis_snapshot_revision import database_identity
from backend.services.analysis_snapshot_store import digest
from backend.services.billboard_snapshot_service import configured_billboard_filters

logger = logging.getLogger(__name__)
JOB_TYPE = "community_snapshot_rebuild"
BUILDER_VERSION = "community_rows_v1"
CONTENT_POLICY_VERSION = "completed_weeks_time_capsule_v1"


def context(conn, params):
    resolved = configured_billboard_filters(conn)
    resolved.update(params)
    if resolved["max_merge_gap_minutes"] is None:
        resolved["max_merge_gap_minutes"] = configured_billboard_filters(conn)[
            "max_merge_gap_minutes"
        ]
    key = digest(
        {
            "namespace": database_identity(conn),
            "params": resolved,
            "builder": BUILDER_VERSION,
            "policy": CONTENT_POLICY_VERSION,
        }
    )
    # Exact semantic digests support legacy sources without an import dataset digest.
    # data_version in the shared observer is only an invalidation hint, never a revision.
    revision = source_revision(conn)
    return resolved, key, revision


def enrich(conn, payloads):
    from backend.domains.community.accounts import ACCOUNT_BY_HANDLE
    from backend.domains.community.feed_helpers import _generate_metrics
    from backend.domains.community.feed_images import _enrich_post_images, load_page_cover_maps
    from backend.domains.community.post_types import CommunityPost

    posts = [CommunityPost(**p) for p in payloads]
    maps = load_page_cover_maps(conn, posts)
    for post in posts:
        _enrich_post_images(post, maps)
        acct = ACCOUNT_BY_HANDLE.get(post.account_handle, {})
        post.metrics = _generate_metrics(post.significance, str(acct.get("follower_tier", "mid")))
    return [asdict(p) for p in posts]


def read(conn, view, params, **filters):
    if not store.path().is_file():
        raise snapshot_unavailable("community")
    revision = None
    try:
        _, key, revision = context(conn, params)
        with store.reader(key) as (cache, row):
            if row is None:
                raise snapshot_unavailable("community", revision)
            generation = row["generation"]
            if view == "feed":
                result = store.feed(cache, generation, **filters)
                result["posts"] = enrich(conn, result["posts"])
            elif view == "trending":
                result = store.trending(cache, generation, **filters)
            elif view == "post":
                result = store.detail(cache, generation, filters["post_id"])
                if result is None:
                    from fastapi import HTTPException

                    raise HTTPException(404, "Post not found")
                enriched = enrich(conn, [result["post"], *result["replies"]])
                result = {"post": enriched[0], "replies": enriched[1:]}
                for reply in result["replies"]:
                    reply.pop("attached_list", None)  # existing reply projection
            else:
                raise ValueError("Unknown Community projection")
            exact = row["revision"] == revision
            result["snapshot"] = {
                "status": "ready" if exact else "warming",
                "freshness": "current" if exact else "last_known_good",
                "source_revision": row["revision"],
                "target_revision": revision,
                "request_key": key,
                "builder_version": BUILDER_VERSION,
                "build_status": "failed"
                if row["failed_revision"] == revision
                else ("ready" if exact else "pending"),
            }
            return result
    except (OSError, ValueError, store.sqlite3.Error):
        logger.exception("Community publication unavailable")
        raise snapshot_unavailable("community", revision) from None


def ensure(conn, params=None):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build Community")
    resolved, key, _ = context(conn, params or {})
    import fcntl

    lock_path = store.path().with_suffix(".build.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _ensure_once(key, json.dumps(resolved, sort_keys=True))


@singleflight
def _ensure_once(key, params_json):
    # Primitive key covers all revisions: late old jobs cannot overtake a new build.
    conn = get_db(readonly=True)
    try:
        params, current_key, revision = context(conn, json.loads(params_json))
        if key != current_key:
            raise ValueError("Community namespace changed")
        try:
            with store.reader(key) as (_, row):
                if row and row["revision"] == revision:
                    return {"published": False, "revision": revision}
        except (FileNotFoundError, store.sqlite3.OperationalError):
            pass
        from backend.domains.community.feed_generator import build_publication_posts

        settings = configured_billboard_filters(conn)

        def fence():
            if (
                context(conn, params)[1:] != (key, revision)
                or configured_billboard_filters(conn) != settings
            ):
                raise ValueError("Community source/config changed during build")

        try:
            posts = build_publication_posts(conn, **params)
            published = store.publish(key, revision, posts, fence)
            return {"published": published, "revision": revision, "posts": len(posts)}
        except Exception:
            store.mark_failed(key, revision)
            raise
    finally:
        conn.close()


def enqueue_defaults(reason, *, queue=None):
    return enqueue(None, queue=queue, default=True)


def enqueue(params, *, queue=None, default=False):
    if public_readonly_db_guard_active():
        return []
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            return []
        params, key, revision = context(conn, params or {})
        try:
            with store.reader(key) as (_, row):
                if row and row["revision"] == revision:
                    return []
        except (FileNotFoundError, store.sqlite3.OperationalError):
            pass
        job = queue.enqueue_if_not_pending(
            Job.create(
                JOB_TYPE,
                "community",
                key,
                params_json=json.dumps(params, sort_keys=True),
                default=default,
            )
        )
        return [job] if job else []
    finally:
        conn.close()


def handle_rebuild(job):
    conn = get_db(readonly=True)
    try:
        # Jobs represent desired maintenance, never an obsolete publication target.
        ensure(
            conn,
            configured_billboard_filters(conn)
            if job.payload.get("default")
            else json.loads(job.payload["params_json"]),
        )
    finally:
        conn.close()
