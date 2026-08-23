"""Post-import derived data maintenance pipeline."""

from __future__ import annotations

import time
from typing import Any

from backend.core.db import (
    build_aggregations,
    build_aggregations_for_replaced_weeks,
    build_aggregations_for_weeks,
    get_db,
)
from backend.domains.imports.change_set import PlaybackChangeSet
from backend.domains.metadata.import_health import build_import_health_report
from backend.domains.metadata.spotify_refresh import (
    MetadataRefreshScope,
    refresh_missing_spotify_metadata,
)
from backend.domains.music_search.revisions import MusicSearchRevisionKind
from backend.domains.playback.album_projects import rebuild_album_projects_for_impact
from backend.domains.settings.repository import SettingsRepository
from backend.providers.spotify.client import SpotifyProvider
from backend.services.cover_cache_service import enqueue_missing_cover_downloads
from backend.services.music_search_maintenance_service import (
    build_shared_full_music_search_plan,
    mark_music_search_for_rebuild,
    rebuild_current_music_search_derived_data,
    schedule_current_music_search_derived_data_rebuild,
)


def _progress(progress_callback, message: str, pct: float) -> None:
    if progress_callback:
        progress_callback(message, pct)


def run_post_streaming_import_maintenance(
    progress_callback=None,
    *,
    defer_music_search_snapshots: bool = False,
    change_set: PlaybackChangeSet | None = None,
) -> dict[str, Any]:
    """Refresh metadata, rebuild derived statistics, and invalidate runtime caches."""
    conn = get_db(readonly=False)
    try:
        provider = SpotifyProvider()
        token = provider.get_cc_token()

        _progress(progress_callback, "刷新 Spotify 元数据...", 0.72)
        targeted_change = change_set is not None and change_set.strategy in {
            "incremental",
            "reconcile",
        }
        metadata_scope = (
            MetadataRefreshScope(
                generation_id=change_set.generation_id,
                track_ids=change_set.track_ids,
                album_ids=change_set.album_ids,
                artist_ids=change_set.artist_ids,
                spotify_track_ids=change_set.spotify_track_ids,
                spotify_album_ids=change_set.spotify_album_ids,
            )
            if targeted_change and change_set is not None
            else None
        )
        metadata_started = time.perf_counter()
        metadata_report = refresh_missing_spotify_metadata(
            conn,
            provider=provider,
            access_token=token,
            progress_callback=lambda message, _pct: _progress(progress_callback, message, 0.76),
            scope=metadata_scope,
        )
        metadata_seconds = time.perf_counter() - metadata_started

        _progress(progress_callback, "补齐并排队下载缺失封面...", 0.79)
        cover_started = time.perf_counter()
        cover_report = enqueue_missing_cover_downloads(
            conn,
            album_ids=(
                change_set.album_ids | metadata_report.local_album_ids_relinked
                if metadata_scope is not None and change_set is not None
                else None
            ),
            artist_ids=(change_set.artist_ids if metadata_scope is not None else None),
        )
        cover_seconds = time.perf_counter() - cover_started

        _progress(progress_callback, "合并重复曲目（spotify_track_id）...", 0.80)
        grouping_started = time.perf_counter()
        groups_created, members_added = _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=(
                change_set.track_ids if targeted_change and change_set is not None else None
            ),
            spotify_track_ids=(
                metadata_report.spotify_track_ids_updated if targeted_change else None
            ),
        )
        grouping_seconds = time.perf_counter() - grouping_started

        _progress(progress_callback, "重建 album projects...", 0.84)
        album_projects_started = time.perf_counter()
        album_project_report = rebuild_album_projects_for_impact(
            conn,
            local_album_ids=(
                change_set.album_ids | metadata_report.local_album_ids_relinked
                if targeted_change and change_set is not None
                else ()
            ),
            spotify_album_ids=metadata_report.spotify_album_ids_updated,
            spotify_track_ids=metadata_report.spotify_track_ids_updated,
            impact_scope_exact=targeted_change and metadata_report.impact_scope_exact,
            has_deletions=bool(change_set and change_set.removed_count),
        )
        album_projects_seconds = time.perf_counter() - album_projects_started

        _progress(progress_callback, "重建 Billboard 预聚合...", 0.9)
        settings = SettingsRepository(conn).load_all()
        aggregations_started = time.perf_counter()
        min_ms = int(settings.get("min_ms", 30_000))
        music_only = bool(settings.get("music_only", True))
        week_start_dow = int(settings.get("bb_week_start_dow", 4))
        week_start_hour = int(settings.get("bb_week_start_hour", 0))
        max_merge_gap_minutes = int(settings.get("max_merge_gap_minutes", 5))
        expected_generation_id = change_set.generation_id if change_set is not None else None
        if change_set is not None and change_set.strategy == "incremental":
            agg_results = build_aggregations_for_weeks(
                set(change_set.billboard_weeks),
                change_generation_id=change_set.generation_id,
                previous_dataset_digest=change_set.previous_dataset_digest,
                billboard_scope_exact=change_set.billboard_scope_exact,
                min_ms=min_ms,
                music_only=music_only,
                week_start_dow=week_start_dow,
                week_start_hour=week_start_hour,
                dynamic_threshold=True,
                max_merge_gap_minutes=max_merge_gap_minutes,
                expected_generation_id=expected_generation_id,
            )
        elif change_set is not None and change_set.strategy == "reconcile":
            active_state = conn.execute(
                """SELECT active_generation_id, dataset_digest
                   FROM playback_import_state WHERE state_id=1"""
            ).fetchone()
            if (
                active_state is None
                or str(active_state["active_generation_id"] or "") != change_set.generation_id
                or not active_state["dataset_digest"]
            ):
                raise RuntimeError("active reconcile facts do not match the maintenance scope")
            agg_results = build_aggregations_for_replaced_weeks(
                set(change_set.billboard_weeks),
                replacement_scope_exact=change_set.billboard_scope_exact,
                expected_generation_id=change_set.generation_id,
                expected_dataset_digest=str(active_state["dataset_digest"]),
                previous_dataset_digest=change_set.previous_dataset_digest,
                min_ms=min_ms,
                music_only=music_only,
                week_start_dow=week_start_dow,
                week_start_hour=week_start_hour,
                dynamic_threshold=True,
                max_merge_gap_minutes=max_merge_gap_minutes,
            )
        else:
            agg_results = build_aggregations(
                min_ms=min_ms,
                music_only=music_only,
                week_start_dow=week_start_dow,
                week_start_hour=week_start_hour,
                dynamic_threshold=True,
                max_merge_gap_minutes=max_merge_gap_minutes,
                expected_generation_id=expected_generation_id,
            )
        aggregations_seconds = time.perf_counter() - aggregations_started

        revision_kinds: list[MusicSearchRevisionKind] = [
            "playback",
            "billboard",
            "candidate",
        ]
        if any(
            (
                metadata_report.tracks_updated,
                metadata_report.albums_updated,
                metadata_report.artists_updated,
                metadata_report.artist_searches_updated,
                metadata_report.album_links_backfilled,
            )
        ):
            revision_kinds.append("metadata")
        mark_music_search_for_rebuild(
            reason="streaming import maintenance published",
            documents=True,
            revision_kinds=tuple(revision_kinds),
            conn=conn,
        )
        shared_full_search_plan = (
            build_shared_full_music_search_plan(
                conn,
                change_set=change_set,
            )
            if change_set is not None
            else None
        )

        _progress(progress_callback, "核验导入派生数据...", 0.93)
        health = build_import_health_report(conn)

        # build_aggregations() has already invalidated the previous generation.
        # Warm the two interactive surfaces before the long exact-search job
        # is allowed to compete for CPU and SQLite reads.
        _progress(progress_callback, "预热首页与最新完整榜单...", 0.95)
        from backend.core.warmup import prewarm_import_critical_caches

        prewarm_import_critical_caches()

        if defer_music_search_snapshots:
            _progress(progress_callback, "更新音乐查找索引，精确快照转入后台...", 0.98)
            search_report = schedule_current_music_search_derived_data_rebuild(
                conn,
                rebuild_documents=True,
                prewarm_yearly_review=True,
                shared_full_snapshot_plan=shared_full_search_plan,
            )
        else:
            _progress(progress_callback, "重建音乐查找索引与精确快照...", 0.98)
            search_report = rebuild_current_music_search_derived_data(
                conn,
                rebuild_documents=True,
                shared_full_snapshot_plan=shared_full_search_plan,
            )
        if search_report["status"] not in {"ready", "warming"}:
            snapshot_set = search_report["snapshot_set"]
            raise RuntimeError(
                "music-search snapshot set incomplete after import: "
                f"ready={snapshot_set['ready_count']} failed={snapshot_set['failed_count']}"
            )

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
            "artists_metadata_requested": metadata_report.artists_requested,
            "artists_metadata_updated": metadata_report.artists_updated,
            "artist_cover_searches_requested": metadata_report.artist_searches_requested,
            "artist_cover_searches_updated": metadata_report.artist_searches_updated,
            "album_links_backfilled": metadata_report.album_links_backfilled,
            "cover_album_urls_synced": cover_report.album_urls_synced,
            "cover_artist_urls_synced": cover_report.artist_urls_synced,
            "cover_missing_albums": cover_report.missing_albums,
            "cover_missing_artists": cover_report.missing_artists,
            "cover_download_jobs_enqueued": cover_report.jobs_enqueued,
            "cover_sources_scanned": cover_report.sources_scanned,
            "cover_stale_sources": cover_report.stale_sources,
            "metadata_errors": list(metadata_report.errors),
            "track_groups_created": groups_created,
            "track_group_members_added": members_added,
            "album_projects_rebuilt": True,
            "album_project_rebuild_strategy": album_project_report.strategy,
            "album_project_rebuild_fallback_reason": album_project_report.fallback_reason,
            "album_project_affected_albums": album_project_report.affected_album_count,
            "album_project_affected_projects": album_project_report.affected_project_count,
            "maintenance_scope": (
                change_set.strategy
                if metadata_scope is not None and change_set is not None
                else "full"
            ),
            "changed_entity_count": change_set.entity_count if change_set is not None else None,
            "changed_years": sorted(change_set.years) if change_set is not None else [],
            "changed_billboard_weeks": (
                sorted(change_set.billboard_weeks) if change_set is not None else []
            ),
            "metadata_seconds": round(metadata_seconds, 3),
            "cover_seconds": round(cover_seconds, 3),
            "track_grouping_seconds": round(grouping_seconds, 3),
            "album_projects_seconds": round(album_projects_seconds, 3),
            "aggregations_seconds": round(aggregations_seconds, 3),
            "agg_track_wks": agg_results.get("tracks", 0),
            "agg_album_wks": agg_results.get("albums", 0),
            "agg_artist_wks": agg_results.get("artists", 0),
            "aggregation_build_strategy": agg_results.get("build_strategy", "full"),
            "aggregation_fallback_reason": agg_results.get("fallback_reason"),
            "music_search_index_status": (search_report.get("index") or {}).get("status", "ready"),
            "music_search_snapshot_status": search_report["snapshot"]["status"],
            "music_search_snapshot_entities": search_report["snapshot"]["entity_count"],
            "music_search_snapshot_ready_count": search_report["snapshot_set"]["ready_count"],
            "music_search_snapshot_failed_count": search_report["snapshot_set"]["failed_count"],
            "music_search_snapshot_job_id": search_report.get("job_id"),
            "music_search_snapshot_strategy": search_report["snapshot_set"].get("strategy", "full"),
            **health,
        }
    finally:
        conn.close()


