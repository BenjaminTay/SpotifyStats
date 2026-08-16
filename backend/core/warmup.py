"""Backend cache warmup helpers."""

import logging
import threading

from backend.core.db import get_db, load_plays, load_plays_for_artists
from backend.domains.account_archive.overview import get_archive_overview
from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository
from backend.services.analysis_stats_service import get_analysis_charts, get_analysis_stats
from backend.services.billboard_service import compute_billboard_data

logger = logging.getLogger(__name__)

DEFAULT_PLAY_FILTERS = {
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "dynamic_threshold": True,
    "max_merge_gap_minutes": 5,
}

DEFAULT_BILLBOARD_FILTERS = {
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 0,
    "year_start": None,
    "year_end": None,
    "dynamic_threshold": True,
    "max_merge_gap_minutes": 5,
    "merge_level": 2,
}


def _configured_warmup_filters(conn) -> tuple[dict, dict]:
    """Resolve the same persisted defaults used by omitted-query API calls."""
    try:
        settings = SettingsRepository(conn).load_all()
    except Exception:
        settings = dict(SETTINGS_DEFAULTS)
    play = {
        "min_ms": int(settings["min_ms"]),
        "music_only": bool(settings["music_only"]),
        "merge_enabled": bool(settings["merge_enabled"]),
        "dynamic_threshold": True,
        "max_merge_gap_minutes": int(settings["max_merge_gap_minutes"]),
    }
    billboard = {
        "min_ms": play["min_ms"],
        "music_only": play["music_only"],
        "merge_enabled": play["merge_enabled"],
        "bb_top_n": int(settings["bb_top_n"]),
        "bb_album_top_n": int(settings["bb_album_top_n"]),
        "bb_artist_top_n": int(settings["bb_artist_top_n"]),
        "bb_week_start_dow": int(settings["bb_week_start_dow"]),
        "bb_week_start_hour": int(settings["bb_week_start_hour"]),
        "year_start": None,
        "year_end": None,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": int(settings["max_merge_gap_minutes"]),
        "merge_level": 2,
        "include_compilations": bool(settings["include_compilations"]),
    }
    return play, billboard


def warm_common_caches() -> None:
    """Prime expensive default caches used by first-page navigation."""
    conn = get_db()
    try:
        play_filters, billboard_filters = _configured_warmup_filters(conn)
        load_plays(conn, **play_filters)
        load_plays_for_artists(conn, **play_filters)
        get_analysis_stats(conn, **play_filters, period="lifetime")
        get_analysis_charts(
            conn,
            **play_filters,
            period="lifetime",
            entity="track",
            metric="plays",
            limit=250,
        )
        get_analysis_charts(
            conn,
            **play_filters,
            period="lifetime",
            entity="album",
            metric="plays",
            limit=250,
        )
        get_analysis_charts(
            conn,
            **play_filters,
            period="lifetime",
            entity="artist",
            metric="plays",
            limit=250,
        )
        get_archive_overview(conn)
    finally:
        conn.close()

    compute_billboard_data(**billboard_filters)

    from backend.services.home_service import prewarm_default_home_overview

    prewarm_default_home_overview()

    # Persist the latest deterministic Yearly Review artifact after shared
    # playback/Billboard caches are warm. This runs inside the existing daemon
    # warmup thread and never blocks application startup.
    from backend.services.yearly_review_service import prewarm_latest_yearly_review

    prewarm_latest_yearly_review()


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
