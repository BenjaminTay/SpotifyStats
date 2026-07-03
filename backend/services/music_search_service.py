"""Local read-only music entity search service."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any, cast
from urllib.parse import quote

from backend.domains.ai_agent.entity_resolver import EntityType, resolve_entities
from backend.models.music_search import MusicSearchResponse, MusicSearchResult

_ALL_KINDS: tuple[EntityType, ...] = ("track", "album", "artist")


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 10))


def _valid_kinds(kinds: Iterable[str] | None) -> tuple[EntityType, ...]:
    if kinds is None:
        return _ALL_KINDS
    selected = tuple(cast(EntityType, kind) for kind in kinds if kind in _ALL_KINDS)
    return selected or _ALL_KINDS


def _plays_text(play_events: int) -> str:
    return f"{play_events} 次播放"


def _cover_url(kind: str, entity_id: Any) -> str | None:
    if entity_id is None:
        return None
    try:
        resolved_id = int(entity_id)
    except (TypeError, ValueError):
        return None
    return f"/covers/{kind}/{resolved_id}.jpg"


def _track_result(candidate: dict[str, Any]) -> MusicSearchResult | None:
    track_id = candidate.get("track_id")
    label = candidate.get("track_name") or candidate.get("name")
    if track_id is None or not label:
        return None
    artist_name = candidate.get("artist_name")
    album_name = candidate.get("album_name")
    subtitle_parts = [part for part in (artist_name, album_name) if part]
    return MusicSearchResult(
        kind="track",
        label=str(label),
        subtitle=" · ".join(str(part) for part in subtitle_parts) or None,
        href=f"/music/tracks/{track_id}",
        play_events=int(candidate.get("play_events") or 0),
        total_ms=int(candidate.get("total_ms") or 0),
        track_id=int(track_id),
        album_name=str(album_name) if album_name else None,
        artist_name=str(artist_name) if artist_name else None,
        cover_url=_cover_url("albums", candidate.get("album_id")),
    )


def _album_result(candidate: dict[str, Any]) -> MusicSearchResult | None:
    album_name = candidate.get("album_name") or candidate.get("name")
    if not album_name:
        return None
    artist_name = candidate.get("artist_name")
    href = f"/music/albums/{quote(str(album_name), safe='')}"
    if artist_name:
        href = f"{href}?artist={quote(str(artist_name), safe='')}"
    return MusicSearchResult(
        kind="album",
        label=str(album_name),
        subtitle=str(artist_name) if artist_name else None,
        href=href,
        play_events=int(candidate.get("play_events") or 0),
        total_ms=int(candidate.get("total_ms") or 0),
        album_name=str(album_name),
        artist_name=str(artist_name) if artist_name else None,
        cover_url=_cover_url("albums", candidate.get("album_id")),
    )


def _artist_result(candidate: dict[str, Any]) -> MusicSearchResult | None:
    artist_name = candidate.get("artist_name") or candidate.get("name")
    if not artist_name:
        return None
    play_events = int(candidate.get("play_events") or 0)
    return MusicSearchResult(
        kind="artist",
        label=str(artist_name),
        subtitle=_plays_text(play_events),
        href=f"/music/artists/{quote(str(artist_name), safe='')}",
        play_events=play_events,
        total_ms=int(candidate.get("total_ms") or 0),
        artist_name=str(artist_name),
        cover_url=_cover_url("artists", candidate.get("artist_id")),
    )


def _convert(kind: EntityType, candidate: dict[str, Any]) -> MusicSearchResult | None:
    if kind == "track":
        return _track_result(candidate)
    if kind == "album":
        return _album_result(candidate)
    return _artist_result(candidate)


def search_music_entities(
    conn: sqlite3.Connection,
    *,
    query: str,
    kinds: Iterable[str] | None = None,
    limit_per_type: int = 5,
) -> MusicSearchResponse:
    bounded_limit = _bounded_limit(limit_per_type)
    selected_kinds = _valid_kinds(kinds)

    grouped: dict[EntityType, list[MusicSearchResult]] = {
        "track": [],
        "album": [],
        "artist": [],
    }
    if not query.strip():
        return MusicSearchResponse(
            query=query,
            limit_per_type=bounded_limit,
            total=0,
            tracks=[],
            albums=[],
            artists=[],
        )

    for kind in selected_kinds:
        resolved = resolve_entities(conn, query=query, entity_type=kind, limit=bounded_limit)
        rows = []
        for candidate in resolved.get("candidates", []):
            item = _convert(kind, candidate)
            if item is not None:
                rows.append(item)
        grouped[kind] = rows

    return MusicSearchResponse(
        query=query,
        limit_per_type=bounded_limit,
        total=sum(len(items) for items in grouped.values()),
        tracks=grouped["track"],
        albums=grouped["album"],
        artists=grouped["artist"],
    )
