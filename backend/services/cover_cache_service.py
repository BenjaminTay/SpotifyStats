"""Cover-cache source synchronization and bounded backfill scheduling."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from backend.core import db as db_module
from backend.core.job_queue import Job, JobQueue, get_job_queue
from backend.domains.metadata.spotify_refresh import sync_local_cover_urls


@dataclass(frozen=True)
class CoverCacheBackfillReport:
    album_urls_synced: int
    artist_urls_synced: int
    missing_albums: int
    missing_artists: int
    jobs_enqueued: int


def _covers_root() -> str:
    return os.path.join(os.path.dirname(db_module.DB_PATH), "covers")


def _played_cover_sources(conn: sqlite3.Connection) -> list[tuple[str, int, str]]:
    rows = conn.execute(
        """SELECT 'albums' AS cover_type, al.album_id AS entity_id, al.image_url
           FROM albums al
           WHERE al.image_url IS NOT NULL AND al.image_url!=''
             AND (
               EXISTS (SELECT 1 FROM tracks t JOIN plays p ON p.track_id=t.track_id
                       WHERE t.album_id=al.album_id)
               OR EXISTS (SELECT 1 FROM plays p WHERE p.source_album_id=al.album_id)
             )
           UNION ALL
           SELECT 'artists', a.artist_id, a.image_url
           FROM artists a
           WHERE a.image_url IS NOT NULL AND a.image_url!=''
             AND EXISTS (
               SELECT 1 FROM track_artists ta
               JOIN plays p ON p.track_id=ta.track_id
               WHERE ta.artist_id=a.artist_id
             )
           ORDER BY cover_type, entity_id"""
    ).fetchall()
    return [(str(row[0]), int(row[1]), str(row[2])) for row in rows]


def enqueue_missing_cover_downloads(
    conn: sqlite3.Connection,
    *,
    queue: JobQueue | None = None,
) -> CoverCacheBackfillReport:
    """Synchronize cover URLs and enqueue only missing played-entity files."""
    album_synced, artist_synced = sync_local_cover_urls(conn)
    missing: list[tuple[str, int, str]] = []
    root = _covers_root()
    for cover_type, entity_id, image_url in _played_cover_sources(conn):
        path = os.path.join(root, cover_type, f"{entity_id}.jpg")
        if not os.path.isfile(path) or os.path.getsize(path) < 1024:
            missing.append((cover_type, entity_id, image_url))

    target_queue = queue or get_job_queue()
    jobs_enqueued = 0
    for cover_type, entity_id, image_url in missing:
        job = Job.create(
            "cover_download",
            cover_type,
            str(entity_id),
            cdn_url=image_url,
        )
        if target_queue.enqueue_if_not_pending(job) is not None:
            jobs_enqueued += 1

    return CoverCacheBackfillReport(
        album_urls_synced=album_synced,
        artist_urls_synced=artist_synced,
        missing_albums=sum(item[0] == "albums" for item in missing),
        missing_artists=sum(item[0] == "artists" for item in missing),
        jobs_enqueued=jobs_enqueued,
    )
