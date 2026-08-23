"""Refresh Spotify metadata needed by imported playback facts."""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import dataclass

TRACK_BATCH_SIZE = 50
ALBUM_BATCH_SIZE = 20
ARTIST_BATCH_SIZE = 50


@dataclass(frozen=True)
class MetadataRefreshReport:
    tracks_requested: int = 0
    tracks_updated: int = 0
    albums_requested: int = 0
    albums_updated: int = 0
    artists_requested: int = 0
    artists_updated: int = 0
    artist_searches_requested: int = 0
    artist_searches_updated: int = 0
    album_links_backfilled: int = 0
    provider_available: bool = True
    errors: tuple[str, ...] = ()


def select_missing_track_ids(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT candidate.spotify_track_id
        FROM (
            SELECT spotify_track_id_at_play AS spotify_track_id
            FROM plays
            WHERE spotify_track_id_at_play IS NOT NULL AND spotify_track_id_at_play != ''
            UNION
            SELECT spotify_track_id
            FROM tracks
            WHERE spotify_track_id IS NOT NULL AND spotify_track_id != ''
        ) candidate
        LEFT JOIN spotify_track_meta stm
          ON stm.spotify_track_id = candidate.spotify_track_id
        WHERE stm.spotify_track_id IS NULL
        ORDER BY candidate.spotify_track_id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row["spotify_track_id"] for row in rows]


def _normalized_name(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").casefold()
    return "".join(char for char in normalized if char.isalnum())


def _link_local_artist_from_track(conn: sqlite3.Connection, track: dict) -> int:
    spotify_artists = track.get("artists") or []
    if not spotify_artists:
        return 0
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artists'"
    ).fetchone():
        return 0
    track_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(tracks)")}
    if "artist_id" not in track_columns:
        return 0
    local_rows = conn.execute(
        """SELECT DISTINCT a.artist_id, a.artist_name
           FROM tracks t
           JOIN artists a ON a.artist_id=t.artist_id
           WHERE t.spotify_track_id=?""",
        (track.get("id"),),
    ).fetchall()
    linked = 0
    for local in local_rows:
        local_name = _normalized_name(local["artist_name"])
        match = next(
            (
                artist
                for artist in spotify_artists
                if _normalized_name(artist.get("name")) == local_name
            ),
            None,
        )
        if match and match.get("id"):
            cursor = conn.execute(
                """UPDATE artists SET spotify_artist_id=?
                   WHERE artist_id=?
                     AND (spotify_artist_id IS NULL OR spotify_artist_id='')""",
                (match["id"], local["artist_id"]),
            )
            linked += max(cursor.rowcount, 0)
    return linked


