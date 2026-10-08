"""Exact, compact personal ranks built by bounded private maintenance only."""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache

import pandas as pd

from backend.core.access_surface import public_readonly_db_guard_active, snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.db import get_db, load_plays_uncached
from backend.core.job_queue import (
    Job,
    PendingTargetCapacityError,
    get_job_queue,
    queue_targets_connection,
)
from backend.services import analysis_snapshot_store as store
from backend.services.analysis_snapshot_revision import database_identity

FAMILY = "entity_rank_context"
CUSTOM_FAMILY = "entity_rank_context_custom"
VERSION = "entity_rank_context_v2"
JOB_TYPE = "versus_rank_context_rebuild"
MAX_CUSTOM_PENDING_TARGETS = 4
PERIODS = ("lifetime", "last_6_months", "last_4_weeks")
KINDS = ("track", "album", "artist")
LOAD_FILTERS = (
    "min_ms",
    "music_only",
    "merge_enabled",
    "dynamic_threshold",
    "max_merge_gap_minutes",
)
RANK_COLUMNS = (
    "track_id",
    "track_name",
    "artist_name",
    "album_name",
    "album_id",
    "source_album_id",
    "ts",
    "ts_date",
    "ms_played",
)
RANK_SOURCE_COLUMNS = (
    "p.play_id, p.track_id, p.ts, p.ts_date, p.ms_played, p.source_album_id, "
    "t.track_name, t.album_id AS album_id, t.album_id AS track_album_id, "
    "t.artist_id, a.artist_name, al.album_name, stm.duration_ms"
)


def _rank_loader(conn, **params):
    return load_plays_uncached(conn, columns=RANK_SOURCE_COLUMNS, **params)


def _artist_rank_loader(conn, **params):
    # Effective credits provide artist_id after fan-out.
    columns = RANK_SOURCE_COLUMNS.replace("t.artist_id, ", "")
    return load_plays_uncached(conn, columns=columns, for_artists=True, **params)


def _rank_frame(frame):
    narrowed = frame.loc[:, [column for column in RANK_COLUMNS if column in frame.columns]].copy()
    narrowed.attrs = {}
    return narrowed


def default_configurations(conn):
    from backend.services.versus_personal_context import normalise_filters

    base = normalise_filters(conn, {})
    return [
        {**base, "merge_level": level, "dynamic_threshold": dynamic}
        for level in (2, 3)
        for dynamic in (True, False)
    ]


def request_context(conn, filters=None):
    from backend.services.versus_personal_context import context, normalise_filters

    params = normalise_filters(conn, filters or {})
    metadata = context(conn, params)
    family = FAMILY if params in default_configurations(conn) else CUSTOM_FAMILY
    key = store.digest({"database": database_identity(conn), "params": params, "version": VERSION})
    return params, key, metadata, family


def _filter_slices(slices, resolved):
    frame = slices
    for name, operation in (("start_date", "ge"), ("end_date", "le")):
        if resolved.get(name) and not frame.empty:
            values = frame["ts_date"].astype(str)
            mask = (
                values.ge(str(resolved[name]))
                if operation == "ge"
                else values.le(str(resolved[name]))
            )
            frame = frame.loc[mask]
    return frame


def _rank_map(conn, events, duration, kind, params):
    from backend.services.analysis_stats_service import _chart_agg, _sort_chart_rows

    agg = _chart_agg(
        events,
        kind,
        conn=conn,
        merge_level=params["merge_level"],
        include_compilations=params["include_compilations"],
        duration_frame=duration,
    )
    if agg.empty:
        return {}
    agg = agg.loc[pd.to_numeric(agg["plays"], errors="coerce").fillna(0) > 0]
    if agg.empty:
        return {}
    if kind == "album" and params["merge_level"] <= 1:
        # Explicit private L1 configurations retain public chart eligibility.
        from backend.domains.playback.album_type import is_album_chart_eligible
        from backend.services.analysis_stats_service import _resolve_album_category

        categories = [
            _resolve_album_category(conn, a, b)
            for a, b in zip(agg["album_name"], agg["artist_name"])
        ]
        mask = [
            is_album_chart_eligible(c) and (params["include_compilations"] or c != "compilation")
            for c in categories
        ]
        agg = agg.loc[mask]
    ordered = _sort_chart_rows(agg, kind, "plays")
    column = {
        "track": "track_id",
        "album": "album_project_id" if params["merge_level"] > 1 else "album_id",
        "artist": "artist_name",
    }[kind]
    # setdefault matches the legacy track ID consumer when rare presentations
    # split one ID into multiple chart rows. Do not replace its first rank.
    result = {}
    for index, value in enumerate(ordered[column]):
        key = str(value) if kind == "artist" else str(int(value))
        result.setdefault(key, index + 1)
    return result


