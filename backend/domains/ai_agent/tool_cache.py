"""Bounded revision-aware cache for deterministic local Agent tools."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace

from pydantic import BaseModel

from backend.domains.ai_agent.tool_registry import AgentToolResult
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import get_track_credit_revision
from backend.domains.metadata.track_identity import get_track_identity_revision
from backend.domains.music_search.revisions import get_music_search_revision_state
from backend.domains.playback.album_projects import get_album_project_revision

_MAX_ENTRIES = 128


@dataclass(frozen=True)
class AgentToolCacheKey:
    tool_name: str
    database_path: str
    database_device: int
    database_inode: int
    revision: tuple[int, ...]
    normalized_params: str


class AgentToolRevisionCache:
    """A small process-local LRU whose keys never cross a data revision."""

    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[AgentToolCacheKey, AgentToolResult] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: AgentToolCacheKey) -> AgentToolResult | None:
        with self._lock:
            value = self._entries.get(key)
            if value is None:
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return replace(copy.deepcopy(value), cache_hit=True)

    def put(self, key: AgentToolCacheKey, value: AgentToolResult) -> None:
        # Operational failures and not-ready gates must be retried instead of cached.
        if value.data.get("error") or value.data.get("status") == "error":
            return
        with self._lock:
            self._entries[key] = replace(copy.deepcopy(value), cache_hit=False)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
            }


_CACHE = AgentToolRevisionCache()


def agent_tool_data_revision(
    conn: sqlite3.Connection,
    *,
    include_billboard: bool = False,
) -> tuple[str, int, int, tuple[int, ...]] | None:
    """Return a cheap revision fingerprint, or ``None`` for non-file test DBs."""
    if not isinstance(conn, sqlite3.Connection):
        return None
    try:
        database_row = conn.execute("PRAGMA database_list").fetchone()
        database_path = str(database_row[2] or "") if database_row is not None else ""
        if not database_path:
            return None
        canonical_path = os.path.realpath(database_path)
        file_state = os.stat(canonical_path)
        state = get_music_search_revision_state(conn)
        revision = (
            state.playback_revision,
            state.metadata_revision,
            state.settings_revision,
            state.candidate_revision,
            get_identity_revision(conn),
            get_track_credit_revision(conn),
            get_track_identity_revision(conn),
            get_album_project_revision(conn),
            state.billboard_revision if include_billboard else 0,
        )
        return canonical_path, int(file_state.st_dev), int(file_state.st_ino), revision
    except (AttributeError, IndexError, KeyError, OSError, sqlite3.Error, TypeError, ValueError):
        # Lightweight fakes and pre-migration databases remain directly executable.
        return None


def normalized_tool_params(params: BaseModel) -> str:
    return json.dumps(
        params.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def make_cache_key(
    conn: sqlite3.Connection,
    *,
    tool_name: str,
    params: BaseModel,
    include_billboard: bool = False,
) -> AgentToolCacheKey | None:
    state = agent_tool_data_revision(conn, include_billboard=include_billboard)
    if state is None:
        return None
    database_path, database_device, database_inode, revision = state
    return AgentToolCacheKey(
        tool_name=tool_name,
        database_path=database_path,
        database_device=database_device,
        database_inode=database_inode,
        revision=revision,
        normalized_params=normalized_tool_params(params),
    )


def get_cached_tool_result(key: AgentToolCacheKey | None) -> AgentToolResult | None:
    return _CACHE.get(key) if key is not None else None


def cache_tool_result(key: AgentToolCacheKey | None, value: AgentToolResult) -> None:
    if key is not None:
        _CACHE.put(key, value)


def clear_agent_tool_cache() -> None:
    _CACHE.clear()


def agent_tool_cache_stats() -> dict[str, int]:
    return _CACHE.stats()
