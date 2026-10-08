"""Shared, read-only identity and revision contract for personal comparisons."""

from __future__ import annotations

import json
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from backend.core.access_surface import snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.cache_manager import register_ttl
from backend.domains.metadata.artist_identity import get_identity_revision, resolve_artist_name
from backend.domains.metadata.track_credits import (
    TRACK_CREDIT_POLICY_VERSION,
    get_effective_track_credits,
    get_track_credit_revision,
)
from backend.domains.playback.album_project_identity import resolve_album_project_identity
from backend.domains.playback.logical_timeline import LISTENING_DURATION_POLICY_VERSION
from backend.domains.playback.track_groups import resolve_track_aggregation_scope
from backend.domains.settings.repository import SettingsRepository
from backend.services.analysis_snapshot_revision import (
    COMMON,
    RECORDS,
    _revision_vector,
    database_identity,
)
from backend.services.analysis_snapshot_store import digest

STATISTICS_CONTRACT_VERSION = "versus_personal_v1"


@dataclass(frozen=True)
class SelectedEntity:
    requested_key: str
    entity_key: str
    rank_key: str
    track_ids: tuple[int, ...] = ()
    track_id: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    artist_id: int | None = None
    project_id: int | None = None
    song_keys: tuple[str, ...] = ()
    credited_track_ids: tuple[int, ...] = ()


def normalise_filters(conn: sqlite3.Connection, filters: dict | None = None) -> dict:
    settings = SettingsRepository(conn).load_all()
    provided = filters or {}
    result = {
        name: provided.get(name, settings[name])
        for name in ("min_ms", "music_only", "merge_enabled", "max_merge_gap_minutes")
    }
    if result["max_merge_gap_minutes"] is None:
        result["max_merge_gap_minutes"] = settings["max_merge_gap_minutes"]
    result.update(
        dynamic_threshold=provided.get("dynamic_threshold", True),
        merge_level=provided.get("merge_level", 2),
        include_compilations=provided.get("include_compilations", settings["include_compilations"]),
    )
    for name in ("min_ms", "max_merge_gap_minutes", "merge_level"):
        result[name] = int(result[name])
    for name in ("music_only", "merge_enabled", "dynamic_threshold", "include_compilations"):
        result[name] = bool(result[name])
    if result["min_ms"] < 0 or not 1 <= result["max_merge_gap_minutes"] <= 240:
        raise ValueError("Invalid personal-statistics play filters")
    if result["merge_level"] not in (2, 3):
        raise ValueError("Personal comparisons support L2 and L3")
    return result


def context(conn: sqlite3.Connection, filters: dict | None = None, *, _attempt: int = 0) -> dict:
    from backend.domains.metadata.track_identity import get_track_identity_revision
    from backend.domains.metadata.track_presentation import TRACK_PRESENTATION_POLICY_VERSION
    from backend.domains.music_search.revisions import get_music_search_revision_state
    from backend.domains.playback.album_projects import get_album_project_revision
    from backend.domains.playback.l3_album_attribution import get_l3_album_attribution_revision

    if conn.in_transaction:
        raise ValueError("Personal statistics require committed source facts")
    source_token = conn.execute("PRAGMA data_version").fetchone()[0]
    params = normalise_filters(conn, filters)
    state = get_music_search_revision_state(conn)
    result = {
        "filter_fingerprint": digest(params),
        "source_revision": digest(
            {
                "entity": {
                    "playback_revision": state.playback_revision,
                    "metadata_revision": state.metadata_revision,
                    "settings_revision": state.settings_revision,
                    "track_identity_revision": get_track_identity_revision(conn),
                    "album_project_revision": get_album_project_revision(conn),
                    "l3_album_attribution_revision": get_l3_album_attribution_revision(conn),
                    "track_presentation_policy": TRACK_PRESENTATION_POLICY_VERSION,
                },
                "artist_identity": get_identity_revision(conn),
                "track_credits": get_track_credit_revision(conn),
                "duration_policy": LISTENING_DURATION_POLICY_VERSION,
                "credit_policy": TRACK_CREDIT_POLICY_VERSION,
                "source": _revision_vector(conn, COMMON + RECORDS),
                "contract": STATISTICS_CONTRACT_VERSION,
            }
        ),
        "statistics_contract_version": STATISTICS_CONTRACT_VERSION,
    }
    if conn.execute("PRAGMA data_version").fetchone()[0] != source_token:
        if _attempt < 2:
            return context(conn, filters, _attempt=_attempt + 1)
        raise ValueError("Personal statistics source changed during revision collection")
    return result


