"""Shared entity reference and deep-link construction for Yearly Review V2."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel

from backend.models.yearly_review import YearlyEntityRef
from backend.services.play_service import (
    _album_cover_lookup,
    _artist_cover_lookup,
    _track_cover_urls,
)


def normalized_entity_id(value: Any) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def entity_deep_link(
    entity_type: str,
    *,
    entity_id: Any = None,
    name: str | None = None,
    artist_name: str | None = None,
) -> str | None:
    normalized_id = normalized_entity_id(entity_id)
    if entity_type == "track" and normalized_id is not None:
        return f"/music/tracks/{normalized_id}"
    if entity_type == "album" and name:
        return f"/music/albums/{quote(name, safe='')}?artist={quote(artist_name or '', safe='')}"
    if entity_type == "artist" and name:
        return f"/music/artists/{quote(name, safe='')}"
    return None


def entity_ref_from_row(
    row: Mapping[str, Any], entity_type: str | None = None
) -> YearlyEntityRef | None:
    if entity_type is None:
        if row.get("track_name") or row.get("track_id") is not None:
            entity_type = "track"
        elif row.get("album_name"):
            entity_type = "album"
        elif row.get("artist_name"):
            entity_type = "artist"
    specs = {
        "track": ("track_id", "track_name"),
        "album": ("album_project_id", "album_name"),
        "artist": ("artist_id", "artist_name"),
    }
    if entity_type not in specs:
        return None
    id_key, name_key = specs[entity_type]
    name = row.get(name_key)
    if not name:
        return None
    entity_id = normalized_entity_id(row.get(id_key))
    artist_name = (
        str(row.get("artist_name")) if entity_type != "artist" and row.get("artist_name") else None
    )
    return YearlyEntityRef(
        entity_type=entity_type,
        entity_id=entity_id,
        name=str(name),
        artist_name=artist_name,
        cover_url=row.get("cover_url"),
        deep_link=row.get("deep_link")
        or entity_deep_link(
            entity_type,
            entity_id=entity_id,
            name=str(name),
            artist_name=artist_name,
        ),
    )


def ensure_row_deep_link(row: Mapping[str, Any], entity_type: str) -> dict[str, Any]:
    result = dict(row)
    ref = entity_ref_from_row(result, entity_type)
    if ref is not None:
        result["deep_link"] = ref.deep_link
        if ref.entity_id is not None:
            id_key = {"track": "track_id", "album": "album_project_id", "artist": "artist_id"}[
                entity_type
            ]
            result[id_key] = ref.entity_id
    return result


def _iter_entity_refs(value: Any):
    if isinstance(value, YearlyEntityRef):
        yield value
        return
    if isinstance(value, BaseModel):
        for field_name in value.__class__.model_fields:
            yield from _iter_entity_refs(getattr(value, field_name))
        return
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _iter_entity_refs(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_entity_refs(child)


def _iter_cover_rows(value: Any):
    if isinstance(value, BaseModel):
        for field_name in value.__class__.model_fields:
            yield from _iter_cover_rows(getattr(value, field_name))
        return
    if isinstance(value, Mapping):
        if value.get("cover_url"):
            yield value
        for child in value.values():
            yield from _iter_cover_rows(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_cover_rows(child)


def enrich_entity_ref_covers(conn: sqlite3.Connection, value: Any) -> None:
    """Fill missing report artwork in one bulk pass without changing entity identity."""
    refs = list(_iter_entity_refs(value))
    if not refs:
        return
    track_ids = [ref.entity_id for ref in refs if ref.entity_type == "track" and ref.entity_id]
    try:
        track_covers = _track_cover_urls(conn, track_ids)
        album_covers = _album_cover_lookup(conn)
        artist_covers = _artist_cover_lookup(conn)
    except sqlite3.Error:
        return
    album_name_fallback: dict[str, str] = {}
    for (album_name, _), cover in album_covers.items():
        if cover and album_name not in album_name_fallback:
            album_name_fallback[album_name] = cover
    report_track_ids: dict[str, str] = {}
    report_track_names: dict[tuple[str, str], str] = {}
    report_albums: dict[tuple[str, str], str] = {}
    report_artists: dict[str, str] = {}
    for row in _iter_cover_rows(value):
        cover = str(row["cover_url"])
        if row.get("track_id") is not None:
            report_track_ids[str(normalized_entity_id(row.get("track_id")))] = cover
        if row.get("track_name"):
            report_track_names[(str(row["track_name"]), str(row.get("artist_name") or ""))] = cover
        if row.get("album_name") and not row.get("track_name"):
            report_albums[(str(row["album_name"]), str(row.get("artist_name") or ""))] = cover
        if row.get("artist_name") and not row.get("track_name") and not row.get("album_name"):
            report_artists[str(row["artist_name"])] = cover
    for ref in refs:
        if ref.cover_url:
            continue
        if ref.entity_type == "track" and ref.entity_id is not None:
            try:
                ref.cover_url = report_track_ids.get(str(ref.entity_id)) or track_covers.get(
                    int(ref.entity_id)
                )
            except (TypeError, ValueError):
                pass
            if not ref.cover_url:
                ref.cover_url = report_track_names.get((ref.name, ref.artist_name or ""))
        elif ref.entity_type == "album":
            ref.cover_url = report_albums.get((ref.name, ref.artist_name or ""))
            if not ref.cover_url:
                ref.cover_url = album_covers.get((ref.name, ref.artist_name or ""))
            if not ref.cover_url:
                ref.cover_url = album_name_fallback.get(ref.name)
        elif ref.entity_type == "artist":
            ref.cover_url = report_artists.get(ref.name) or artist_covers.get(ref.name)