def select_track_ids_for_artist_linkage(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    """Return one played Spotify track per local artist missing its Spotify ID."""
    rows = conn.execute(
        """SELECT MIN(t.spotify_track_id) AS spotify_track_id
           FROM artists a
           JOIN tracks t ON t.artist_id=a.artist_id
           JOIN plays p ON p.track_id=t.track_id
           WHERE (a.spotify_artist_id IS NULL OR a.spotify_artist_id='')
             AND t.spotify_track_id IS NOT NULL AND t.spotify_track_id!=''
           GROUP BY a.artist_id
           ORDER BY a.artist_id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [str(row["spotify_track_id"]) for row in rows if row["spotify_track_id"]]


def upsert_track_batch(conn: sqlite3.Connection, tracks: list[dict]) -> int:
    updated = 0
    for track in tracks:
        if not track:
            continue
        album_id = (track.get("album") or {}).get("id")
        conn.execute(
            """INSERT OR REPLACE INTO spotify_track_meta(
                   spotify_track_id, track_name, duration_ms, popularity,
                   explicit, track_number, disc_number, isrc, spotify_album_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                track["id"],
                track.get("name"),
                track.get("duration_ms"),
                track.get("popularity"),
                1 if track.get("explicit") else 0,
                track.get("track_number"),
                track.get("disc_number"),
                (track.get("external_ids") or {}).get("isrc"),
                album_id,
            ),
        )
        if album_id:
            conn.execute(
                """UPDATE plays
                   SET spotify_album_id_at_play = ?
                   WHERE spotify_track_id_at_play = ?""",
                (album_id, track["id"]),
            )
            conn.execute(
                """INSERT OR REPLACE INTO album_spotify_links(
                       album_id, spotify_album_id, evidence, confidence,
                       play_count, track_count, first_seen, last_seen, updated_at)
                   SELECT source_album_id, ?, 'play_track_api', 1.0,
                          COUNT(*), COUNT(DISTINCT track_id), MIN(ts_date), MAX(ts_date),
                          CURRENT_TIMESTAMP
                   FROM plays
                   WHERE spotify_track_id_at_play = ?
                     AND source_album_id IS NOT NULL
                   GROUP BY source_album_id""",
                (album_id, track["id"]),
            )
        _link_local_artist_from_track(conn, track)
        updated += 1
    conn.commit()
    return updated


def backfill_album_links_from_existing_metadata(conn: sqlite3.Connection) -> int:
    track_cursor = conn.execute(
        """UPDATE plays
           SET spotify_track_id_at_play = (
               SELECT t.spotify_track_id
               FROM tracks t
               WHERE t.track_id = plays.track_id
           )
           WHERE (spotify_track_id_at_play IS NULL OR spotify_track_id_at_play = '')
             AND track_id IS NOT NULL
             AND EXISTS (
               SELECT 1
               FROM tracks t
               WHERE t.track_id = plays.track_id
                 AND t.spotify_track_id IS NOT NULL
                 AND t.spotify_track_id != ''
             )"""
    )
    album_cursor = conn.execute(
        """UPDATE plays
           SET spotify_album_id_at_play = (
               SELECT stm.spotify_album_id
               FROM spotify_track_meta stm
               WHERE stm.spotify_track_id = plays.spotify_track_id_at_play
           )
           WHERE (spotify_album_id_at_play IS NULL OR spotify_album_id_at_play = '')
             AND spotify_track_id_at_play IS NOT NULL
             AND spotify_track_id_at_play != ''
             AND EXISTS (
               SELECT 1
               FROM spotify_track_meta stm
               WHERE stm.spotify_track_id = plays.spotify_track_id_at_play
                 AND stm.spotify_album_id IS NOT NULL
                 AND stm.spotify_album_id != ''
             )"""
    )
    link_cursor = conn.execute(
        """INSERT OR REPLACE INTO album_spotify_links(
               album_id, spotify_album_id, evidence, confidence,
               play_count, track_count, first_seen, last_seen, updated_at)
           SELECT p.source_album_id, stm.spotify_album_id, 'play_track_meta', 0.9,
                  COUNT(*), COUNT(DISTINCT p.track_id), MIN(p.ts_date), MAX(p.ts_date),
                  CURRENT_TIMESTAMP
           FROM plays p
           JOIN spotify_track_meta stm
             ON stm.spotify_track_id = p.spotify_track_id_at_play
           WHERE p.source_album_id IS NOT NULL
             AND stm.spotify_album_id IS NOT NULL
             AND stm.spotify_album_id != ''
           GROUP BY p.source_album_id, stm.spotify_album_id"""
    )
    conn.commit()
    return (
        max(track_cursor.rowcount, 0) + max(album_cursor.rowcount, 0) + max(link_cursor.rowcount, 0)
    )


def select_missing_album_ids(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT candidate.spotify_album_id
        FROM (
            SELECT spotify_album_id_at_play AS spotify_album_id
            FROM plays
            WHERE spotify_album_id_at_play IS NOT NULL AND spotify_album_id_at_play != ''
            UNION
            SELECT spotify_album_id
            FROM spotify_track_meta
            WHERE spotify_album_id IS NOT NULL AND spotify_album_id != ''
            UNION
            SELECT spotify_album_id
            FROM album_spotify_links
            WHERE spotify_album_id IS NOT NULL AND spotify_album_id != ''
        ) candidate
        LEFT JOIN spotify_album_meta sam
          ON sam.spotify_album_id = candidate.spotify_album_id
        WHERE sam.spotify_album_id IS NULL
           OR sam.image_url IS NULL
           OR sam.image_url = ''
           OR sam.total_tracks IS NULL
        ORDER BY candidate.spotify_album_id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row["spotify_album_id"] for row in rows]


def upsert_album_batch(conn: sqlite3.Connection, albums: list[dict]) -> int:
    updated = 0
    for album in albums:
        if not album:
            continue
        images = album.get("images") or []
        artists = ", ".join(
            artist.get("name", "") for artist in album.get("artists", []) if artist.get("name")
        )
        tracks = (album.get("tracks") or {}).get("items", [])
        track_ids = [item.get("id") for item in tracks if item.get("id")]
        genres = (
            json.dumps(album.get("genres", []), ensure_ascii=False) if album.get("genres") else None
        )
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   popularity, label, genres, image_url, album_artists,
                   total_tracks, track_list)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(spotify_album_id) DO UPDATE SET
                   album_name = excluded.album_name,
                   album_type = excluded.album_type,
                   release_date = excluded.release_date,
                   popularity = excluded.popularity,
                   label = excluded.label,
                   genres = COALESCE(excluded.genres, spotify_album_meta.genres),
                   image_url = COALESCE(excluded.image_url, spotify_album_meta.image_url),
                   album_artists = COALESCE(excluded.album_artists, spotify_album_meta.album_artists),
                   total_tracks = COALESCE(excluded.total_tracks, spotify_album_meta.total_tracks),
                   track_list = COALESCE(excluded.track_list, spotify_album_meta.track_list)""",
            (
                album["id"],
                album.get("name"),
                album.get("album_type"),
                album.get("release_date"),
                album.get("popularity"),
                album.get("label"),
                genres,
                images[0].get("url") if images else None,
                artists or None,
                album.get("total_tracks"),
                json.dumps(track_ids, ensure_ascii=False) if track_ids else None,
            ),
        )
        updated += 1
    conn.commit()
    return updated


def select_missing_artist_ids(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    rows = conn.execute(
        """SELECT DISTINCT a.spotify_artist_id
           FROM artists a
           LEFT JOIN spotify_artist_meta sam
             ON sam.spotify_artist_id=a.spotify_artist_id
           WHERE a.spotify_artist_id IS NOT NULL AND a.spotify_artist_id!=''
             AND (a.image_url IS NULL OR a.image_url='')
             AND (sam.spotify_artist_id IS NULL OR sam.image_url IS NULL OR sam.image_url='')
           ORDER BY a.spotify_artist_id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [str(row["spotify_artist_id"]) for row in rows]


