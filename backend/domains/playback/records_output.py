"""Output helpers for Playback Records: cover URLs, serialization."""

from __future__ import annotations

import pandas as pd

from backend.core.db import get_db
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.core.json_helpers import py_val as _py_val


def _is_track_record(df, key: str) -> bool:
    """Heuristic: is this DataFrame/record-key for track-type entities?"""
    key_lower = key.lower()
    if "_track" in key_lower or key_lower.endswith("track"):
        return True
    if "_album" in key_lower or "_artist" in key_lower:
        return False
    if "entity_type" in df.columns:
        return (df["entity_type"] == "track").any()
    return False


def _add_cover_urls_to_records(records: dict) -> None:
    """Add cover_url to record DataFrames that have track_id or album/artist identifiers.

    For track records: use track_id -> album cover
    For album records: use (album_name, artist_name) -> album cover
    For artist records: use artist_name -> artist cover
    """
    conn = get_db()

    def _build_url(image_path, image_url, cover_type, entity_id):
        if image_path or image_url:
            return f"/covers/{cover_type}/{entity_id}.jpg"
        return None

    # ── Track cover lookup ──
    # Collect track IDs from both track_id and entity_id columns (entity_id may be
    # canonical_track_id for L2/L3 or track_id for L1, stored as string)
    track_ids_set = set()
    for key, val in records.items():
        if not isinstance(val, pd.DataFrame) or val.empty:
            continue
        # Direct track_id column
        if "track_id" in val.columns:
            for tid in val["track_id"].dropna().unique():
                try:
                    track_ids_set.add(int(tid))
                except (ValueError, TypeError):
                    pass
        # entity_id for track records (may be canonical_track_id or track_id as string)
        if "entity_id" in val.columns and (
            "entity_type" not in val.columns or _is_track_record(val, key)
        ):
            for eid in val["entity_id"].dropna().unique():
                try:
                    track_ids_set.add(int(eid))
                except (ValueError, TypeError):
                    pass

    if track_ids_set:
        placeholders = ",".join("?" for _ in track_ids_set)
        rows = conn.execute(
            f"""SELECT t.track_id, al.album_id, al.image_path, al.image_url
                FROM tracks t
                LEFT JOIN albums al ON t.album_id = al.album_id
                WHERE t.track_id IN ({placeholders})""",
            list(track_ids_set),
        ).fetchall()
        track_cover_map = {
            r["track_id"]: _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
            if r["album_id"]
            else None
            for r in rows
        }
        for key, val in records.items():
            if not isinstance(val, pd.DataFrame) or val.empty:
                continue
            val = val.copy()
            applied = False
            if "track_id" in val.columns:
                val["cover_url"] = val["track_id"].map(track_cover_map)
                applied = True
            elif "entity_id" in val.columns and (
                "entity_type" not in val.columns or _is_track_record(val, key)
            ):
                try:
                    val["cover_url"] = val["entity_id"].apply(
                        lambda eid: track_cover_map.get(int(eid))
                        if eid and str(eid).isdigit()
                        else None
                    )
                    applied = True
                except (ValueError, TypeError):
                    pass
            if applied:
                records[key] = val

    # ── Album cover lookup ──
    # Build lookup by (album_name, artist_name)
    album_rows = conn.execute(
        """SELECT al.album_id, al.album_name, a.artist_name,
                  al.image_path, al.image_url
           FROM albums al
           JOIN artists a ON al.artist_id = a.artist_id"""
    ).fetchall()
    album_cover_map = {}
    for r in album_rows:
        key = (r["album_name"], r["artist_name"])
        url = _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
        if url or key not in album_cover_map:
            album_cover_map[key] = url

    album_records_keys = [k for k in records if "album" in k.lower() and "_track" not in k.lower()]
    for key in album_records_keys:
        val = records[key]
        if isinstance(val, pd.DataFrame) and not val.empty and "name" in val.columns:
            val = val.copy()
            if "artist_name" in val.columns:
                val["cover_url"] = val.apply(
                    lambda row: album_cover_map.get((row["name"], row["artist_name"])), axis=1
                )
            records[key] = val

    # ── Artist cover lookup ──
    artist_rows = conn.execute(
        """SELECT artist_id, artist_name, image_path, image_url
           FROM artists
           WHERE image_path IS NOT NULL AND image_path != ''
              OR image_url IS NOT NULL AND image_url != ''"""
    ).fetchall()
    artist_cover_map = {
        r["artist_name"]: _build_url(r["image_path"], r["image_url"], "artists", r["artist_id"])
        for r in artist_rows
    }

    artist_records_keys = [
        k
        for k in records
        if "artist" in k.lower() and "_track" not in k.lower() and "_album" not in k.lower()
    ]
    for key in artist_records_keys:
        val = records[key]
        if isinstance(val, pd.DataFrame) and not val.empty:
            val = val.copy()
            # For artist records, the artist name may be in "name" column (if safe_rename moved it)
            # or in "artist_name" column
            cover_col = None
            if "artist_name" in val.columns and val["artist_name"].notna().any():
                cover_col = "artist_name"
            elif "name" in val.columns and val["name"].notna().any():
                cover_col = "name"
            if cover_col:
                val["cover_url"] = val[cover_col].map(artist_cover_map)
                records[key] = val

    conn.close()


def _serialize_records(records: dict) -> dict:
    """Convert the records dict to JSON-safe format.

    Each value is either a DataFrame (→ list of dicts) or a scalar dict (→ native types).
    Cleans up NaN/NaT values that would break JSON serialization.
    """
    result: dict = {}
    for key, val in records.items():
        if isinstance(val, pd.DataFrame):
            if val.empty:
                result[key] = []
            else:
                # Replace NaN/NaT with None before serialization
                cleaned = val.where(pd.notnull(val), None)
                result[key] = _df_to_json(cleaned)
        elif isinstance(val, dict):
            result[key] = {k: _py_val(v) for k, v in val.items()}
        elif isinstance(val, list):
            result[key] = val
        else:
            result[key] = _py_val(val)
    return result
