"""Build-local, bounded album facts for Records' complete-replay ranking.

No process/global cache: the maps die with this one Records build. Original
edition trust rules are identical to the per-project lookup.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

import pandas as pd


def load_original_memberships(conn, merge_level):
    from backend.domains.playback.album_projects import apply_canonical_song_keys

    try:
        projects = conn.execute(
            """SELECT ap.project_id, ap.primary_album_id, ap.canonical_name, ap.release_date,
                      al.album_name, ar.artist_name
               FROM album_projects ap
               JOIN album_project_albums apa
                 ON apa.project_id = ap.project_id
                AND apa.album_id = ap.primary_album_id
               JOIN albums al ON al.album_id = ap.primary_album_id
               LEFT JOIN artists ar ON ar.artist_id = ap.artist_id
               WHERE apa.role = 'primary'
                 AND apa.source_bucket = 'original_album'"""
        ).fetchall()
        members = conn.execute(
            """SELECT DISTINCT apt.project_id, apt.source_album_id, apt.track_id, t.spotify_track_id
                 FROM album_project_tracks apt JOIN tracks t ON t.track_id=apt.track_id
                 JOIN album_projects ap ON ap.project_id=apt.project_id
                   AND apt.source_album_id=ap.primary_album_id
                 WHERE apt.membership_role='standard' AND apt.min_merge_level <= ?
                 ORDER BY apt.track_id""",
            (merge_level,),
        ).fetchall()
        candidates = conn.execute(
            """WITH metadata AS MATERIALIZED (
                   SELECT *, REPLACE(spotify_album_id, 'spotify:album:', '') AS normalized_id
                   FROM spotify_album_meta
               )
               SELECT asl.album_id, sam.normalized_id AS spotify_album_id,
                      sam.album_name, sam.album_artists, sam.release_date,
                      sam.total_tracks, sam.track_list,
                      MAX(COALESCE(asl.confidence, 0)) AS confidence,
                      SUM(COALESCE(asl.play_count, 0)) AS play_count,
                      MAX(COALESCE(asl.track_count, 0)) AS linked_track_count
               FROM album_spotify_links asl
               JOIN metadata sam
                 ON sam.normalized_id =
                    REPLACE(asl.spotify_album_id, 'spotify:album:', '')
               WHERE LOWER(COALESCE(sam.album_type, '')) = 'album'
               GROUP BY asl.album_id, sam.normalized_id"""
        ).fetchall()
        by_original = defaultdict(dict)
        for row in members:
            if row["spotify_track_id"]:
                by_original[(int(row["project_id"]), int(row["source_album_id"]))][
                    str(row["spotify_track_id"])
                ] = int(row["track_id"])
        by_album = defaultdict(list)
        for row in candidates:
            by_album[int(row["album_id"])].append(row)
        track_ids = sorted({int(row["track_id"]) for row in members})
        keyed = apply_canonical_song_keys(pd.DataFrame({"track_id": track_ids}), conn, merge_level)
        canonical_keys = dict(zip(keyed["track_id"], keyed["canonical_song_key"].astype(str)))
        result = {}
        for project in projects:
            if project["primary_album_id"] is None:
                continue
            original = int(project["primary_album_id"])
            local = by_original[(int(project["project_id"]), original)]
            if local:
                try:
                    result[int(project["project_id"])] = _trusted_original(
                        project, local, by_album[original], canonical_keys
                    )
                except (TypeError, ValueError, KeyError):
                    continue
        return result
    except Exception:
        # Compact/legacy fixtures can lack these metadata tables. They were
        # ineligible for trusted original membership before batching too.
        return {}


def _trusted_original(project, local_spotify_to_track, candidates, canonical_keys):
    def normalized(value):
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    expected_titles = {
        normalized(project["canonical_name"]),
        normalized(project["album_name"]),
    }
    expected_titles.discard("")
    expected_artist = normalized(project["artist_name"])
    expected_date = project["release_date"]

    trusted = []
    for candidate in candidates:
        if normalized(candidate["album_name"]) not in expected_titles:
            continue
        album_artists = {
            normalized(value)
            for value in re.split(r"\s*,\s*", str(candidate["album_artists"] or ""))
            if normalized(value)
        }
        if expected_artist and expected_artist not in album_artists:
            continue
        if expected_date and candidate["release_date"] != expected_date:
            continue
        total = int(candidate["total_tracks"] or 0)
        try:
            spotify_track_ids = {
                str(value) for value in json.loads(candidate["track_list"] or "[]") if value
            }
        except (json.JSONDecodeError, TypeError):
            continue
        if total < 2 or len(spotify_track_ids) != total:
            continue
        if int(candidate["linked_track_count"] or 0) < total:
            continue
        if not spotify_track_ids.issubset(local_spotify_to_track):
            continue

        song_keys = {canonical_keys[local_spotify_to_track[value]] for value in spotify_track_ids}
        if len(song_keys) != total:
            continue
        trusted.append(
            (
                song_keys,
                total,
                int(candidate["play_count"] or 0),
                float(candidate["confidence"] or 0),
            )
        )

    if not trusted:
        return None
    canonical_sets = {frozenset(item[0]) for item in trusted}
    if len(canonical_sets) != 1:
        return None
    selected = max(trusted, key=lambda item: (item[2], item[3]))
    return selected[0], selected[1]
