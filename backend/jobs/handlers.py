"""Job handlers for background job types."""

from __future__ import annotations

import logging
import os
import urllib.request

from backend.core.job_queue import Job

logger = logging.getLogger(__name__)


def handle_cover_download(job: Job):
    """Download a cover image from Spotify CDN and cache locally."""
    cover_type = job.entity_type  # "albums" or "artists"
    entity_id = job.entity_id
    cdn_url = job.payload.get("cdn_url", "")

    if not cdn_url:
        # Look up CDN URL from DB
        from backend.core.db import get_db

        conn = get_db()
        table = "albums" if cover_type == "albums" else "artists"
        id_col = "album_id" if cover_type == "albums" else "artist_id"
        row = conn.execute(
            f"SELECT image_url FROM {table} WHERE {id_col} = ? AND image_url IS NOT NULL AND image_url != ''",
            [entity_id],
        ).fetchone()
        conn.close()
        if not row:
            return
        cdn_url = row["image_url"]

    try:
        req = urllib.request.Request(cdn_url, headers={"User-Agent": "SpotifyStats/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()

        # Determine cache path
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        filepath = os.path.join(project_root, "data", "covers", cover_type, f"{entity_id}.jpg")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(data)

        # Update DB
        from backend.core.db import get_db

        conn = get_db(readonly=False)
        rel_path = f"covers/{cover_type}/{entity_id}.jpg"
        if cover_type == "albums":
            conn.execute(
                "UPDATE albums SET image_path = ? WHERE album_id = ?", [rel_path, entity_id]
            )
        elif cover_type == "artists":
            conn.execute(
                "UPDATE artists SET image_path = ? WHERE artist_id = ?", [rel_path, entity_id]
            )
        conn.commit()
        conn.close()
        logger.info("Cover downloaded: %s/%s", cover_type, entity_id)
    except Exception:
        logger.exception("Cover download failed: %s/%s", cover_type, entity_id)


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
