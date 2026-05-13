"""ETL pipeline: import Spotify Extended Streaming History JSON into SQLite."""

import json
import glob
import os
from typing import Any, Optional

from .db import get_db, init_db, DB_PATH
from .utils import convert_to_local_time, classify_platform

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "Spotify Extended Streaming History - 251029",
)


def _cache_artist(conn, name: str, cache: dict[str, int]) -> int:
    if name in cache:
        return cache[name]
    cur = conn.execute(
        "INSERT OR IGNORE INTO artists(artist_name) VALUES (?)", (name,)
    )
    if cur.lastrowid:
        cache[name] = cur.lastrowid
    else:
        row = conn.execute(
            "SELECT artist_id FROM artists WHERE artist_name = ?", (name,)
        ).fetchone()
        cache[name] = row[0]
    return cache[name]


def _cache_album(conn, album_name: str, artist_id: int, cache: dict[tuple, int]) -> int:
    key = (album_name, artist_id)
    if key in cache:
        return cache[key]
    cur = conn.execute(
        "INSERT OR IGNORE INTO albums(album_name, artist_id) VALUES (?, ?)",
        (album_name, artist_id),
    )
    if cur.lastrowid:
        cache[key] = cur.lastrowid
    else:
        row = conn.execute(
            "SELECT album_id FROM albums WHERE album_name = ? AND artist_id = ?",
            (album_name, artist_id),
        ).fetchone()
        cache[key] = row[0]
    return cache[key]


def _cache_track(
    conn,
    track_name: str,
    artist_id: int,
    album_id: Optional[int],
    spotify_uri: Optional[str],
    cache: dict[tuple, int],
) -> int:
    # Use (artist_id, track_name) as canonical key to merge duplicate versions
    key = (artist_id, track_name)
    if key in cache:
        tid = cache[key]
    else:
        cur = conn.execute(
            """INSERT OR IGNORE INTO tracks(track_name, artist_id, album_id, spotify_track_uri)
               VALUES (?, ?, ?, ?)""",
            (track_name, artist_id, album_id, spotify_uri),
        )
        if cur.lastrowid:
            tid = cur.lastrowid
        else:
            row = conn.execute(
                "SELECT track_id FROM tracks WHERE track_name = ? AND artist_id = ?",
                (track_name, artist_id),
            ).fetchone()
            tid = row[0]
        cache[key] = tid

    # If track already existed and current play has a different album, record the association
    if album_id is not None:
        conn.execute(
            "INSERT OR IGNORE INTO track_albums(track_id, album_id) VALUES (?, ?)",
            (tid, album_id),
        )

    return tid


def import_data(
    data_dir: Optional[str] = None,
    progress_callback=None,
) -> dict[str, Any]:
    """Import all JSON streaming history files into the SQLite database.

    Args:
        data_dir: Path to the folder containing JSON files.
        progress_callback: Optional callable(step: str, pct: float) for progress.

    Returns:
        Dict with summary stats.
    """
    if data_dir is None:
        data_dir = DATA_DIR

    json_files = sorted(glob.glob(os.path.join(data_dir, "Streaming_History_Audio_*.json")))

    if not json_files:
        raise FileNotFoundError(f"No Streaming_History_Audio_*.json files found in {data_dir}")

    # Reset database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

    conn = get_db(readonly=False)

    artist_cache: dict[str, int] = {}
    album_cache: dict[tuple, int] = {}
    track_cache: dict[str, int] = {}

    total_files = len(json_files)
    total_records = 0
    total_skipped = 0

    for file_idx, filepath in enumerate(json_files):
        with open(filepath, encoding="utf-8") as f:
            records = json.load(f)

        plays_batch: list[tuple] = []

        for rec in records:
            ts_raw = rec.get("ts", "")
            country = rec.get("conn_country", "CN")
            time_info = convert_to_local_time(ts_raw, country)

            platform = classify_platform(rec.get("platform", ""))
            ms_played = rec.get("ms_played", 0)
            skipped = 1 if rec.get("skipped") else 0
            if skipped:
                total_skipped += 1

            track_name = rec.get("master_metadata_track_name")
            artist_name = rec.get("master_metadata_album_artist_name")
            album_name = rec.get("master_metadata_album_album_name")
            spotify_uri = rec.get("spotify_track_uri")

            # Resolve or create dimension rows
            track_id = None
            if track_name and artist_name:
                artist_id = _cache_artist(conn, artist_name, artist_cache)
                album_id = None
                if album_name:
                    album_id = _cache_album(conn, album_name, artist_id, album_cache)
                track_id = _cache_track(
                    conn, track_name, artist_id, album_id, spotify_uri, track_cache
                )

            plays_batch.append((
                time_info["ts"],
                time_info["ts_year"],
                time_info["ts_month"],
                time_info["ts_week"],
                time_info["ts_dow"],
                time_info["ts_hour"],
                time_info["ts_date"],
                platform,
                ms_played,
                country,
                track_id,
                rec.get("reason_start"),
                rec.get("reason_end"),
                1 if rec.get("shuffle") else 0,
                skipped,
                1 if rec.get("offline") else 0,
                1 if rec.get("incognito_mode") else 0,
            ))

            # Batch insert every 5000 rows to keep memory in check
            if len(plays_batch) >= 5000:
                conn.executemany(
                    """INSERT INTO plays(ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
                       ts_date, platform, ms_played, conn_country, track_id,
                       reason_start, reason_end, shuffle, skipped, offline, incognito_mode)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    plays_batch,
                )
                conn.commit()
                total_records += len(plays_batch)
                plays_batch.clear()

            if progress_callback and total_records > 0 and total_records % 10000 == 0:
                progress_callback(
                    f"处理中... ({total_records} 条)",
                    (file_idx + (len(records) - len(plays_batch)) / max(len(records), 1))
                    / total_files,
                )

        # Insert remaining batch
        if plays_batch:
            conn.executemany(
                """INSERT INTO plays(ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
                   ts_date, platform, ms_played, conn_country, track_id,
                   reason_start, reason_end, shuffle, skipped, offline, incognito_mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                plays_batch,
            )
            conn.commit()
            total_records += len(plays_batch)

        if progress_callback:
            progress_callback(
                f"已导入 {os.path.basename(filepath)}",
                (file_idx + 1) / total_files,
            )

    conn.commit()
    conn.close()

    return {
        "total_records": total_records,
        "total_skipped": total_skipped,
        "unique_artists": len(artist_cache),
        "unique_albums": len(album_cache),
        "unique_tracks": len(track_cache),
        "files_imported": total_files,
    }