def requested_key(kind: str, item: Any) -> str:
    if kind == "track":
        parts = [kind, int(item)]
    elif kind == "album":
        parts = [kind, item["artist_name"], item["album_name"]]
    elif kind == "artist":
        parts = [kind, str(item)]
    else:
        raise ValueError("Unknown comparison entity kind")
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _source_tracks(conn: sqlite3.Connection, l1_ids: tuple[int, ...]) -> tuple[int, ...]:
    if not l1_ids:
        return ()
    markers = ",".join("?" for _ in l1_ids)
    if _table_exists(conn, "track_l1_source_links"):
        rows = conn.execute(
            f"SELECT DISTINCT track_id FROM track_l1_source_links WHERE l1_id IN ({markers})",
            l1_ids,
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT track_id FROM tracks WHERE track_id IN ({markers})", l1_ids
        ).fetchall()
    return tuple(sorted(int(row[0]) for row in rows))


def _l1_tracks(conn: sqlite3.Connection, source_ids: tuple[int, ...]) -> tuple[int, ...]:
    if not source_ids or not _table_exists(conn, "track_l1_source_links"):
        return source_ids
    markers = ",".join("?" for _ in source_ids)
    return tuple(
        sorted(
            {
                int(row[0])
                for row in conn.execute(
                    f"SELECT DISTINCT l1_id FROM track_l1_source_links WHERE track_id IN ({markers})",
                    source_ids,
                )
            }
        )
    )


def _album_song_keys(conn: sqlite3.Connection, merge_level: int) -> dict[int, set[str]]:
    """Read published membership without schema/bootstrap side effects."""
    import pandas as pd

    if merge_level >= 3:
        from backend.core.access_surface import snapshot_unavailable
        from backend.domains.playback.l3_album_attribution import load_l3_song_album_attributions

        try:
            membership = load_l3_song_album_attributions(conn, require_ready=True)
        except RuntimeError:
            raise snapshot_unavailable("versus_personal_context") from None
        if not membership.empty:
            membership = membership[membership["include_in_charts"] == 1]
    else:
        from backend.domains.playback.album_projects import apply_canonical_song_keys

        membership = pd.read_sql_query(
            """SELECT DISTINCT apt.project_id,
                      COALESCE(links.l1_id,apt.track_id) AS track_id,
                      COALESCE(rep.track_name,t.track_name) AS track_name
                 FROM album_project_tracks apt
                 JOIN tracks t ON t.track_id=apt.track_id
                 LEFT JOIN track_l1_source_links links ON links.track_id=apt.track_id
                 LEFT JOIN track_l1_identities li ON li.l1_id=links.l1_id
                 LEFT JOIN tracks rep ON rep.track_id=li.representative_track_id
                WHERE apt.min_merge_level<=?""",
            conn,
            params=(merge_level,),
        )
        membership = apply_canonical_song_keys(membership, conn, merge_level)
    if membership.empty:
        return {}
    return {
        int(str(project_id)): set(rows["canonical_song_key"].dropna())
        for project_id, rows in membership.groupby("project_id")
    }


