"""Shared play-data loading and aggregation service.

All play-history endpoints use this service for data loading and groupby operations.
Replaces the st.cache_data pattern from Streamlit with lru_cache for computation results.
"""

import sqlite3
from functools import lru_cache
from typing import Optional, Any

import pandas as pd
import numpy as np

from backend.core.db import get_db, base_filters, load_plays
from backend.core.json_helpers import py_val as _py


def _hour(x):
    """Sum hours from ms_played series."""
    return float(x.sum() / 3_600_000)


def _count(x):
    return int(x.count())


# ── Dashboard ──────────────────────────────────────────────────────────────

def get_dashboard_summary(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    df: Optional[pd.DataFrame] = None,
) -> dict:
    """Compute dashboard KPIs from plays data."""
    if df is None:
        df = load_plays(
            conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
        )
    if df.empty:
        return {
            "total_plays": 0, "total_hours": 0.0, "total_tracks": 0,
            "total_artists": 0, "total_albums": 0, "total_days": 0,
            "avg_daily_hours": 0.0,
        }
    total_plays = int(len(df))
    total_hours = float(df["ms_played"].sum() / 3_600_000)
    total_tracks = int(df["track_id"].nunique())
    total_artists = int(df["artist_name"].dropna().nunique())
    total_albums = int(df["album_name"].dropna().nunique())
    total_days = int(df["ts_date"].nunique())
    avg_daily_hours = float(total_hours / total_days) if total_days > 0 else 0.0
    return {
        "total_plays": total_plays, "total_hours": round(total_hours, 1),
        "total_tracks": total_tracks, "total_artists": total_artists,
        "total_albums": total_albums, "total_days": total_days,
        "avg_daily_hours": round(avg_daily_hours, 1),
    }


def get_account_kpis(conn: sqlite3.Connection) -> Optional[dict]:
    """Get account data KPIs if account data has been imported."""
    try:
        sc = conn.execute("SELECT COUNT(*) FROM search_queries").fetchone()[0]
        if sc == 0:
            return None
        stc = conn.execute("SELECT COUNT(*) FROM saved_tracks").fetchone()[0]
        plc = conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        video_count = conn.execute(
            "SELECT COUNT(*) FROM plays WHERE content_type='video'"
        ).fetchone()[0]
        return {
            "saved_tracks": stc, "playlists": plc,
            "search_queries": sc, "video_plays": video_count,
        }
    except Exception:
        return None


