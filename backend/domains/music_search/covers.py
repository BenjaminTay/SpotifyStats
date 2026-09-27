"""Bounded cover availability checks for music-search responses.

The local cover route is only meaningful when the catalog has either a local
image path or provider image metadata for that entity.  Candidate generations
created before this rule may still contain synthetic local URLs, so readers
also sanitize the bounded result page without touching the filesystem or
rebuilding the index.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel

CoverKind = Literal["albums", "artists"]

_LOCAL_COVER_RE = re.compile(r"^/covers/(?P<kind>albums|artists)/(?P<id>[1-9]\d*)\.jpg$")
_COVER_TABLES: Mapping[CoverKind, tuple[str, str]] = {
    "albums": ("albums", "album_id"),
    "artists": ("artists", "artist_id"),
}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}
    except sqlite3.Error:
        return set()


def available_cover_entity_ids(
    conn: sqlite3.Connection,
    kind: CoverKind,
    entity_ids: Iterable[int] | None = None,
) -> set[int]:
    """Return metadata-backed entity IDs in one bounded catalog query."""

    table, id_column = _COVER_TABLES[kind]
    columns = _table_columns(conn, table)
    image_columns = [name for name in ("image_path", "image_url") if name in columns]
    if id_column not in columns or not image_columns:
        return set()

    predicates = [f"trim(COALESCE({name}, '')) <> ''" for name in image_columns]
    params: tuple[int, ...] = ()
    scope = ""
    if entity_ids is not None:
        ids = tuple(sorted({int(value) for value in entity_ids if int(value) > 0}))
        if not ids:
            return set()
        placeholders = ",".join("?" for _ in ids)
        scope = f" AND {id_column} IN ({placeholders})"
        params = ids
    try:
        rows = conn.execute(
            f"SELECT {id_column} FROM {table} WHERE ({' OR '.join(predicates)}){scope}",
            params,
        ).fetchall()
    except sqlite3.Error:
        return set()
    return {int(row[0]) for row in rows}


def local_cover_url(kind: CoverKind, entity_id: Any, available_ids: set[int]) -> str | None:
    try:
        resolved = int(entity_id)
    except (TypeError, ValueError):
        return None
    if resolved <= 0 or resolved not in available_ids:
        return None
    return f"/covers/{kind}/{resolved}.jpg"


def validated_cover_url(
    cover_url: str | None,
    available_by_kind: Mapping[CoverKind, set[int]],
) -> str | None:
    """Drop only stale synthetic local URLs; preserve external/provider URLs."""

    if not cover_url:
        return None
    match = _LOCAL_COVER_RE.fullmatch(str(cover_url))
    if match is None:
        return str(cover_url)
    kind = cast(CoverKind, match.group("kind"))
    entity_id = int(match.group("id"))
    return str(cover_url) if entity_id in available_by_kind[kind] else None


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def sanitize_result_covers(
    conn: sqlite3.Connection,
    groups: Sequence[Sequence[_ModelT]],
) -> list[list[_ModelT]]:
    """Sanitize a bounded response page with at most two metadata queries."""

    refs: dict[CoverKind, set[int]] = {"albums": set(), "artists": set()}
    for group in groups:
        for item in group:
            match = _LOCAL_COVER_RE.fullmatch(str(getattr(item, "cover_url", "") or ""))
            if match is not None:
                kind = cast(CoverKind, match.group("kind"))
                refs[kind].add(int(match.group("id")))
    available: dict[CoverKind, set[int]] = {
        kind: available_cover_entity_ids(conn, kind, ids) for kind, ids in refs.items()
    }
    sanitized: list[list[_ModelT]] = []
    for group in groups:
        rows: list[_ModelT] = []
        for item in group:
            current = getattr(item, "cover_url", None)
            resolved = validated_cover_url(current, available)
            if resolved == current:
                rows.append(item)
            else:
                rows.append(item.model_copy(update={"cover_url": resolved}))
        sanitized.append(rows)
    return sanitized
