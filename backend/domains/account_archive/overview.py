"""Small, privacy-whitelisted overview for the music archive landing state."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.domains.account_archive.revision import get_archive_revisions

ARCHIVE_OVERVIEW_CACHE_TTL_SECONDS = 300


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
    return {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _period_bounds(
    conn: sqlite3.Connection, table: str, column: str
) -> tuple[str | None, str | None]:
    if column not in _columns(conn, table):
        return None, None
    row = conn.execute(
        f"SELECT MIN({column}), MAX({column}) FROM {table} "
        f"WHERE {column} IS NOT NULL AND TRIM({column}) != ''"
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def _revision_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    first_play, latest_play = _period_bounds(conn, "plays", "ts_date")
    first_saved, latest_saved = _period_bounds(conn, "saved_tracks", "added_date")
    revisions = get_archive_revisions(conn)
    payload: dict[str, Any] = {
        "account_import_revision": revisions["account_import"],
        "collection_date_revision": revisions["collection_date"],
        "saved_tracks": _count(conn, "saved_tracks"),
        "saved_albums": _count(conn, "saved_albums"),
        "saved_artists": _count(conn, "saved_artists"),
        "saved_shows": _count(conn, "saved_shows"),
        "playlists": _count(conn, "playlists"),
        "playlist_items": _count(conn, "playlist_tracks"),
        "plays": _count(conn, "plays"),
        "first_saved": first_saved,
        "latest_saved": latest_saved,
        "first_play": first_play,
        "latest_play": latest_play,
    }
    if _table_exists(conn, "plays"):
        play_columns = _columns(conn, "plays")
        row = conn.execute(
            "SELECT "
            + ", ".join(
                [
                    "COALESCE(MAX(play_id), 0)" if "play_id" in play_columns else "0",
                    "COALESCE(MAX(ts), '')" if "ts" in play_columns else "''",
                    "COALESCE(SUM(ms_played), 0)" if "ms_played" in play_columns else "0",
                ]
            )
            + " FROM plays"
        ).fetchone()
        payload.update(
            {
                "max_play_id": int(row[0] or 0),
                "latest_play_at": row[1] or "",
                "total_play_ms": int(row[2] or 0),
            }
        )
    for table in ("artist_identity_state", "track_credit_state"):
        if _table_exists(conn, table):
            row = conn.execute(
                f"SELECT current_revision FROM {table} WHERE state_id = 1"
            ).fetchone()
            payload[table] = int(row[0] or 0) if row else 0
    return payload


def archive_data_revision(conn: sqlite3.Connection) -> str:
    """Return an opaque revision that changes when any overview input changes."""
    encoded = json.dumps(
        _revision_payload(conn), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def load_saved_track_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "saved_tracks"):
        return []

    saved_columns = _columns(conn, "saved_tracks")
    album_columns = _columns(conn, "albums")
    source_expr = "st.added_date_source" if "added_date_source" in saved_columns else "NULL"
    local_release_expr = "al.release_date" if "release_date" in album_columns else "NULL"
    image_path_expr = "al.image_path" if "image_path" in album_columns else "NULL"
    image_url_expr = "al.image_url" if "image_url" in album_columns else "NULL"

    rows = conn.execute(
        f"""
        SELECT
            st.track_uri,
            COALESCE(st.track_name, '') AS track_name,
            COALESCE(st.artist_name, '') AS artist_name,
            st.album_name,
            st.added_date,
            {source_expr} AS added_date_source,
            t.track_id AS local_track_id,
            al.album_id AS local_album_id,
            {image_path_expr} AS image_path,
            {image_url_expr} AS image_url,
            COALESCE({local_release_expr}, sam.release_date) AS release_date,
            stm.duration_ms AS duration_ms
        FROM saved_tracks st
        LEFT JOIN tracks t ON t.track_id = COALESCE(
            (SELECT tx.track_id FROM tracks tx
             WHERE st.spotify_track_id IS NOT NULL
               AND tx.spotify_track_id = st.spotify_track_id
             ORDER BY tx.track_id LIMIT 1),
            (SELECT tx.track_id FROM tracks tx
             WHERE tx.spotify_track_uri = st.track_uri
             ORDER BY tx.track_id LIMIT 1)
        )
        LEFT JOIN albums al ON al.album_id = t.album_id
        LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = st.spotify_track_id
        LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = stm.spotify_album_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    # Product percentages use conventional half-up rounding, not Python's
    # banker rounding (762 / 800 should display as 95.3%, not 95.2%).
    tenths = (2 * numerator * 1000 + denominator) // (2 * denominator)
    return tenths / 10


def _capability_status(count: int, total: int) -> str:
    if count <= 0:
        return "unavailable"
    if count < total:
        return "partial"
    return "available"


def _feature_payload(role: str, row: dict[str, Any]) -> dict[str, Any]:
    cover_url = None
    if row.get("local_album_id") is not None and (row.get("image_path") or row.get("image_url")):
        cover_url = f"/covers/albums/{int(row['local_album_id'])}.jpg"
    local_track_id = row.get("local_track_id")
    return {
        "role": role,
        "track_name": row.get("track_name") or "",
        "artist_name": row.get("artist_name") or "",
        "album_name": row.get("album_name"),
        "added_date": row.get("added_date"),
        "release_date": row.get("release_date"),
        "cover_url": cover_url,
        "deep_link": f"/music/tracks/{int(local_track_id)}" if local_track_id is not None else None,
    }