def get_monthly_trend(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    df: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Get monthly plays/hours trend."""
    if df is None:
        df = load_plays(
            conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
        )
    if df.empty:
        return []
    monthly = (
        df.groupby(["ts_year", "ts_month"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .reset_index()
    )
    monthly["period"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)
    monthly = monthly.sort_values("period")
    return [
        {"period": r.period, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
        for r in monthly.itertuples(index=False)
    ]


def get_hourly_dist(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    df: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Get hourly play count distribution."""
    if df is None:
        df = load_plays(
            conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
        )
    if df.empty:
        return []
    hourly = df.groupby("ts_hour").size().reset_index(name="count")
    hourly = hourly.sort_values("ts_hour")
    return [
        {"hour": int(r.ts_hour), "count": int(r.count)}
        for r in hourly.itertuples(index=False)
    ]


def get_top_tracks(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    n: int = 10, df: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Get top N most-played tracks."""
    if df is None:
        df = load_plays(
            conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
        )
    if df.empty:
        return []
    top = (
        df.groupby(["track_name", "artist_name"])
        .size()
        .sort_values(ascending=False)
        .head(n)
        .reset_index(name="plays")
    )
    return [
        {"track_name": r.track_name, "artist_name": r.artist_name, "plays": int(r.plays)}
        for r in top.itertuples(index=False)
    ]


def get_platform_dist(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    df: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Get platform distribution."""
    if df is None:
        df = load_plays(
            conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
        )
    if df.empty:
        return []
    dist = df["platform"].value_counts().reset_index()
    dist.columns = ["platform", "cnt"]
    return [{"platform": r.platform, "count": int(r.cnt)} for r in dist.itertuples(index=False)]


def get_dow_dist(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    df: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Get day-of-week distribution."""
    dow_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    if df is None:
        df = load_plays(
            conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
        )
    if df.empty:
        return []
    counts = df["ts_dow"].value_counts().sort_index()
    return [{"day": dow_names.get(d, str(d)), "count": int(counts.get(d, 0))} for d in range(7)]


def get_random_track(conn: sqlite3.Connection, min_ms: int, music_only: bool) -> Optional[dict]:
    """Get a random track for nostalgic recommendation."""
    f, fp = base_filters(min_ms=min_ms, music_only=music_only)
    w = f"WHERE {f}" if f else ""
    row = conn.execute(
        f"""SELECT t.track_name, a.artist_name, al.album_name,
                   MAX(p.ts_date) as last_played, COUNT(*) as total_plays
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            {w}
            GROUP BY p.track_id
            ORDER BY RANDOM() LIMIT 1""",
        fp,
    ).fetchone()
    if not row:
        return None
    return {
        "track_name": row["track_name"],
        "artist_name": row["artist_name"],
        "album_name": row["album_name"],
        "last_played": row["last_played"],
        "total_plays": int(row["total_plays"]),
    }


# ── Timeline ───────────────────────────────────────────────────────────────

def get_annual_timeline(conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool) -> list[dict]:
    """Annual breakdown: plays, hours, unique tracks/artists, and top track per year."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return []

    def _top_track_year(grp):
        top = grp.groupby(["track_name", "artist_name"]).size()
        if top.empty:
            return pd.Series({"top_track": "", "top_artist": ""})
        idx = top.idxmax()
        return pd.Series({"top_track": idx[0], "top_artist": idx[1]})

    annual = (
        df.groupby("ts_year")
        .agg(
            plays=("play_id", "count"),
            hours=("ms_played", _hour),
            unique_tracks=("track_id", "nunique"),
            unique_artists=("artist_name", "nunique"),
        )
        .reset_index()
    )
    tops = df.groupby("ts_year").apply(_top_track_year).reset_index()
    annual = annual.merge(tops, on="ts_year", how="left")
    annual = annual.sort_values("ts_year")
    return [
        {
            "year": int(r.ts_year), "plays": int(r.plays),
            "hours": round(float(r.hours), 1), "unique_tracks": int(r.unique_tracks),
            "unique_artists": int(r.unique_artists),
            "top_track": r.top_track or "",
            "top_artist": r.top_artist or "",
        }
        for r in annual.itertuples(index=False)
    ]


def get_monthly_timeline_drilldown(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    period: Optional[str] = None,
) -> dict:
    """Monthly timeline with optional top-5 drilldown for a specific period."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return {"months": [], "drilldown": None}

    monthly = (
        df.groupby(["ts_year", "ts_month"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .reset_index()
    )
    monthly["period"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)
    monthly = monthly.sort_values("period")

    result = {
        "months": [
            {"period": r.period, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in monthly.itertuples(index=False)
        ],
        "drilldown": None,
    }

    if period:
        try:
            year, month = period.split("-")
            mask = (df["ts_year"] == int(year)) & (df["ts_month"] == int(month))
            month_df = df[mask]
            if not month_df.empty:
                top5 = (
                    month_df.groupby(["track_name", "artist_name"])
                    .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
                    .sort_values("plays", ascending=False)
                    .head(5)
                    .reset_index()
                )
                result["drilldown"] = [
                    {"track_name": r.track_name, "artist_name": r.artist_name,
                     "plays": int(r.plays), "hours": round(float(r.hours), 1)}
                    for r in top5.itertuples(index=False)
                ]
        except (ValueError, TypeError):
            pass
    return result


def get_weekly_timeline(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    week_label: Optional[str] = None,
) -> dict:
    """Weekly timeline with optional top-5 drilldown for a specific week."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return {"weeks": [], "drilldown": None}

    weekly = (
        df.groupby(["ts_year", "ts_week"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .reset_index()
    )
    weekly["label"] = weekly["ts_year"].astype(str) + "-W" + weekly["ts_week"].astype(str).str.zfill(2)

    result = {
        "weeks": [
            {"label": r.label, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in weekly.sort_values(["ts_year", "ts_week"]).itertuples(index=False)
        ],
        "drilldown": None,
    }

    if week_label:
        try:
            yr, wk = week_label.split("-W")
            yr, wk = int(yr), int(wk)
            week_df = df[(df["ts_year"] == yr) & (df["ts_week"] == wk)]
            if not week_df.empty:
                top5 = (
                    week_df.groupby(["track_name", "artist_name"])
                    .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
                    .sort_values("plays", ascending=False)
                    .head(5)
                    .reset_index()
                )
                result["drilldown"] = [
                    {"track_name": r.track_name, "artist_name": r.artist_name,
                     "plays": int(r.plays), "hours": round(float(r.hours), 1)}
                    for r in top5.itertuples(index=False)
                ]
        except (ValueError, TypeError):
            pass
    return result


# ── Leaderboard ─────────────────────────────────────────────────────────────

def get_leaderboard(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    entity: str = "track", time_range: str = "all",
    year: Optional[int] = None, month: Optional[str] = None,
    metric: str = "plays", top_n: int = 30,
) -> dict:
    """Get top-N leaderboard for tracks/artists/albums."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return {"time_label": "", "total_records": 0, "rows": []}

    # Time filter
    label_parts = []
    if time_range == "this_year" and year:
        df = df[df["ts_year"] == year]
        label_parts.append(str(year))
    elif time_range == "this_month" and month:
        try:
            y, m = month.split("-")
            df = df[(df["ts_year"] == int(y)) & (df["ts_month"] == int(m))]
            label_parts.append(month)
        except (ValueError, TypeError):
            pass
    elif time_range == "custom" and year:
        df = df[df["ts_year"] == year]
        label_parts.append(str(year))
    else:
        label_parts.append("全部时间")

    time_label = " · ".join(label_parts) if label_parts else "全部时间"

    if entity == "track":
        agg = (
            df.groupby(["track_name", "artist_name"])
            .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
            .reset_index()
        )
    elif entity == "artist":
        agg = (
            df.groupby("artist_name")
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", _hour),
                unique_tracks=("track_id", "nunique"),
            )
            .reset_index()
        )
    elif entity == "album":
        agg = (
            df.groupby(["album_name", "artist_name"])
            .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
            .reset_index()
        )
    else:
        return {"time_label": time_label, "total_records": 0, "rows": []}

    sort_col = "plays" if metric == "plays" else "hours"
    agg = agg.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)

    rows = []
    for i, r in enumerate(agg.itertuples(index=False)):
        row = {"rank": i + 1, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
        if entity == "track":
            row["track_name"] = r.track_name
            row["artist_name"] = r.artist_name
        elif entity == "artist":
            row["artist_name"] = r.artist_name
            row["unique_tracks"] = int(r.unique_tracks)
        elif entity == "album":
            row["album_name"] = r.album_name
            row["artist_name"] = r.artist_name
        rows.append(row)

    return {"time_label": time_label, "total_records": len(df), "rows": rows}


# ── Wrapped ─────────────────────────────────────────────────────────────────

def get_wrapped_data(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool, year: int,
) -> dict:
    """Generate a custom yearly wrapped report for a given year."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    year_df = df[df["ts_year"] == year]
    if year_df.empty:
        return {"year": year, "empty": True}

    total_minutes = year_df["ms_played"].sum() / 60_000
    total_plays = len(year_df)
    unique_tracks = year_df["track_id"].nunique()
    unique_artists = year_df["artist_name"].dropna().nunique()
    total_days = year_df["ts_date"].nunique()
    avg_minutes_per_day = total_minutes / total_days if total_days > 0 else 0
    avg_hours_per_day = total_minutes / 60 / max(total_days, 1)

    # Top artists
    top_artists = (
        year_df.groupby("artist_name")
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values("hours", ascending=False)
        .head(5)
        .reset_index()
    )

    # Top tracks
    top_tracks = (
        year_df.groupby(["track_name", "artist_name"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values("plays", ascending=False)
        .head(5)
        .reset_index()
    )

    # Top album
    top_album_row = (
        year_df.groupby(["album_name", "artist_name"])
        .agg(hours=("ms_played", _hour))
        .sort_values("hours", ascending=False)
        .head(1)
        .reset_index()
    )
    top_album = {"album_name": "", "artist_name": "", "hours": 0.0}
    if not top_album_row.empty:
        top_album = {
            "album_name": top_album_row.iloc[0]["album_name"] or "",
            "artist_name": top_album_row.iloc[0]["artist_name"] or "",
            "hours": round(top_album_row.iloc[0]["hours"], 1),
        }

    # Platform distribution
    platform_hours = (
        year_df.groupby("platform")["ms_played"].sum() / 3_600_000
    ).to_dict()

    # Peak hour
    peak_hour = int(year_df.groupby("ts_hour").size().idxmax()) if not year_df.empty else 0

    # First and last tracks of the year
    sorted_df = year_df.sort_values("ts")
    first_track_row = sorted_df.iloc[0]
    last_track_row = sorted_df.iloc[-1]

    # Seasonal top tracks
    season_months = {"spring": [3, 4, 5], "summer": [6, 7, 8], "autumn": [9, 10, 11], "winter": [12, 1, 2]}
    season_tops = {}
    for season, months in season_months.items():
        season_df = year_df[year_df["ts_month"].isin(months)]
        if not season_df.empty:
            top = season_df.groupby("track_name").size().sort_values(ascending=False)
            season_tops[season] = top.index[0] if len(top) > 0 else ""
        else:
            season_tops[season] = ""

    # Monthly pulse
    monthly_pulse = (
        year_df.groupby("ts_month")
        .agg(hours=("ms_played", _hour))
        .reset_index()
    )

    # Personality scoring
    unique_ratio = unique_tracks / max(total_plays, 1) * 100
    top_artist_share = (top_artists.iloc[0]["plays"] / max(total_plays, 1) * 100) if len(top_artists) > 0 else 0
    personality = {
        "explorer": {"label": "Explorer 探索者", "score": round(min(unique_ratio / 40 * 100, 100), 1), "desc": "广泛涉猎不同曲目，保持音乐品味多样化"},
        "loyalist": {"label": "Loyalist 专一者", "score": round(min(top_artist_share / 20 * 100, 100), 1), "desc": "对喜爱的艺人从一而终，深入了解他们的作品"},
        "binger": {"label": "Binger 狂听者", "score": round(min(avg_hours_per_day / 4 * 100, 100), 1), "desc": "音乐是日常必需品，每天大量时间沉浸在旋律中"},
    }
    primary_personality = max(personality.items(), key=lambda x: x[1]["score"])

    return {
        "year": year,
        "empty": False,
        "hero": {
            "total_minutes": round(total_minutes, 0),
            "total_plays": total_plays,
            "unique_tracks": unique_tracks,
            "unique_artists": unique_artists,
            "total_days": total_days,
            "avg_minutes_per_day": round(avg_minutes_per_day, 1),
        },
        "top_artists": [
            {"artist_name": r.artist_name, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in top_artists.itertuples(index=False)
        ],
        "top_tracks": [
            {"track_name": r.track_name, "artist_name": r.artist_name,
             "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in top_tracks.itertuples(index=False)
        ],
        "top_album": top_album,
        "platform_hours": {k: round(v, 1) for k, v in platform_hours.items()},
        "peak_hour": peak_hour,
        "first_track": {
            "track_name": first_track_row["track_name"],
            "artist_name": first_track_row["artist_name"],
            "date": str(first_track_row["ts_date"]),
        },
        "last_track": {
            "track_name": last_track_row["track_name"],
            "artist_name": last_track_row["artist_name"],
            "date": str(last_track_row["ts_date"]),
        },
        "season_tops": season_tops,
        "monthly_pulse": [
            {"month": int(r.ts_month), "hours": round(float(r.hours), 1)}
            for r in monthly_pulse.itertuples(index=False)
        ],
        "personality": {
            "primary": {"label": primary_personality[1]["label"], "score": primary_personality[1]["score"], "desc": primary_personality[1]["desc"]},
            "explorer": personality["explorer"],
            "loyalist": personality["loyalist"],
            "binger": personality["binger"],
        },
    }


# ── Behavior ────────────────────────────────────────────────────────────────

def get_behavior_data(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
) -> dict:
    """Playback behavior analysis (skip/forward/shuffle/platform usage)."""
    # Behavior analysis uses unfiltered data
    df = load_plays(
        conn, filtered=False, music_only=music_only,
    )

    if df.empty:
        return {
            "reason_end": [], "reason_start": [], "fwdbtn_by_hour": [],
            "most_forwarded": [], "platform_monthly": [], "platform_hourly": {"z": [], "x": [], "y": []},
            "shuffle_rate_by_platform": [], "shuffle_monthly": [],
        }

    reason_end = df["reason_end"].value_counts().reset_index()
    reason_end.columns = ["reason", "cnt"]

    reason_start = df["reason_start"].value_counts().reset_index()
    reason_start.columns = ["reason", "cnt"]

    fwdbtn = df[df["reason_end"] == "fwdbtn"]
    fwdbtn_by_hour = fwdbtn.groupby("ts_hour").size().to_dict() if not fwdbtn.empty else {}

    most_forwarded = (
        fwdbtn.groupby(["track_name", "artist_name"]).size()
        .sort_values(ascending=False).head(15).reset_index(name="cnt")
    ) if not fwdbtn.empty else pd.DataFrame(columns=["track_name", "artist_name", "cnt"])

    # Platform monthly trend
    platform_monthly = (
        df.groupby(["ts_year", "ts_month", "platform"])
        .size().reset_index(name="cnt")
    )
    platform_monthly["period"] = (
        platform_monthly["ts_year"].astype(str) + "-" + platform_monthly["ts_month"].astype(str).str.zfill(2)
    )

    # Platform x Hour heatmap data for top platforms
    top_platforms = df["platform"].value_counts().head(5).index.tolist()
    platform_hourly_pivot = df.groupby(["platform", "ts_hour"]).size().reset_index(name="cnt")
    # Return as raw data for frontend to pivot
    hrs = list(range(24))

    # Shuffle rate by platform
    shuffle_by_platform = (
        df.groupby("platform")["shuffle"].mean().mul(100).round(1).reset_index()
    )
    shuffle_by_platform.columns = ["platform", "rate"]

    # Monthly shuffle rate
    shuffle_monthly = (
        df.groupby(["ts_year", "ts_month"])["shuffle"].mean().mul(100).round(1).reset_index()
    )
    shuffle_monthly.columns = ["ts_year", "ts_month", "rate"]
    shuffle_monthly["period"] = shuffle_monthly["ts_year"].astype(str) + "-" + shuffle_monthly["ts_month"].astype(str).str.zfill(2)

    return {
        "reason_end": [{"reason": r.reason, "count": int(r.cnt)} for r in reason_end.itertuples(index=False)],
        "reason_start": [{"reason": r.reason, "count": int(r.cnt)} for r in reason_start.itertuples(index=False)],
        "fwdbtn_by_hour": [{"hour": int(h), "count": int(fwdbtn_by_hour.get(h, 0))} for h in hrs],
        "most_forwarded": [
            {"track_name": r.track_name, "artist_name": r.artist_name, "count": int(r.cnt)}
            for r in most_forwarded.itertuples(index=False)
        ],
        "platform_monthly": [
            {"period": r.period, "platform": r.platform, "count": int(r.cnt)}
            for r in platform_monthly.itertuples(index=False)
        ],
        "platform_hourly": [
            {"platform": r.platform, "hour": int(r.ts_hour), "count": int(r.cnt)}
            for r in platform_hourly_pivot.itertuples(index=False)
        ] if not platform_hourly_pivot.empty else [],
        "shuffle_rate_by_platform": [
            {"platform": r.platform, "rate": float(r.rate)}
            for r in shuffle_by_platform.itertuples(index=False)
        ],
        "shuffle_monthly": [
            {"period": r.period, "rate": float(r.rate)}
            for r in shuffle_monthly.itertuples(index=False)
        ],
    }


# ── Listening Hours ─────────────────────────────────────────────────────────

def get_listening_heatmap(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
) -> dict:
    """Day-of-week x Hour heatmap data."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return {"z": [], "x": list(range(24)), "y": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}

    dow_names_cn = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    pivot = df.groupby(["ts_dow", "ts_hour"]).size().unstack(fill_value=0)
    z = []
    y = []
    for d in range(7):
        row = [int(pivot.loc[d, h]) if d in pivot.index and h in pivot.columns else 0 for h in range(24)]
        z.append(row)
        y.append(dow_names_cn[d])
    return {"z": z, "x": list(range(24)), "y": y}


def get_yearly_heatmaps(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
) -> list[dict]:
    """Year-by-year listening heatmaps."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return []

    years = sorted(df["ts_year"].unique())
    result = []
    for y in years:
        ydf = df[df["ts_year"] == y]
        pivot = ydf.groupby(["ts_dow", "ts_hour"]).size().unstack(fill_value=0)
        z = []
        for d in range(7):
            row = [int(pivot.loc[d, h]) if d in pivot.index and h in pivot.columns else 0 for h in range(24)]
            z.append(row)
        result.append({"year": int(y), "z": z})
    return result


def get_late_night_ratio(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
) -> list[dict]:
    """Late night (0-5) listening ratio by year."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return []

    late_night = df[df["ts_hour"].between(0, 5)]
    total = df.groupby("ts_year").size()
    ln = late_night.groupby("ts_year").size()
    ratio = (ln / total * 100).round(1)
    return [{"year": int(y), "rate": float(ratio.get(y, 0))} for y in sorted(total.index)]


def get_weekday_weekend_comparison(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
) -> dict:
    """Weekend vs workday hourly listening comparison."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return {"weekend": [], "weekday": [], "comparison": []}

    hours = list(range(24))
    df["day_type"] = df["ts_dow"].apply(lambda d: "weekend" if d >= 5 else "weekday")

    weekend_df = df[df["day_type"] == "weekend"]
    weekday_df = df[df["day_type"] == "weekday"]

    weekend_counts = weekend_df.groupby("ts_hour").size().reindex(hours, fill_value=0)
    weekday_counts = weekday_df.groupby("ts_hour").size().reindex(hours, fill_value=0)

    return {
        "hours": [f"{h}:00" for h in hours],
        "weekend": [int(weekend_counts.get(h, 0)) for h in hours],
        "weekday": [int(weekday_counts.get(h, 0)) for h in hours],
    }


def get_platform_hourly_listening(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
) -> dict:
    """Platform × hour listening distribution (stacked area + normalized %)."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    if df.empty:
        return {"platform_hourly": [], "platform_pct": [], "platform_peaks": []}

    # Raw counts: platform × hour
    platform_hourly = (
        df.groupby(["platform", "ts_hour"])
        .size()
        .reset_index(name="count")
    )

    # Normalized percentage per hour
    hourly_total = platform_hourly.groupby("ts_hour")["count"].sum().reset_index()
    platform_pct = platform_hourly.merge(hourly_total, on="ts_hour", suffixes=("", "_total"))
    platform_pct["pct"] = (platform_pct["count"] / platform_pct["count_total"] * 100).round(1)

    # Peak hour per platform
    peaks = []
    for plat in platform_hourly["platform"].unique():
        plat_df = platform_hourly[platform_hourly["platform"] == plat]
        if not plat_df.empty:
            peak_row = plat_df.loc[plat_df["count"].idxmax()]
            total = int(plat_df["count"].sum())
            pct = round(total / max(int(platform_hourly["count"].sum()), 1) * 100, 1)
            peaks.append({
                "platform": plat,
                "peak_hour": int(peak_row["ts_hour"]),
                "peak_count": int(peak_row["count"]),
                "total_count": total,
                "total_pct": pct,
            })

    return {
        "platform_hourly": [
            {"platform": str(r.platform), "hour": int(r.ts_hour), "count": int(r.count)}
            for r in platform_hourly.itertuples(index=False)
        ],
        "platform_pct": [
            {"platform": str(r.platform), "hour": int(r.ts_hour), "pct": float(r.pct)}
            for r in platform_pct.itertuples(index=False)
        ],
        "platform_peaks": peaks,
    }


# ── Artist Deep Dive ────────────────────────────────────────────────────────

def get_artist_list(
    conn: sqlite3.Connection, min_ms: int, music_only: bool,
) -> list[dict]:
    """Get ranked list of artists for the selector."""
    f, fp = base_filters(min_ms=min_ms, music_only=music_only)
    w = f"WHERE {f}" if f else ""
    rows = conn.execute(
        f"""SELECT a.artist_id, a.artist_name, COUNT(*) as cnt
            FROM plays p JOIN tracks t ON p.track_id = t.track_id
            JOIN artists a ON t.artist_id = a.artist_id
            {w}
            GROUP BY a.artist_id ORDER BY cnt DESC""",
        fp,
    ).fetchall()
    return [{"artist_id": r["artist_id"], "artist_name": r["artist_name"], "play_count": r["cnt"]} for r in rows]


def get_artist_deep_dive(
    conn: sqlite3.Connection, min_ms: int, music_only: bool, merge_enabled: bool,
    artist_name: str,
) -> dict:
    """In-depth analysis for a single artist."""
    df = load_plays(
        conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled,
    )
    artist_df = df[df["artist_name"] == artist_name]
    if artist_df.empty:
        return {"found": False}

    dow_names_cn = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}

    # Heatmap
    pivot = artist_df.groupby(["ts_dow", "ts_hour"]).size().unstack(fill_value=0)
    heatmap_z = []
    for d in range(7):
        row = [int(pivot.loc[d, h]) if d in pivot.index and h in pivot.columns else 0 for h in range(24)]
        heatmap_z.append(row)

    # Top tracks
    top_tracks = (
        artist_df.groupby("track_name")
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values("plays", ascending=False)
        .reset_index()
    )

    # Monthly trend
    monthly = (
        artist_df.groupby(["ts_year", "ts_month"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .reset_index()
    )
    monthly["period"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)

    # Album breakdown
    album_stats = (
        artist_df.groupby("album_name")
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values("hours", ascending=False)
        .reset_index()
    )

    return {
        "found": True,
        "artist_name": artist_name,
        "info": {
            "total_plays": len(artist_df),
            "total_hours": round(artist_df["ms_played"].sum() / 3_600_000, 1),
            "unique_tracks": artist_df["track_id"].nunique(),
            "unique_albums": artist_df["album_name"].dropna().nunique(),
        },
        "heatmap": {
            "z": heatmap_z,
            "x": list(range(24)),
            "y": [dow_names_cn[d] for d in range(7)],
        },
        "top_tracks": [
            {"track_name": r.track_name, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in top_tracks.itertuples(index=False)
        ],
        "monthly_trend": [
            {"period": r.period, "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in monthly.itertuples(index=False)
        ],
        "album_breakdown": [
            {"album_name": r.album_name or "未知专辑", "plays": int(r.plays), "hours": round(float(r.hours), 1)}
            for r in album_stats.itertuples(index=False)
        ],
    }
