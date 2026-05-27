"""Backend cache warmup helpers."""

import logging
import threading

from backend.core.db import get_db, load_plays
from backend.services.billboard_service import compute_billboard_data

logger = logging.getLogger(__name__)

DEFAULT_PLAY_FILTERS = {
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
}

DEFAULT_BILLBOARD_FILTERS = {
    "min_ms": 30000,
    "music_only": True,
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 0,
    "year_start": None,
    "year_end": None,
}


def warm_common_caches() -> None:
    """Prime expensive default caches used by first-page navigation."""
    conn = get_db()
    try:
        load_plays(conn, **DEFAULT_PLAY_FILTERS)
    finally:
        conn.close()

    compute_billboard_data(**DEFAULT_BILLBOARD_FILTERS)


def start_warmup_thread() -> threading.Thread:
    """Start cache warmup in the background and return the thread."""

    def run() -> None:
        try:
            warm_common_caches()
        except Exception:
            logger.exception("Backend cache warmup failed")

    thread = threading.Thread(target=run, name="spotify-stats-cache-warmup", daemon=True)
    thread.start()
    return thread