class _SelectionCache:
    """Keep eight immutable scopes, without frames or caller connections."""

    def __init__(self):
        self.values: OrderedDict[tuple, tuple[SelectedEntity, ...]] = OrderedDict()
        self.lock = RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self.lock:
            result = self.values.get(key)
            if result is None:
                self.misses += 1
            else:
                self.hits += 1
                self.values.move_to_end(key)
            return result

    def put(self, key, value):
        with self.lock:
            self.values[key] = value
            self.values.move_to_end(key)
            while len(self.values) > 8:
                self.values.popitem(last=False)

    def cache_clear(self):
        with self.lock:
            self.values.clear()
            self.hits = self.misses = 0

    def cache_stats(self):
        with self.lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self.values),
                "maxsize": 8,
            }


_SELECTION_CACHE = _SelectionCache()
register_ttl("analysis", "versus_personal_identity", _SELECTION_CACHE)


@dataclass(frozen=True)
class _SelectionWork:
    key: tuple
    conn: sqlite3.Connection = field(compare=False, hash=False)
    kind: str = field(compare=False, hash=False)
    items: tuple = field(compare=False, hash=False)
    params: dict = field(compare=False, hash=False)
    metadata: dict = field(compare=False, hash=False)


def _selection_context(conn, params):
    try:
        return context(conn, params)
    except (ValueError, RuntimeError, sqlite3.Error):
        raise snapshot_unavailable("versus_personal_context") from None


@singleflight(key_fn=lambda args, kwargs: args[0].key)
def _selection_for_work(work: _SelectionWork) -> tuple[SelectedEntity, ...]:
    cached = _SELECTION_CACHE.get(work.key)
    if cached is not None:
        return cached
    result = tuple(
        _resolve_selection_uncached(
            work.conn, work.kind, list(work.items), work.params["merge_level"]
        )
    )
    # Do not publish a mixed or stale scope. Waiting readers still perform
    # their own final fence before consuming a shared immutable result.
    if _selection_context(work.conn, work.params) != work.metadata:
        raise snapshot_unavailable("versus_personal_context")
    _SELECTION_CACHE.put(work.key, result)
    return result


def resolve_selection(
    conn: sqlite3.Connection,
    kind: str,
    items: list,
    merge_level: int = 2,
    *,
    filters: dict | None = None,
    metadata: dict | None = None,
) -> list[SelectedEntity]:
    if not 2 <= len(items) <= 4:
        raise ValueError("请选择2至4个对象进行对决")
    requested = [requested_key(kind, item) for item in items]
    if len(set(requested)) != len(requested):
        raise ValueError("选中的对象归并后重复，请选择不同对象")
    params = normalise_filters(conn, {**(filters or {}), "merge_level": merge_level})
    before = _selection_context(conn, params)
    if metadata is not None and metadata != before:
        raise snapshot_unavailable("versus_personal_context")
    lineage = database_identity(conn)
    sorted_items = tuple(
        item for _, item in sorted(zip(requested, items), key=lambda pair: pair[0])
    )
    key = (
        lineage["device"],
        lineage["inode"],
        before["source_revision"],
        tuple(sorted(params.items())),
        kind,
        tuple(sorted(requested)),
    )
    selected = _selection_for_work(_SelectionWork(key, conn, kind, sorted_items, params, before))
    if _selection_context(conn, params) != before:
        raise snapshot_unavailable("versus_personal_context")
    by_key = {entity.requested_key: entity for entity in selected}
    return [by_key[key] for key in requested]