def upsert_artist_batch(conn: sqlite3.Connection, artists: list[dict]) -> int:
    updated = 0
    for artist in artists:
        if not artist or not artist.get("id"):
            continue
        images = artist.get("images") or []
        image_url = images[0].get("url") if images else None
        genres = (
            json.dumps(artist.get("genres", []), ensure_ascii=False)
            if artist.get("genres")
            else None
        )
        conn.execute(
            """INSERT INTO spotify_artist_meta(
                   spotify_artist_id, artist_name, popularity, followers, genres, image_url)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(spotify_artist_id) DO UPDATE SET
                   artist_name=excluded.artist_name,
                   popularity=excluded.popularity,
                   followers=excluded.followers,
                   genres=COALESCE(excluded.genres, spotify_artist_meta.genres),
                   image_url=COALESCE(excluded.image_url, spotify_artist_meta.image_url)""",
            (
                artist["id"],
                artist.get("name") or artist["id"],
                artist.get("popularity"),
                (artist.get("followers") or {}).get("total"),
                genres,
                image_url,
            ),
        )
        conn.execute(
            """UPDATE artists SET
                   popularity=COALESCE(?, popularity),
                   followers=COALESCE(?, followers),
                   genres=COALESCE(?, genres),
                   image_url=COALESCE(?, image_url)
               WHERE spotify_artist_id=?""",
            (
                artist.get("popularity"),
                (artist.get("followers") or {}).get("total"),
                genres,
                image_url,
                artist["id"],
            ),
        )
        updated += 1
    conn.commit()
    return updated


