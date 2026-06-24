"""Health probes for post-import derived data coverage."""

from __future__ import annotations

import sqlite3


def build_import_health_report(
    conn: sqlite3.Connection,
    since_date: str = "2026-05-13",
) -> dict[str, int]:
    row = conn.execute(
        """
        WITH recent_plays AS (
          SELECT p.play_id, p.track_id, p.source_album_id, p.spotify_track_id_at_play
          FROM plays p
          WHERE p.ts_date > ?
            AND p.content_type = 'audio'
            AND p.track_id IS NOT NULL
        ),
        recent_tracks AS (
          SELECT DISTINCT
            rp.track_id,
            COALESCE(NULLIF(rp.spotify_track_id_at_play, ''), t.spotify_track_id) AS spotify_track_id
          FROM recent_plays rp
          JOIN tracks t ON t.track_id = rp.track_id
        ),
        recent_albums AS (
          SELECT DISTINCT source_album_id AS album_id
          FROM recent_plays
          WHERE source_album_id IS NOT NULL
        ),
        recent_album_state AS (
          SELECT
            ra.album_id,
            COUNT(DISTINCT rp.track_id) AS local_tracks,
            MAX(CASE WHEN sam.album_type = 'album' THEN 1 ELSE 0 END) AS has_album_type,
            MAX(COALESCE(sam.total_tracks, 0)) AS max_total_tracks
          FROM recent_albums ra
          LEFT JOIN recent_plays rp ON rp.source_album_id = ra.album_id
          LEFT JOIN album_spotify_links asl ON asl.album_id = ra.album_id
          LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = asl.spotify_album_id
          GROUP BY ra.album_id
        ),
        project_candidate_albums AS (
          SELECT album_id
          FROM recent_album_state
          WHERE has_album_type = 1
             OR local_tracks >= 7
        )
        SELECT
          (SELECT COUNT(*) FROM recent_plays) AS recent_plays,
          (SELECT COUNT(*) FROM recent_tracks) AS recent_tracks,
          (SELECT COUNT(*) FROM recent_albums) AS recent_source_albums,
          (SELECT COUNT(*)
             FROM recent_tracks rt
             LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = rt.spotify_track_id
             LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = stm.spotify_album_id
            WHERE stm.spotify_track_id IS NULL OR sam.spotify_album_id IS NULL
               OR COALESCE(sam.image_url, '') = '') AS unresolved_recent_tracks,
          (SELECT COUNT(*)
             FROM project_candidate_albums pca
             LEFT JOIN album_project_albums apa ON apa.album_id = pca.album_id
            WHERE apa.album_id IS NULL) AS unresolved_recent_albums
        """,
        (since_date,),
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}
