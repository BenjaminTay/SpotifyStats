"""探索發現：新歌、多樣性、專輯完成度（P1 section）。"""

from __future__ import annotations

import json
import re
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
    best["unit"] = {
        "track": "首新歌",
        "album": "张新专辑",
        "artist": "位新艺人",
    }.get(entity_type, "个新发现")
    best["date"] = best["first_date"].astype(str)
    return best


def _same_name_diff_artist(track_frame, conn: sqlite3.Connection | None = None):
    """同名異曲，返回完整艺人列表及与其对齐的头像列表。"""
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
    artist_cover_map: dict[str, str | None] = {}
    if conn is not None:
        try:
            artist_rows = conn.execute(
                """SELECT artist_id, artist_name, image_path, image_url FROM artists"""
            ).fetchall()
            artist_cover_map = {
                str(row["artist_name"]): (
                    f"/covers/artists/{int(row['artist_id'])}.jpg"
                    if row["image_path"] or row["image_url"]
                    else None
                )
                for row in artist_rows
            }
        except Exception:
            artist_cover_map = {}

    rows: list[dict[str, object]] = []
    for _, sn in same_name.iterrows():
        artist_counts = (
            track_frame[track_frame["track_name"] == sn["track_name"]]
            .groupby("artist_name")
            .size()
            .sort_values(ascending=False)
        )
        artists = [str(name) for name in artist_counts.index]
        play_counts = [int(count) for count in artist_counts.tolist()]
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": sn["track_name"],
                "value": float(sn["artist_count"]),
                "unit": "位不同藝人",
                "artist_names": artists,
                "artist_cover_urls": [artist_cover_map.get(name) for name in artists],
                "artist_play_counts": play_counts,
                "caption": "、".join(artists),
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
    merge_level: int = 2,
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

    records["discovery_same_name_diff_artist"] = _same_name_diff_artist(track_frame, conn)
    # Use album_frame (has album_project_id/name for L2/L3) for album completionist
    completion_frame = album_frame if not album_frame.empty else event_frame
    records["discovery_album_completionist"] = (
        _album_full_replays(completion_frame, conn, merge_level=merge_level)
        if conn
        else pd.DataFrame()
    )
    records["discovery_feat_lover_track"] = (
        _feat_lover_track(event_frame) if not event_frame.empty else pd.DataFrame()
    )
    records["discovery_feat_lover_album"] = (
        _feat_lover_album(album_frame) if not album_frame.empty else pd.DataFrame()
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


def _album_full_replays(frame, conn, merge_level=2):
    """Rank albums by complete replay rounds.

    A complete replay round is one play of every canonical song in a project.
    Therefore the replay count is the minimum per-song play count. Albums only
    participate when their complete canonical membership (L2/L3) or a reliable
    Spotify total (L1 fallback) is available and every expected song was heard.
    """
    if frame.empty or conn is None:
        return pd.DataFrame()

    # Use album project columns for L2/L3, fall back to album_name
    album_id_col = "album_project_id" if "album_project_id" in frame.columns else "album_name"
    album_name_col = "album_project_name" if "album_project_name" in frame.columns else "album_name"

    song_col = "canonical_song_key" if "canonical_song_key" in frame.columns else "track_id"

    song_group_cols = list(dict.fromkeys([album_id_col, album_name_col, "artist_name", song_col]))
    per_song = frame.groupby(song_group_cols, dropna=False).size().reset_index(name="song_plays")
    if per_song.empty:
        return pd.DataFrame()

    results = []
    group_cols = list(dict.fromkeys([album_id_col, album_name_col, "artist_name"]))
    for keys, songs in per_song.groupby(group_cols, dropna=False):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        group_values = dict(zip(group_cols, key_values))
        album_id = group_values[album_id_col]
        album_name = group_values[album_name_col]
        artist_name = group_values["artist_name"]
        album_name = str(album_name)
        artist_name = str(artist_name)
        total_plays = int(songs["song_plays"].sum())
        total = None
        replay_songs = songs
        is_numeric_project = False
        if album_id_col == "album_project_id":
            try:
                project_id = int(float(album_id))
                is_numeric_project = True
                original = _get_album_project_original_membership(conn, project_id, merge_level)
                if original is None:
                    continue
                original_song_keys, total = original
                replay_songs = songs[songs[song_col].astype(str).isin(original_song_keys)]
            except (TypeError, ValueError, OverflowError):
                total = None
        if not total and not is_numeric_project:
            total = _get_album_total_tracks(conn, album_name, artist_name)

        observed = int(replay_songs[song_col].nunique())
        # Unknown totals and incomplete coverage cannot produce a complete round.
        if not total or total < 2 or observed != int(total):
            continue
        full_replays = int(replay_songs["song_plays"].min())
        if full_replays <= 0:
            continue

        results.append(
            {
                "name": album_name,
                "artist_name": artist_name,
                "user_track_count": observed,
                "total_tracks": int(total),
                "total_plays": total_plays,
                "full_replays": full_replays,
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values(
        ["full_replays", "total_plays", "user_track_count"],
        ascending=[False, False, False],
    ).head(TOP_RECORD_LIMIT)
    df["rank"] = range(1, len(df) + 1)
    df["entity_type"] = "album"
    df["value"] = df["full_replays"].astype(float)
    df["unit"] = "次完整回放"
    df["secondary_value"] = df["user_track_count"].astype(float)
    df["secondary_unit"] = df["total_tracks"].apply(lambda total: f"/ {int(total)} 首")
    df["caption"] = df["total_plays"].apply(lambda plays: f"总播放 {int(plays)} 次")
    return df


# Backward-compatible private alias for existing callers and API contract tests.
_album_completionist = _album_full_replays


def _get_album_project_original_membership(conn, project_id, merge_level=2):
    """Return trusted original-edition song keys and its Spotify track total.

    A project is eligible only when its declared primary album is also
    explicitly classified as ``original_album``. This alignment is the safety
    boundary: we never infer the original by release order, title length, or an
    arbitrary project member. The local original membership must also match one
    unambiguous Spotify ``total_tracks`` value, otherwise the project is
    conservatively excluded from complete-replay ranking.
    """
    try:
        project = conn.execute(
            """SELECT ap.primary_album_id, ap.canonical_name, ap.release_date,
                      al.album_name, ar.artist_name
               FROM album_projects ap
               JOIN album_project_albums apa
                 ON apa.project_id = ap.project_id
                AND apa.album_id = ap.primary_album_id
               JOIN albums al ON al.album_id = ap.primary_album_id
               LEFT JOIN artists ar ON ar.artist_id = ap.artist_id
               WHERE ap.project_id = ?
                 AND apa.role = 'primary'
                 AND apa.source_bucket = 'original_album'""",
            (project_id,),
        ).fetchone()
        if not project or project["primary_album_id"] is None:
            return None
        primary_album_id = int(project["primary_album_id"])

        track_rows = conn.execute(
            """SELECT DISTINCT track_id
               FROM album_project_tracks
               WHERE project_id = ?
                 AND source_album_id = ?
                 AND membership_role = 'standard'
                 AND min_merge_level <= ?
               ORDER BY track_id""",
            (project_id, primary_album_id, merge_level),
        ).fetchall()
        track_ids = [int(row["track_id"]) for row in track_rows]
        if not track_ids:
            return None

        from backend.domains.playback.album_projects import apply_canonical_song_keys

        def normalized(value):
            return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

        expected_titles = {
            normalized(project["canonical_name"]),
            normalized(project["album_name"]),
        }
        expected_titles.discard("")
        expected_artist = normalized(project["artist_name"])
        expected_date = project["release_date"]

        local_rows = conn.execute(
            f"""SELECT t.track_id, t.spotify_track_id
                FROM tracks t
                WHERE t.track_id IN ({",".join("?" for _ in track_ids)})""",
            track_ids,
        ).fetchall()
        local_spotify_to_track = {
            str(row["spotify_track_id"]): int(row["track_id"])
            for row in local_rows
            if row["spotify_track_id"]
        }
        if not local_spotify_to_track:
            return None

        candidates = conn.execute(
            """SELECT REPLACE(sam.spotify_album_id, 'spotify:album:', '') AS spotify_album_id,
                      sam.album_name, sam.album_artists, sam.release_date,
                      sam.total_tracks, sam.track_list,
                      MAX(COALESCE(asl.confidence, 0)) AS confidence,
                      SUM(COALESCE(asl.play_count, 0)) AS play_count,
                      MAX(COALESCE(asl.track_count, 0)) AS linked_track_count
               FROM album_spotify_links asl
               JOIN spotify_album_meta sam
                 ON REPLACE(sam.spotify_album_id, 'spotify:album:', '') =
                    REPLACE(asl.spotify_album_id, 'spotify:album:', '')
               WHERE asl.album_id = ?
                 AND LOWER(COALESCE(sam.album_type, '')) = 'album'
               GROUP BY REPLACE(sam.spotify_album_id, 'spotify:album:', '')""",
            (primary_album_id,),
        ).fetchall()

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

            selected_track_ids = [local_spotify_to_track[value] for value in spotify_track_ids]
            keyed = apply_canonical_song_keys(
                pd.DataFrame({"track_id": selected_track_ids}), conn, merge_level
            )
            song_keys = {str(value) for value in keyed["canonical_song_key"].dropna().tolist()}
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
                 AND LOWER(COALESCE(sam.album_type, '')) = 'album'
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
    top_artists["unit"] = "次"
    return top_artists


def _feat_lover_album(album_frame):
    """合作曲偏好：含合作歌曲播放的专辑排行。"""
    if album_frame.empty or "track_name" not in album_frame.columns:
        return pd.DataFrame()

    af = album_frame.copy()
    af["_has_feat"] = af["track_name"].apply(_has_feat_marker)
    feat_plays = af[af["_has_feat"]]
    if feat_plays.empty:
        return pd.DataFrame()

    album_id_col = "album_project_id" if "album_project_id" in feat_plays.columns else "album_name"
    album_name_col = (
        "album_project_name" if "album_project_name" in feat_plays.columns else "album_name"
    )
    group_cols = list(dict.fromkeys([album_id_col, album_name_col, "artist_name"]))
    result = feat_plays.groupby(group_cols, dropna=False).size().reset_index(name="count")
    result = result.sort_values("count", ascending=False).head(TOP_RECORD_LIMIT).copy()
    result["rank"] = range(1, len(result) + 1)
    result["entity_type"] = "album"
    result["entity_id"] = result[album_id_col].astype(str)
    result["name"] = result[album_name_col].astype(str)
    result["value"] = result["count"].astype(float)
    result["unit"] = "次"
    return result
