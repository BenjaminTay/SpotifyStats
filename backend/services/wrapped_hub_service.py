"""Official Spotify Wrapped data service."""

import sqlite3
from pathlib import Path

import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl
from backend.domains.metadata.artist_spotify_meta import resolve_artist_image_url

WRAPPED_HUB_CACHE_TTL = 600


def _resolve_track_id(conn: sqlite3.Connection, track_uri: str) -> int:
    """Resolve a Spotify track URI to internal track_id."""
    if not track_uri:
        return 0
    spotify_id = track_uri.replace("spotify:track:", "")
    if not spotify_id:
        return 0
    r = conn.execute(
        "SELECT track_id FROM tracks WHERE spotify_track_uri = ? LIMIT 1",
        (track_uri,),
    ).fetchone()
    if r:
        return r[0]
    r = conn.execute(
        "SELECT track_id FROM tracks WHERE spotify_track_uri LIKE ? LIMIT 1",
        (f"%{spotify_id}%",),
    ).fetchone()
    return r[0] if r else 0


def _resolve_album_artist(conn: sqlite3.Connection, album_name: str) -> str:
    """Look up artist name for an album by album name."""
    if not album_name:
        return ""
    r = conn.execute(
        "SELECT ar.artist_name FROM albums al "
        "JOIN artists ar ON al.artist_id = ar.artist_id "
        "WHERE al.album_name = ? LIMIT 1",
        (album_name,),
    ).fetchone()
    return (r[0] or "") if r else ""


def _get_cover_for_name(conn: sqlite3.Connection, name: str, kind: str) -> str:
    """Look up cover image URL by display name."""
    if not name:
        return ""
    if kind == "artist":
        return resolve_artist_image_url(conn, name)
    elif kind == "track":
        r = conn.execute(
            "SELECT sam.image_url FROM spotify_track_meta stm "
            "JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id "
            "JOIN tracks t ON t.spotify_track_id = stm.spotify_track_id "
            "WHERE t.track_name = ? LIMIT 1",
            (name,),
        ).fetchone()
    elif kind == "album":
        r = conn.execute(
            "SELECT image_url FROM spotify_album_meta WHERE album_name = ? LIMIT 1",
            (name,),
        ).fetchone()
    else:
        return ""
    return (r[0] or "") if r else ""


def _resolve_uri_name(conn: sqlite3.Connection, uri: str, uri_type: str = "artist") -> str:
    """Resolve a Spotify URI to a display name using saved data and meta tables."""
    spotify_id = uri.replace(f"spotify:{uri_type}:", "") if uri else ""
    if not spotify_id:
        return uri

    if uri_type == "artist":
        # Check spotify_artist_meta
        r = conn.execute(
            "SELECT artist_name FROM spotify_artist_meta WHERE spotify_artist_id = ?", (spotify_id,)
        ).fetchone()
        if r:
            return r[0]
        # Check saved_artists
        r = conn.execute(
            "SELECT artist_name FROM saved_artists WHERE artist_uri = ?", (uri,)
        ).fetchone()
        if r:
            return r[0]
    elif uri_type == "track":
        r = conn.execute(
            "SELECT track_name FROM spotify_track_meta WHERE spotify_track_id = ?", (spotify_id,)
        ).fetchone()
        if r:
            return r[0]
        r = conn.execute(
            "SELECT t.track_name FROM tracks t WHERE t.spotify_track_id = ?",
            (spotify_id,),
        ).fetchone()
        if r:
            return r[0]
    elif uri_type == "album":
        r = conn.execute(
            "SELECT album_name FROM spotify_album_meta WHERE spotify_album_id = ?", (spotify_id,)
        ).fetchone()
        if r:
            return r[0]
        r = conn.execute(
            "SELECT album_name FROM saved_albums WHERE album_uri = ?", (uri,)
        ).fetchone()
        if r:
            return r[0]
    elif uri_type == "show":
        r = conn.execute("SELECT show_name FROM saved_shows WHERE show_uri = ?", (uri,)).fetchone()
        if r:
            return r[0]

    return spotify_id or uri


def _database_file_path(conn: sqlite3.Connection):
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        if not row[2]:
            return None
        return str(Path(row[2]).resolve())
    return None


@ttl_cached(WRAPPED_HUB_CACHE_TTL, namespace="wrapped")
def _get_wrapped_hub_cached(db_path: str) -> dict:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        return _build_wrapped_hub(conn)
    finally:
        conn.close()


def get_wrapped_hub(conn: sqlite3.Connection) -> dict:
    """Load all official Spotify Wrapped 2025 data."""
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_wrapped_hub(conn)
    return _get_wrapped_hub_cached(db_path)


