"""Shared entity reference and deep-link construction for Yearly Review V2."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from backend.models.yearly_review import YearlyEntityRef


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
