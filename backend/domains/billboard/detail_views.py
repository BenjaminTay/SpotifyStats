"""Revision-keyed caches and lossless read views for music detail responses.

The legacy ``full`` payload remains the source of truth.  Lightweight views
only select fields (or stable list slices) from that payload, so changing the
delivery shape cannot change any Billboard calculation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from backend.core.cache import singleflight
from backend.core.cache_manager import register_lru
from backend.core.db import get_db
from backend.domains.billboard.chart_load_rank import billboard_revision_state
from backend.domains.billboard.details import (
    get_album_chart_detail,
    get_artist_chart_detail,
    get_track_history,
)
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import get_track_credit_revision
from backend.domains.music_search.revisions import get_music_search_revision_state

DetailView = Literal["full", "summary", "overview", "tracks", "albums", "project"]


def detail_revision_state() -> tuple:
    """Return every persistent revision that can change a detail response."""
    conn = get_db()
    try:
        revisions = get_music_search_revision_state(conn)
        return (
            revisions.playback_revision,
            revisions.billboard_revision,
            revisions.metadata_revision,
            revisions.settings_revision,
            get_identity_revision(conn),
            get_track_credit_revision(conn),
            *billboard_revision_state(),
        )
    finally:
        conn.close()


@singleflight
@lru_cache(maxsize=32)
def _track_detail_cached(args: tuple, _revision_state: tuple) -> dict:
    return get_track_history(*args)


@singleflight
@lru_cache(maxsize=32)
def _album_detail_cached(args: tuple, _revision_state: tuple) -> dict:
    return get_album_chart_detail(*args)


@singleflight
@lru_cache(maxsize=32)
def _artist_detail_cached(args: tuple, _revision_state: tuple) -> dict:
    return get_artist_chart_detail(*args)


def _base_view(payload: dict, keys: tuple[str, ...]) -> dict:
    return {key: payload[key] for key in keys if key in payload}


def select_track_detail_view(payload: dict, view: DetailView) -> dict:
    if view == "full" or view == "overview":
        return payload
    if view != "summary":
        raise ValueError(f"unsupported track detail view: {view}")
    result = _base_view(
        payload,
        (
            "found",
            "chart_status",
            "effective_play_count",
            "track_id",
            "track_name",
            "artist_name",
            "artist_names",
            "primary_artist_name",
            "cover_url",
            "meta",
            "summary",
        ),
    )
    result.update({"history": [], "chart_data": {}})
    return result


def select_album_detail_view(payload: dict, view: DetailView) -> dict:
    if view == "full":
        return payload
    if view not in {"summary", "overview", "tracks", "project"}:
        raise ValueError(f"unsupported album detail view: {view}")

    result = _base_view(
        payload,
        (
            "found",
            "chart_status",
            "track_chart_status",
            "effective_play_count",
            "album_name",
            "artist_name",
            "cover_url",
            "meta",
            "info",
            "chart_summary",
        ),
    )
    result.update(
        {
            "album_project": None,
            "album_weekly_history": [],
            "album_no1_by_week": [],
            "best_singles_overlay": [],
            "tracks": [],
        }
    )

    if view == "summary" and isinstance(result.get("meta"), dict):
        meta = dict(result["meta"])
        meta.pop("release_group", None)
        result["meta"] = meta
    elif view == "overview":
        for key in ("album_weekly_history", "album_no1_by_week", "best_singles_overlay"):
            result[key] = payload.get(key, [])
    elif view == "tracks":
        result["tracks"] = payload.get("tracks", [])
    elif view == "project":
        result["album_project"] = payload.get("album_project")
    return result


def select_artist_detail_view(
    payload: dict,
    view: DetailView,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    if view == "full":
        return payload
    if view not in {"summary", "overview", "tracks", "albums"}:
        raise ValueError(f"unsupported artist detail view: {view}")

    result = _base_view(
        payload,
        (
            "found",
            "chart_status",
            "track_chart_status",
            "album_chart_status",
            "effective_play_count",
            "artist_name",
            "cover_url",
            "meta",
            "info",
            "chart_summary",
        ),
    )
    result.update(
        {
            "artist_weekly_history": [],
            "artist_no1_by_week": [],
            "week_no1_albums": [],
            "best_singles_overlay": [],
            "best_albums_overlay": [],
            "tracks": [],
            "albums": [],
        }
    )

    if view == "overview":
        for key in (
            "artist_weekly_history",
            "artist_no1_by_week",
            "week_no1_albums",
            "best_singles_overlay",
            "best_albums_overlay",
        ):
            result[key] = payload.get(key, [])
    elif view == "tracks":
        tracks = payload.get("tracks", [])
        result["tracks"] = tracks[offset : offset + limit]
        result["tracks_total"] = len(tracks)
        result["tracks_limit"] = limit
        result["tracks_offset"] = offset
        result["tracks_max_chart_plays"] = max(
            (int(row.get("total_chart_plays") or 0) for row in tracks),
            default=0,
        )
    elif view == "albums":
        result["albums"] = payload.get("albums", [])
    return result


def get_track_detail_view(*args, view: DetailView = "full") -> dict:
    payload = _track_detail_cached(tuple(args), detail_revision_state())
    return select_track_detail_view(payload, view)


def get_album_detail_view(*args, view: DetailView = "full") -> dict:
    payload = _album_detail_cached(tuple(args), detail_revision_state())
    return select_album_detail_view(payload, view)


def get_artist_detail_view(
    *args,
    view: DetailView = "full",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    payload = _artist_detail_cached(tuple(args), detail_revision_state())
    return select_artist_detail_view(payload, view, limit=limit, offset=offset)


register_lru("billboard", "track_detail", _track_detail_cached)
register_lru("billboard", "album_detail", _album_detail_cached)
register_lru("billboard", "artist_detail", _artist_detail_cached)
