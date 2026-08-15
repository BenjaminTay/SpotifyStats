"""Minimal podcast and video archive facts with shared audio/video filters."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.core.db import merge_consecutive_plays
from backend.domains.account_archive.overview import _database_path
from backend.domains.account_archive.source_data import load_track_preview_map
from backend.domains.playback.counting import filter_effective_plays
from backend.models.account_archive import ArchiveFilterContext

ARCHIVE_OTHER_MEDIA_CACHE_TTL_SECONDS = 300
PODCAST_PREVIEW_LIMIT = 3
VIDEO_PREVIEW_LIMIT = 3


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _podcast_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    required = {
        "id",
        "end_time",
        "podcast_name",
        "episode_name",
        "ms_played",
        "play_date",
    }
    if not required.issubset(_columns(conn, "podcast_plays")):
        return []
    rows = conn.execute(
        """
        SELECT id, end_time, podcast_name, episode_name, ms_played, play_date
        FROM podcast_plays
        ORDER BY end_time, id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _normalize_show_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _saved_show_metadata(conn: sqlite3.Connection) -> dict[str, dict[str, str | None]]:
    columns = _columns(conn, "saved_shows")
    if "show_name" not in columns:
        return {}
    publisher = "publisher" if "publisher" in columns else "NULL"
    image_url = "image_url" if "image_url" in columns else "NULL"
    rows = conn.execute(
        f"SELECT show_name, {publisher} AS publisher, {image_url} AS image_url "
        "FROM saved_shows WHERE show_name IS NOT NULL"
    ).fetchall()
    metadata: dict[str, dict[str, str | None]] = {}
    for row in rows:
        show_name = str(row["show_name"] or "").strip()
        if not show_name:
            continue
        metadata[_normalize_show_name(show_name)] = {
            "publisher": str(row["publisher"]).strip() if row["publisher"] else None,
            "cover_url": str(row["image_url"]).strip() if row["image_url"] else None,
        }
    return metadata


