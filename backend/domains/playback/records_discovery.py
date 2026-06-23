"""探索發現：新歌、多樣性、專輯完成度（P1 section）。"""

from __future__ import annotations

import sqlite3

import pandas as pd

from backend.domains.playback.records_helpers import TOP_RECORD_LIMIT, safe_groupby_cols


def _group_col_for(frame, entity_type):
    if entity_type == "track":
        return (
            "canonical_track_id" if "canonical_track_id" in frame.columns else "track_id",
            "canonical_track_name" if "canonical_track_name" in frame.columns else "track_name",
            "artist_name",
        )
    elif entity_type == "album":
        return (
            "album_project_id" if "album_project_id" in frame.columns else "album_name",
            "album_project_name" if "album_project_name" in frame.columns else "album_name",
            "artist_name",
        )
    else:
        return "artist_name", "artist_name", "artist_name"


def _discovery_day(frame, group_col, name_col, artist_col, entity_type):
    """單日首次播放新 entity 數量最多的日期。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    first_seen = frame.groupby(gb_cols)["ts_date"].min().reset_index(name="first_date")
    new_per_day = first_seen.groupby("first_date").size().reset_index(name="new_count")
    best = new_per_day.sort_values("new_count", ascending=False).head(TOP_RECORD_LIMIT).copy()
    best["rank"] = range(1, len(best) + 1)
    best["name"] = best["first_date"].astype(str)
    best["value"] = best["new_count"].astype(float)
    best["unit"] = f"首新{entity_type}"
    best["date"] = best["first_date"].astype(str)
    return best


def _same_name_diff_artist(track_frame):
    """同名異曲。"""
    if track_frame.empty:
        return pd.DataFrame()
    same_name = (
        track_frame.groupby("track_name")["artist_name"].nunique().reset_index(name="artist_count")
    )
    same_name = (
        same_name[same_name["artist_count"] >= 2]
        .sort_values("artist_count", ascending=False)
        .head(TOP_RECORD_LIMIT)
    )
    if same_name.empty:
        return pd.DataFrame()
    rows = []
    for _, sn in same_name.iterrows():
        artists = track_frame[track_frame["track_name"] == sn["track_name"]]["artist_name"].unique()
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": sn["track_name"],
                "value": float(sn["artist_count"]),
                "unit": "位不同藝人",
                "caption": "、".join(str(a) for a in artists[:5]),
            }
        )
    return pd.DataFrame(rows)


def compute_discovery_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
    conn: sqlite3.Connection | None = None,
):
    """Populate discovery records."""
    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            records[f"discovery_day_{entity_type}"] = pd.DataFrame()
            records[f"discovery_no_repeat_{entity_type}"] = pd.DataFrame()
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            records[f"discovery_day_{entity_type}"] = _discovery_day(
                frame, gcol, ncol, acol, entity_type
            )
            records[f"discovery_no_repeat_{entity_type}"] = _no_repeat_streak(
                frame, gcol, entity_type
            )

    records["discovery_same_name_diff_artist"] = _same_name_diff_artist(track_frame)
    # Use album_frame (has album_project_id/name for L2/L3) for album completionist
    completion_frame = album_frame if not album_frame.empty else event_frame
    records["discovery_album_completionist"] = (
        _album_completionist(completion_frame, conn) if conn else pd.DataFrame()
    )
    records["discovery_feat_lover_track"] = (
        _feat_lover_track(event_frame) if not event_frame.empty else pd.DataFrame()
    )
    records["discovery_feat_lover_artist"] = (
        _feat_lover_artist(artist_frame) if not artist_frame.empty else pd.DataFrame()
    )


def _no_repeat_streak(frame, group_col, entity_type):
    """最長不重複序列。"""
    if frame.empty:
        return pd.DataFrame()
    df = frame.sort_values("ts").copy()
    df["_entity"] = df[group_col].astype(str)
    seen = set()
    run_length = 0
    max_run = 0
    for _, row in df.iterrows():
        eid = row["_entity"]
        if eid in seen:
            if run_length > max_run:
                max_run = run_length
            seen = {eid}
            run_length = 1
        else:
            seen.add(eid)
            run_length += 1
    if run_length > max_run:
        max_run = run_length
    return (
        pd.DataFrame(
            [
                {
                    "rank": 1,
                    "name": f"最長不重複{entity_type}序列",
                    "value": float(max_run),
                    "unit": "首不重複",
                }
            ]
        )
        if max_run > 0
        else pd.DataFrame()
    )


def _album_completionist(frame, conn):
    """專輯完成者：播放過的 album project 中不同歌曲覆蓋率最高。"""
    if frame.empty or conn is None:
        return pd.DataFrame()

    # Use album project columns for L2/L3, fall back to album_name
    album_id_col = "album_project_id" if "album_project_id" in frame.columns else "album_name"
    album_name_col = "album_project_name" if "album_project_name" in frame.columns else "album_name"

    song_col = "canonical_song_key" if "canonical_song_key" in frame.columns else "track_id"

    # Get distinct canonical songs per album project
    user_album_tracks = (
        frame.groupby([album_id_col, album_name_col, "artist_name"])[song_col]
        .nunique()
        .reset_index(name="user_track_count")
    )
    if user_album_tracks.empty:
        return pd.DataFrame()

    # Get total track count from Spotify metadata
    results = []
    for _, row in user_album_tracks.iterrows():
        if row["user_track_count"] < 3:  # minimum for meaningful completion
            continue
        album_name = (
            str(row[album_name_col])
            if album_name_col in row.index
            else str(row.get("album_name", ""))
        )
        artist_name = str(row["artist_name"])
        project_total = (
            _get_album_project_total_tracks(conn, row[album_id_col])
            if album_id_col == "album_project_id"
            else None
        )
        total = project_total or _get_album_total_tracks(conn, album_name, artist_name)
        if total and total > 0:
            completion_pct = min(row["user_track_count"] / total * 100, 100)
        else:
            completion_pct = None  # unknown total tracks

        results.append(
            {
                "name": album_name,
                "artist_name": artist_name,
                "user_track_count": int(row["user_track_count"]),
                "total_tracks": total,
                "completion_pct": round(completion_pct, 1) if completion_pct is not None else None,
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    # Sort by completion_pct desc, then by user_track_count desc
    df = df.sort_values(
        ["completion_pct", "user_track_count"],
        ascending=[False, False],
        na_position="last",
    ).head(TOP_RECORD_LIMIT)
    df["rank"] = range(1, len(df) + 1)
    df["entity_type"] = "album"
    df["value"] = df["completion_pct"].fillna(0).astype(float)
    df["unit"] = "% 完成度"
    df["secondary_value"] = df["user_track_count"].astype(float)
    df["secondary_unit"] = df["total_tracks"].apply(
        lambda total: f"首 / {int(total)} 首總計" if pd.notna(total) and int(total) > 0 else "首"
    )
    return df


def _get_album_project_total_tracks(conn, album_project_id):
    """Get album project track membership count for completion percentage."""
    try:
        if pd.isna(album_project_id):
            return None
        project_id = int(float(album_project_id))
    except (TypeError, ValueError, OverflowError):
        return None

    try:
        row = conn.execute(
            """SELECT COUNT(DISTINCT track_id) AS total_tracks
               FROM album_project_tracks
               WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        return row["total_tracks"] if row and row["total_tracks"] else None
    except Exception:
        return None


