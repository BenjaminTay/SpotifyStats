"""Library / account data services — direct SQL queries on account tables."""

import sqlite3
from pathlib import Path

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl

LIBRARY_CACHE_TTL = 300


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


@ttl_cached(LIBRARY_CACHE_TTL, namespace="library")
def _get_library_overview_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_library_overview(conn)
    finally:
        conn.close()


def get_library_overview(conn: sqlite3.Connection) -> dict:
    """Full library overview: saved tracks, coverage, forgotten treasures, etc."""
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_library_overview(conn)
    return _get_library_overview_cached(db_path)


def _build_library_overview(conn: sqlite3.Connection) -> dict:
    try:
        saved_tracks_df = pd.read_sql_query("SELECT * FROM saved_tracks", conn)
        saved_albums_df = pd.read_sql_query("SELECT * FROM saved_albums", conn)
        saved_artists_df = pd.read_sql_query("SELECT * FROM saved_artists", conn)
        playlists_df = pd.read_sql_query("SELECT * FROM playlists", conn)
        banned_df = pd.read_sql_query("SELECT * FROM banned_items", conn)
    except Exception:
        return {"available": False}

    # Cross-reference saved tracks with play history
    if not saved_tracks_df.empty:
        track_uris = saved_tracks_df["track_uri"].dropna().tolist()
        # Extract Spotify track IDs from URIs
        track_ids = [uri.replace("spotify:track:", "") for uri in track_uris if uri]
        if track_ids:
            placeholders = ",".join("?" * len(track_ids))
            coverage_df = pd.read_sql_query(
                f"""SELECT t.spotify_track_id as tid,
                           COUNT(p.play_id) as play_count, MAX(p.ts_date) as last_played
                    FROM tracks t
                    LEFT JOIN plays p ON t.track_id = p.track_id
                    WHERE t.spotify_track_id IN ({placeholders})
                    GROUP BY 1""",
                conn,
                params=track_ids,
            )
            coverage_pct = (
                (coverage_df["play_count"] > 0).mean() * 100 if not coverage_df.empty else 0
            )

            # Forgotten treasures (saved but never played)
            forgotten = coverage_df[coverage_df["play_count"] == 0]
            forgotten_list = [
                {"track_id": r.tid, "never_played": True} for r in forgotten.itertuples(index=False)
            ]
        else:
            coverage_pct = 0
            forgotten_list = []
    else:
        coverage_pct = 0
        forgotten_list = []

    # Artist comparison (saved vs played)
    artist_comp_rows = conn.execute(
        """SELECT sa.artist_name,
                  COUNT(DISTINCT st.track_uri) as saved_count
           FROM saved_artists sa
           LEFT JOIN saved_tracks st ON st.artist_name = sa.artist_name
           GROUP BY sa.artist_name
           ORDER BY saved_count DESC"""
    ).fetchall()

    artist_comparison = []
    for r in artist_comp_rows:
        play_count = conn.execute(
            """SELECT COUNT(DISTINCT p.play_id)
               FROM plays p JOIN tracks t ON p.track_id = t.track_id
               JOIN track_artists ta ON t.track_id = ta.track_id
               JOIN artists a ON ta.artist_id = a.artist_id
               WHERE a.artist_name = ?""",
            (r["artist_name"],),
        ).fetchone()[0]
        artist_comparison.append(
            {
                "artist_name": r["artist_name"],
                "saved_count": r["saved_count"] or 0,
                "play_count": play_count or 0,
            }
        )

    return {
        "available": True,
        "saved_tracks": len(saved_tracks_df),
        "saved_albums": len(saved_albums_df),
        "saved_artists": len(saved_artists_df),
        "playlists": len(playlists_df),
        "banned_items": len(banned_df),
        "coverage_pct": round(coverage_pct, 1),
        "forgotten_count": len(forgotten_list),
        "forgotten_tracks": forgotten_list[:20],
        "artist_comparison": artist_comparison[:15],
    }


def get_playlists(conn: sqlite3.Connection) -> list[dict]:
    """Get all playlists with track counts."""
    rows = conn.execute(
        "SELECT playlist_id, playlist_name, last_modified_date, track_count FROM playlists ORDER BY playlist_name"
    ).fetchall()
    return [
        {
            "id": r["playlist_id"],
            "name": r["playlist_name"],
            "last_modified": r["last_modified_date"] or "",
            "track_count": r["track_count"] or 0,
        }
        for r in rows
    ]


