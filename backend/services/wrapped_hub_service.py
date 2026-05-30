"""Official Spotify Wrapped data service."""

import sqlite3

import pandas as pd


def _get_cover_for_name(conn: sqlite3.Connection, name: str, kind: str) -> str:
    """Look up cover image URL by display name."""
    if not name:
        return ""
    if kind == "artist":
        r = conn.execute(
            "SELECT image_url FROM spotify_artist_meta WHERE artist_name = ? LIMIT 1",
            (name,),
        ).fetchone()
    elif kind == "track":
        r = conn.execute(
            "SELECT sam.image_url FROM spotify_track_meta stm "
            "JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id "
            "JOIN tracks t ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id "
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
            "SELECT t.track_name FROM tracks t WHERE REPLACE(t.spotify_track_uri, 'spotify:track:', '') = ?",
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


def get_wrapped_hub(conn: sqlite3.Connection) -> dict:
    """Load all official Spotify Wrapped 2025 data."""
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

    # Resolve all URIs to names
    for df, uri_col, uri_type in [
        (top_artists, "artist_uri", "artist"),
        (top_tracks, "track_uri", "track"),
        (top_albums, "album_uri", "album"),
        (top_genres, "genre_uri", "artist"),  # genres use artist URIs
        (top_podcasts, "podcast_uri", "show"),
        (clubs, "artist_uri", "artist"),
    ]:
        if uri_col in df.columns:
            df["display_name"] = df[uri_col].apply(
                lambda u: _resolve_uri_name(conn, u, uri_type) if pd.notna(u) else ""
            )

    return {
        "available": True,
        "empty": False,
        "top_artists": [
            {
                "rank": int(r.rank),
                "name": r.display_name or r.artist_uri,
                "ms_played": int(r.ms_played) if pd.notna(r.ms_played) else 0,
                "percentile": float(r.percentile) if pd.notna(r.percentile) else None,
                "cover_url": _get_cover_for_name(conn, r.display_name, "artist")
                if pd.notna(r.display_name)
                else "",
            }
            for r in top_artists.itertuples(index=False)
        ],
        "top_tracks": [
            {
                "rank": int(r.rank),
                "name": r.display_name or r.track_uri,
                "play_count": int(r.play_count) if pd.notna(r.play_count) else 0,
                "ms_played": int(r.ms_played) if pd.notna(r.ms_played) else 0,
                "cover_url": _get_cover_for_name(conn, r.display_name, "track")
                if pd.notna(r.display_name)
                else "",
            }
            for r in top_tracks.itertuples(index=False)
        ],
        "top_albums": [
            {
                "rank": int(r.rank),
                "name": r.display_name or r.album_uri,
                "play_count": int(r.play_count) if pd.notna(r.play_count) else 0,
                "ms_played": int(r.ms_played) if pd.notna(r.ms_played) else 0,
                "cover_url": _get_cover_for_name(conn, r.display_name, "album")
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
                "artist_name": _resolve_uri_name(conn, r.artist_uri, "artist")
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
