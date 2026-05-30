"""Genius lyrics service — on-demand lyrics fetching with SQLite caching."""

from backend.core.config import GENIUS_ACCESS_TOKEN, GENIUS_PROXY, HTTPS_PROXY
from backend.core.db import get_db
from backend.core.genius.client import GeniusClient

_client = None


def _get_client():
    """Lazy-load GeniusClient singleton."""
    global _client
    if _client is None:
        if not GENIUS_ACCESS_TOKEN:
            return None
        proxy_url = GENIUS_PROXY or HTTPS_PROXY
        proxy = {"https": proxy_url} if proxy_url else None
        _client = GeniusClient(access_token=GENIUS_ACCESS_TOKEN, proxy=proxy)
    return _client


def get_track_lyrics(track_id: int):
    """Get lyrics for a track. Returns dict with lyrics, genius_url, genius_song_id or None."""
    # Check cache first
    conn = get_db()
    row = conn.execute(
        "SELECT lyrics_text, genius_url, genius_song_id FROM track_lyrics WHERE track_id = ?",
        (track_id,)
    ).fetchone()

    if row and row["lyrics_text"]:
        conn.close()
        return {
            "found": True,
            "lyrics": row["lyrics_text"],
            "genius_url": row["genius_url"],
            "genius_song_id": row["genius_song_id"],
            "cached": True,
        }

    # Get track info
    track = conn.execute(
        "SELECT t.track_name, a.artist_name FROM tracks t JOIN artists a ON t.artist_id = a.artist_id WHERE t.track_id = ?",
        (track_id,)
    ).fetchone()
    conn.close()

    if not track:
        return {"found": False}

    # Fetch from Genius
    client = _get_client()
    if client is None:
        return {"found": False}

    try:
        song = client.get_song(title=track["track_name"], artist=track["artist_name"])
    except Exception:
        return {"found": False}

    if song is None:
        return {"found": False}

    # Cache to DB (need writable connection)
    wconn = get_db(readonly=False)
    wconn.execute(
        """INSERT OR REPLACE INTO track_lyrics (track_id, genius_song_id, lyrics_text, genius_url, fetched_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (track_id, song.id, song.lyrics, song.url)
    )
    wconn.commit()
    wconn.close()

    return {
        "found": True,
        "lyrics": song.lyrics,
        "genius_url": song.url,
        "genius_song_id": song.id,
        "cached": False,
    }


def get_track_genius_url(track_id: int):
    """Get just the Genius URL for a track (lightweight, no lyrics fetch if cached)."""
    conn = get_db()
    row = conn.execute(
        "SELECT genius_url FROM track_lyrics WHERE track_id = ?",
        (track_id,)
    ).fetchone()

    if row and row["genius_url"]:
        conn.close()
        return {"found": True, "genius_url": row["genius_url"]}

    # Not cached — do a full lyrics fetch and return just the URL
    result = get_track_lyrics(track_id)
    if result.get("found"):
        return {"found": True, "genius_url": result["genius_url"]}

    conn.close()
    return {"found": False}
