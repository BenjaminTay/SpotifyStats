"""探索發現：新歌、多樣性、專輯完成度（P1 section）。"""

from __future__ import annotations

import re
import sqlite3

import pandas as pd

from backend.domains.playback.records_helpers import (
    TOP_RECORD_LIMIT,
    grouped_records_duration,
    safe_groupby_cols,
    unique_cols,
)
from backend.domains.playback.records_sorting import sort_and_limit


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


def _discovery_day(
    frame,
    group_col,
    name_col,
    artist_col,
    entity_type,
    *,
    target_year: int | None = None,
):
    """Return daily first-seen counts at the identity grain of ``frame``.

    Passing a complete history frame plus ``target_year`` yields genuine
    personal discoveries in that year.  Passing an already sliced frame keeps
    the standalone Playback Records period semantics.
    """
    if frame.empty:
        return pd.DataFrame()
    gb_cols = (
        [group_col]
        if target_year is not None and group_col in frame.columns
        else safe_groupby_cols([], group_col, name_col, artist_col)
    )
    first_seen = frame.groupby(gb_cols)["ts_date"].min().reset_index(name="first_date")
    if target_year is not None:
        first_dates = pd.to_datetime(first_seen["first_date"], errors="coerce")
        first_seen = first_seen[first_dates.dt.year == target_year]
        if first_seen.empty:
            return pd.DataFrame()
    new_per_day = first_seen.groupby("first_date").size().reset_index(name="new_count")
    best = (
        new_per_day.sort_values(["new_count", "first_date"], ascending=[False, True], kind="stable")
        .head(TOP_RECORD_LIMIT)
        .copy()
    )
    best["rank"] = best["new_count"].rank(method="min", ascending=False).astype(int)
    best["name"] = best["first_date"].astype(str)
    best["value"] = best["new_count"].astype(float)
    best["unit"] = {
        "track": "首新歌",
        "album": "张新专辑",
        "artist": "位新艺人",
    }.get(entity_type, "个新发现")
    best["date"] = best["first_date"].astype(str)
    best["entity_type"] = entity_type
    best["rank_basis"] = f"new_{entity_type}s"
    best["is_top"] = best["rank"].eq(1)
    best["is_tied_top"] = best["rank"].eq(1) & bool(best["rank"].eq(1).sum() > 1)
    best["scope"] = "lifetime_first_seen" if target_year is not None else "annual_first_seen"
    return best


