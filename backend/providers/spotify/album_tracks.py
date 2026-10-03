"""Validate release positions, never the number of distinct recordings."""

from __future__ import annotations

import json


class AlbumTracksIncompleteError(ValueError):
    """No complete replacement may be published for this observation."""


def complete_track_ids(raw, total_tracks):
    """Legacy caches are usable only with a declared count and every position."""
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        total = int(total_tracks or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0 or not isinstance(items, list) or len(items) != total:
        return None
    ids = []
    for item in items:
        if isinstance(item, dict):
            item = item.get("id") or item.get("spotify_track_id") or item.get("uri")
        if not isinstance(item, str) or not item.strip():
            return None
        normalized = item.removeprefix("spotify:track:").strip()
        if not normalized:
            return None
        ids.append(normalized)
    return tuple(ids)


def fetch_complete_album_tracks(provider, album, access_token):
    """Use an Album's validated first page, then fixed limit/offset requests.

    next is checked only for end-of-list consistency, never used as a URL.
    Empty/short/interleaved/repeated pages fail closed before any persistence.
    """
    total = album.get("total_tracks")
    if type(total) is not int or total <= 0:
        raise AlbumTracksIncompleteError("invalid_declared_total")
    page = album.get("tracks")
    if not isinstance(page, dict) or any(
        key not in page for key in ("offset", "limit", "total", "next")
    ):
        page = provider.get_album_tracks_page(album["id"], access_token, offset=0)
    offset = 0
    items = []
    seen_pages = set()
    previous_position = (0, 0)
    while True:
        if not isinstance(page, dict):
            raise AlbumTracksIncompleteError(f"page_failed:{offset}")
        if type(page.get("total")) is not int or page["total"] != total:
            raise AlbumTracksIncompleteError(f"total_changed:{offset}")
        limit = page.get("limit")
        if (
            type(page.get("offset")) is not int
            or page["offset"] != offset
            or type(limit) is not int
            or not 1 <= limit <= 50
        ):
            raise AlbumTracksIncompleteError(f"invalid_page_position:{offset}")
        batch = page.get("items")
        if not isinstance(batch, list) or len(batch) != min(limit, total - offset):
            raise AlbumTracksIncompleteError(f"empty_or_short_page:{offset}")
        signature = tuple(
            (t.get("id"), t.get("disc_number"), t.get("track_number"))
            for t in batch
            if isinstance(t, dict)
        )
        if signature in seen_pages:
            raise AlbumTracksIncompleteError(f"duplicate_page:{offset}")
        seen_pages.add(signature)
        for track in batch:
            if (
                not isinstance(track, dict)
                or not isinstance(track.get("id"), str)
                or not track["id"].strip()
            ):
                raise AlbumTracksIncompleteError(f"missing_track_id:{offset}")
            position = (track.get("disc_number"), track.get("track_number"))
            if any(type(n) is not int or n <= 0 for n in position) or position <= previous_position:
                raise AlbumTracksIncompleteError(f"invalid_track_position:{offset}")
            if not track.get("name"):
                raise AlbumTracksIncompleteError(f"missing_track_name:{offset}")
            previous_position = position
        items.extend(batch)
        offset += len(batch)
        if offset == total:
            if page.get("next") is not None:
                raise AlbumTracksIncompleteError("unexpected_next_page")
            return items
        if not page.get("next"):
            raise AlbumTracksIncompleteError(f"missing_next_page:{offset}")
        page = provider.get_album_tracks_page(album["id"], access_token, offset=offset)