def _resolve_selection_uncached(
    conn: sqlite3.Connection, kind: str, items: list, merge_level: int = 2
) -> list[SelectedEntity]:
    if not 2 <= len(items) <= 4:
        raise ValueError("请选择2至4个对象进行对决")
    result: list[SelectedEntity] = []
    credits = get_effective_track_credits(conn) if kind == "artist" else []
    keyed_tracks = None
    album_song_keys = {}
    if kind == "album":
        import pandas as pd

        from backend.domains.playback.album_projects import apply_canonical_song_keys

        if _table_exists(conn, "track_l1_identities"):
            candidates = pd.read_sql_query(
                "SELECT i.l1_id AS track_id,t.track_name FROM track_l1_identities i "
                "JOIN tracks t ON t.track_id=i.representative_track_id "
                "WHERE i.identity_status IN ('active','unresolved')",
                conn,
            )
        else:
            candidates = pd.read_sql_query("SELECT track_id,track_name FROM tracks", conn)
        keyed_tracks = apply_canonical_song_keys(candidates, conn, merge_level)
        album_song_keys = _album_song_keys(conn, merge_level)
    for item in items:
        key = requested_key(kind, item)
        if kind == "track":
            track_id = int(item)
            # Billboard picker ids are L1 aggregation ids. Accept a uniquely
            # resolvable historical raw id only when no L1 identity owns it.
            if (
                _table_exists(conn, "track_l1_identities")
                and not conn.execute(
                    "SELECT 1 FROM track_l1_identities WHERE l1_id=?", (track_id,)
                ).fetchone()
            ):
                from backend.domains.metadata.track_identity import resolve_public_track_l1_ids

                ids = resolve_public_track_l1_ids(conn, track_id)
                if len(ids) > 1:
                    raise ValueError("歌曲来源对应多个身份，请重新选择")
                if ids:
                    track_id = ids[0]
            scope = resolve_track_aggregation_scope(conn, track_id, merge_level)
            sources = _source_tracks(conn, scope.member_track_ids)
            if not sources:
                result.append(SelectedEntity(key, f"unavailable:{key}", ""))
                continue
            result.append(
                SelectedEntity(
                    key,
                    f"track:{scope.primary_track_id}",
                    str(scope.primary_track_id),
                    sources,
                    track_id=scope.primary_track_id,
                )
            )
        elif kind == "album":
            identity = resolve_album_project_identity(
                conn,
                album_name=item["album_name"],
                artist_name=item["artist_name"],
                merge_level=merge_level,
            )
            if identity is None:
                result.append(
                    SelectedEntity(
                        key,
                        f"unavailable:{key}",
                        "",
                        album_name=item["album_name"],
                        artist_name=item["artist_name"],
                    )
                )
                continue
            song_keys = album_song_keys.get(identity.project_id, set())
            assert keyed_tracks is not None
            l1_ids = tuple(
                sorted(
                    {
                        int(value)
                        for value in keyed_tracks.loc[
                            keyed_tracks["canonical_song_key"].isin(song_keys), "track_id"
                        ]
                    }
                )
            )
            source_ids = _source_tracks(conn, l1_ids)
            result.append(
                SelectedEntity(
                    key,
                    f"album:{identity.project_id}",
                    str(identity.project_id),
                    tuple(source_ids),
                    album_name=identity.canonical_name,
                    artist_name=identity.artist_name,
                    artist_id=identity.artist_id,
                    project_id=identity.project_id,
                    song_keys=tuple(sorted(song_keys)),
                )
            )
        elif kind == "artist":
            artist = resolve_artist_name(conn, str(item))
            if artist is None:
                result.append(SelectedEntity(key, f"unavailable:{key}", "", artist_name=str(item)))
                continue
            credited_ids = tuple(
                sorted(
                    {
                        int(row["track_id"])
                        for row in credits
                        if int(row["artist_id"]) == artist.canonical_artist_id
                    }
                )
            )
            source_ids = _source_tracks(conn, _l1_tracks(conn, credited_ids))
            result.append(
                SelectedEntity(
                    key,
                    f"artist:{artist.canonical_artist_id}",
                    artist.display_name,
                    source_ids,
                    artist_name=artist.display_name,
                    artist_id=artist.canonical_artist_id,
                    credited_track_ids=credited_ids,
                )
            )
        else:
            raise ValueError("Unknown comparison entity kind")
    if len({row.entity_key for row in result}) != len(result):
        raise ValueError("选中的对象归并后重复，请选择不同对象")
    return result