def sync_local_cover_urls(conn: sqlite3.Connection) -> tuple[int, int]:
    """Copy resolved Spotify image sources onto local album/artist entities."""
    albums_before = int(
        conn.execute(
            "SELECT COUNT(*) FROM albums WHERE image_url IS NOT NULL AND image_url!=''"
        ).fetchone()[0]
    )
    artists_before = int(
        conn.execute(
            "SELECT COUNT(*) FROM artists WHERE image_url IS NOT NULL AND image_url!=''"
        ).fetchone()[0]
    )
    conn.execute(
        """UPDATE albums
           SET spotify_album_id=COALESCE(
                   NULLIF(spotify_album_id, ''),
                   (SELECT asl.spotify_album_id
                    FROM album_spotify_links asl
                    JOIN spotify_album_meta sam
                      ON sam.spotify_album_id=asl.spotify_album_id
                    WHERE asl.album_id=albums.album_id
                      AND sam.image_url IS NOT NULL AND sam.image_url!=''
                    ORDER BY CASE sam.album_type WHEN 'album' THEN 0 ELSE 1 END,
                             asl.confidence DESC, asl.play_count DESC
                    LIMIT 1)
               ),
               image_url=COALESCE(
                   NULLIF(image_url, ''),
                   (SELECT sam.image_url
                    FROM album_spotify_links asl
                    JOIN spotify_album_meta sam
                      ON sam.spotify_album_id=asl.spotify_album_id
                    WHERE asl.album_id=albums.album_id
                      AND sam.image_url IS NOT NULL AND sam.image_url!=''
                    ORDER BY CASE sam.album_type WHEN 'album' THEN 0 ELSE 1 END,
                             asl.confidence DESC, asl.play_count DESC
                    LIMIT 1)
               )
           WHERE image_url IS NULL OR image_url=''"""
    )
    conn.execute(
        """UPDATE artists
           SET image_url=COALESCE(
               NULLIF(image_url, ''),
               (SELECT sam.image_url FROM spotify_artist_meta sam
                WHERE sam.spotify_artist_id=artists.spotify_artist_id
                  AND sam.image_url IS NOT NULL AND sam.image_url!=''
                LIMIT 1),
               (SELECT sam.image_url FROM spotify_artist_meta sam
                WHERE sam.artist_name=artists.artist_name
                  AND sam.image_url IS NOT NULL AND sam.image_url!=''
                LIMIT 1)
           )
           WHERE image_url IS NULL OR image_url=''"""
    )
    conn.commit()
    albums_after = int(
        conn.execute(
            "SELECT COUNT(*) FROM albums WHERE image_url IS NOT NULL AND image_url!=''"
        ).fetchone()[0]
    )
    artists_after = int(
        conn.execute(
            "SELECT COUNT(*) FROM artists WHERE image_url IS NOT NULL AND image_url!=''"
        ).fetchone()[0]
    )
    return albums_after - albums_before, artists_after - artists_before


