"""Job handlers for background job types."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile

from backend.core.job_queue import Job
from backend.infrastructure.http.client import HttpClient

logger = logging.getLogger(__name__)


def handle_cover_download(job: Job):
    """Download a cover image from Spotify CDN and cache locally."""
    cover_type = job.entity_type  # "albums" or "artists"
    entity_id = job.entity_id
    cdn_url = job.payload.get("cdn_url", "")
    source_hash = str(job.payload.get("source_url_hash") or "")
    temp_path: str | None = None
    try:
        if cover_type not in {"albums", "artists"}:
            raise ValueError(f"unsupported cover type: {cover_type}")
        numeric_entity_id = int(entity_id)
        if not cdn_url:
            cdn_url = _lookup_cover_source(cover_type, numeric_entity_id)

        actual_source_hash = hashlib.sha256(cdn_url.encode()).hexdigest()
        if source_hash and source_hash != actual_source_hash:
            logger.info(
                "Skipping stale cover job with mismatched payload: %s/%s",
                cover_type,
                entity_id,
            )
            return
        source_hash = actual_source_hash

        resp = HttpClient(timeout=20, retries=2).get(cdn_url)
        if resp.status != 200:
            raise RuntimeError(f"cover download HTTP {resp.status}: {cover_type}/{entity_id}")
        data = resp.body
        if len(data) < 1024 or not data.startswith((b"\xff\xd8\xff", b"\x89PNG", b"RIFF")):
            raise ValueError(f"invalid cover payload: {cover_type}/{entity_id} ({len(data)} bytes)")

        # Write atomically so an interrupted worker never leaves a truncated file
        # that the cover endpoint later treats as a valid cache hit.
        from backend.core import db as db_module

        filepath = os.path.join(
            os.path.dirname(db_module.DB_PATH), "covers", cover_type, f"{entity_id}.jpg"
        )
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=os.path.dirname(filepath), prefix=f".{entity_id}.", delete=False
        ) as handle:
            temp_path = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        published = _publish_cover_if_current(
            cover_type,
            numeric_entity_id,
            cdn_url=cdn_url,
            source_hash=source_hash,
            temp_path=temp_path,
            filepath=filepath,
        )
        if not published:
            logger.info("Skipping stale cover job: %s/%s", cover_type, entity_id)
            return
        temp_path = None
        logger.info("Cover downloaded: %s/%s", cover_type, entity_id)
    except Exception as exc:
        if source_hash and cover_type in {"albums", "artists"}:
            try:
                _update_cover_source_state(
                    cover_type,
                    entity_id,
                    source_hash=source_hash,
                    status="failed",
                    error=str(exc)[:500],
                )
            except Exception:
                logger.exception(
                    "Failed to persist cover failure state: %s/%s", cover_type, entity_id
                )
        raise
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _lookup_cover_source(cover_type: str, entity_id: int) -> str:
    from backend.core.db import get_db

    table = "albums" if cover_type == "albums" else "artists"
    id_col = "album_id" if cover_type == "albums" else "artist_id"
    conn = get_db()
    try:
        row = conn.execute(
            f"SELECT image_url FROM {table} "
            f"WHERE {id_col} = ? AND image_url IS NOT NULL AND image_url != ''",
            [entity_id],
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError(f"cover source missing: {cover_type}/{entity_id}")
    return str(row["image_url"])


def _publish_cover_if_current(
    cover_type: str,
    entity_id: int,
    *,
    cdn_url: str,
    source_hash: str,
    temp_path: str,
    filepath: str,
) -> bool:
    """Publish a downloaded file only while its source URL is still current."""
    from backend.core.db import get_db

    table = "albums" if cover_type == "albums" else "artists"
    id_col = "album_id" if cover_type == "albums" else "artist_id"
    conn = get_db(readonly=False)
    try:
        conn.execute("BEGIN IMMEDIATE")
        entity_row = conn.execute(
            f"SELECT image_url FROM {table} WHERE {id_col} = ?", (entity_id,)
        ).fetchone()
        if not entity_row:
            conn.rollback()
            return False
        has_state_table = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cover_cache_state'"
            ).fetchone()
        )
        state_row = None
        if has_state_table:
            state_row = conn.execute(
                """SELECT source_url_hash FROM cover_cache_state
                   WHERE entity_type=? AND entity_id=?""",
                (cover_type, entity_id),
            ).fetchone()
            if state_row and state_row["source_url_hash"] != source_hash:
                conn.rollback()
                return False
        if not state_row:
            current_url = str(entity_row["image_url"] or "")
            if (
                current_url != cdn_url
                or hashlib.sha256(current_url.encode()).hexdigest() != source_hash
            ):
                conn.rollback()
                return False

        os.replace(temp_path, filepath)
        rel_path = f"covers/{cover_type}/{entity_id}.jpg"
        conn.execute(f"UPDATE {table} SET image_path = ? WHERE {id_col} = ?", (rel_path, entity_id))
        if has_state_table:
            if state_row:
                cursor = conn.execute(
                    """UPDATE cover_cache_state
                       SET cached_source_url_hash=?, status='ready', last_error=NULL,
                           updated_at=datetime('now')
                       WHERE entity_type=? AND entity_id=? AND source_url_hash=?""",
                    (source_hash, cover_type, entity_id, source_hash),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("cover source changed during publication")
            else:
                conn.execute(
                    """INSERT INTO cover_cache_state(
                           entity_type, entity_id, source_url_hash,
                           cached_source_url_hash, status, last_error, updated_at
                       ) VALUES (?, ?, ?, ?, 'ready', NULL, datetime('now'))""",
                    (cover_type, entity_id, source_hash, source_hash),
                )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_cover_source_state(
    cover_type: str,
    entity_id: str,
    *,
    source_hash: str,
    status: str,
    error: str | None,
) -> None:
    from backend.core.db import get_db

    conn = get_db(readonly=False)
    try:
        numeric_entity_id = int(entity_id)
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cover_cache_state'"
        ).fetchone():
            conn.rollback()
            return
        state_row = conn.execute(
            """SELECT source_url_hash FROM cover_cache_state
               WHERE entity_type=? AND entity_id=?""",
            (cover_type, numeric_entity_id),
        ).fetchone()
        if state_row:
            if state_row["source_url_hash"] != source_hash:
                conn.rollback()
                return
            conn.execute(
                """UPDATE cover_cache_state
                   SET status=?, last_error=?, updated_at=datetime('now')
                   WHERE entity_type=? AND entity_id=? AND source_url_hash=?""",
                (status, error, cover_type, numeric_entity_id, source_hash),
            )
        else:
            table = "albums" if cover_type == "albums" else "artists"
            id_col = "album_id" if cover_type == "albums" else "artist_id"
            row = conn.execute(
                f"SELECT image_url FROM {table} WHERE {id_col}=?", (numeric_entity_id,)
            ).fetchone()
            current_url = str(row["image_url"] or "") if row else ""
            if hashlib.sha256(current_url.encode()).hexdigest() != source_hash:
                conn.rollback()
                return
            conn.execute(
                """INSERT INTO cover_cache_state(
                       entity_type, entity_id, source_url_hash,
                       cached_source_url_hash, status, last_error, updated_at
                   ) VALUES (?, ?, ?, NULL, ?, ?, datetime('now'))""",
                (cover_type, numeric_entity_id, source_hash, status, error),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def handle_wikipedia_enrich(job: Job):
    """Fetch Wikipedia data + translate + LLM enrichment for an entity."""
    entity_type = job.entity_type  # "album", "artist", or "track"
    entity_name = job.payload.get("entity_name", job.entity_id)
    artist_name = job.payload.get("artist_name", "")

    from backend.services.wikipedia_service import (
        get_album_wiki,
        get_artist_wiki,
        get_track_wiki,
    )

    try:
        if entity_type == "album":
            get_album_wiki(entity_name, artist_name)
        elif entity_type == "artist":
            get_artist_wiki(entity_name)
        elif entity_type == "track":
            get_track_wiki(entity_name, artist_name)
        logger.info("Wikipedia enrich completed: %s/%s", entity_type, entity_name)
    except Exception:
        logger.exception("Wikipedia enrich failed: %s/%s", entity_type, entity_name)


def handle_genius_lyrics(job: Job):
    """Fetch Genius lyrics for a track and cache in DB."""
    try:
        track_id = int(job.entity_id)
    except (TypeError, ValueError):
        logger.warning("Invalid track_id for genius_lyrics job: %s", job.entity_id)
        return

    from backend.services.genius_service import get_track_lyrics

    try:
        get_track_lyrics(track_id)
        logger.info("Genius lyrics fetched: track_id=%s", track_id)
    except Exception:
        logger.exception("Genius lyrics fetch failed: track_id=%s", track_id)
