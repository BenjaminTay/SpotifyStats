"""Private publication of shared artist ranks using the existing Analysis store."""

from __future__ import annotations

import json
from collections import Counter

from backend.core.access_surface import public_readonly_db_guard_active, snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.db import get_db, load_plays_for_artists
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.services import analysis_snapshot_store as store
from backend.services.analysis_snapshot_revision import database_identity
from backend.services.analysis_snapshot_service import default_params

FAMILY = "artist_rank_context"
VERSION = "artist_rank_context_v1"
JOB_TYPE = "artist_rank_context_rebuild"
PERIODS = ("lifetime", "last_6_months", "last_4_weeks")


def context(conn, filters=None):
    from backend.domains.account_archive.snapshot_revision import RELATIONSHIPS, revision_vector
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import get_track_credit_revision
    from backend.services.entity_stats_service import _entity_stats_revision_state

    params = default_params(conn, "analysis_stats")
    params.update(filters or {})
    for name in ("period", "start_date", "end_date"):
        params.pop(name, None)
    if params["max_merge_gap_minutes"] is None:
        params["max_merge_gap_minutes"] = default_params(conn, "analysis_stats")[
            "max_merge_gap_minutes"
        ]
    key = store.digest({"database": database_identity(conn), "params": params, "version": VERSION})
    if (
        conn.execute("SELECT 1 FROM music_search_revision_state WHERE state_id=1").fetchone()
        is None
    ):
        raise snapshot_unavailable(FAMILY)
    revision = store.digest(
        {
            "entity": _entity_stats_revision_state(conn),
            "artist_identity": get_identity_revision(conn),
            "track_credits": get_track_credit_revision(conn),
            "source": revision_vector(conn, RELATIONSHIPS),
        }
    )
    return params, key, revision


def read(conn, filters):
    _, key, revision = context(conn, filters)
    found = store.read(FAMILY, key, revision, VERSION)
    if found is None or found[1]["source_revision"] != revision:
        raise snapshot_unavailable(FAMILY, revision)
    return found[0]


def ensure(conn, filters=None):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build rank context")
    params, key, revision = context(conn, filters)
    return _ensure(json.dumps(params, sort_keys=True), key, revision)


@singleflight
def _ensure(params_json, key, revision):
    from backend.services.analysis_stats_service import (
        build_duration_frame,
        chart_rows,
        filter_period_events,
        load_period_plays,
        resolve_period,
    )

    conn = get_db(readonly=True)
    try:
        params, current_key, current_revision = context(conn, json.loads(params_json))
        if (current_key, current_revision) != (key, revision):
            raise ValueError("Rank source changed before publication")
        found = store.read(FAMILY, key, revision, VERSION)
        if found is not None and found[1]["source_revision"] == revision:
            return {"published": False}
        all_df, _, _ = load_period_plays(
            conn, **params, attach_duration_slices=False, _loader=load_plays_for_artists
        )
        payload = {"periods": {}, "ranks": {}, "top250_counts": {}}
        for period in PERIODS:
            resolved = resolve_period(all_df, period, None, None)
            frame = filter_period_events(all_df, resolved)
            duration = build_duration_frame(all_df, resolved)
            _, artists = chart_rows(
                conn, frame, "artist", "plays", None, 0, duration_frame=duration
            )
            _, tracks = chart_rows(
                conn,
                frame,
                "track",
                "plays",
                250,
                0,
                duration_frame=build_duration_frame(frame, resolved),
            )
            payload["periods"][period] = resolved
            payload["ranks"][period] = {row["artist_name"]: row["rank"] for row in artists}
            payload["top250_counts"][period] = dict(
                Counter(row.get("artist_name") for row in tracks)
            )
        if "_logical_event_id" in all_df.columns:
            ids = (
                all_df.sort_values("ts", ascending=False)
                .drop_duplicates("_logical_event_id")
                .head(50)["_logical_event_id"]
            )
            recent = all_df[all_df["_logical_event_id"].isin(set(ids))]
            counts = recent.groupby("artist_name")["_logical_event_id"].nunique()
        else:
            counts = (
                all_df.sort_values("ts", ascending=False).head(50).groupby("artist_name").size()
            )
        payload["recent_50_counts"] = {name: int(count) for name, count in counts.items()}
        if context(conn, params)[1:] != (key, revision):
            raise ValueError("Rank source changed during publication")
        store.publish(FAMILY, key, revision, VERSION, payload)
        return {"published": True}
    finally:
        conn.close()


def enqueue_default(reason, *, queue=None):
    if public_readonly_db_guard_active():
        return []
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            return []
        _, key, revision = context(conn)
        found = store.read(FAMILY, key, revision, VERSION)
        if found is not None and found[1]["source_revision"] == revision:
            return []
        job = queue.enqueue_if_not_pending(Job.create(JOB_TYPE, FAMILY, key, reason=reason))
        return [job] if job else []
    finally:
        conn.close()


def handle_rebuild(job):
    conn = get_db(readonly=True)
    try:
        return ensure(conn)
    finally:
        conn.close()