def build_payload(conn, filters=None):
    """Build complete rank maps without covers or display chart serialization."""
    from backend.services.analysis_stats_service import (
        build_duration_frame,
        filter_period_events,
        load_period_plays,
        resolve_period,
    )

    params, _, metadata, _ = request_context(conn, filters)
    loader_params = {key: params[key] for key in LOAD_FILTERS}
    events, _, _ = load_period_plays(
        conn,
        **loader_params,
        attach_duration_slices=False,
        reuse_unfiltered_frame=True,
        _loader=_rank_loader,
    )
    payload = {**metadata, "periods": {}, "ranks": {kind: {} for kind in KINDS}}
    # Count windows are shared by all kinds and stay anchored to source coverage.
    resolved_periods = {period: resolve_period(events, period, None, None) for period in PERIODS}
    from backend.domains.playback.logical_timeline import LISTENING_INTERVALS_COLUMN

    duration = _rank_frame(
        build_duration_frame(events, source_columns=(*RANK_COLUMNS, LISTENING_INTERVALS_COLUMN))
    )
    events = _rank_frame(events)
    for period, resolved in resolved_periods.items():
        selected = filter_period_events(events, resolved)
        selected_duration = duration if period == "lifetime" else _filter_slices(duration, resolved)
        payload["periods"][period] = resolved
        for kind in ("track", "album"):
            payload["ranks"][kind][period] = _rank_map(
                conn, selected, selected_duration, kind, params
            )
    # Release general frames before loading the canonical credit fan-out.
    del duration, selected, selected_duration, events
    artist_events, _, _ = load_period_plays(
        conn,
        **loader_params,
        attach_duration_slices=False,
        reuse_unfiltered_frame=True,
        _loader=_artist_rank_loader,
    )
    artist_duration = _rank_frame(
        build_duration_frame(
            artist_events, source_columns=(*RANK_COLUMNS, LISTENING_INTERVALS_COLUMN)
        )
    )
    artist_events = _rank_frame(artist_events)
    for period, resolved in resolved_periods.items():
        payload["ranks"]["artist"][period] = _rank_map(
            conn,
            filter_period_events(artist_events, resolved),
            artist_duration if period == "lifetime" else _filter_slices(artist_duration, resolved),
            "artist",
            params,
        )
    return payload


def _valid_payload(payload, metadata):
    if not isinstance(payload, dict) or any(
        payload.get(key) != value for key, value in metadata.items()
    ):
        return False
    periods = payload.get("periods")
    ranks = payload.get("ranks")
    if not isinstance(periods, dict) or not isinstance(ranks, dict):
        return False
    for period in PERIODS:
        if not isinstance(periods.get(period), dict) or periods[period].get("period") != period:
            return False
        for kind in KINDS:
            mapping = ranks.get(kind, {}).get(period) if isinstance(ranks.get(kind), dict) else None
            if not isinstance(mapping, dict) or any(
                not isinstance(k, str) or type(v) is not int or v < 1 for k, v in mapping.items()
            ):
                return False
    return True


@lru_cache(maxsize=8)
def _read_cached(family, key, revision, metadata_json, file_state):
    del file_state
    found = store.read(family, key, revision, VERSION)
    if (
        found is None
        or found[1]["source_revision"] != revision
        or not _valid_payload(found[0], json.loads(metadata_json))
    ):
        raise snapshot_unavailable(FAMILY, revision)
    return found


def read(conn, filters=None):
    try:
        _, key, metadata, family = request_context(conn, filters)
    except (sqlite3.Error, ValueError, RuntimeError):
        raise snapshot_unavailable(FAMILY) from None
    try:
        cache_path = store.path()
        stat = cache_path.stat()
        # Include WAL changes when a private maintenance tool uses WAL mode.
        wal = cache_path.with_name(cache_path.name + "-wal")
        wal_state = (wal.stat().st_mtime_ns, wal.stat().st_size) if wal.exists() else None
        state = (str(cache_path.resolve()), stat.st_ino, stat.st_mtime_ns, stat.st_size, wal_state)
        payload, row = _read_cached(
            family, key, metadata["source_revision"], json.dumps(metadata, sort_keys=True), state
        )
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        raise snapshot_unavailable(FAMILY, metadata["source_revision"])
    return payload, {
        "status": "ready",
        "freshness": "current",
        "source_revision": row["source_revision"],
        "target_revision": metadata["source_revision"],
        "builder_version": VERSION,
        "request_key": key,
    }


