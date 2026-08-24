"""Lightweight music-detail summaries backed by the published search snapshot.

The detail shell needs entity identity, artwork, basic provider metadata and a
small chart summary.  None of those facts require rebuilding complete weekly
Billboard histories.  This module reads the exact active search/chart snapshot
and returns ``None`` when that exact semantic variant is unavailable, allowing
the legacy full builder to remain the compatibility fallback.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.db import get_db
from backend.domains.metadata.album_detail_meta import resolve_album_detail_meta
from backend.domains.metadata.artist_genres import resolve_artist_genres
from backend.domains.metadata.artist_identity import resolve_artist_id, resolve_artist_name
from backend.domains.metadata.artist_spotify_meta import resolve_artist_spotify_meta
from backend.domains.metadata.track_credits import canonical_artist_names_for_effective_tracks
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    build_music_search_filter_context,
)


def _filter_values(args: tuple, *, album_name: str | None = None) -> dict[str, Any]:
    offset = 2 if album_name is not None else 1
    return {
        "min_ms": args[offset],
        "music_only": args[offset + 1],
        "bb_top_n": args[offset + 2],
        "bb_album_top_n": args[offset + 3],
        "bb_artist_top_n": args[offset + 4],
        "bb_week_start_dow": args[offset + 5],
        "bb_week_start_hour": args[offset + 6],
        "year_start": args[offset + 7],
        "year_end": args[offset + 8],
        "dynamic_threshold": args[offset + 9],
        "max_merge_gap_minutes": args[offset + 10],
        "merge_enabled": args[offset + 11],
        "merge_level": args[offset + 12],
        "include_compilations": args[offset + 13],
    }


def _snapshot_key(conn: sqlite3.Connection, values: dict[str, Any]) -> str | None:
    context = build_music_search_filter_context(conn, values)
    row = conn.execute(
        """SELECT snapshot_key FROM music_search_snapshot_meta
           WHERE filter_fingerprint=? AND status='ready' AND builder_version=?""",
        (context.filter_fingerprint, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
    ).fetchone()
    return str(row[0]) if row is not None else None


def _active_document(
    conn: sqlite3.Connection,
    *,
    kind: str,
    merge_level: int,
    track_id: int | None = None,
    name: str | None = None,
    artist_name: str | None = None,
) -> sqlite3.Row | None:
    clauses = ["d.generation_id=s.active_generation_id", "d.kind=?"]
    params: list[Any] = [kind]
    if kind == "track":
        clauses.extend(("d.merge_level=?", "d.track_id=?"))
        params.extend((merge_level, track_id))
    elif kind in {"album", "album_project"}:
        clauses.append("lower(d.label)=lower(?)")
        params.append(name)
        if artist_name:
            clauses.append("lower(d.artist_name)=lower(?)")
            params.append(artist_name)
    else:
        clauses.append("(lower(d.label)=lower(?) OR lower(d.artist_name)=lower(?))")
        params.extend((name, name))
    return conn.execute(
        f"""SELECT d.* FROM music_search_documents d
            CROSS JOIN music_search_index_state s
            WHERE {" AND ".join(clauses)}
            ORDER BY d.entity_key LIMIT 1""",
        params,
    ).fetchone()


def _context_row(
    conn: sqlite3.Connection, snapshot_key: str, entity_key: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM music_search_entity_context
           WHERE snapshot_key=? AND entity_key=?""",
        (snapshot_key, entity_key),
    ).fetchone()


def _track_meta(conn: sqlite3.Connection, track_id: int) -> dict | None:
    row = conn.execute(
        """SELECT stm.duration_ms, stm.popularity, stm.explicit,
                  stm.track_number, stm.disc_number,
                  sam.album_name AS spotify_album_name
           FROM tracks t
           LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id=t.spotify_track_id
           LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id=stm.spotify_album_id
           WHERE t.track_id=? LIMIT 1""",
        (track_id,),
    ).fetchone()
    if row is None:
        return None
    meta = {
        key: row[key]
        for key in (
            "duration_ms",
            "popularity",
            "track_number",
            "disc_number",
            "spotify_album_name",
        )
        if row[key] is not None
    }
    if row["explicit"] is not None:
        meta["explicit"] = bool(row["explicit"])
    return meta or None


