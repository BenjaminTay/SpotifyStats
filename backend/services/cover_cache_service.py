"""Cover-cache source synchronization and bounded backfill scheduling."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass

from backend.core import db as db_module
from backend.core.job_queue import Job, JobQueue, get_job_queue
from backend.domains.metadata.spotify_refresh import sync_local_cover_urls

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoverCacheBackfillReport:
    album_urls_synced: int
    artist_urls_synced: int
    missing_albums: int
    missing_artists: int
    jobs_enqueued: int
    sources_scanned: int = 0
    stale_sources: int = 0


def _covers_root() -> str:
    return os.path.join(os.path.dirname(db_module.DB_PATH), "covers")


def _played_cover_sources(
    conn: sqlite3.Connection,
    *,
    album_ids: set[int] | None = None,
    artist_ids: set[int] | None = None,
) -> list[tuple[str, int, str]]:
    rows = conn.execute(
        """SELECT 'albums' AS cover_type, al.album_id AS entity_id,
                  COALESCE(
                    (SELECT sam.image_url
                     FROM album_spotify_links asl
                     JOIN spotify_album_meta sam
                       ON sam.spotify_album_id=asl.spotify_album_id
                     WHERE asl.album_id=al.album_id
                       AND sam.image_url IS NOT NULL AND sam.image_url!=''
                     ORDER BY CASE sam.album_type WHEN 'album' THEN 0 ELSE 1 END,
                              asl.confidence DESC, asl.play_count DESC
                     LIMIT 1),
                    NULLIF(al.image_url, '')
                  ) AS image_url
           FROM albums al
           WHERE (
               EXISTS (SELECT 1 FROM tracks t JOIN plays p ON p.track_id=t.track_id
                       WHERE t.album_id=al.album_id)
               OR EXISTS (SELECT 1 FROM plays p WHERE p.source_album_id=al.album_id)
             )
           UNION ALL
           SELECT 'artists', a.artist_id,
                  COALESCE(
                    (SELECT sam.image_url FROM spotify_artist_meta sam
                     WHERE sam.spotify_artist_id=a.spotify_artist_id
                       AND sam.image_url IS NOT NULL AND sam.image_url!=''
                     LIMIT 1),
                    (SELECT sam.image_url FROM spotify_artist_meta sam
                     WHERE sam.artist_name=a.artist_name
                       AND sam.image_url IS NOT NULL AND sam.image_url!=''
                     LIMIT 1),
                    NULLIF(a.image_url, '')
                  ) AS image_url
           FROM artists a
           WHERE (
               EXISTS (
                 SELECT 1 FROM track_artists ta
                 JOIN plays p ON p.track_id=ta.track_id
                 WHERE ta.artist_id=a.artist_id
               )
               OR EXISTS (
                 SELECT 1 FROM tracks t JOIN plays p ON p.track_id=t.track_id
                 WHERE t.artist_id=a.artist_id
               )
             )
           ORDER BY cover_type, entity_id"""
    ).fetchall()
    return [
        (str(row[0]), int(row[1]), str(row[2]))
        for row in rows
        if row[2]
        and (
            (row[0] == "albums" and (album_ids is None or int(row[1]) in album_ids))
            or (row[0] == "artists" and (artist_ids is None or int(row[1]) in artist_ids))
        )
    ]


def enqueue_missing_cover_downloads(
    conn: sqlite3.Connection,
    *,
    queue: JobQueue | None = None,
    album_ids: set[int] | frozenset[int] | None = None,
    artist_ids: set[int] | frozenset[int] | None = None,
    include_failed_backlog: bool = True,
    backlog_limit: int = 200,
    synchronize_sources: bool = True,
) -> CoverCacheBackfillReport:
    """Synchronize sources and enqueue missing, stale, or failed cover files."""
    scoped_albums = None if album_ids is None else set(album_ids)
    scoped_artists = None if artist_ids is None else set(artist_ids)
    album_synced, artist_synced = (
        sync_local_cover_urls(
            conn,
            album_ids=scoped_albums,
            artist_ids=scoped_artists,
        )
        if synchronize_sources
        else (0, 0)
    )
    if include_failed_backlog and _table_exists(conn, "cover_cache_state"):
        failed = conn.execute(
            """SELECT entity_type, entity_id FROM cover_cache_state
               WHERE status='failed' ORDER BY updated_at LIMIT ?""",
            (max(0, backlog_limit),),
        ).fetchall()
        if scoped_albums is not None:
            scoped_albums.update(int(row[1]) for row in failed if row[0] == "albums")
        if scoped_artists is not None:
            scoped_artists.update(int(row[1]) for row in failed if row[0] == "artists")
    missing: list[tuple[str, int, str]] = []
    stale_sources = 0
    root = _covers_root()
    sources = _played_cover_sources(
        conn,
        album_ids=scoped_albums,
        artist_ids=scoped_artists,
    )
    for cover_type, entity_id, image_url in sources:
        path = os.path.join(root, cover_type, f"{entity_id}.jpg")
        valid_file = os.path.isfile(path) and os.path.getsize(path) >= 1024
        source_hash = hashlib.sha256(image_url.encode()).hexdigest()
        state = _cover_state(conn, cover_type, entity_id)
        # A pre-migration file has no provenance. Its bytes may belong to an
        # older provider URL, so establish the first trusted hash by fetching
        # once instead of certifying an unknown file as current.
        if valid_file and state is None:
            missing.append((cover_type, entity_id, image_url))
            _store_cover_state(
                conn,
                cover_type,
                entity_id,
                source_hash=source_hash,
                cached_hash=None,
                status="pending",
            )
            continue
        stale = state is not None and state[1] != source_hash
        if stale:
            stale_sources += 1
        if not valid_file or stale or (state is not None and state[2] == "failed"):
            missing.append((cover_type, entity_id, image_url))
            _store_cover_state(
                conn,
                cover_type,
                entity_id,
                source_hash=source_hash,
                cached_hash=(str(state[1]) if state and valid_file else None),
                status="pending",
            )
    conn.commit()

    target_queue = queue or get_job_queue()
    jobs_enqueued = 0
    for cover_type, entity_id, image_url in missing:
        job = Job.create(
            "cover_download",
            cover_type,
            str(entity_id),
            cdn_url=image_url,
            source_url_hash=hashlib.sha256(image_url.encode()).hexdigest(),
        )
        if target_queue.enqueue_if_not_pending(job) is not None:
            jobs_enqueued += 1

    return CoverCacheBackfillReport(
        album_urls_synced=album_synced,
        artist_urls_synced=artist_synced,
        missing_albums=sum(item[0] == "albums" for item in missing),
        missing_artists=sum(item[0] == "artists" for item in missing),
        jobs_enqueued=jobs_enqueued,
        sources_scanned=len(sources),
        stale_sources=stale_sources,
    )


def enqueue_failed_cover_download_recovery(
    queue: JobQueue | None = None,
    *,
    backlog_limit: int = 50,
) -> CoverCacheBackfillReport:
    """Recover a bounded slice of failed covers without scanning all played entities.

    Startup calls this only after import-maintenance priority work has cleared its
    barrier. Empty explicit scopes are important: the failed-state rows expand
    those scopes up to ``backlog_limit`` instead of turning startup into a full
    cover inventory scan.
    """
    empty_report = CoverCacheBackfillReport(0, 0, 0, 0, 0)
    if backlog_limit <= 0:
        return empty_report
    conn = db_module.get_db(readonly=False)
    try:
        if not _table_exists(conn, "cover_cache_state"):
            return empty_report
        failed_exists = conn.execute(
            "SELECT 1 FROM cover_cache_state WHERE status='failed' LIMIT 1"
        ).fetchone()
        if failed_exists is None:
            return empty_report
        try:
            return enqueue_missing_cover_downloads(
                conn,
                queue=queue,
                album_ids=set(),
                artist_ids=set(),
                include_failed_backlog=True,
                backlog_limit=backlog_limit,
                synchronize_sources=False,
            )
        except sqlite3.OperationalError as exc:
            # Cover recovery is best-effort startup work. A legacy or partially
            # migrated metadata schema must not prevent the application from
            # starting; the next import can repair and retry these rows.
            logger.warning("Skipped failed-cover startup recovery: %s", exc)
            return empty_report
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _cover_state(
    conn: sqlite3.Connection, cover_type: str, entity_id: int
) -> tuple[str, str | None, str] | None:
    if not _table_exists(conn, "cover_cache_state"):
        return None
    row = conn.execute(
        """SELECT source_url_hash, cached_source_url_hash, status
           FROM cover_cache_state WHERE entity_type=? AND entity_id=?""",
        (cover_type, entity_id),
    ).fetchone()
    return (str(row[0]), str(row[1]) if row[1] else None, str(row[2])) if row else None


def _store_cover_state(
    conn: sqlite3.Connection,
    cover_type: str,
    entity_id: int,
    *,
    source_hash: str,
    cached_hash: str | None,
    status: str,
) -> None:
    if not _table_exists(conn, "cover_cache_state"):
        return
    conn.execute(
        """INSERT INTO cover_cache_state(
               entity_type, entity_id, source_url_hash,
               cached_source_url_hash, status, last_error, updated_at
           ) VALUES (?, ?, ?, ?, ?, NULL, datetime('now'))
           ON CONFLICT(entity_type, entity_id) DO UPDATE SET
               source_url_hash=excluded.source_url_hash,
               cached_source_url_hash=excluded.cached_source_url_hash,
               status=excluded.status, last_error=NULL,
               updated_at=datetime('now')""",
        (cover_type, entity_id, source_hash, cached_hash, status),
    )