def _featured_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dated = sorted(
        (row for row in rows if row.get("added_date")), key=lambda row: row["added_date"]
    )
    released = sorted(
        (row for row in rows if row.get("release_date")), key=lambda row: row["release_date"]
    )
    candidates = (
        ("first_saved", dated),
        ("latest_saved", list(reversed(dated))),
        ("oldest_release", released),
        ("newest_release", list(reversed(released))),
    )
    used: set[str] = set()
    featured: list[dict[str, Any]] = []
    for role, role_rows in candidates:
        selected = next(
            (row for row in role_rows if (row.get("track_uri") or "") not in used), None
        )
        if selected is None:
            continue
        used.add(selected.get("track_uri") or "")
        featured.append(_feature_payload(role, selected))
    return featured


def build_archive_overview(
    conn: sqlite3.Connection, *, data_revision: str | None = None
) -> dict[str, Any]:
    """Build the strict, compact overview without calling any online provider."""
    rows = load_saved_track_rows(conn)
    saved_tracks = len(rows)
    dated = sum(1 for row in rows if row.get("added_date"))
    linked = sum(1 for row in rows if row.get("local_track_id") is not None)
    known_duration_rows = [row for row in rows if int(row.get("duration_ms") or 0) > 0]
    known_duration = len(known_duration_rows)
    first_saved, latest_saved = _period_bounds(conn, "saved_tracks", "added_date")
    first_play, latest_play = _period_bounds(conn, "plays", "ts_date")

    source_counts = {"oauth": 0, "manual": 0, "legacy": 0}
    for row in rows:
        source = row.get("added_date_source")
        if row.get("added_date") and source in source_counts:
            source_counts[source] += 1
        elif row.get("added_date"):
            source_counts["legacy"] += 1

    playlists = _count(conn, "playlists")
    saved_albums = _count(conn, "saved_albums")
    saved_artists = _count(conn, "saved_artists")
    saved_shows = _count(conn, "saved_shows")
    has_snapshot = saved_tracks + saved_albums + saved_artists + playlists > 0
    if not has_snapshot:
        status = "empty"
    elif saved_tracks > 0 and dated == saved_tracks and linked == saved_tracks and latest_play:
        status = "ready"
    else:
        status = "partial"

    cross_status = "unavailable"
    if saved_tracks and linked and latest_play:
        cross_status = _capability_status(linked, saved_tracks)

    return {
        "schema_version": "account_archive_v1",
        "content_version": "account_archive_v1_0",
        "data_revision": data_revision or archive_data_revision(conn),
        "status": status,
        "counts": {
            "saved_tracks": saved_tracks,
            "saved_albums": saved_albums,
            "saved_artists": saved_artists,
            "saved_shows": saved_shows,
            "playlists": playlists,
            "playlist_items": _count(conn, "playlist_tracks"),
        },
        "coverage": {
            "saved_tracks_with_date": dated,
            "saved_tracks_with_date_pct": _pct(dated, saved_tracks),
            "saved_tracks_linked_to_history": linked,
            "saved_tracks_linked_to_history_pct": _pct(linked, saved_tracks),
            "saved_tracks_with_known_duration": known_duration,
            "saved_tracks_with_known_duration_pct": _pct(known_duration, saved_tracks),
            "known_duration_ms": sum(int(row["duration_ms"]) for row in known_duration_rows),
        },
        "period": {
            "first_saved_at": first_saved,
            "latest_saved_at": latest_saved,
            "first_play_date": first_play,
            "latest_play_date": latest_play,
        },
        "date_provenance": {
            **source_counts,
            "missing": saved_tracks - dated,
        },
        "capabilities": {
            "collection_browse": "available" if has_snapshot else "unavailable",
            "collection_timeline": _capability_status(dated, saved_tracks),
            "playback_cross_analysis": cross_status,
        },
        "featured_items": _featured_items(rows),
    }


def _database_path(conn: sqlite3.Connection) -> str | None:
    for row in conn.execute("PRAGMA database_list").fetchall():
        if row[1] == "main" and row[2]:
            return os.path.realpath(row[2])
    return None


@ttl_cached(ARCHIVE_OVERVIEW_CACHE_TTL_SECONDS, namespace="account_archive")
def _get_archive_overview_cached(db_path: str, data_revision: str) -> dict[str, Any]:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        return build_archive_overview(conn, data_revision=data_revision)
    finally:
        conn.close()


register_ttl("account_archive", "overview", _get_archive_overview_cached)


def get_archive_overview(conn: sqlite3.Connection) -> dict[str, Any]:
    """Use revision-keyed caching for file DBs and direct reads for memory DBs."""
    data_revision = archive_data_revision(conn)
    db_path = _database_path(conn)
    if db_path and os.path.exists(db_path):
        return _get_archive_overview_cached(db_path, data_revision)
    return build_archive_overview(conn, data_revision=data_revision)
