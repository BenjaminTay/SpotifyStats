"""Invocation-local duration facts; never retains a wide plays DataFrame."""

from __future__ import annotations

import pandas as pd

from backend.core.db import base_filters
from backend.domains.metadata.artist_languages import build_primary_artist_ms
from backend.domains.playback.logical_timeline import reconstruct_listening_intervals


def build_facts(conn, params):
    # Match load_plays' pre-count-filter duration track. Count thresholds and
    # merge_enabled do not discard short listening intervals.
    condition, bindings = base_filters(min_ms=0, music_only=params["music_only"])
    where = "WHERE " + condition if condition else ""
    identity_ready = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_external_ids'"
    ).fetchone()
    if identity_ready:
        # Materializing the small active identity relation avoids a repeated
        # fallback-identity scan on historical databases; selection is unchanged.
        sql = f"""WITH active_local AS MATERIALIZED (
          SELECT l1_id, fallback_track_id, representative_track_id
          FROM track_l1_identities WHERE identity_status!='superseded'
        )
        SELECT p.track_id AS source_track_id,p.ts,p.ms_played,p.source_album_id,
          COALESCE(s.l1_id,l.l1_id,p.track_id) AS track_id,
          COALESCE(s.representative_track_id,l.representative_track_id,p.track_id) AS representative_track_id
        FROM plays p
        LEFT JOIN tracks t ON t.track_id=p.track_id
        LEFT JOIN track_l1_external_ids e ON e.provider='spotify'
          AND e.external_track_id=COALESCE(NULLIF(p.spotify_track_id_at_play,''),NULLIF(t.spotify_track_id,''))
        LEFT JOIN track_l1_identities s ON s.l1_id=e.l1_id AND s.identity_status!='superseded'
        LEFT JOIN active_local l ON l.fallback_track_id=p.track_id
          AND COALESCE(NULLIF(p.spotify_track_id_at_play,''),NULLIF(t.spotify_track_id,'')) IS NULL
        {where} ORDER BY p.ts"""
    else:
        sql = f"""SELECT p.track_id,p.track_id AS representative_track_id,p.ts,p.ms_played,p.source_album_id
          FROM plays p {where} ORDER BY p.ts"""
    frame = pd.read_sql_query(sql, conn, params=bindings)
    duration = reconstruct_listening_intervals(
        frame,
        identity_column="track_id",
        max_gap_minutes=params["max_merge_gap_minutes"],
        boundary_column="source_album_id",
    )
    artist_ms, excluded_ms = build_primary_artist_ms(conn, duration)
    return {"artist_ms": {str(k): v for k, v in artist_ms.items()}, "excluded_ms": excluded_ms}


def artist_hours(conn, facts):
    artist_ms = {int(k): int(v) for k, v in facts["artist_ms"].items()}
    names = {}
    ids = list(artist_ms)
    for offset in range(0, len(ids), 500):
        chunk = ids[offset : offset + 500]
        names.update(
            {
                int(r[0]): str(r[1])
                for r in conn.execute(
                    f"SELECT artist_id,artist_name FROM artists WHERE artist_id IN ({','.join('?' for _ in chunk)})",
                    chunk,
                ).fetchall()
            }
        )
    return {names[k]: v / 3_600_000 for k, v in artist_ms.items() if k in names and v > 0}, facts[
        "excluded_ms"
    ] / 3_600_000
