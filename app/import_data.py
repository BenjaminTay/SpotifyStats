"""ETL pipeline: import Spotify Extended Streaming History JSON into SQLite."""

import json
import glob
import os
from typing import Any, Optional

from .db import get_db, init_db, DB_PATH, build_aggregations
from .utils import convert_to_local_time, classify_platform

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "Spotify Extended Streaming History",
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
    agg_min_ms: int = 30000,
    agg_exclude_skipped: bool = True,
    agg_music_only: bool = True,
    agg_week_start_dow: int = 4,
    agg_week_start_hour: int = 0,
) -> dict[str, Any]:
    """Import all JSON streaming history files into the SQLite database.

    Args:
        data_dir: Path to the folder containing JSON files.
        progress_callback: Optional callable(step: str, pct: float) for progress.
        agg_*: Parameters for building pre-aggregated Billboard tables after import.

    Returns:
        Dict with summary stats.
    """
    if data_dir is None:
        data_dir = DATA_DIR

    json_files = sorted(glob.glob(os.path.join(data_dir, "Streaming_History_Audio_*.json")))

    if not json_files:
        raise FileNotFoundError(f"No Streaming_History_Audio_*.json files found in {data_dir}")

    # Pre-count total records for accurate progress (fast — just json.load)
    if progress_callback:
        progress_callback("计算总记录数...", 0.0)
    total_records_est = 0
    file_record_counts = {}
    for filepath in json_files:
        with open(filepath, encoding="utf-8") as f:
            records = json.load(f)
            file_record_counts[filepath] = len(records)
            total_records_est += len(records)

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
        records_in_file = len(records)

        for rec_idx, rec in enumerate(records):
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

            # Progress: per-file granularity
            if progress_callback and total_records_est > 0:
                processed = total_records + len(plays_batch)
                pct = min(0.95, processed / total_records_est)
                if processed % 5000 == 0:
                    progress_callback(
                        f"导入中... {processed:,} / {total_records_est:,} ({pct:.0%})",
                        pct,
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

    conn.commit()

    # Build pre-aggregated weekly Billboard tables
    if progress_callback:
        progress_callback("构建预聚合表...", 0.96)
    try:
        agg_results = build_aggregations(
            min_ms=agg_min_ms,
            exclude_skipped=agg_exclude_skipped,
            music_only=agg_music_only,
            week_start_dow=agg_week_start_dow,
            week_start_hour=agg_week_start_hour,
            progress_callback=progress_callback,
        )
    except Exception as e:
        import traceback
        print(f"[WARN] 预聚合表构建失败（Billboard 页面将使用实时计算）: {e}")
        traceback.print_exc()
        agg_results = {}

    conn.close()

    result = {
        "total_records": total_records,
        "total_skipped": total_skipped,
        "unique_artists": len(artist_cache),
        "unique_albums": len(album_cache),
        "unique_tracks": len(track_cache),
        "files_imported": total_files,
        "agg_track_wks": agg_results.get("tracks", 0),
        "agg_album_wks": agg_results.get("albums", 0),
        "agg_artist_wks": agg_results.get("artists", 0),
    }

    if progress_callback:
        progress_callback("导入完成", 1.0)

    return result