def _same_name_diff_artist(track_frame, conn: sqlite3.Connection | None = None):
    """同名異曲，返回完整艺人列表及与其对齐的头像列表。"""
    if track_frame.empty:
        return pd.DataFrame()
    same_name = track_frame.groupby("track_name").agg(
        artist_count=("artist_name", "nunique"),
    )
    if "play_id" in track_frame.columns:
        same_name["total_plays"] = track_frame.groupby("track_name")["play_id"].count()
    else:
        same_name["total_plays"] = track_frame.groupby("track_name").size()
    same_name = same_name.reset_index()
    same_name = same_name[same_name["artist_count"] >= 2].copy()
    same_name["_normalized_name"] = same_name["track_name"].astype(str).str.strip().str.casefold()
    same_name = sort_and_limit(
        same_name,
        ["artist_count", "total_plays", "_normalized_name", "track_name"],
        [False, False, True, True],
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

    duration_rows = grouped_records_duration(track_frame, ["track_name", "artist_name"])
    rows: list[dict[str, object]] = []
    for _, sn in same_name.iterrows():
        versions = track_frame[track_frame["track_name"] == sn["track_name"]]
        artist_counts = versions.groupby("artist_name").size().reset_index(name="plays")
        durations = duration_rows[duration_rows["track_name"] == sn["track_name"]].set_index(
            "artist_name"
        )["total_ms"]
        artist_counts["total_ms"] = artist_counts["artist_name"].map(durations).fillna(0)
        artist_counts = artist_counts.sort_values(
            ["plays", "total_ms", "artist_name"],
            ascending=[False, False, True],
            kind="stable",
        )
        artists = [str(name) for name in artist_counts["artist_name"].tolist()]
        play_counts = [int(count) for count in artist_counts["plays"].tolist()]
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
    sequence_columns = ["ts"]
    if "play_id" in frame.columns:
        sequence_columns.append("play_id")
    sequence = (
        frame[unique_cols(*sequence_columns, group_col)]
        .sort_values(sequence_columns, kind="stable")[group_col]
        .astype(str)
    )
    seen = set()
    run_length = 0
    max_run = 0
    for eid in sequence:
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

    working = frame.copy(deep=False)
    if "play_id" not in working.columns:
        working["_play_marker"] = 1
        play_column = "_play_marker"
    else:
        play_column = "play_id"
    song_group_cols = list(dict.fromkeys([album_id_col, album_name_col, "artist_name", song_col]))
    per_song = (
        working.groupby(song_group_cols, dropna=False)
        .agg(song_plays=(play_column, "count"))
        .reset_index()
    )
    if per_song.empty:
        return pd.DataFrame()

    from backend.domains.playback.records_album_facts import load_original_memberships

    original_memberships = (
        load_original_memberships(conn, merge_level) if album_id_col == "album_project_id" else {}
    )
    album_totals = _load_album_total_tracks(conn)
    results = []
    group_cols = list(dict.fromkeys([album_id_col, album_name_col, "artist_name"]))
    duration_totals = grouped_records_duration(frame, group_cols)
    duration_map = {
        tuple(str(row[column]) for column in group_cols): float(row["total_ms"])
        for _, row in duration_totals.iterrows()
    }
    for keys, songs in per_song.groupby(group_cols, dropna=False):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        group_values = dict(zip(group_cols, key_values))
        album_id = group_values[album_id_col]
        album_name = group_values[album_name_col]
        artist_name = group_values["artist_name"]
        album_name = str(album_name)
        artist_name = str(artist_name)
        total_plays = int(songs["song_plays"].sum())
        duration_key = tuple(str(group_values[column]) for column in group_cols)
        total_ms = duration_map.get(duration_key, 0.0)
        total = None
        replay_songs = songs
        is_numeric_project = False
        if album_id_col == "album_project_id":
            try:
                project_id = int(float(album_id))
                is_numeric_project = True
                original = original_memberships.get(project_id)
                if original is None:
                    continue
                original_song_keys, total = original
                replay_songs = songs[songs[song_col].astype(str).isin(original_song_keys)]
            except (TypeError, ValueError, OverflowError):
                total = None
        if not total and not is_numeric_project:
            total = album_totals.get((album_name, artist_name))

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
                "total_ms": total_ms,
                "full_replays": full_replays,
                "entity_id": str(album_id),
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = sort_and_limit(
        df,
        ["full_replays", "total_plays", "total_ms", "entity_id"],
        [False, False, False, True],
    )
    df["entity_type"] = "album"
    df["value"] = df["full_replays"].astype(float)
    df["unit"] = "次完整回放"
    df["secondary_value"] = df["user_track_count"].astype(float)
    df["secondary_unit"] = df["total_tracks"].apply(lambda total: f"/ {int(total)} 首")
    df["total_hours"] = (df["total_ms"] / 3_600_000).round(1)
    df["caption"] = df["total_plays"].apply(lambda plays: f"总播放 {int(plays)} 次")
    return df


# Backward-compatible private alias for existing callers and API contract tests.
_album_completionist = _album_full_replays


def _get_album_project_original_membership(conn, project_id, merge_level=2):
    from backend.domains.playback.records_album_facts import load_original_memberships

    return load_original_memberships(conn, merge_level).get(project_id)


def _load_album_total_tracks(conn):
    """One statement; retain each legacy LIMIT 1 lookup's exact selection."""
    try:
        rows = conn.execute(
            """SELECT names.album_name, names.artist_name, (SELECT sam.total_tracks
               FROM albums al
               JOIN artists a ON al.artist_id = a.artist_id
               LEFT JOIN tracks t ON t.album_id = al.album_id
               LEFT JOIN spotify_track_meta stm ON t.spotify_track_id = stm.spotify_track_id
               LEFT JOIN spotify_album_meta sam
                 ON stm.spotify_album_id = sam.spotify_album_id
                 OR 'spotify:album:' || stm.spotify_album_id = sam.spotify_album_id
               WHERE al.album_name = names.album_name AND a.artist_name = names.artist_name
                 AND sam.total_tracks IS NOT NULL
                 AND LOWER(COALESCE(sam.album_type, '')) = 'album'
               LIMIT 1) AS total_tracks FROM (SELECT DISTINCT al.album_name, a.artist_name FROM albums al JOIN artists a ON a.artist_id=al.artist_id
                 WHERE al.album_name IS NOT NULL AND a.artist_name IS NOT NULL) names"""
        ).fetchall()
        return {
            (str(row["album_name"]), str(row["artist_name"])): row["total_tracks"] for row in rows
        }
    except Exception:
        return {}


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

    ef = event_frame.copy(deep=False)
    event_names = ef["track_name"].unique()
    ef["_has_feat"] = ef["track_name"].map({name: _has_feat_marker(name) for name in event_names})
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
        ef[ef["_has_feat"]]
        .groupby(["track_name", "artist_name"])
        .agg(count=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    top_feat = sort_and_limit(
        feat_tracks,
        ["count", "total_ms", "track_name", "artist_name"],
        [False, False, True, True],
    )

    rows = []
    for _, row in top_feat.iterrows():
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": row["track_name"],
                "artist_name": row["artist_name"],
                "value": float(row["count"]),
                "unit": "次",
                "total_ms": float(row["total_ms"]),
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
    if "role" not in artist_frame.columns:
        # A role-less fan-out frame cannot distinguish the primary artist from
        # the collaborator; fail closed instead of publishing a contaminated
        # collaborator ranking.
        return pd.DataFrame()

    # Detect feat tracks by track_name markers and group by artist
    af = artist_frame.copy(deep=False)
    event_names = af["track_name"].unique() if "track_name" in af.columns else []
    af["_has_feat"] = (
        af["track_name"].map({name: _has_feat_marker(name) for name in event_names})
        if "track_name" in af.columns
        else False
    )
    feat_plays = af[af["_has_feat"] & af["role"].eq("featured")]
    if feat_plays.empty:
        return pd.DataFrame()

    top_artists = (
        feat_plays.groupby("artist_name")
        .agg(count=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    top_artists = sort_and_limit(
        top_artists,
        ["count", "total_ms", "artist_name"],
        [False, False, True],
    )
    top_artists["name"] = top_artists["artist_name"]
    top_artists["value"] = top_artists["count"].astype(float)
    top_artists["unit"] = "次"
    top_artists["total_hours"] = (top_artists["total_ms"] / 3_600_000).round(1)
    return top_artists


def _feat_lover_album(album_frame):
    """合作曲偏好：含合作歌曲播放的专辑排行。"""
    if album_frame.empty or "track_name" not in album_frame.columns:
        return pd.DataFrame()

    af = album_frame.copy(deep=False)
    event_names = af["track_name"].unique() if "track_name" in af.columns else []
    af["_has_feat"] = af["track_name"].map({name: _has_feat_marker(name) for name in event_names})
    feat_plays = af[af["_has_feat"]]
    if feat_plays.empty:
        return pd.DataFrame()

    album_id_col = "album_project_id" if "album_project_id" in feat_plays.columns else "album_name"
    album_name_col = (
        "album_project_name" if "album_project_name" in feat_plays.columns else "album_name"
    )
    group_cols = list(dict.fromkeys([album_id_col, album_name_col, "artist_name"]))
    result = (
        feat_plays.groupby(group_cols, dropna=False)
        .agg(count=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    result = sort_and_limit(
        result,
        ["count", "total_ms", album_name_col, album_id_col],
        [False, False, True, True],
    )
    result["entity_type"] = "album"
    result["entity_id"] = result[album_id_col].astype(str)
    result["name"] = result[album_name_col].astype(str)
    result["value"] = result["count"].astype(float)
    result["unit"] = "次"
    result["total_hours"] = (result["total_ms"] / 3_600_000).round(1)
    return result