def _album_meta(
    conn: sqlite3.Connection,
    album_name: str,
    artist_name: str,
    *,
    merge_level: int = 2,
    album_project_id: int | None = None,
    album_id: int | None = None,
) -> dict | None:
    return resolve_album_detail_meta(
        conn,
        album_name,
        artist_name,
        merge_level=merge_level,
        album_project_id=album_project_id,
        album_id=album_id,
    )


def _artist_meta(conn: sqlite3.Connection, artist_name: str) -> dict | None:
    provider = resolve_artist_spotify_meta(conn, artist_name)
    genres = resolve_artist_genres(conn, artist_name)
    raw = provider.metadata or {}
    meta: dict[str, Any] = {}
    for key in ("popularity", "followers"):
        if raw.get(key) is not None:
            meta[key] = raw[key]
    if raw.get("genres"):
        meta.update({"genres": raw["genres"], "genre_source": "spotify", "genre_confidence": 1.0})
    elif genres.genres:
        meta.update(
            {
                "genres": genres.genres,
                "genre_source": genres.source,
                "genre_confidence": genres.confidence,
            }
        )
    return meta or None


def _chart_summary(row: sqlite3.Row) -> dict | None:
    if row["peak_position"] is None:
        return None
    return {
        "peak_position": int(row["peak_position"]),
        "weeks_on_chart": int(row["weeks_on_chart"] or 0),
        "first_week": row["first_week"],
        "first_peak_week": row["first_peak_week"],
        "latest_week": row["latest_week"],
        "no1_weeks": int(row["weeks_at_no1"] or 0),
        "peak_weeks": int(row["peak_weeks"] or 0),
        "power_score": int(row["power_score"] or 0),
        "power_rank": int(row["power_rank"]) if row["power_rank"] is not None else None,
    }


def build_track_detail_summary(args: tuple) -> dict | None:
    values = _filter_values(args)
    if values["year_start"] is not None or values["year_end"] is not None:
        return None
    track_id = int(args[0])
    conn = get_db(readonly=True)
    try:
        snapshot_key = _snapshot_key(conn, values)
        document = _active_document(
            conn, kind="track", merge_level=int(values["merge_level"]), track_id=track_id
        )
        if snapshot_key is None or document is None:
            return None
        context = _context_row(conn, snapshot_key, str(document["entity_key"]))
        if context is None:
            return None
        credits = canonical_artist_names_for_effective_tracks(conn, [track_id]).get(track_id, [])
        raw = conn.execute(
            """SELECT t.track_name, t.artist_id, ar.artist_name
               FROM tracks t JOIN artists ar ON ar.artist_id=t.artist_id
               WHERE t.track_id=?""",
            (track_id,),
        ).fetchone()
        if raw is None:
            return None
        primary = resolve_artist_id(conn, int(raw["artist_id"])).display_name
        artist_names = credits or [primary]
        chart = _chart_summary(context)
        summary = None
        if chart is not None:
            total_chart_plays = conn.execute(
                """WITH ranked AS (
                       SELECT track_id, play_count,
                              ROW_NUMBER() OVER (
                                  PARTITION BY billboard_week
                                  ORDER BY play_count DESC, total_ms DESC, track_id ASC
                              ) AS chart_rank
                       FROM agg_weekly_tracks
                   )
                   SELECT COALESCE(SUM(play_count), 0) FROM ranked
                   WHERE track_id=? AND chart_rank<=?""",
                (track_id, int(values["bb_top_n"])),
            ).fetchone()[0]
            summary = {
                "peak_position": chart["peak_position"],
                "weeks_on_chart": chart["weeks_on_chart"],
                "weeks_at_peak": chart["peak_weeks"],
                "first_week": chart["first_week"],
                "last_week": chart["latest_week"],
                "first_peak_week": chart["first_peak_week"],
                "total_chart_plays": int(total_chart_plays or 0),
                "total_plays": int(context["play_events"]),
                "weeks_at_no1": chart["no1_weeks"],
                "power_score": chart["power_score"],
                "power_rank": chart["power_rank"],
            }
        return {
            "found": True,
            "chart_status": "charted" if chart else "not_charted",
            "track_id": track_id,
            "track_name": str(raw["track_name"]),
            "artist_name": ", ".join(artist_names),
            "artist_names": artist_names,
            "primary_artist_name": primary,
            "cover_url": document["cover_url"],
            "meta": _track_meta(conn, track_id),
            "summary": summary,
            "history": [],
            "chart_data": {},
        }
    finally:
        conn.close()


