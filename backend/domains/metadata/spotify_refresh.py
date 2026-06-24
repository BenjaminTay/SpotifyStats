"""Refresh Spotify metadata needed by imported playback facts."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

TRACK_BATCH_SIZE = 50
ALBUM_BATCH_SIZE = 20


@dataclass(frozen=True)
class MetadataRefreshReport:
    tracks_requested: int = 0
    tracks_updated: int = 0
    albums_requested: int = 0
    albums_updated: int = 0
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
    track_ids = select_missing_track_ids(conn)
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

    return MetadataRefreshReport(
        tracks_requested=len(track_ids),
        tracks_updated=tracks_updated,
        albums_requested=len(album_ids),
        albums_updated=albums_updated,
        album_links_backfilled=album_links_backfilled,
        provider_available=True,
        errors=tuple(errors),
    )