def get_playlist_tracks(conn: sqlite3.Connection, playlist_id: int) -> list[dict]:
    """Get tracks in a specific playlist."""
    rows = conn.execute(
        "SELECT track_uri, track_name, artist_name, album_name, added_date FROM playlist_tracks WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchall()
    tracks = [
        {
            "track_uri": r["track_uri"],
            "track_name": r["track_name"],
            "artist_name": r["artist_name"],
            "album_name": r["album_name"] or "",
            "added_date": r["added_date"] or "",
        }
        for r in rows
    ]

    # Resolve cover URLs via tracks→albums join
    if tracks:
        pairs = [(t["track_name"], t["artist_name"]) for t in tracks]
        placeholders = ",".join("(?,?)" for _ in pairs)
        flat_params = [v for pair in pairs for v in pair]
        cover_rows = conn.execute(
            f"""SELECT t.track_name, a.artist_name, al.album_id, al.image_path, al.image_url
                FROM tracks t
                JOIN artists a ON t.artist_id = a.artist_id
                LEFT JOIN albums al ON t.album_id = al.album_id
                WHERE (t.track_name, a.artist_name) IN ({placeholders})""",
            flat_params,
        ).fetchall()
        for r in cover_rows:
            key = (r["track_name"], r["artist_name"])
            entity_id = r["album_id"]
            if entity_id and (r["image_path"] or r["image_url"]):
                for t in tracks:
                    if t["track_name"] == key[0] and t["artist_name"] == key[1]:
                        t["cover_url"] = f"/covers/albums/{int(entity_id)}.jpg"
                        break

    return tracks


def get_saved_tracks_paginated(
    conn: sqlite3.Connection, page: int = 1, limit: int = 50, search: str = ""
) -> dict:
    """Paginated saved tracks with optional search."""
    offset = (page - 1) * limit
    where = ""
    params: list = []
    if search:
        where = "WHERE track_name LIKE ? OR artist_name LIKE ?"
        params = [f"%{search}%", f"%{search}%"]

    count_row = conn.execute(f"SELECT COUNT(*) FROM saved_tracks {where}", params).fetchone()
    total = count_row[0]

    rows = conn.execute(
        f"""SELECT track_uri, track_name, artist_name, album_name, added_date
            FROM saved_tracks
            {where}
            ORDER BY added_date DESC, track_name
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    # Resolve cover URLs via tracks→albums join for this page
    tracks = [dict(r) for r in rows]
    if tracks:
        pairs = [(t["track_name"], t["artist_name"]) for t in tracks]
        placeholders = ",".join("(?,?)" for _ in pairs)
        flat_params = [v for pair in pairs for v in pair]
        cover_rows = conn.execute(
            f"""SELECT t.track_name, a.artist_name, al.album_id, al.image_path, al.image_url
                FROM tracks t
                JOIN artists a ON t.artist_id = a.artist_id
                LEFT JOIN albums al ON t.album_id = al.album_id
                WHERE (t.track_name, a.artist_name) IN ({placeholders})""",
            flat_params,
        ).fetchall()
        cover_map: dict = {}
        for r in cover_rows:
            key = (r["track_name"], r["artist_name"])
            if key not in cover_map:
                entity_id = r["album_id"]
                if entity_id and (r["image_path"] or r["image_url"]):
                    cover_map[key] = f"/covers/albums/{int(entity_id)}.jpg"
        for t in tracks:
            t["cover_url"] = cover_map.get((t["track_name"], t["artist_name"]))

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        "tracks": tracks,
    }


def get_playlist_overlap_matrix(conn: sqlite3.Connection) -> dict:
    """Compute playlist overlap matrix (shared tracks between playlists)."""
    rows = conn.execute(
        "SELECT playlist_id, track_uri FROM playlist_tracks ORDER BY playlist_id"
    ).fetchall()
    playlists = {r["playlist_id"]: set() for r in rows}
    for r in rows:
        playlists[r["playlist_id"]].add(r["track_uri"])

    ids = sorted(playlists.keys())
    names = {}
    for pid in ids:
        n = conn.execute(
            "SELECT playlist_name FROM playlists WHERE playlist_id = ?", (pid,)
        ).fetchone()
        names[pid] = n["playlist_name"] if n else str(pid)

    n = len(ids)
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(len(playlists[ids[i]]))
            else:
                overlap = len(playlists[ids[i]] & playlists[ids[j]])
                row.append(overlap)
        matrix.append(row)

    return {
        "playlist_ids": ids,
        "playlist_names": [names[pid] for pid in ids],
        "matrix": matrix,
    }


register_ttl("library", "overview", _get_library_overview_cached)
