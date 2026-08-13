"""Strict, privacy-safe server pagination for the current music library snapshot."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

LIBRARY_DEFAULT_LIMIT = 20
LIBRARY_MAX_LIMIT = 50
LIBRARY_PLAYLIST_PREVIEW_LIMIT = 3

ALLOWED_SORTS: dict[str, tuple[str, ...]] = {
    "tracks": ("recent", "oldest", "name", "artist"),
    "albums": ("name", "artist"),
    "artists": ("name",),
    "playlists": ("name", "recent", "tracks"),
}


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


def _like_pattern(search: str) -> str:
    escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _cover(entity_type: str, entity_id: Any, image_path: Any, image_url: Any) -> str | None:
    if entity_id is None or not (image_path or image_url):
        return None
    return f"/covers/{entity_type}/{int(entity_id)}.jpg"


def _opaque_key(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(str(value or "").encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _library_revision(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    table_columns = {
        "saved_tracks": (
            "track_uri",
            "track_name",
            "artist_name",
            "album_name",
            "added_date",
            "spotify_track_id",
        ),
        "saved_albums": ("album_uri", "album_name", "artist_name"),
        "saved_artists": ("artist_uri", "artist_name"),
        "playlists": (
            "playlist_id",
            "playlist_name",
            "last_modified_date",
            "track_count",
            "follower_count",
        ),
        "playlist_tracks": (
            "playlist_id",
            "track_uri",
            "track_name",
            "artist_name",
            "album_name",
            "added_date",
        ),
    }
    for table, wanted in table_columns.items():
        available = _columns(conn, table)
        columns = [column for column in wanted if column in available]
        digest.update(f"table:{table}\n".encode())
        if not columns:
            digest.update(b"missing\n")
            continue
        selected = ", ".join(f'"{column}"' for column in columns)
        for row in conn.execute(f'SELECT {selected} FROM "{table}" ORDER BY {selected}'):
            digest.update(json.dumps(list(row), ensure_ascii=True, separators=(",", ":")).encode())
            digest.update(b"\n")
    return digest.hexdigest()[:20]


def _page_meta(
    entity_type: str,
    page: int,
    limit: int,
    total: int,
    sort: str,
    search: str,
    items: list[dict[str, Any]],
    data_revision: str,
) -> dict[str, Any]:
    return {
        "schema_version": "account_archive_library_v1",
        "content_version": "account_archive_library_v1_0",
        "data_revision": data_revision,
        "entity_type": entity_type,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit if total else 0,
        "sort": sort,
        "search_applied": bool(search.strip()),
        "items": items,
    }


def _track_page(
    conn: sqlite3.Connection,
    page: int,
    limit: int,
    search: str,
    sort: str,
) -> tuple[int, list[dict[str, Any]]]:
    if not _table_exists(conn, "saved_tracks"):
        return 0, []
    pattern = _like_pattern(search)
    where = (
        "WHERE (st.track_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR st.artist_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR st.album_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
        if search.strip()
        else ""
    )
    params: list[Any] = [pattern, pattern, pattern] if where else []
    order_by = {
        "recent": "CASE WHEN st.added_date IS NULL OR TRIM(st.added_date) = '' THEN 1 ELSE 0 END, st.added_date DESC, st.track_name COLLATE NOCASE, st.track_uri",
        "oldest": "CASE WHEN st.added_date IS NULL OR TRIM(st.added_date) = '' THEN 1 ELSE 0 END, st.added_date, st.track_name COLLATE NOCASE, st.track_uri",
        "name": "st.track_name COLLATE NOCASE, st.artist_name COLLATE NOCASE, st.track_uri",
        "artist": "st.artist_name COLLATE NOCASE, st.track_name COLLATE NOCASE, st.track_uri",
    }[sort]
    total = int(conn.execute(f"SELECT COUNT(*) FROM saved_tracks st {where}", params).fetchone()[0])
    saved_columns = _columns(conn, "saved_tracks")
    track_columns = _columns(conn, "tracks")
    album_columns = _columns(conn, "albums")
    track_lookup_queries: list[str] = []
    if "track_id" in track_columns:
        if "spotify_track_id" in saved_columns and "spotify_track_id" in track_columns:
            track_lookup_queries.append(
                "(SELECT tx.track_id FROM tracks tx "
                "WHERE st.spotify_track_id IS NOT NULL "
                "AND tx.spotify_track_id = st.spotify_track_id "
                "ORDER BY tx.track_id LIMIT 1)"
            )
        if "spotify_track_uri" in track_columns:
            track_lookup_queries.append(
                "(SELECT tx.track_id FROM tracks tx "
                "WHERE tx.spotify_track_uri = st.track_uri ORDER BY tx.track_id LIMIT 1)"
            )
    if track_lookup_queries:
        lookup = (
            track_lookup_queries[0]
            if len(track_lookup_queries) == 1
            else f"COALESCE({', '.join(track_lookup_queries)})"
        )
        has_album_mapping = {
            "album_id",
        }.issubset(track_columns) and {"album_id"}.issubset(album_columns)
        album_join = "LEFT JOIN albums al ON al.album_id = t.album_id" if has_album_mapping else ""
        album_id = "al.album_id" if has_album_mapping else "NULL"
        image_path = (
            "al.image_path" if has_album_mapping and "image_path" in album_columns else "NULL"
        )
        image_url = "al.image_url" if has_album_mapping and "image_url" in album_columns else "NULL"
        catalog_fields = f"t.track_id, {album_id}, {image_path}, {image_url}"
        catalog_join = f"""
        LEFT JOIN tracks t ON t.track_id = {lookup}
        {album_join}
        """
    else:
        catalog_fields = "NULL, NULL, NULL, NULL"
        catalog_join = ""
    rows = conn.execute(
        f"""
        SELECT st.track_uri, st.track_name, st.artist_name, st.album_name, st.added_date,
               {catalog_fields}
        FROM saved_tracks st
        {catalog_join}
        {where}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, (page - 1) * limit],
    ).fetchall()
    items = [
        {
            "entity_type": "track",
            "item_key": (
                f"track:{int(row[5])}" if row[5] is not None else _opaque_key("saved-track", row[0])
            ),
            "track_name": row[1] or "",
            "artist_name": row[2] or "",
            "album_name": row[3],
            "added_date": row[4],
            "cover_url": _cover("albums", row[6], row[7], row[8]),
            "deep_link": f"/music/tracks/{int(row[5])}" if row[5] is not None else None,
        }
        for row in rows
    ]
    return total, items