def _get_album_total_tracks(conn, album_name, artist_name):
    """Get total track count for an album from Spotify metadata."""
    try:
        rows = conn.execute(
            """SELECT sam.total_tracks
               FROM albums al
               JOIN artists a ON al.artist_id = a.artist_id
               LEFT JOIN tracks t ON t.album_id = al.album_id
               LEFT JOIN spotify_track_meta stm ON t.spotify_track_id = stm.spotify_track_id
               LEFT JOIN spotify_album_meta sam
                 ON stm.spotify_album_id = sam.spotify_album_id
                 OR 'spotify:album:' || stm.spotify_album_id = sam.spotify_album_id
               WHERE al.album_name = ? AND a.artist_name = ?
                 AND sam.total_tracks IS NOT NULL
               LIMIT 1""",
            (album_name, artist_name),
        ).fetchone()
        return rows["total_tracks"] if rows else None
    except Exception:
        return None


def _has_feat_marker(name):
    """Check if a track name contains feat/collaboration markers.

    Uses regex context matching to distinguish real collaboration markers from
    ordinary words that happen to appear in song titles:

    - "(feat. X)" / "[feat. X]" / "feat. X" — explicit featured artist
    - "(with X)" / "[with X]" — parenthesized "with" = collaboration billing
    - "(vs. X)" / "[vs. X]" / "vs. X" — versus / remix collaboration

    Plain occurrences of "with", "&", "x" in the middle of song titles
    (e.g. "I'm with You", "Dumb & Poetic", "Taco Truck x VB") are NOT
    treated as collaboration markers.
    """
    if not isinstance(name, str):
        return False

    import re

    # feat. / ft. — explicit collab, with or without parentheses/brackets
    if re.search(r"(?:^|[(\[\s])(?:feat|ft)\.\s", name, re.IGNORECASE):
        return True

    # (with X) or [with X] — parenthesized "with" indicates featured artist
    if re.search(r"[(\[]with\s", name, re.IGNORECASE):
        return True

    # vs. — remix/collaboration marker
    if re.search(r"(?:^|[(\[\s])vs\.\s", name, re.IGNORECASE):
        return True

    return False


