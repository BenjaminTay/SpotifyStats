"""Post-import derived data maintenance pipeline."""

from __future__ import annotations

from typing import Any

from backend.core.cache_manager import invalidate_all
from backend.core.db import build_aggregations, get_db
from backend.domains.metadata.import_health import build_import_health_report
from backend.domains.metadata.spotify_refresh import refresh_missing_spotify_metadata
from backend.domains.playback.album_projects import rebuild_album_projects
from backend.providers.spotify.client import SpotifyProvider


def _progress(progress_callback, message: str, pct: float) -> None:
    if progress_callback:
        progress_callback(message, pct)


def run_post_streaming_import_maintenance(progress_callback=None) -> dict[str, Any]:
    """Refresh metadata, rebuild derived statistics, and invalidate runtime caches."""
    conn = get_db(readonly=False)
    try:
        provider = SpotifyProvider()
        token = provider.get_cc_token()

        _progress(progress_callback, "刷新 Spotify 元数据...", 0.72)
        metadata_report = refresh_missing_spotify_metadata(
            conn,
            provider=provider,
            access_token=token,
            progress_callback=lambda message, _pct: _progress(progress_callback, message, 0.76),
        )

        _progress(progress_callback, "重建 album projects...", 0.84)
        rebuild_album_projects(conn)

        _progress(progress_callback, "重建 Billboard 预聚合...", 0.9)
        agg_results = build_aggregations(
            min_ms=30000,
            music_only=True,
            week_start_dow=4,
            week_start_hour=0,
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
        )

        _progress(progress_callback, "核验导入派生数据...", 0.96)
        health = build_import_health_report(conn)
        invalidate_all()

        status = "ok"
        if not metadata_report.provider_available or metadata_report.errors:
            status = "partial"
        if health["unresolved_recent_tracks"] or health["unresolved_recent_albums"]:
            status = "partial"

        return {
            "maintenance_status": status,
            "tracks_metadata_requested": metadata_report.tracks_requested,
            "tracks_metadata_updated": metadata_report.tracks_updated,
            "albums_metadata_requested": metadata_report.albums_requested,
            "albums_metadata_updated": metadata_report.albums_updated,
            "album_links_backfilled": metadata_report.album_links_backfilled,
            "metadata_errors": list(metadata_report.errors),
            "album_projects_rebuilt": True,
            "agg_track_wks": agg_results.get("tracks", 0),
            "agg_album_wks": agg_results.get("albums", 0),
            "agg_artist_wks": agg_results.get("artists", 0),
            **health,
        }
    finally:
        conn.close()