def read_personal_ranks(conn, kind, items, filters):
    from backend.services.versus_personal_context import (
        context,
        normalise_filters,
        resolve_selection,
    )

    params = normalise_filters(conn, filters)
    try:
        metadata = context(conn, params)
    except (sqlite3.Error, ValueError, RuntimeError):
        raise snapshot_unavailable(FAMILY) from None
    selected = resolve_selection(
        conn, kind, items, params["merge_level"], filters=params, metadata=metadata
    )
    payload, snapshot = read(conn, params)
    if any(payload.get(k) != v for k, v in metadata.items()):
        raise snapshot_unavailable(FAMILY, metadata["source_revision"])
    try:
        current_metadata = context(conn, params)
    except (sqlite3.Error, ValueError, RuntimeError):
        raise snapshot_unavailable(FAMILY) from None
    if current_metadata != metadata:
        raise snapshot_unavailable(FAMILY, current_metadata["source_revision"])
    entities = []
    for entity in selected:
        known = bool(entity.rank_key)
        entity_ranks = {
            period: payload["ranks"][kind][period].get(entity.rank_key) for period in PERIODS
        }
        found = known and any(value is not None for value in entity_ranks.values())
        entities.append(
            {
                "requested_key": entity.requested_key,
                "entity_key": entity.entity_key,
                "found": found,
                "status": "found" if found else "empty" if known else "unavailable",
                "ranks": entity_ranks if known else None,
            }
        )
    return {
        **metadata,
        "periods": payload["periods"],
        "snapshot": snapshot,
        "entities": entities,
    }


def ensure(conn, filters=None):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build personal ranks")
    params, key, metadata, family = request_context(conn, filters)
    return _ensure(
        json.dumps(params, sort_keys=True), key, metadata["source_revision"], family, conn
    )


@singleflight(key_fn=lambda args, kwargs: args[:4])
def _ensure(params_json, key, revision, family, conn):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build personal ranks")
    params, actual_key, metadata, actual_family = request_context(conn, json.loads(params_json))
    if (actual_key, metadata["source_revision"], actual_family) != (key, revision, family):
        raise ValueError("Personal rank source changed before publication")
    found = store.read(family, key, revision, VERSION)
    if (
        found is not None
        and found[1]["source_revision"] == revision
        and _valid_payload(found[0], metadata)
    ):
        return {"published": False, "exact": True, "request_key": key}
    payload = build_payload(conn, params)
    if request_context(conn, params)[1:] != (key, metadata, family):
        raise ValueError("Personal rank source changed during publication")
    if not _valid_payload(payload, metadata):
        raise ValueError("Invalid personal rank publication")
    store.publish(family, key, revision, VERSION, payload)
    return {"published": True, "exact": True, "request_key": key}


def export_publication(conn, filters=None):
    """Portable payload; installer must recheck semantic source and local key."""
    params, key, metadata, family = request_context(conn, filters)
    payload, _ = read(conn, params)
    if any(payload.get(name) != value for name, value in metadata.items()):
        raise snapshot_unavailable(FAMILY, metadata["source_revision"])
    return {
        "family": family,
        "builder_version": VERSION,
        "filters": params,
        **metadata,
        "origin_request_key": key,
        "payload_digest": store.digest(payload),
        "payload": payload,
    }


def prepare_snapshot(filters=None, *, queue=None):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot prepare personal ranks")
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            raise ValueError("Personal rank queue targets a different database")
        params, key, metadata, family = request_context(conn, filters)
        found = store.read(family, key, metadata["source_revision"], VERSION)
        if (
            found
            and found[1]["source_revision"] == metadata["source_revision"]
            and _valid_payload(found[0], metadata)
        ):
            return {"status": "ready", "request_key": key, "job_id": None}
        options = (
            {"max_pending_targets": MAX_CUSTOM_PENDING_TARGETS} if family == CUSTOM_FAMILY else {}
        )
        try:
            job_id = queue.enqueue_if_not_pending(
                Job.create(JOB_TYPE, family, key, params_json=json.dumps(params, sort_keys=True)),
                **options,
            )
        except PendingTargetCapacityError:
            return {"status": "deferred", "request_key": key, "job_id": None}
        return {"status": "queued", "request_key": key, "job_id": job_id}
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
        variants = default_configurations(conn)
    finally:
        conn.close()
    results = [prepare_snapshot(params, queue=queue) for params in variants]
    return [result["job_id"] for result in results if result["job_id"]]


def handle_rebuild(job):
    conn = get_db(readonly=True)
    try:
        return ensure(conn, json.loads(job.payload["params_json"]))
    finally:
        conn.close()