def _podcast_revision(
    rows: list[dict[str, Any]], show_metadata: dict[str, dict[str, str | None]]
) -> str:
    digest = hashlib.sha256()
    digest.update(b"account_archive_podcast_v2\n")
    for row in rows:
        digest.update(
            json.dumps(
                [
                    row.get("end_time") or "",
                    row.get("podcast_name") or "",
                    row.get("episode_name") or "",
                    int(row.get("ms_played") or 0),
                    row.get("play_date") or "",
                ],
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode()
        )
        digest.update(b"\n")
    for show_name, metadata in sorted(show_metadata.items()):
        digest.update(
            json.dumps(
                [show_name, metadata.get("publisher") or "", metadata.get("cover_url") or ""],
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()[:20]


def _podcast_summary(
    rows: list[dict[str, Any]],
    min_ms: int,
    show_metadata: dict[str, dict[str, str | None]],
) -> dict[str, Any]:
    effective = [row for row in rows if int(row.get("ms_played") or 0) >= min_ms]
    by_show: dict[str, dict[str, Any]] = {}
    for row in effective:
        show_name = str(row.get("podcast_name") or "")
        item = by_show.setdefault(
            show_name,
            {"effective_events": 0, "effective_ms": 0, "active_dates": set()},
        )
        item["effective_events"] += 1
        item["effective_ms"] += int(row.get("ms_played") or 0)
        if row.get("play_date"):
            item["active_dates"].add(str(row["play_date"]))
    top_shows = sorted(
        by_show.items(),
        key=lambda item: (-item[1]["effective_ms"], item[0].casefold()),
    )[:PODCAST_PREVIEW_LIMIT]
    effective_times = [str(row["end_time"]) for row in effective if row.get("end_time")]
    active_months = {
        str(row["play_date"])[:7]
        for row in effective
        if row.get("play_date") and len(str(row["play_date"])) >= 7
    }
    return {
        "source_rows": len(rows),
        "effective_events": len(effective),
        "effective_ms": sum(int(row.get("ms_played") or 0) for row in effective),
        "unique_shows": len(by_show),
        "active_months": len(active_months),
        "returning_shows": sum(1 for item in by_show.values() if len(item["active_dates"]) >= 2),
        "first_effective_at": min(effective_times) if effective_times else None,
        "latest_effective_at": max(effective_times) if effective_times else None,
        "top_shows": [
            {
                "show_name": show_name,
                "publisher": show_metadata.get(_normalize_show_name(show_name), {}).get(
                    "publisher"
                ),
                "cover_url": show_metadata.get(_normalize_show_name(show_name), {}).get(
                    "cover_url"
                ),
                "effective_events": int(item["effective_events"]),
                "effective_ms": int(item["effective_ms"]),
            }
            for show_name, item in top_shows
        ],
    }


def _media_source_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    play_columns = _columns(conn, "plays")
    track_columns = _columns(conn, "tracks")
    if not {"play_id", "ts", "ms_played", "track_id", "content_type"}.issubset(play_columns):
        return pd.DataFrame()
    source_album = "p.source_album_id" if "source_album_id" in play_columns else "NULL"
    has_track_catalog = "track_id" in track_columns
    duration_candidates = []
    if has_track_catalog and "duration_ms" in track_columns:
        duration_candidates.append("t.duration_ms")
    spotify_meta_columns = _columns(conn, "spotify_track_meta")
    has_spotify_meta = {"spotify_track_id", "duration_ms"}.issubset(spotify_meta_columns)
    if has_track_catalog and has_spotify_meta and "spotify_track_id" in track_columns:
        duration_candidates.append("stm.duration_ms")
    duration = (
        f"COALESCE({', '.join(duration_candidates)})"
        if len(duration_candidates) > 1
        else (duration_candidates[0] if duration_candidates else "NULL")
    )
    meta_join = (
        "LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = t.spotify_track_id"
        if has_track_catalog and has_spotify_meta and "spotify_track_id" in track_columns
        else ""
    )
    track_join = "LEFT JOIN tracks t ON t.track_id = p.track_id" if has_track_catalog else ""
    mapped_track_id = "t.track_id" if has_track_catalog else "NULL"
    return pd.read_sql_query(
        f"""
        SELECT p.play_id, p.ts, p.ms_played, p.track_id,
               {mapped_track_id} AS mapped_track_id, {source_album} AS source_album_id,
               p.content_type, {duration} AS duration_ms
        FROM plays p
        {track_join}
        {meta_join}
        WHERE p.content_type IN ('audio', 'video')
        ORDER BY p.ts, p.play_id
        """,
        conn,
    )


def _effective_media_frames(
    source: pd.DataFrame, context: ArchiveFilterContext
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if source.empty:
        return source.copy(), source.copy()
    frame = source.copy()
    if context.merge_enabled:
        frame = merge_consecutive_plays(
            frame,
            context.min_ms,
            max_gap_minutes=context.max_merge_gap_minutes,
            boundary_column=["source_album_id", "content_type"],
            dynamic_threshold=context.dynamic_threshold,
        )
    frame = filter_effective_plays(
        frame,
        min_ms=context.min_ms,
        dynamic_threshold=context.dynamic_threshold,
    )
    frame["event_at"] = pd.to_datetime(frame["ts"], errors="coerce", utc=True) - pd.to_timedelta(
        frame["ms_played"].clip(lower=0), unit="ms"
    )
    frame = frame.dropna(subset=["event_at"]).reset_index(drop=True)
    return (
        frame[(frame["content_type"] == "audio") & frame["mapped_track_id"].notna()].reset_index(
            drop=True
        ),
        frame[frame["content_type"] == "video"].reset_index(drop=True),
    )


def _video_summary(
    conn: sqlite3.Connection, source: pd.DataFrame, video: pd.DataFrame
) -> dict[str, Any]:
    source_rows = int((source["content_type"] == "video").sum()) if not source.empty else 0
    if video.empty:
        return {
            "source_rows": source_rows,
            "effective_events": 0,
            "effective_ms": 0,
            "unique_tracks": 0,
            "active_days": 0,
            "first_effective_at": None,
            "latest_effective_at": None,
            "top_tracks": [],
        }
    mapped_video = video[video["mapped_track_id"].notna()].copy()
    ranked: list[tuple[int, int, int]] = []
    if not mapped_video.empty:
        grouped = mapped_video.groupby("mapped_track_id", sort=False)["ms_played"].agg(
            ["size", "sum"]
        )
        ranked = [
            (int(row.mapped_track_id), int(row.size), int(row.sum))
            for row in grouped.reset_index().itertuples(index=False)
        ]
    preview_map = load_track_preview_map(conn, {track_id for track_id, _, _ in ranked})
    ranked.sort(
        key=lambda item: (
            -item[1],
            not bool(preview_map.get(item[0], {}).get("cover_url")),
            -item[2],
            item[0],
        )
    )
    top_tracks = []
    for track_id, events, effective_ms in ranked:
        metadata = preview_map.get(track_id)
        if metadata is None:
            continue
        top_tracks.append(
            {
                **metadata,
                "effective_events": events,
                "effective_ms": effective_ms,
            }
        )
        if len(top_tracks) >= VIDEO_PREVIEW_LIMIT:
            break
    return {
        "source_rows": source_rows,
        "effective_events": len(video),
        "effective_ms": int(video["ms_played"].sum()),
        "unique_tracks": int(video["mapped_track_id"].nunique()),
        "active_days": int(video["event_at"].dt.date.nunique()),
        "first_effective_at": video["event_at"].min().isoformat().replace("+00:00", "Z"),
        "latest_effective_at": video["event_at"].max().isoformat().replace("+00:00", "Z"),
        "top_tracks": top_tracks,
    }


def build_archive_other_media(
    conn: sqlite3.Connection,
    context: ArchiveFilterContext,
    podcast_revision: str | None = None,
) -> dict[str, Any]:
    podcast_rows = _podcast_rows(conn)
    show_metadata = _saved_show_metadata(conn)
    podcast_rev = podcast_revision or _podcast_revision(podcast_rows, show_metadata)
    podcast = _podcast_summary(podcast_rows, context.min_ms, show_metadata)
    source = _media_source_frame(conn)
    audio, video_frame = _effective_media_frames(source, context)
    video = _video_summary(conn, source, video_frame)

    has_source = bool(podcast["source_rows"] or video["source_rows"])
    has_effective = bool(podcast["effective_events"] or video["effective_events"])
    if not has_source:
        status = "unavailable"
    elif not has_effective or not podcast["effective_events"] or not video["effective_events"]:
        status = "partial"
    else:
        status = "available"
    data_revision = hashlib.sha256(f"{context.source_revision}:{podcast_rev}".encode()).hexdigest()[
        :20
    ]
    return {
        "schema_version": "account_archive_other_media_v2",
        "content_version": "account_archive_other_media_v2_0",
        "data_revision": data_revision,
        "status": status,
        "filter_context": context.model_dump(mode="json"),
        "observation_window": {
            "first_play_at": context.first_play_at,
            "latest_play_at": context.latest_play_at,
        },
        "podcast": podcast,
        "video": video,
        "audio_video_comparison": {
            "audio_effective_events": len(audio),
            "audio_effective_ms": int(audio["ms_played"].sum()) if not audio.empty else 0,
            "video_effective_events": len(video_frame),
            "video_effective_ms": (
                int(video_frame["ms_played"].sum()) if not video_frame.empty else 0
            ),
        },
    }


@ttl_cached(ARCHIVE_OTHER_MEDIA_CACHE_TTL_SECONDS, namespace="account_archive")
def _get_archive_other_media_cached(
    db_path: str,
    context_json: str,
    podcast_revision: str,
    cache_key: str,
) -> dict[str, Any]:
    del cache_key
    context = ArchiveFilterContext.model_validate_json(context_json)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        return build_archive_other_media(conn, context, podcast_revision)
    finally:
        conn.close()


register_ttl("account_archive", "other_media", _get_archive_other_media_cached)


def get_archive_other_media(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> dict[str, Any]:
    podcast_revision = _podcast_revision(_podcast_rows(conn), _saved_show_metadata(conn))
    db_path = _database_path(conn)
    cache_key = f"other-media:{context.filter_fingerprint}:{podcast_revision}"
    if db_path and os.path.exists(db_path):
        return _get_archive_other_media_cached(
            db_path,
            context.model_dump_json(),
            podcast_revision,
            cache_key,
        )
    return build_archive_other_media(conn, context, podcast_revision)