def _album_page(
    conn: sqlite3.Connection,
    page: int,
    limit: int,
    search: str,
    sort: str,
) -> tuple[int, list[dict[str, Any]]]:
    if not _table_exists(conn, "saved_albums"):
        return 0, []
    pattern = _like_pattern(search)
    where = (
        "WHERE (sa.album_name LIKE ? ESCAPE '\\' COLLATE NOCASE "
        "OR sa.artist_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
        if search.strip()
        else ""
    )
    params: list[Any] = [pattern, pattern] if where else []
    order_by = (
        "sa.artist_name COLLATE NOCASE, sa.album_name COLLATE NOCASE, sa.album_uri"
        if sort == "artist"
        else "sa.album_name COLLATE NOCASE, sa.artist_name COLLATE NOCASE, sa.album_uri"
    )
    total = int(conn.execute(f"SELECT COUNT(*) FROM saved_albums sa {where}", params).fetchone()[0])
    album_columns = _columns(conn, "albums")
    artist_columns = _columns(conn, "artists")
    if {"album_id", "album_name", "artist_id"}.issubset(album_columns) and {
        "artist_id",
        "artist_name",
    }.issubset(artist_columns):
        image_path = "al.image_path" if "image_path" in album_columns else "NULL"
        image_url = "al.image_url" if "image_url" in album_columns else "NULL"
        catalog_fields = f"al.album_id, {image_path}, {image_url}"
        catalog_join = """
        LEFT JOIN albums al ON al.album_id = (
            SELECT alx.album_id FROM albums alx
            JOIN artists arx ON arx.artist_id = alx.artist_id
            WHERE LOWER(TRIM(alx.album_name)) = LOWER(TRIM(sa.album_name))
              AND LOWER(TRIM(arx.artist_name)) = LOWER(TRIM(sa.artist_name))
            ORDER BY alx.album_id LIMIT 1
        )
        """
    else:
        catalog_fields = "NULL, NULL, NULL"
        catalog_join = ""
    rows = conn.execute(
        f"""
        SELECT sa.album_uri, sa.album_name, sa.artist_name,
               {catalog_fields}
        FROM saved_albums sa
        {catalog_join}
        {where}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, (page - 1) * limit],
    ).fetchall()
    return total, [
        {
            "entity_type": "album",
            "item_key": (
                f"album:{int(row[3])}" if row[3] is not None else _opaque_key("saved-album", row[0])
            ),
            "album_name": row[1] or "",
            "artist_name": row[2] or "",
            "cover_url": _cover("albums", row[3], row[4], row[5]),
            "deep_link": (
                f"/music/albums/{quote(row[1] or '', safe='')}?artist={quote(row[2] or '', safe='')}"
                if row[1] and row[3] is not None
                else None
            ),
        }
        for row in rows
    ]


def _artist_page(
    conn: sqlite3.Connection,
    page: int,
    limit: int,
    search: str,
) -> tuple[int, list[dict[str, Any]]]:
    if not _table_exists(conn, "saved_artists"):
        return 0, []
    pattern = _like_pattern(search)
    where = "WHERE sa.artist_name LIKE ? ESCAPE '\\' COLLATE NOCASE" if search.strip() else ""
    params: list[Any] = [pattern] if where else []
    total = int(
        conn.execute(f"SELECT COUNT(*) FROM saved_artists sa {where}", params).fetchone()[0]
    )
    artist_columns = _columns(conn, "artists")
    if {"artist_id", "artist_name"}.issubset(artist_columns):
        image_path = "a.image_path" if "image_path" in artist_columns else "NULL"
        image_url = "a.image_url" if "image_url" in artist_columns else "NULL"
        catalog_fields = f"a.artist_id, {image_path}, {image_url}"
        catalog_join = """
        LEFT JOIN artists a ON a.artist_id = (
            SELECT ax.artist_id FROM artists ax
            WHERE LOWER(TRIM(ax.artist_name)) = LOWER(TRIM(sa.artist_name))
            ORDER BY ax.artist_id LIMIT 1
        )
        """
    else:
        catalog_fields = "NULL, NULL, NULL"
        catalog_join = ""
    rows = conn.execute(
        f"""
        SELECT sa.artist_uri, sa.artist_name,
               {catalog_fields}
        FROM saved_artists sa
        {catalog_join}
        {where}
        ORDER BY sa.artist_name COLLATE NOCASE, sa.artist_uri
        LIMIT ? OFFSET ?
        """,
        [*params, limit, (page - 1) * limit],
    ).fetchall()
    return total, [
        {
            "entity_type": "artist",
            "item_key": (
                f"artist:{int(row[2])}"
                if row[2] is not None
                else _opaque_key("saved-artist", row[0])
            ),
            "artist_name": row[1] or "",
            "cover_url": _cover("artists", row[2], row[3], row[4]),
            "deep_link": (
                f"/music/artists/{quote(row[1] or '', safe='')}"
                if row[1] and row[2] is not None
                else None
            ),
        }
        for row in rows
    ]


def _playlist_page(
    conn: sqlite3.Connection,
    page: int,
    limit: int,
    search: str,
    sort: str,
) -> tuple[int, list[dict[str, Any]]]:
    if not _table_exists(conn, "playlists"):
        return 0, []
    pattern = _like_pattern(search)
    where = "WHERE p.playlist_name LIKE ? ESCAPE '\\' COLLATE NOCASE" if search.strip() else ""
    params: list[Any] = [pattern] if where else []
    order_by = {
        "name": "p.playlist_name COLLATE NOCASE, p.playlist_id",
        "recent": "CASE WHEN p.last_modified_date IS NULL OR TRIM(p.last_modified_date) = '' THEN 1 ELSE 0 END, p.last_modified_date DESC, p.playlist_name COLLATE NOCASE, p.playlist_id",
        "tracks": "actual_track_count DESC, p.playlist_name COLLATE NOCASE, p.playlist_id",
    }[sort]
    total = int(conn.execute(f"SELECT COUNT(*) FROM playlists p {where}", params).fetchone()[0])
    rows = conn.execute(
        f"""
        SELECT p.playlist_id, p.playlist_name, p.last_modified_date,
               COUNT(pt.rowid) AS actual_track_count, COALESCE(p.follower_count, 0)
        FROM playlists p
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
        {where}
        GROUP BY p.playlist_id, p.playlist_name, p.last_modified_date, p.follower_count
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, (page - 1) * limit],
    ).fetchall()
    playlist_ids = [int(row[0]) for row in rows]
    previews: dict[int, list[dict[str, str]]] = {playlist_id: [] for playlist_id in playlist_ids}
    if playlist_ids and _table_exists(conn, "playlist_tracks"):
        placeholders = ",".join("?" for _ in playlist_ids)
        preview_rows = conn.execute(
            f"""
            SELECT playlist_id, track_name, artist_name, rowid
            FROM playlist_tracks
            WHERE playlist_id IN ({placeholders})
            ORDER BY playlist_id, rowid
            """,
            playlist_ids,
        ).fetchall()
        for preview in preview_rows:
            bucket = previews[int(preview[0])]
            if len(bucket) < LIBRARY_PLAYLIST_PREVIEW_LIMIT:
                bucket.append({"track_name": preview[1] or "", "artist_name": preview[2] or ""})
    return total, [
        {
            "entity_type": "playlist",
            "item_key": f"playlist:{int(row[0])}",
            "playlist_id": int(row[0]),
            "playlist_name": row[1] or "",
            "last_modified_date": row[2],
            "track_count": int(row[3] or 0),
            "follower_count": int(row[4] or 0),
            "preview_tracks": previews[int(row[0])],
        }
        for row in rows
    ]