def _feat_lover_track(event_frame):
    """合作曲偏好：feat 歌曲播放佔比。"""
    if event_frame.empty or "track_name" not in event_frame.columns:
        return pd.DataFrame()

    ef = event_frame.copy()
    ef["_has_feat"] = ef["track_name"].apply(_has_feat_marker)
    feat_count = int(ef["_has_feat"].sum())
    total = len(ef)
    if total == 0:
        return pd.DataFrame()
    feat_pct = round(feat_count / total * 100, 1)

    if feat_count == 0:
        return pd.DataFrame(
            [
                {
                    "rank": 1,
                    "name": "合作曲播放佔比",
                    "value": 0.0,
                    "unit": "% feat 歌曲",
                    "secondary_value": 0.0,
                    "secondary_unit": "次",
                    "caption": f"在 {total} 次播放中未檢測到合作歌曲",
                }
            ]
        )

    # Top feat tracks
    feat_tracks = (
        ef[ef["_has_feat"]].groupby(["track_name", "artist_name"]).size().reset_index(name="count")
    )
    top_feat = feat_tracks.sort_values("count", ascending=False).head(TOP_RECORD_LIMIT)

    rows = []
    for _, row in top_feat.iterrows():
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": row["track_name"],
                "artist_name": row["artist_name"],
                "value": float(row["count"]),
                "unit": "次",
            }
        )
    # Add summary row
    rows.insert(
        0,
        {
            "rank": 0,
            "name": "合作曲播放佔比",
            "value": float(feat_pct),
            "unit": "%",
            "secondary_value": float(feat_count),
            "secondary_unit": "次合作曲播放",
            "caption": f"在 {total} 次播放中，有 {feat_count} 次是合作歌曲 ({feat_pct}%)",
        },
    )
    return pd.DataFrame(rows)


def _feat_lover_artist(artist_frame):
    """合作曲偏好：最常出現的合作藝人（按播放次數）。"""
    if artist_frame.empty or "track_name" not in artist_frame.columns:
        return pd.DataFrame()

    # Detect feat tracks by track_name markers and group by artist
    af = artist_frame.copy()
    af["_has_feat"] = (
        af["track_name"].apply(_has_feat_marker) if "track_name" in af.columns else False
    )
    feat_plays = af[af["_has_feat"]]
    if feat_plays.empty:
        return pd.DataFrame()

    top_artists = feat_plays.groupby("artist_name").size().reset_index(name="count")
    top_artists = top_artists.sort_values("count", ascending=False).head(TOP_RECORD_LIMIT)
    top_artists["rank"] = range(1, len(top_artists) + 1)
    top_artists["name"] = top_artists["artist_name"]
    top_artists["value"] = top_artists["count"].astype(float)
    top_artists["unit"] = "次合作曲播放"
    return top_artists
