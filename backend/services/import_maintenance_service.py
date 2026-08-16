"""Post-import derived data maintenance pipeline."""

from __future__ import annotations

from typing import Any

from backend.core.cache_manager import invalidate_all
from backend.core.db import build_aggregations, get_db
from backend.domains.metadata.import_health import build_import_health_report
from backend.domains.metadata.spotify_refresh import refresh_missing_spotify_metadata
from backend.domains.playback.album_projects import rebuild_album_projects
from backend.domains.settings.repository import SettingsRepository
from backend.providers.spotify.client import SpotifyProvider
from backend.services.music_search_maintenance_service import (
    mark_music_search_for_rebuild,
    rebuild_current_music_search_derived_data,
)


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

        _progress(progress_callback, "合并重复曲目（spotify_track_id）...", 0.80)
        groups_created, members_added = _auto_group_tracks_by_spotify_id(conn)

        _progress(progress_callback, "重建 album projects...", 0.84)
        rebuild_album_projects(conn)

        _progress(progress_callback, "重建 Billboard 预聚合...", 0.9)
        settings = SettingsRepository(conn).load_all()
        agg_results = build_aggregations(
            min_ms=int(settings.get("min_ms", 30_000)),
            music_only=bool(settings.get("music_only", True)),
            week_start_dow=int(settings.get("bb_week_start_dow", 4)),
            week_start_hour=int(settings.get("bb_week_start_hour", 0)),
            dynamic_threshold=True,
            max_merge_gap_minutes=int(settings.get("max_merge_gap_minutes", 5)),
        )

        mark_music_search_for_rebuild(
            reason="streaming import maintenance published",
            documents=True,
            revision_kinds=("playback", "billboard", "metadata", "candidate"),
            conn=conn,
        )

        _progress(progress_callback, "重建音乐查找索引与精确快照...", 0.94)
        search_report = rebuild_current_music_search_derived_data(
            conn,
            rebuild_documents=True,
        )
        if search_report["status"] != "ready":
            snapshot_set = search_report["snapshot_set"]
            raise RuntimeError(
                "music-search snapshot set incomplete after import: "
                f"ready={snapshot_set['ready_count']} failed={snapshot_set['failed_count']}"
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
            "track_groups_created": groups_created,
            "track_group_members_added": members_added,
            "album_projects_rebuilt": True,
            "agg_track_wks": agg_results.get("tracks", 0),
            "agg_album_wks": agg_results.get("albums", 0),
            "agg_artist_wks": agg_results.get("artists", 0),
            "music_search_index_status": (search_report.get("index") or {}).get("status", "ready"),
            "music_search_snapshot_status": search_report["snapshot"]["status"],
            "music_search_snapshot_entities": search_report["snapshot"]["entity_count"],
            "music_search_snapshot_ready_count": search_report["snapshot_set"]["ready_count"],
            "music_search_snapshot_failed_count": search_report["snapshot_set"]["failed_count"],
            **health,
        }
    finally:
        conn.close()


def _auto_group_tracks_by_spotify_id(conn) -> tuple[int, int]:
    """Create recording-scope track groups for tracks sharing a spotify_track_id
    WITHIN THE SAME ARTIST.  Cross-artist spotify_track_id matches are metadata
    errors and must not be merged.

    Returns (groups_created, members_added).
    """
    # ① Create groups — one per (spotify_track_id, artist_id), primary = most-plays,
    #     canonical_name = primary track's name (no artist suffix needed:
    #     grouping by artist_id prevents cross-artist clashes).
    conn.execute(
        """INSERT OR IGNORE INTO track_groups
           (canonical_name, primary_track_id, scope, is_manual)
           SELECT
             pt.track_name,
             pt.track_id,
             'recording', 0
           FROM (
               SELECT spotify_track_id, artist_id,
                      (SELECT t2.track_id FROM tracks t2
                       WHERE t2.spotify_track_id = tracks.spotify_track_id
                         AND t2.artist_id = tracks.artist_id
                       ORDER BY (SELECT COUNT(*) FROM plays p WHERE p.track_id = t2.track_id) DESC
                       LIMIT 1) AS best_track_id
               FROM tracks
               WHERE spotify_track_id IS NOT NULL AND spotify_track_id != ''
               GROUP BY spotify_track_id, artist_id
               HAVING COUNT(*) > 1
           ) dup
           JOIN tracks pt ON pt.track_id = dup.best_track_id"""
    )
    groups_created = conn.execute("SELECT CHANGES()").fetchone()[0]

    # ② Add members — match by (spotify_track_id, artist_id) to primary_track_id
    conn.execute(
        """INSERT OR IGNORE INTO track_group_members (group_id, track_id)
           SELECT tg.group_id, t.track_id
           FROM tracks t
           JOIN track_groups tg ON tg.scope = 'recording' AND tg.is_manual = 0
           WHERE t.spotify_track_id IS NOT NULL AND t.spotify_track_id != ''
             AND EXISTS (
               SELECT 1 FROM tracks t2
               WHERE t2.spotify_track_id = t.spotify_track_id
                 AND t2.artist_id = t.artist_id
                 AND t2.track_id = tg.primary_track_id
             )
             AND EXISTS (
               SELECT 1 FROM tracks t3
               WHERE t3.spotify_track_id = t.spotify_track_id
                 AND t3.artist_id = t.artist_id
               GROUP BY t3.spotify_track_id, t3.artist_id
               HAVING COUNT(*) > 1
             )"""
    )
    members_added = conn.execute("SELECT CHANGES()").fetchone()[0]

    return groups_created, members_added