def build_archive_library_page(
    conn: sqlite3.Connection,
    entity_type: str,
    page: int = 1,
    limit: int = LIBRARY_DEFAULT_LIMIT,
    search: str = "",
    sort: str | None = None,
) -> dict[str, Any]:
    if entity_type not in ALLOWED_SORTS:
        raise ValueError(f"unsupported library entity type: {entity_type}")
    if page < 1 or limit < 1 or limit > LIBRARY_MAX_LIMIT:
        raise ValueError("invalid pagination")
    default_sort = "recent" if entity_type == "tracks" else "name"
    resolved_sort = sort or default_sort
    if resolved_sort not in ALLOWED_SORTS[entity_type]:
        raise ValueError(f"unsupported sort {resolved_sort} for {entity_type}")

    builders: Mapping[str, Any] = {
        "tracks": lambda: _track_page(conn, page, limit, search, resolved_sort),
        "albums": lambda: _album_page(conn, page, limit, search, resolved_sort),
        "artists": lambda: _artist_page(conn, page, limit, search),
        "playlists": lambda: _playlist_page(conn, page, limit, search, resolved_sort),
    }
    total, items = builders[entity_type]()
    return _page_meta(
        entity_type,
        page,
        limit,
        total,
        resolved_sort,
        search,
        items,
        _library_revision(conn),
    )
