"""Bounded, read-only personal facts for a complete Versus selection.

The batch reconstructs one union of source tracks, including the preceding
eligible row in the actual import-stable timeline. Context rows establish run
boundaries only; they never contribute to a selected entity. Interval inference
uses left context and the complete same-track run, with no right-neighbour
clipping. Every selected source track is loaded for its complete lifetime.
"""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from time import perf_counter
from typing import Any

import pandas as pd

from backend.core.cache import singleflight
from backend.core.cache_manager import register_ttl
from backend.core.db import merge_consecutive_plays
from backend.domains.metadata.artist_identity import canonicalize_artist_frame
from backend.domains.metadata.track_credits import get_effective_track_credit_frame
from backend.domains.playback.counting import assign_logical_event_id, filter_effective_plays
from backend.domains.playback.logical_timeline import (
    _timestamp_ns,
    reconstruct_listening_intervals,
)


class _ResultCache:
    """Keep at most 128 tiny fact payloads, never source frames/connections."""

    def __init__(self):
        self.results: OrderedDict[tuple, dict] = OrderedDict()
        self.lock = RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self.lock:
            result = self.results.get(key)
            if result is None:
                self.misses += 1
            else:
                self.hits += 1
                self.results.move_to_end(key)
            return result

    def put(self, key, result):
        with self.lock:
            self.results[key] = deepcopy(result)
            self.results.move_to_end(key)
            while len(self.results) > 128:
                self.results.popitem(last=False)

    def selected_facts(self, key: tuple, entity_keys: set[str]) -> tuple[dict | None, dict]:
        """Reuse tiny exact facts from overlapping batches within the same budget."""
        found: dict[str, dict] = {}
        period = None
        with self.lock:
            for cached_key, payload in reversed(self.results.items()):
                if len(cached_key) != len(key) or cached_key[:-1] != key[:-1]:
                    continue
                for entity in payload["entities"]:
                    entity_key = entity["entity_key"]
                    if entity_key in entity_keys and entity_key not in found:
                        found[entity_key] = deepcopy(entity)
                        period = deepcopy(payload["period"])
                if found.keys() >= entity_keys:
                    break
        return period, found

    def cache_clear(self):
        with self.lock:
            self.results.clear()
            self.hits = self.misses = 0

    def cache_stats(self):
        with self.lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self.results),
                "maxsize": 128,
            }


_RESULT_CACHE = _ResultCache()
register_ttl("analysis", "versus_personal_stats", _RESULT_CACHE)


@dataclass(frozen=True)
class _BatchWork:
    key: tuple
    conn: sqlite3.Connection = field(compare=False, hash=False)
    kind: str = field(compare=False, hash=False)
    params: dict = field(compare=False, hash=False)
    selection: list = field(compare=False, hash=False)
    metadata: dict = field(compare=False, hash=False)
    timings: Any = field(default=None, compare=False, hash=False)