def build_album_detail_summary(args: tuple) -> dict | None:
    values = _filter_values(args, album_name=str(args[0]))
    if values["year_start"] is not None or values["year_end"] is not None:
        return None
    album_name, artist_name = str(args[0]), str(args[1])
    kind = "album" if int(values["merge_level"]) <= 1 else "album_project"
    conn = get_db(readonly=True)
    try:
        snapshot_key = _snapshot_key(conn, values)
        document = _active_document(
            conn,
            kind=kind,
            merge_level=int(values["merge_level"]),
            name=album_name,
            artist_name=artist_name,
        )
        if snapshot_key is None or document is None:
            return None
        context = _context_row(conn, snapshot_key, str(document["entity_key"]))
        if context is None:
            return None
        resolved_album = str(document["label"])
        resolved_artist = str(document["artist_name"])
        chart = _chart_summary(context)
        return {
            "found": True,
            "chart_status": "charted" if chart else "not_charted",
            "track_chart_status": None,
            "effective_play_count": int(context["play_events"]),
            "album_name": resolved_album,
            "artist_name": resolved_artist,
            "cover_url": document["cover_url"],
            "meta": _album_meta(
                conn,
                resolved_album,
                resolved_artist,
                merge_level=int(values["merge_level"]),
                album_project_id=document["album_project_id"],
                album_id=document["album_id"],
            ),
            "info": None,
            "chart_summary": chart,
            "album_project": None,
            "album_weekly_history": [],
            "album_no1_by_week": [],
            "best_singles_overlay": [],
            "tracks": [],
        }
    finally:
        conn.close()


def build_artist_detail_summary(args: tuple) -> dict | None:
    values = _filter_values(args)
    if values["year_start"] is not None or values["year_end"] is not None:
        return None
    requested = str(args[0])
    conn = get_db(readonly=True)
    try:
        snapshot_key = _snapshot_key(conn, values)
        identity = resolve_artist_name(conn, requested)
        resolved = identity.display_name if identity else requested
        document = _active_document(
            conn, kind="artist", merge_level=int(values["merge_level"]), name=resolved
        )
        if snapshot_key is None or document is None:
            return None
        context = _context_row(conn, snapshot_key, str(document["entity_key"]))
        if context is None:
            return None
        artist_name = str(document["label"])
        chart = _chart_summary(context)
        return {
            "found": True,
            "chart_status": "charted" if chart else "not_charted",
            "track_chart_status": None,
            "album_chart_status": None,
            "effective_play_count": int(context["play_events"]),
            "artist_name": artist_name,
            "cover_url": document["cover_url"],
            "meta": _artist_meta(conn, artist_name),
            "info": None,
            "chart_summary": chart,
            "artist_weekly_history": [],
            "artist_no1_by_week": [],
            "week_no1_albums": [],
            "best_singles_overlay": [],
            "best_albums_overlay": [],
            "tracks": [],
            "albums": [],
        }
    finally:
        conn.close()
