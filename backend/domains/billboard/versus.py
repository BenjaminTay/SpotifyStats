"""Billboard entity versus comparison endpoints."""

import pandas as pd

from backend.core.db import get_db
from backend.domains.billboard.chart_compute import compute_billboard_data


def _get_ps_rank(power_scores_df, key_col, key_val, artist_val=None):
    """Look up power score and rank for an entity in a power_scores DataFrame."""
    if power_scores_df is None or len(power_scores_df) == 0:
        return None, None
    ps = power_scores_df.sort_values("power_score", ascending=False).reset_index(drop=True)
    if artist_val is not None:
        mask = (ps[key_col] == key_val) & (ps["artist_name"] == artist_val)
    else:
        mask = ps[key_col] == key_val
    match = ps[mask]
    if len(match) == 0:
        return None, None
    idx = int(match.index[0])
    return int(match.iloc[0]["power_score"]), idx + 1


def _resolve_album_members_vs(album_name, artist_name):
    """Resolve all member album names in a release group."""
    conn = get_db()
    row = conn.execute(
        """SELECT a.album_name FROM release_group_members rgm
           JOIN release_groups rg ON rg.group_id = rgm.group_id
           JOIN albums a ON a.album_id = rgm.album_id
           JOIN artists ar ON a.artist_id = ar.artist_id
           WHERE rg.canonical_name = ? AND ar.artist_name = ?
           UNION SELECT ?""",
        (album_name, artist_name, album_name),
    ).fetchall()
    conn.close()
    if row:
        return [r["album_name"] for r in row]
    return [album_name]


def get_versus_track(
    tid_a,
    tid_b,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare two tracks side-by-side."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    power_scores = pd.DataFrame(data["power_scores"])

    def _track_data(tid):
        grp = weekly[weekly["track_id"] == tid].sort_values("billboard_week")
        if grp.empty:
            return None
        ps_val, ps_rank = _get_ps_rank(power_scores, "track_id", tid)
        return {
            "name": f"{grp['track_name'].iloc[0]} — {grp['artist_name'].iloc[0]}",
            "track_name": str(grp["track_name"].iloc[0]),
            "artist_name": str(grp["artist_name"].iloc[0]),
            "rank_history": [
                {
                    "week": str(r["billboard_week"]),
                    "rank": int(r["rank"]),
                    "play_count": int(r["play_count"]),
                }
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": ps_val,
                "power_rank": ps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "top5_weeks": int((grp["rank"] <= 5).sum()),
                "total_chart_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _track_data(tid_a)
    result_b = _track_data(tid_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一首歌在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b}


def get_versus_album(
    aname_a,
    aart_a,
    aname_b,
    aart_b,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare two albums side-by-side."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])

    def _album_data(aname, aart):
        grp = weekly_album[
            (weekly_album["album_name"] == aname) & (weekly_album["artist_name"] == aart)
        ].sort_values("billboard_week")
        if grp.empty:
            return None
        aps_val, aps_rank = _get_ps_rank(album_power_scores, "album_name", aname, aart)

        # Track-level stats via release group members
        member_names = _resolve_album_members_vs(aname, aart)
        album_tracks = weekly[weekly["album_name"].isin(member_names)]
        num_tracks = int(album_tracks["track_id"].nunique())
        num_no1_tracks = int(album_tracks[album_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_weeks = int((album_tracks["rank"] == 1).sum())

        # Sum of track power scores
        album_track_ids = album_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(
                track_power_scores[track_power_scores["track_id"].isin(album_track_ids)][
                    "power_score"
                ].sum()
            )

        return {
            "name": f"{aname} — {aart}",
            "album_name": aname,
            "artist_name": aart,
            "rank_history": [
                {
                    "week": str(r["billboard_week"]),
                    "rank": int(r["rank"]),
                    "play_count": int(r["play_count"]),
                }
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": aps_val,
                "power_rank": aps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "num_tracks": num_tracks,
                "num_no1_tracks": num_no1_tracks,
                "total_no1_track_weeks": total_no1_weeks,
                "track_power_sum": track_ps_sum,
                "total_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _album_data(aname_a, aart_a)
    result_b = _album_data(aname_b, aart_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一张专辑在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b}


def get_versus_artist(
    sel_a,
    sel_b,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare two artists side-by-side."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    artist_power_scores = pd.DataFrame(data["artist_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])

    def _artist_data(artist_name):
        grp = weekly_artist[weekly_artist["artist_name"] == artist_name].sort_values(
            "billboard_week"
        )
        if grp.empty:
            return None
        aps_val, aps_rank = _get_ps_rank(artist_power_scores, "artist_name", artist_name)

        # Track-level stats
        artist_tracks = weekly[weekly["artist_name"] == artist_name]
        num_tracks = int(artist_tracks["track_id"].nunique())
        num_no1_tracks = int(artist_tracks[artist_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_track_weeks = int((artist_tracks["rank"] == 1).sum())

        # Sum of track power scores
        artist_track_ids = artist_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(
                track_power_scores[track_power_scores["track_id"].isin(artist_track_ids)][
                    "power_score"
                ].sum()
            )

        # Album-level stats
        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        num_albums = int(artist_albums["album_name"].dropna().nunique())
        num_no1_albums = int(artist_albums[artist_albums["rank"] == 1]["album_name"].nunique())
        total_no1_album_weeks = int((artist_albums["rank"] == 1).sum())

        # Sum of album power scores
        album_ps_sum = 0
        if album_power_scores is not None and len(album_power_scores) > 0:
            album_ps_sum = int(
                album_power_scores[album_power_scores["artist_name"] == artist_name][
                    "power_score"
                ].sum()
            )

        return {
            "name": artist_name,
            "rank_history": [
                {
                    "week": str(r["billboard_week"]),
                    "rank": int(r["rank"]),
                    "play_count": int(r["play_count"]),
                }
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": aps_val,
                "power_rank": aps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "num_tracks": num_tracks,
                "num_no1_tracks": num_no1_tracks,
                "total_no1_track_weeks": total_no1_track_weeks,
                "track_power_sum": track_ps_sum,
                "num_albums": num_albums,
                "num_no1_albums": num_no1_albums,
                "total_no1_album_weeks": total_no1_album_weeks,
                "album_power_sum": album_ps_sum,
                "total_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _artist_data(sel_a)
    result_b = _artist_data(sel_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一位艺人在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b}