def select_played_artists_missing_covers(
    conn: sqlite3.Connection, limit: int = 1000
) -> list[tuple[int, str]]:
    rows = conn.execute(
        """SELECT a.artist_id, a.artist_name
           FROM artists a
           WHERE (a.image_url IS NULL OR a.image_url='')
             AND EXISTS (
               SELECT 1 FROM track_artists ta
               JOIN plays p ON p.track_id=ta.track_id
               WHERE ta.artist_id=a.artist_id
             )
           ORDER BY a.artist_id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [(int(row["artist_id"]), str(row["artist_name"])) for row in rows]


def refresh_missing_spotify_metadata(
    conn: sqlite3.Connection,
    provider,
    access_token: str | None,
    progress_callback=None,
) -> MetadataRefreshReport:
    album_links_backfilled = backfill_album_links_from_existing_metadata(conn)
    if not access_token:
        return MetadataRefreshReport(
            album_links_backfilled=album_links_backfilled,
            provider_available=False,
            errors=("spotify_credentials_missing",),
        )

    errors: list[str] = []
    track_ids = list(
        dict.fromkeys([*select_missing_track_ids(conn), *select_track_ids_for_artist_linkage(conn)])
    )
    tracks_updated = 0
    album_ids_seen: set[str] = set()

    for offset in range(0, len(track_ids), TRACK_BATCH_SIZE):
        batch = track_ids[offset : offset + TRACK_BATCH_SIZE]
        if progress_callback:
            progress_callback(
                f"刷新 Spotify 曲目元数据 {offset + len(batch)} / {len(track_ids)}",
                0.0,
            )
        data = provider.get_tracks(batch, access_token)
        if data is None:
            errors.append("tracks_batch_failed")
            continue
        tracks = data.get("tracks", [])
        tracks_updated += upsert_track_batch(conn, tracks)
        for track in tracks:
            album_id = track and (track.get("album") or {}).get("id")
            if album_id:
                album_ids_seen.add(album_id)

    album_ids = list(dict.fromkeys([*album_ids_seen, *select_missing_album_ids(conn)]))
    albums_updated = 0
    for offset in range(0, len(album_ids), ALBUM_BATCH_SIZE):
        batch = album_ids[offset : offset + ALBUM_BATCH_SIZE]
        if progress_callback:
            progress_callback(
                f"刷新 Spotify 专辑元数据 {offset + len(batch)} / {len(album_ids)}",
                0.0,
            )
        data = provider.get_albums(batch, access_token)
        if data is None:
            errors.append("albums_batch_failed")
            continue
        albums_updated += upsert_album_batch(conn, data.get("albums", []))

    artist_ids = select_missing_artist_ids(conn)
    artists_updated = 0
    for offset in range(0, len(artist_ids), ARTIST_BATCH_SIZE):
        batch = artist_ids[offset : offset + ARTIST_BATCH_SIZE]
        if progress_callback:
            progress_callback(
                f"刷新 Spotify 艺人封面 {offset + len(batch)} / {len(artist_ids)}",
                0.0,
            )
        data = provider.get_artists_by_ids(batch, access_token)
        if data is None:
            errors.append("artists_batch_failed")
            continue
        artists_updated += upsert_artist_batch(conn, data.get("artists", []))

    sync_local_cover_urls(conn)
    search_candidates = select_played_artists_missing_covers(conn)
    artist_searches_updated = 0
    search_artist = getattr(provider, "search_artist", None)
    if callable(search_artist):
        for index, (local_artist_id, artist_name) in enumerate(search_candidates, start=1):
            if progress_callback:
                progress_callback(
                    f"精确搜索缺失艺人封面 {index} / {len(search_candidates)}",
                    0.0,
                )
            artist = search_artist(artist_name, access_token)
            if not artist or not artist.get("id"):
                continue
            conn.execute(
                "UPDATE artists SET spotify_artist_id=? WHERE artist_id=?",
                (artist["id"], local_artist_id),
            )
            artist_searches_updated += upsert_artist_batch(conn, [artist])
        sync_local_cover_urls(conn)

    return MetadataRefreshReport(
        tracks_requested=len(track_ids),
        tracks_updated=tracks_updated,
        albums_requested=len(album_ids),
        albums_updated=albums_updated,
        artists_requested=len(artist_ids),
        artists_updated=artists_updated,
        artist_searches_requested=len(search_candidates) if callable(search_artist) else 0,
        artist_searches_updated=artist_searches_updated,
        album_links_backfilled=album_links_backfilled,
        provider_available=True,
        errors=tuple(errors),
    )
