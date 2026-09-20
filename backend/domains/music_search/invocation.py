"""Short-lived maintenance ownership and uncached logical frames for Search."""

from __future__ import annotations

import inspect
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from backend.core import db
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import get_track_credit_revision
from backend.domains.metadata.track_identity import get_track_identity_revision
from backend.domains.playback.logical_timeline import (
    attach_listening_duration_frame,
    get_listening_duration_frame,
)

_guard = threading.Lock()
_owners: dict[str, tuple[threading.Lock, int]] = {}


def database_namespace(conn: sqlite3.Connection) -> str:
    filename = next(str(row[2]) for row in conn.execute("PRAGMA database_list") if row[1] == "main")
    return str(Path(filename).resolve()) if filename else f"memory:{id(conn)}"


@contextmanager
def maintenance_owner(conn: sqlite3.Connection):
    """Serialize writers per database; waiters re-read the exact current set.

    Only locks are shared, never connections, frames or results. Reference
    counts include waiters so an exiting builder cannot split ownership.
    """
    namespace = database_namespace(conn)
    with _guard:
        lock, users = _owners.get(namespace, (threading.Lock(), 0))
        _owners[namespace] = lock, users + 1
    try:
        with lock:
            yield
    finally:
        with _guard:
            _, users = _owners[namespace]
            if users == 1:
                del _owners[namespace]
            else:
                _owners[namespace] = lock, users - 1


def attribution_dependencies_ready(conn: sqlite3.Connection) -> bool:
    from backend.domains.playback.l3_album_attribution import (
        L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
        _album_project_revision,
        get_l3_album_attribution_state,
    )

    state = get_l3_album_attribution_state(conn)
    return (
        state["status"] == "ready"
        and state["policy_version"] == L3_ALBUM_ATTRIBUTION_POLICY_VERSION
        and state["track_identity_revision"] == get_track_identity_revision(conn)
        and state["album_project_revision"] == _album_project_revision(conn)
        and bool(state["mapping_digest"])
        and not state["conflict_count"]
        and not state["uncovered_count"]
    )


# Keep the logical-event identity and interval evidence as well as every
# identity/date field consumed by metric and Billboard reducers. Platform,
# device and ingestion payloads are not part of these reducers.
_FRAME_COLUMNS = frozenset(
    {
        "track_id",
        "l1_id",
        "representative_track_id",
        "track_name",
        "artist_id",
        "artist_name",
        "album_name",
        "source_album_name",
        "source_album_id",
        "track_album_id",
        "album_id",
        "ts",
        "ts_date",
        "ms_played",
        "counted_at",
        "event_start_at",
        "event_end_at",
        "_listening_intervals_ns",
        "_logical_event_id",
        "_logical_event_ordinal",
        "play_count",
        "total_ms",
    }
)


def _compact_frame(frame: pd.DataFrame) -> pd.DataFrame:
    # Discard loader metadata; the duration frame is projected explicitly below.
    frame.attrs = {}
    return frame.loc[:, [column for column in frame.columns if column in _FRAME_COLUMNS]].copy()


def load_invocation_frames(conn, contexts, selected_kinds):
    """Use the existing logical loader once, without retaining its LRU/copy.

    These are lifetime contexts. Count qualification and inferred duration
    intervals still come from the canonical loader, not a Search algorithm.
    """
    if database_namespace(conn) != str(Path(db.DB_PATH).resolve()):
        raise RuntimeError("Search logical loader database namespace changed")
    context = contexts[0]
    if any(item.dynamic_threshold != context.dynamic_threshold for item in contexts):
        raise ValueError("invocation frames require one threshold")
    artists = selected_kinds == ("artist",)
    loader = db._load_plays_for_artists_cached if artists else db._load_plays_cached
    columns = (
        "p.play_id, p.track_id, p.ts, p.ms_played, p.source_album_id, "
        "t.track_name, t.spotify_track_uri, a.artist_name, al.album_name, stm.duration_ms"
    )
    if "ts_date" in {row[1] for row in conn.execute("PRAGMA table_info(plays)")}:
        columns += ", p.ts_date"
    if not artists:
        columns += (
            ", t.album_id AS track_album_id, t.artist_id, al_src.album_name AS source_album_name"
        )
    options = dict(
        min_ms=context.min_ms,
        music_only=context.music_only,
        merge_enabled=context.merge_enabled,
        filtered=True,
        join_albums=True,
        columns=columns,
        extra_where="",
        extra_params=(),
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
        boundary_column="source_album_id",
        track_identity_revision=get_track_identity_revision(conn),
    )
    if artists:
        options.update(
            identity_revision=get_identity_revision(conn),
            track_credit_revision=get_track_credit_revision(conn),
        )
    frame = inspect.unwrap(loader)(**options)
    duration = get_listening_duration_frame(frame)
    compact = _compact_frame(frame)
    if duration is not None:
        attach_listening_duration_frame(compact, _compact_frame(duration))
    empty = pd.DataFrame()
    return {context.dynamic_threshold: (empty, compact) if artists else (compact, empty)}


def build_invocation_full_fallback(conn, contexts):
    from backend.domains.music_search.snapshot import (
        _active_playback_generation,
        build_shared_full_music_search_snapshot_set,
    )
    from backend.domains.music_search.snapshot_lineage import (
        music_search_snapshot_dependency_digest,
    )

    # Narrow legacy/test schemas keep their existing compatibility builder.
    if database_namespace(conn) != str(Path(db.DB_PATH).resolve()):
        return None
    try:
        music_search_snapshot_dependency_digest(conn)
    except RuntimeError:
        return None
    return build_shared_full_music_search_snapshot_set(
        conn,
        contexts,
        source_generation_id=str(_active_playback_generation(conn) or ""),
        require_complete_weekly_ledger=True,
        invocation_fallback=True,
    )


def compact_album_facts(frame, *, weekly=False):
    """Sum weighted facts at the identity/day grain used by project membership.

    Day remains in weekly facts because release-date eligibility is daily,
    even when two days belong to the same Billboard week.
    """
    if frame.empty:
        return frame
    keys = ["track_id", "track_name", "artist_name"]
    if weekly:
        keys += ["billboard_week", "ts_date" if "ts_date" in frame else "ts"]
    keys = [key for key in keys if key in frame]
    return frame.groupby(keys, as_index=False, dropna=False, sort=False)[
        ["play_count", "total_ms"]
    ].sum()