def _load_target_timeline(
    conn: sqlite3.Connection,
    source_track_ids: tuple[int, ...],
    filters: dict,
    timings: dict[str, float] | None = None,
    *,
    include_duration: bool = True,
    canonicalize_artists: bool = True,
    basic_event_projection: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read one union, then reconstruct counts and unthresholded listening.

    Do not use the global play-loader cache here: its implementation opens the
    configured database independently of the supplied connection and retains
    source frames. A batch owns these small frames only for its request.
    """
    started = perf_counter()
    if not source_track_ids:
        columns = ["track_id", "source_track_id", "representative_track_id", "ts_date"]
        empty = pd.DataFrame(columns=columns)
        return empty, empty.copy()
    placeholders = ",".join("?" for _ in source_track_ids)
    eligible = "AND prior.track_id IS NOT NULL" if filters["music_only"] else ""
    earlier_eligible = "AND earlier.track_id IS NOT NULL" if filters["music_only"] else ""
    identity_ready = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_external_ids'"
    ).fetchone()
    if identity_ready:
        identity_columns = """COALESCE(ls.l1_id, ll.l1_id, p.track_id) AS l1_id,
            COALESCE(ls.representative_track_id, ll.representative_track_id,
                     p.track_id) AS representative_track_id"""
        identity_joins = """
            LEFT JOIN track_l1_external_ids ext ON ext.provider='spotify'
              AND ext.external_track_id=COALESCE(NULLIF(p.spotify_track_id_at_play,''),
                                                NULLIF(src.spotify_track_id,''))
            LEFT JOIN track_l1_identities ls ON ls.l1_id=ext.l1_id
              AND ls.identity_status!='superseded'
            LEFT JOIN track_l1_identities ll ON ll.fallback_track_id=p.track_id
              AND ll.identity_status!='superseded'
              AND COALESCE(NULLIF(p.spotify_track_id_at_play,''),
                           NULLIF(src.spotify_track_id,'')) IS NULL
            LEFT JOIN tracks t ON t.track_id=COALESCE(ls.representative_track_id,
                                                     ll.representative_track_id,p.track_id)
        """
    else:
        identity_columns = "p.track_id AS l1_id, p.track_id AS representative_track_id"
        identity_joins = "LEFT JOIN tracks t ON t.track_id=p.track_id"
    # Keep source_fingerprint before play_id, exactly as the full-library
    # loader does. Equal timestamps in exports are not exceptional.
    sql = f"""
        WITH target AS (
            SELECT play_id, ts, COALESCE(source_fingerprint,'') AS fingerprint
            FROM plays WHERE track_id IN ({placeholders})
        ), selected AS (
            SELECT play_id FROM target
            UNION
            SELECT COALESCE(
                (SELECT prior.play_id FROM plays prior
                 WHERE prior.ts=target.ts
                   AND (COALESCE(prior.source_fingerprint,''),prior.play_id)
                       < (target.fingerprint,target.play_id)
                   {eligible}
                 ORDER BY COALESCE(prior.source_fingerprint,'') DESC,
                          prior.play_id DESC LIMIT 1),
                (SELECT prior.play_id FROM plays prior
                 WHERE prior.ts=(SELECT earlier.ts FROM plays earlier
                                 WHERE earlier.ts<target.ts {earlier_eligible}
                                 ORDER BY earlier.ts DESC LIMIT 1)
                   {eligible}
                 ORDER BY COALESCE(prior.source_fingerprint,'') DESC,
                          prior.play_id DESC LIMIT 1)
            )
            FROM target
        )
        SELECT p.play_id,p.ts,p.ts_date,p.ts_hour,p.ms_played,p.source_album_id,
               p.track_id AS source_track_id, {identity_columns},
               t.track_name, t.artist_id, t.album_id AS track_album_id,
               a.artist_name, al.album_name, stm.duration_ms
        FROM plays p
        LEFT JOIN tracks src ON src.track_id=p.track_id
        {identity_joins}
        LEFT JOIN artists a ON a.artist_id=t.artist_id
        LEFT JOIN albums al ON al.album_id=t.album_id
        LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id=
          COALESCE(NULLIF(p.spotify_track_id_at_play,''),NULLIF(src.spotify_track_id,''))
        WHERE p.play_id IN (SELECT play_id FROM selected)
        ORDER BY p.ts, COALESCE(p.source_fingerprint,''), p.play_id
    """
    raw = pd.read_sql_query(sql, conn, params=source_track_ids)
    _record_timing(timings, "target_sql", started)
    started = perf_counter()
    raw["track_id"] = raw["l1_id"]
    parsed_timestamp_ns = _timestamp_ns(raw["ts"]) if basic_event_projection else None
    durations = (
        reconstruct_listening_intervals(
            raw,
            identity_column="l1_id",
            max_gap_minutes=filters["max_merge_gap_minutes"],
            boundary_column="source_album_id",
            parsed_timestamp_ns=parsed_timestamp_ns,
        )
        if include_duration
        else pd.DataFrame()
    )
    events = raw
    if filters["merge_enabled"]:
        events = merge_consecutive_plays(
            raw,
            filters["min_ms"],
            max_gap_minutes=filters["max_merge_gap_minutes"],
            boundary_column="source_album_id",
            dynamic_threshold=filters["dynamic_threshold"],
            count_only=basic_event_projection,
            parsed_timestamp_ns=parsed_timestamp_ns,
        )
    events = filter_effective_plays(
        events, min_ms=filters["min_ms"], dynamic_threshold=filters["dynamic_threshold"]
    )
    if canonicalize_artists:
        events = canonicalize_artist_frame(events, conn, dedupe=False)
        if include_duration:
            durations = canonicalize_artist_frame(durations, conn, dedupe=False)
    _record_timing(timings, "timeline", started)
    return events, durations


def _record_timing(timings: dict[str, float] | None, name: str, started: float) -> None:
    if timings is not None:
        timings[name] = (perf_counter() - started) * 1000


def _artist_frames(
    conn: sqlite3.Connection,
    events: pd.DataFrame,
    durations: pd.DataFrame,
    artist_ids: set[int],
    selection: list | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fan out after event reconstruction, once, through effective credits."""
    representatives = set(events["representative_track_id"].dropna().astype(int))
    representatives.update(durations["representative_track_id"].dropna().astype(int))
    if selection is None:
        credits = get_effective_track_credit_frame(conn, sorted(representatives))
        credits = credits[credits["artist_id"].isin(artist_ids)].rename(
            columns={"track_id": "representative_track_id"}
        )
    else:
        # Selection resolution has already applied raw, Spotify, manual and
        # canonical credit policy. Reuse it; a second metadata scan cannot
        # improve these facts and used to dominate the artist cold path.
        credits = pd.DataFrame(
            [
                {
                    "representative_track_id": track_id,
                    "artist_id": item.artist_id,
                    "artist_name": item.artist_name,
                }
                for item in selection
                for track_id in item.credited_track_ids
                if track_id in representatives
            ],
            columns=["representative_track_id", "artist_id", "artist_name"],
        )
    events = assign_logical_event_id(events)

    def fan_out(frame: pd.DataFrame) -> pd.DataFrame:
        # Canonical credit frame already has one row per representative and
        # canonical artist, including aliases and manual overrides. Explicit
        # event IDs preserve expansion of one merged source into many plays.
        return frame.drop(
            columns=["artist_id", "artist_name", "raw_artist_id", "raw_artist_name"],
            errors="ignore",
        ).merge(
            credits[["representative_track_id", "artist_id", "artist_name"]],
            on="representative_track_id",
            how="inner",
        )

    return (
        fan_out(events).drop_duplicates(["_logical_event_id", "artist_id"]),
        fan_out(durations),
    )


def _metrics(events: pd.DataFrame, durations: pd.DataFrame) -> dict[str, Any]:
    """Use the same rounding and active-day denominator as personal details."""
    total_plays = int(len(events))
    total_hours = (
        round(float(durations["ms_played"].sum() / 3_600_000), 1) if not durations.empty else 0.0
    )
    active_days = int(durations["ts_date"].nunique()) if not durations.empty else 0
    denominator = max(active_days, 1)
    return {
        "total_plays": total_plays,
        "total_hours": total_hours,
        "active_days": active_days,
        "avg_daily_plays": round(total_plays / denominator, 2),
        "avg_daily_hours": round(total_hours / denominator, 2),
        "max_daily_plays": int(events.groupby("ts_date").size().max()) if not events.empty else 0,
    }


def _basic_duration_frame(durations: pd.DataFrame) -> pd.DataFrame:
    """Project exact lifetime hours and active dates without display slices.

    The union loader emits one inferred interval per raw positive row. Facts
    here need only its listened milliseconds and the set of local dates; hour
    labels, ISO timestamps and trend rows would be unused work. A zero-weight
    row records each additional active date. Sub-millisecond boundary rounding
    matches the existing hour-slice oracle, including zero-ms boundary pieces.
    """
    columns = [
        name
        for name in (
            "track_id",
            "source_track_id",
            "canonical_song_key",
            "artist_id",
            "ms_played",
            "ts_date",
        )
        if name in durations.columns
    ]
    out = durations.loc[:, columns].copy()
    if out.empty:
        return out
    starts = durations["interval_start_at"]
    ends = durations["interval_end_at"] - pd.Timedelta(1, unit="ns")
    local_starts = starts.dt.tz_convert("Asia/Shanghai").dt.normalize()
    local_ends = ends.dt.tz_convert("Asia/Shanghai").dt.normalize()
    out["ts_date"] = _date_labels(local_starts)
    start_ns = starts.astype("int64").to_numpy()
    end_ns = durations["interval_end_at"].astype("int64").to_numpy()
    crossed_hour = (end_ns - 1) // 3_600_000_000_000 > start_ns // 3_600_000_000_000
    fractional_start = start_ns % 1_000_000 != 0
    out["ms_played"] = out["ms_played"].to_numpy() - (crossed_hour & fractional_start).astype(
        "int64"
    )
    cross_day = local_starts != local_ends
    if not cross_day.any():
        return out
    extra = out.loc[cross_day].copy()
    extra["ts_date"] = _date_labels(local_ends.loc[cross_day])
    extra["ms_played"] = 0
    long_intervals = (local_ends - local_starts) > pd.Timedelta(days=1)
    intermediate = []
    for index in durations.index[long_intervals]:
        for date in pd.date_range(
            local_starts.loc[index] + pd.Timedelta(days=1),
            local_ends.loc[index] - pd.Timedelta(days=1),
            freq="D",
        ):
            intermediate.append(
                {**out.loc[index].to_dict(), "ts_date": date.strftime("%Y-%m-%d"), "ms_played": 0}
            )
    pieces = [out, extra]
    if intermediate:
        pieces.append(pd.DataFrame(intermediate))
    return pd.concat(pieces, ignore_index=True)


def _date_labels(dates: pd.Series) -> pd.Series:
    """Format each active local date once, retaining the source index."""
    unique = dates.drop_duplicates()
    labels = pd.Series(unique.dt.strftime("%Y-%m-%d").to_numpy(), index=unique)
    return dates.map(labels)


def _coverage_bounds(conn: sqlite3.Connection, music_only: bool) -> tuple:
    """Use existing date-index edges, with the same NULL rules as MIN/MAX."""
    where = "ts_date IS NOT NULL"
    if music_only:
        where += " AND track_id IS NOT NULL"
    bounds = []
    for order in ("ASC", "DESC"):
        row = conn.execute(
            f"SELECT ts_date FROM plays WHERE {where} ORDER BY ts_date {order} LIMIT 1"
        ).fetchone()
        bounds.append(row[0] if row is not None else None)
    return tuple(bounds)


def _album_song_frames(
    conn: sqlite3.Connection, events: pd.DataFrame, durations: pd.DataFrame, merge_level: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resolve one union of song identities for both listening tracks."""
    from backend.domains.playback.album_projects import apply_canonical_song_keys

    songs = pd.concat(
        [frame.reindex(columns=["track_id", "track_name"]) for frame in (events, durations)],
        ignore_index=True,
    ).drop_duplicates("track_id")
    keyed = apply_canonical_song_keys(songs, conn, merge_level)
    key_map = keyed.set_index("track_id")["canonical_song_key"]
    result = []
    for frame in (events, durations):
        out = frame.copy()
        out["canonical_song_key"] = out["track_id"].map(key_map)
        result.append(out)
    return result[0], result[1]


def _build_personal_stats_uncached(
    conn: sqlite3.Connection,
    kind: str,
    params: dict,
    resolved: list,
    result: dict,
    timings: dict[str, float] | None = None,
) -> dict:
    """Build all selected personal metrics without global facts or writes."""
    from backend.services.versus_personal_context import context

    source_ids = tuple(sorted({track_id for item in resolved for track_id in item.track_ids}))
    events, durations = (
        _load_target_timeline(
            conn,
            source_ids,
            params,
            timings,
            canonicalize_artists=kind != "artist",
            basic_event_projection=True,
        )
        if timings is not None
        else _load_target_timeline(
            conn,
            source_ids,
            params,
            canonicalize_artists=kind != "artist",
            basic_event_projection=True,
        )
    )
    started = perf_counter()
    events = events[events["source_track_id"].isin(source_ids)].copy()
    durations = durations[durations["source_track_id"].isin(source_ids)].copy()
    bounds = _coverage_bounds(conn, params["music_only"])
    period = {
        "period": "lifetime",
        "label": "全部时间",
        "start_date": str(bounds[0]) if bounds and bounds[0] is not None else None,
        "end_date": str(bounds[1]) if bounds and bounds[1] is not None else None,
    }
    # Lifetime represents the whole listening track. No count-qualified
    # boundaries may discard listened fragments at the coverage edges.
    if kind == "artist":
        events, durations = _artist_frames(
            conn,
            events,
            durations,
            {int(item.artist_id) for item in resolved if item.artist_id is not None},
            selection=resolved,
        )
    elif kind == "album":
        events, durations = _album_song_frames(conn, events, durations, params["merge_level"])
    duration_slices = _basic_duration_frame(durations)
    _record_timing(timings, "attribution", started)
    started = perf_counter()
    entities = []
    for item in resolved:
        if not item.track_ids:
            # Known identity with no sources is a true empty listening history;
            # unresolved identity is unavailable, never a fabricated zero.
            known = bool(item.rank_key)
            entities.append(
                {
                    "requested_key": item.requested_key,
                    "entity_key": item.entity_key,
                    "status": "empty" if known else "unavailable",
                    "found": False,
                    "metrics": _metrics(events.iloc[:0], duration_slices.iloc[:0])
                    if known
                    else None,
                }
            )
            continue
        if kind == "artist":
            entity_events = events[events["artist_id"] == item.artist_id]
            entity_duration = duration_slices[duration_slices["artist_id"] == item.artist_id]
        elif kind == "album":
            entity_events = events[events["canonical_song_key"].isin(item.song_keys)]
            entity_duration = duration_slices[
                duration_slices["canonical_song_key"].isin(item.song_keys)
            ]
        else:
            from backend.domains.playback.track_groups import resolve_track_aggregation_scope

            scope = resolve_track_aggregation_scope(conn, item.track_id, params["merge_level"])
            entity_events = events[events["track_id"].isin(scope.member_track_ids)]
            entity_duration = duration_slices[
                duration_slices["track_id"].isin(scope.member_track_ids)
            ]
        found = not entity_events.empty or not entity_duration.empty
        entities.append(
            {
                "requested_key": item.requested_key,
                "entity_key": item.entity_key,
                "status": "found" if found else "empty",
                "found": found,
                "metrics": _metrics(entity_events, entity_duration),
            }
        )
    _record_timing(timings, "metrics", started)
    started = perf_counter()
    try:
        current = context(conn, params)
    except (ValueError, sqlite3.DatabaseError):
        from backend.core.access_surface import snapshot_unavailable

        raise snapshot_unavailable("versus_personal_stats") from None
    _record_timing(timings, "source_fence", started)
    if current != result:
        from backend.core.access_surface import snapshot_unavailable

        raise snapshot_unavailable("versus_personal_stats", current["source_revision"])
    return {**result, "period": period, "entities": entities}


@singleflight
def _cached_batch(work: _BatchWork) -> dict:
    cached = _RESULT_CACHE.get(work.key)
    if cached is not None:
        return cached
    period, ready = _RESULT_CACHE.selected_facts(
        work.key, {item.entity_key for item in work.selection}
    )
    missing = [item for item in work.selection if item.entity_key not in ready]
    if missing:
        result = _build_personal_stats_uncached(
            work.conn, work.kind, work.params, missing, work.metadata, work.timings
        )
        period = result["period"]
        ready.update({entity["entity_key"]: entity for entity in result["entities"]})
    result = {
        **work.metadata,
        "period": period,
        "entities": [ready[item.entity_key] for item in work.selection],
    }
    _RESULT_CACHE.put(work.key, result)
    return result


def build_personal_stats(
    conn: sqlite3.Connection,
    kind: str,
    items: list,
    filters: dict,
    *,
    timings: dict[str, float] | None = None,
) -> dict:
    """Normalize, resolve, and share only exact revision-keyed aggregate facts."""
    from backend.core.access_surface import snapshot_unavailable
    from backend.services.analysis_snapshot_revision import database_identity
    from backend.services.versus_personal_context import (
        context,
        normalise_filters,
        resolve_selection,
    )

    started = perf_counter()
    params = normalise_filters(conn, filters)
    try:
        metadata = context(conn, filters)
    except (ValueError, sqlite3.DatabaseError):
        raise snapshot_unavailable("versus_personal_stats") from None
    _record_timing(timings, "source_context", started)
    started = perf_counter()
    selection = resolve_selection(
        conn, kind, items, params["merge_level"], filters=params, metadata=metadata
    )
    _record_timing(timings, "identity", started)
    lineage = database_identity(conn)
    key = (
        lineage["device"],
        lineage["inode"],
        metadata["source_revision"],
        metadata["filter_fingerprint"],
        kind,
        tuple(sorted(item.entity_key for item in selection)),
    )
    payload = _cached_batch(_BatchWork(key, conn, kind, params, selection, metadata, timings))
    started = perf_counter()
    try:
        current = context(conn, filters)
    except (ValueError, sqlite3.DatabaseError):
        raise snapshot_unavailable("versus_personal_stats") from None
    _record_timing(timings, "source_fence", started)
    if current != metadata or payload["filter_fingerprint"] != metadata["filter_fingerprint"]:
        raise snapshot_unavailable("versus_personal_stats", current["source_revision"])
    result = deepcopy(payload)
    by_key = {entity["entity_key"]: entity for entity in result["entities"]}
    result["entities"] = [
        {**by_key[item.entity_key], "requested_key": item.requested_key} for item in selection
    ]
    return result