def _auto_group_tracks_by_spotify_id(
    conn,
    *,
    track_ids: frozenset[int] | None = None,
    spotify_track_ids: frozenset[str] | None = None,
) -> tuple[int, int]:
    """Create recording-scope track groups for tracks sharing a spotify_track_id
    WITHIN THE SAME ARTIST.  Cross-artist spotify_track_id matches are metadata
    errors and must not be merged.

    Returns (groups_created, members_added).
    """
    if track_ids is not None or spotify_track_ids is not None:
        impacted_pairs: set[tuple[str, int]] = set()
        for column, values in (
            ("track_id", sorted(track_ids or ())),
            ("spotify_track_id", sorted(spotify_track_ids or ())),
        ):
            for offset in range(0, len(values), 800):
                chunk = values[offset : offset + 800]
                placeholders = ",".join("?" for _ in chunk)
                impacted_pairs.update(
                    (str(row[0]), int(row[1]))
                    for row in conn.execute(
                        f"""SELECT DISTINCT spotify_track_id, artist_id
                            FROM tracks
                            WHERE {column} IN ({placeholders})
                              AND spotify_track_id IS NOT NULL
                              AND spotify_track_id != ''""",
                        chunk,
                    ).fetchall()
                )
        return _auto_group_impacted_spotify_pairs(conn, impacted_pairs)

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