def _build_wrapped_hub(conn: sqlite3.Connection) -> dict:
    try:
        top_artists = pd.read_sql_query("SELECT * FROM wrapped_top_artists ORDER BY rank", conn)
        top_tracks = pd.read_sql_query("SELECT * FROM wrapped_top_tracks ORDER BY rank", conn)
        top_albums = pd.read_sql_query("SELECT * FROM wrapped_top_albums ORDER BY rank", conn)
        artist_race = pd.read_sql_query("SELECT * FROM wrapped_artist_race", conn)
        clubs = pd.read_sql_query("SELECT * FROM wrapped_clubs", conn)
        party = pd.read_sql_query("SELECT * FROM wrapped_party", conn)
        listening_age = conn.execute("SELECT * FROM wrapped_listening_age").fetchone()
        archive = pd.read_sql_query("SELECT * FROM wrapped_archive_reports", conn)
        top_genres = pd.read_sql_query("SELECT * FROM wrapped_top_genres ORDER BY rank", conn)
        top_podcasts = pd.read_sql_query("SELECT * FROM wrapped_top_podcasts ORDER BY rank", conn)
    except Exception:
        return {"available": False}

    if top_artists.empty:
        return {"available": True, "empty": True}

    # ── Batch resolve all URIs → display names ──
    uri_name_map = {}  # type: dict[str, str]

    def _collect_ids(df, uri_col, kind):
        ids = set()
        for u in df[uri_col].dropna():
            spotify_id = u.replace(f"spotify:{kind}:", "")
            if spotify_id:
                ids.add(spotify_id)
                uri_name_map[u] = spotify_id  # fallback: raw ID
        return ids

    # Collect unique spotify IDs per entity type
    artist_ids = _collect_ids(top_artists, "artist_uri", "artist")
    artist_ids |= _collect_ids(top_genres, "genre_uri", "artist")
    artist_ids |= _collect_ids(clubs, "artist_uri", "artist")
    for u in artist_race["artist_uri"].dropna():
        sid = u.replace("spotify:artist:", "")
        if sid:
            artist_ids.add(sid)
            uri_name_map[u] = sid

    track_ids = _collect_ids(top_tracks, "track_uri", "track")
    album_ids = _collect_ids(top_albums, "album_uri", "album")
    show_ids = _collect_ids(top_podcasts, "podcast_uri", "show")

    # Batch query spotify_artist_meta
    if artist_ids:
        placeholders = ",".join("?" * len(artist_ids))
        for r in conn.execute(
            f"SELECT spotify_artist_id, artist_name FROM spotify_artist_meta "
            f"WHERE spotify_artist_id IN ({placeholders})",
            tuple(artist_ids),
        ).fetchall():
            uri_name_map[f"spotify:artist:{r[0]}"] = r[1]
        # Fallback to saved_artists for unmatched
        unmatched = [
            u
            for u, sid in uri_name_map.items()
            if u.startswith("spotify:artist:") and u not in uri_name_map
            if sid == u.replace("spotify:artist:", "")
        ]
        # Re-collect unmatched by direct URI lookup
        unmatched_uris = {
            u
            for u in uri_name_map
            if u.startswith("spotify:artist:")
            and uri_name_map[u] == u.replace("spotify:artist:", "")
        }
        if unmatched_uris:
            placeholders2 = ",".join("?" * len(unmatched_uris))
            for r in conn.execute(
                f"SELECT artist_uri, artist_name FROM saved_artists WHERE artist_uri IN ({placeholders2})",
                tuple(unmatched_uris),
            ).fetchall():
                uri_name_map[r[0]] = r[1]

    # Batch query spotify_track_meta
    if track_ids:
        placeholders = ",".join("?" * len(track_ids))
        for r in conn.execute(
            f"SELECT spotify_track_id, track_name FROM spotify_track_meta "
            f"WHERE spotify_track_id IN ({placeholders})",
            tuple(track_ids),
        ).fetchall():
            uri_name_map[f"spotify:track:{r[0]}"] = r[1]
        # Fallback to tracks table
        unmatched_track = {
            u
            for u in uri_name_map
            if u.startswith("spotify:track:") and uri_name_map[u] == u.replace("spotify:track:", "")
        }
        if unmatched_track:
            sids = [u.replace("spotify:track:", "") for u in unmatched_track]
            pts = ",".join("?" * len(sids))
            for r in conn.execute(
                f"SELECT t.spotify_track_id, t.track_name FROM tracks t "
                f"WHERE t.spotify_track_id IN ({pts})",
                tuple(sids),
            ).fetchall():
                if r[0]:
                    uri_name_map[f"spotify:track:{r[0]}"] = r[1]

    # Batch query spotify_album_meta
    if album_ids:
        placeholders = ",".join("?" * len(album_ids))
        for r in conn.execute(
            f"SELECT spotify_album_id, album_name FROM spotify_album_meta "
            f"WHERE spotify_album_id IN ({placeholders})",
            tuple(album_ids),
        ).fetchall():
            uri_name_map[f"spotify:album:{r[0]}"] = r[1]
        # Fallback to saved_albums
        unmatched_album = {
            u
            for u in uri_name_map
            if u.startswith("spotify:album:") and uri_name_map[u] == u.replace("spotify:album:", "")
        }
        if unmatched_album:
            for r in conn.execute(
                f"SELECT album_uri, album_name FROM saved_albums WHERE album_uri IN "
                f"({','.join('?' * len(unmatched_album))})",
                tuple(unmatched_album),
            ).fetchall():
                uri_name_map[r[0]] = r[1]

    # Batch query saved_shows
    if show_ids:
        for r in conn.execute("SELECT show_uri, show_name FROM saved_shows").fetchall():
            uri_name_map[r[0]] = r[1]

    # Apply display_name to DataFrames
    for df, uri_col in [
        (top_artists, "artist_uri"),
        (top_tracks, "track_uri"),
        (top_albums, "album_uri"),
        (top_genres, "genre_uri"),
        (top_podcasts, "podcast_uri"),
        (clubs, "artist_uri"),
    ]:
        if uri_col in df.columns:
            df["display_name"] = df[uri_col].apply(
                lambda u: uri_name_map.get(u, u) if pd.notna(u) else ""
            )

    # ── Batch resolve track IDs ──
    track_id_map = {}
    if track_ids:
        placeholders = ",".join("?" * len(track_ids))
        for r in conn.execute(
            f"SELECT t.spotify_track_id, t.track_id FROM tracks t "
            f"WHERE t.spotify_track_id IN ({placeholders})",
            tuple(track_ids),
        ).fetchall():
            if r[0]:
                track_id_map[r[0]] = int(r[1])
        # Also match via spotify_track_uri
        unmatched = track_ids - set(track_id_map.keys())
        if unmatched:
            full_uris = [f"spotify:track:{sid}" for sid in unmatched]
            uris_pts = ",".join("?" * len(full_uris))
            for r in conn.execute(
                f"SELECT spotify_track_uri, track_id FROM tracks WHERE spotify_track_uri IN ({uris_pts})",
                tuple(full_uris),
            ).fetchall():
                sid = r[0].replace("spotify:track:", "")
                track_id_map[sid] = int(r[1])

    def _resolve_track_id_fast(track_uri):
        if not track_uri:
            return 0
        sid = track_uri.replace("spotify:track:", "")
        return track_id_map.get(sid, 0)

    # ── Batch resolve album artists ──
    album_artist_map = {}
    album_names = {n for n in top_albums["display_name"].dropna() if n}
    if album_names:
        placeholders = ",".join("?" * len(album_names))
        for r in conn.execute(
            f"SELECT al.album_name, ar.artist_name FROM albums al "
            f"JOIN artists ar ON al.artist_id = ar.artist_id "
            f"WHERE al.album_name IN ({placeholders})",
            tuple(album_names),
        ).fetchall():
            album_artist_map[r[0]] = r[1] or ""

    # ── Batch resolve cover URLs ──
    cover_map = {}  # (name, kind) → url

    # Artist covers
    all_artist_names = {n for n in top_artists["display_name"].dropna() if n}
    all_artist_names |= {n for n in clubs["display_name"].dropna() if n}
    # Collect from artist_race too (resolved via uri_name_map)
    all_artist_names |= {
        uri_name_map.get(r.artist_uri, r.artist_uri)
        for r in artist_race.itertuples(index=False)
        if pd.notna(r.artist_uri)
    }
    if all_artist_names:
        placeholders = ",".join("?" * len(all_artist_names))
        for r in conn.execute(
            f"SELECT artist_name, image_url FROM spotify_artist_meta "
            f"WHERE artist_name IN ({placeholders})",
            tuple(all_artist_names),
        ).fetchall():
            if r[1]:
                cover_map[(r[0], "artist")] = r[1]
        for artist_name in all_artist_names:
            key = (artist_name, "artist")
            if key not in cover_map:
                image_url = resolve_artist_image_url(conn, artist_name)
                if image_url:
                    cover_map[key] = image_url

    # Track covers
    all_track_names = {n for n in top_tracks["display_name"].dropna() if n}
    if all_track_names:
        placeholders = ",".join("?" * len(all_track_names))
        for r in conn.execute(
            f"SELECT t.track_name, sam.image_url FROM spotify_track_meta stm "
            f"JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id "
            f"JOIN tracks t ON t.spotify_track_id = stm.spotify_track_id "
            f"WHERE t.track_name IN ({placeholders})",
            tuple(all_track_names),
        ).fetchall():
            if r[1]:
                cover_map[(r[0], "track")] = r[1]

    # Album covers
    all_album_names = {n for n in top_albums["display_name"].dropna() if n}
    if all_album_names:
        placeholders = ",".join("?" * len(all_album_names))
        for r in conn.execute(
            f"SELECT album_name, image_url FROM spotify_album_meta "
            f"WHERE album_name IN ({placeholders})",
            tuple(all_album_names),
        ).fetchall():
            if r[1]:
                cover_map[(r[0], "album")] = r[1]

    def _get_cover_fast(name, kind):
        if not name:
            return ""
        return cover_map.get((name, kind), "")

    return {
        "available": True,
        "empty": False,
        "top_artists": [
            {
                "rank": int(r.rank),
                "name": r.display_name or r.artist_uri,
                "ms_played": int(r.ms_played) if pd.notna(r.ms_played) else 0,
                "percentile": float(r.percentile) if pd.notna(r.percentile) else None,
                "cover_url": _get_cover_fast(r.display_name, "artist")
                if pd.notna(r.display_name)
                else "",
            }
            for r in top_artists.itertuples(index=False)
        ],
        "top_tracks": [
            {
                "rank": int(r.rank),
                "name": r.display_name or r.track_uri,
                "track_id": _resolve_track_id_fast(r.track_uri) if pd.notna(r.track_uri) else 0,
                "play_count": int(r.play_count) if pd.notna(r.play_count) else 0,
                "ms_played": int(r.ms_played) if pd.notna(r.ms_played) else 0,
                "cover_url": _get_cover_fast(r.display_name, "track")
                if pd.notna(r.display_name)
                else "",
            }
            for r in top_tracks.itertuples(index=False)
        ],
        "top_albums": [
            {
                "rank": int(r.rank),
                "name": r.display_name or r.album_uri,
                "artist_name": album_artist_map.get(r.display_name, "")
                if pd.notna(r.display_name)
                else "",
                "play_count": int(r.play_count) if pd.notna(r.play_count) else 0,
                "ms_played": int(r.ms_played) if pd.notna(r.ms_played) else 0,
                "cover_url": _get_cover_fast(r.display_name, "album")
                if pd.notna(r.display_name)
                else "",
            }
            for r in top_albums.itertuples(index=False)
        ],
        "top_genres": [
            {"rank": int(r.rank), "name": r.display_name or r.genre_uri}
            for r in top_genres.itertuples(index=False)
        ]
        if not top_genres.empty
        else [],
        "top_podcasts": [
            {"rank": int(r.rank), "name": r.display_name or r.podcast_uri}
            for r in top_podcasts.itertuples(index=False)
        ]
        if not top_podcasts.empty
        else [],
        "artist_race": [
            {
                "artist_name": uri_name_map.get(r.artist_uri, r.artist_uri)
                if pd.notna(r.artist_uri)
                else r.artist_uri,
                "month": r.month,
                "rank": int(r.rank) if pd.notna(r.rank) else 0,
                "trail_size": r.trail_size or "",
            }
            for r in artist_race.itertuples(index=False)
        ],
        "clubs": [
            {
                "club_name": r.club_name,
                "artist_name": r.display_name or r.artist_uri,
                "percent_in_club": float(r.percent_in_club) if pd.notna(r.percent_in_club) else 0,
                "role": r.role or "",
            }
            for r in clubs.itertuples(index=False)
        ],
        "party_metrics": [
            {"metric": r.metric, "value": float(r.value) if pd.notna(r.value) else 0}
            for r in party.itertuples(index=False)
        ],
        "listening_age": {
            "age": int(listening_age["listening_age"]) if listening_age else 0,
            "window_start_year": int(listening_age["window_start_year"]) if listening_age else 0,
            "decade_phase": listening_age["decade_phase"] if listening_age else "",
        },
        "archive_reports": [
            {
                "title": r.title,
                "description": r.description or "",
                "reason": r.reason or "",
                "minutes_listened": int(r.minutes_listened) if pd.notna(r.minutes_listened) else 0,
                "filed_under_tags": r.filed_under_tags or "",
            }
            for r in archive.itertuples(index=False)
        ],
    }


register_ttl("wrapped", "hub", _get_wrapped_hub_cached)
