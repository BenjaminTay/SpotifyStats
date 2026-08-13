"""Shared local source adapters for music archive relationship metrics."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from backend.core.db import merge_consecutive_plays
from backend.domains.account_archive.overview import load_saved_track_rows
from backend.domains.playback.counting import filter_effective_plays
from backend.domains.playback.track_groups import load_track_group_keys
from backend.models.account_archive import ArchiveFilterContext


def _track_group_map(conn: sqlite3.Connection, merge_level: int) -> dict[int, int]:
    if merge_level <= 1:
        return {}
    try:
        keys = load_track_group_keys(conn, merge_level=merge_level)
    except Exception:
        return {}
    if keys.empty:
        return {}
    keys = (
        keys.dropna(subset=["track_id", "track_agg_id"])
        .sort_values(["track_id", "track_agg_id"], kind="stable")
        .drop_duplicates("track_id")
    )
    return {int(row.track_id): int(row.track_agg_id) for row in keys.itertuples(index=False)}


def load_saved_track_entities(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return canonical current-save entities plus raw snapshot coverage counts.

    When multiple saved versions resolve to one track group, the earliest
    current-snapshot save date represents that canonical relationship.
    """
    rows = load_saved_track_rows(conn)
    group_map = _track_group_map(conn, context.merge_level)
    matched_rows = [row for row in rows if row.get("local_track_id") is not None]
    for row in matched_rows:
        local_id = int(row["local_track_id"])
        row["archive_track_id"] = group_map.get(local_id, local_id)

    by_entity: dict[int, list[dict[str, Any]]] = {}
    for row in matched_rows:
        by_entity.setdefault(int(row["archive_track_id"]), []).append(row)

    entities: list[dict[str, Any]] = []
    for archive_track_id, members in by_entity.items():
        dated_members = sorted(
            (member for member in members if member.get("added_date")),
            key=lambda member: member["added_date"],
        )
        representative = dict(dated_members[0] if dated_members else members[0])
        representative["archive_track_id"] = archive_track_id
        representative["snapshot_members"] = len(members)
        representative["deep_link"] = f"/music/tracks/{archive_track_id}"
        entities.append(representative)

    coverage = {
        "saved_tracks": len(rows),
        "matched_saved_tracks": len(matched_rows),
        "unmatched_saved_tracks": len(rows) - len(matched_rows),
        "canonical_saved_entities": len(entities),
    }
    return entities, coverage


def load_effective_archive_plays(
    conn: sqlite3.Connection, context: ArchiveFilterContext
) -> pd.DataFrame:
    """Load effective logical music events using the global counting helpers."""
    required_tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if not {"plays", "tracks"}.issubset(required_tables):
        return pd.DataFrame(
            columns=[
                "play_id",
                "ts",
                "ms_played",
                "track_id",
                "source_album_id",
                "duration_ms",
                "archive_track_id",
                "ts_utc",
                "event_at",
            ]
        )

    play_columns = {row[1] for row in conn.execute("PRAGMA table_info(plays)")}
    source_album_expr = "p.source_album_id" if "source_album_id" in play_columns else "NULL"
    has_track_meta = "spotify_track_meta" in required_tables
    duration_expr = "stm.duration_ms" if has_track_meta else "NULL"
    meta_join = (
        "LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = t.spotify_track_id"
        if has_track_meta
        else ""
    )
    frame = pd.read_sql_query(
        f"""
        SELECT p.play_id, p.ts, p.ms_played, p.track_id,
               {source_album_expr} AS source_album_id,
               {duration_expr} AS duration_ms
        FROM plays p
        JOIN tracks t ON t.track_id = p.track_id
        {meta_join}
        WHERE p.track_id IS NOT NULL
        ORDER BY p.ts, p.play_id
        """,
        conn,
    )
    if frame.empty:
        frame["archive_track_id"] = pd.Series(dtype="int64")
        frame["ts_utc"] = pd.Series(dtype="datetime64[ns, UTC]")
        frame["event_at"] = pd.Series(dtype="datetime64[ns, UTC]")
        return frame

    if context.merge_enabled:
        frame = merge_consecutive_plays(
            frame,
            context.min_ms,
            max_gap_minutes=context.max_merge_gap_minutes,
            boundary_column="source_album_id",
        )
    frame = filter_effective_plays(
        frame,
        min_ms=context.min_ms,
        dynamic_threshold=context.dynamic_threshold,
    )
    frame["ts_utc"] = pd.to_datetime(frame["ts"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["ts_utc", "track_id"]).copy()
    # Spotify Extended Streaming History `ts` records when playback stopped.
    # Anchor relationship windows at the logical event start so the play
    # during which Save was pressed is not misclassified as a later revisit.
    frame["event_at"] = frame["ts_utc"] - pd.to_timedelta(
        frame["ms_played"].clip(lower=0), unit="ms"
    )
    group_map = _track_group_map(conn, context.merge_level)
    frame["archive_track_id"] = (
        frame["track_id"].astype(int).map(group_map).fillna(frame["track_id"]).astype(int)
    )
    return frame.reset_index(drop=True)


def load_track_preview_map(
    conn: sqlite3.Connection, track_ids: set[int]
) -> dict[int, dict[str, Any]]:
    """Load compact local metadata for at most the IDs needed by examples."""
    if not track_ids:
        return {}
    placeholders = ",".join("?" for _ in track_ids)
    album_columns = {row[1] for row in conn.execute("PRAGMA table_info(albums)")}
    image_path = "al.image_path" if "image_path" in album_columns else "NULL"
    image_url = "al.image_url" if "image_url" in album_columns else "NULL"
    rows = conn.execute(
        f"""
        SELECT t.track_id, t.track_name, a.artist_name, al.album_name,
               al.album_id, {image_path} AS image_path, {image_url} AS image_url
        FROM tracks t
        JOIN artists a ON a.artist_id = t.artist_id
        LEFT JOIN albums al ON al.album_id = t.album_id
        WHERE t.track_id IN ({placeholders})
        """,
        tuple(sorted(track_ids)),
    ).fetchall()
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        cover_url = None
        if row[4] is not None and (row[5] or row[6]):
            cover_url = f"/covers/albums/{int(row[4])}.jpg"
        result[int(row[0])] = {
            "track_name": row[1] or "",
            "artist_name": row[2] or "",
            "album_name": row[3],
            "cover_url": cover_url,
            "deep_link": f"/music/tracks/{int(row[0])}",
        }
    return result