def _auto_group_impacted_spotify_pairs(
    conn,
    impacted_pairs: set[tuple[str, int]],
) -> tuple[int, int]:
    """Group only Spotify identities whose local evidence changed this run."""

    groups_created = 0
    members_added = 0
    for spotify_track_id, artist_id in sorted(impacted_pairs):
        tracks = conn.execute(
            """SELECT t.track_id, t.track_name, COUNT(p.play_id) AS play_count
               FROM tracks t
               LEFT JOIN plays p ON p.track_id=t.track_id
               WHERE t.spotify_track_id=? AND t.artist_id=?
               GROUP BY t.track_id, t.track_name
               ORDER BY play_count DESC, t.track_id
               """,
            (spotify_track_id, artist_id),
        ).fetchall()
        if len(tracks) <= 1:
            continue
        primary_track_id = int(tracks[0][0])
        canonical_name = str(tracks[0][1])
        cursor = conn.execute(
            """INSERT OR IGNORE INTO track_groups
               (canonical_name, primary_track_id, scope, is_manual)
               VALUES (?, ?, 'recording', 0)""",
            (canonical_name, primary_track_id),
        )
        groups_created += max(cursor.rowcount, 0)
        group = conn.execute(
            """SELECT tg.group_id
               FROM track_groups tg
               JOIN tracks primary_track ON primary_track.track_id=tg.primary_track_id
               WHERE tg.scope='recording' AND tg.is_manual=0
                 AND primary_track.spotify_track_id=?
                 AND primary_track.artist_id=?
               ORDER BY tg.group_id LIMIT 1""",
            (spotify_track_id, artist_id),
        ).fetchone()
        if group is None:
            raise RuntimeError("Spotify recording group identity could not be resolved")
        group_id = int(group[0])
        before = conn.total_changes
        conn.executemany(
            """INSERT OR IGNORE INTO track_group_members(group_id, track_id)
               VALUES (?, ?)""",
            ((group_id, int(track[0])) for track in tracks),
        )
        members_added += conn.total_changes - before
    return groups_created, members_added
