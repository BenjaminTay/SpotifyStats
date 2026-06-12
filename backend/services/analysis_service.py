"""Playback analysis overview service."""

from __future__ import annotations

import sqlite3

import pandas as pd

from backend.core.db import load_plays, load_plays_for_artists
from backend.services.play_service import (
    _album_cover_lookup,
    _artist_cover_lookup,
    _track_cover_urls,
    get_dashboard_summary,
    get_hourly_dist,
    get_monthly_trend,
)


def _hours(series):
    return float(series.sum() / 3_600_000)


def _empty_overview() -> dict:
    return {
        "summary": {
            "total_plays": 0,
            "total_hours": 0.0,
            "total_tracks": 0,
            "total_artists": 0,
            "total_albums": 0,
            "total_days": 0,
            "avg_daily_hours": 0.0,
        },
        "monthly_trend": [],
        "trend_summary": {
            "peak_period": None,
            "peak_plays": 0,
            "low_period": None,
            "low_plays": 0,
            "latest_period": None,
            "latest_plays": 0,
            "previous_period": None,
            "previous_plays": 0,
            "month_delta_pct": None,
        },
        "listening_summary": {
            "peak_hour": None,
            "peak_hour_count": 0,
            "late_night_rate": 0.0,
            "weekend_rate": 0.0,
            "day_type_preference": "unknown",
        },
        "top_tracks": [],
        "top_artists": [],
        "top_albums": [],
        "behavior_summary": {
            "forward_rate": 0.0,
            "shuffle_rate": 0.0,
            "primary_platform": "",
            "primary_platform_rate": 0.0,
            "top_end_reason": "",
        },
        "module_cards": [],
    }


def _trend_summary(monthly: list[dict]) -> dict:
    if not monthly:
        return _empty_overview()["trend_summary"]

    peak = max(monthly, key=lambda item: item["plays"])
    low = min(monthly, key=lambda item: item["plays"])
    latest = monthly[-1]
    previous = monthly[-2] if len(monthly) > 1 else None
    delta = None
    if previous and previous["plays"] > 0:
        delta = round((latest["plays"] - previous["plays"]) / previous["plays"] * 100, 1)

    return {
        "peak_period": peak["period"],
        "peak_plays": peak["plays"],
        "low_period": low["period"],
        "low_plays": low["plays"],
        "latest_period": latest["period"],
        "latest_plays": latest["plays"],
        "previous_period": previous["period"] if previous else None,
        "previous_plays": previous["plays"] if previous else 0,
        "month_delta_pct": delta,
    }


def _listening_summary(df: pd.DataFrame, hourly: list[dict]) -> dict:
    if df.empty:
        return _empty_overview()["listening_summary"]

    peak = max(hourly, key=lambda item: item["count"]) if hourly else None
    late_hours = [23, 0, 1, 2, 3, 4, 5]
    late_rate = round(len(df[df["ts_hour"].isin(late_hours)]) / max(len(df), 1) * 100, 1)
    weekend_rate = round(len(df[df["ts_dow"] >= 5]) / max(len(df), 1) * 100, 1)
    preference = "weekend" if weekend_rate >= 35 else "weekday"

    return {
        "peak_hour": int(peak["hour"]) if peak else None,
        "peak_hour_count": int(peak["count"]) if peak else 0,
        "late_night_rate": late_rate,
        "weekend_rate": weekend_rate,
        "day_type_preference": preference,
    }


def _top_tracks(conn: sqlite3.Connection, df: pd.DataFrame) -> list[dict]:
    cover_map = _track_cover_urls(conn, df["track_id"])
    top = (
        df.groupby(["track_id", "track_name", "artist_name"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hours))
        .sort_values("plays", ascending=False)
        .head(5)
        .reset_index()
    )
    return [
        {
            "track_id": int(r.track_id),
            "track_name": r.track_name,
            "artist_name": r.artist_name,
            "plays": int(r.plays),
            "hours": round(float(r.hours), 1),
            "cover_url": cover_map.get(int(r.track_id)),
        }
        for r in top.itertuples(index=False)
    ]


def _top_artists(conn: sqlite3.Connection, df: pd.DataFrame) -> list[dict]:
    cover_map = _artist_cover_lookup(conn)
    top = (
        df.groupby("artist_name")
        .agg(
            plays=("play_id", "count"), hours=("ms_played", _hours), tracks=("track_id", "nunique")
        )
        .sort_values("plays", ascending=False)
        .head(5)
        .reset_index()
    )
    return [
        {
            "artist_name": r.artist_name,
            "plays": int(r.plays),
            "hours": round(float(r.hours), 1),
            "tracks": int(r.tracks),
            "cover_url": cover_map.get(r.artist_name),
        }
        for r in top.itertuples(index=False)
    ]


def _top_albums(conn: sqlite3.Connection, df: pd.DataFrame) -> list[dict]:
    cover_map = _album_cover_lookup(conn)
    top = (
        df.groupby(["album_name", "artist_name"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hours))
        .sort_values("plays", ascending=False)
        .head(5)
        .reset_index()
    )
    return [
        {
            "album_name": r.album_name or "未知专辑",
            "artist_name": r.artist_name,
            "plays": int(r.plays),
            "hours": round(float(r.hours), 1),
            "cover_url": cover_map.get((r.album_name, r.artist_name)),
        }
        for r in top.itertuples(index=False)
    ]


def _behavior_summary(conn: sqlite3.Connection, music_only: bool) -> dict:
    raw = load_plays(conn, filtered=False, music_only=music_only)
    if raw.empty:
        return _empty_overview()["behavior_summary"]

    total = max(len(raw), 1)
    forward_rate = round(len(raw[raw["reason_end"] == "fwdbtn"]) / total * 100, 1)
    shuffle_rate = round(raw["shuffle"].fillna(False).mean() * 100, 1)
    platform_counts = raw["platform"].fillna("unknown").value_counts()
    reason_counts = raw["reason_end"].fillna("unknown").value_counts()
    primary_platform = str(platform_counts.index[0]) if not platform_counts.empty else ""
    primary_count = int(platform_counts.iloc[0]) if not platform_counts.empty else 0

    return {
        "forward_rate": forward_rate,
        "shuffle_rate": shuffle_rate,
        "primary_platform": primary_platform,
        "primary_platform_rate": round(primary_count / total * 100, 1),
        "top_end_reason": str(reason_counts.index[0]) if not reason_counts.empty else "",
    }


def _module_cards(
    trend: dict,
    listening: dict,
    behavior: dict,
    top_tracks: list[dict],
    top_artists: list[dict],
) -> list[dict]:
    cards = []
    if trend["peak_period"]:
        cards.append(
            {
                "key": "timeline",
                "title": "总体统计",
                "metric": trend["peak_period"],
                "detail": f"峰值月份 {trend['peak_plays']:,} 次播放",
                "to": "/analysis/stats",
                "cover_url": None,
            }
        )
    if top_tracks:
        cards.append(
            {
                "key": "leaderboard",
                "title": "个人排行榜",
                "metric": top_tracks[0]["track_name"],
                "detail": f"{top_tracks[0]['artist_name']} · {top_tracks[0]['plays']:,} 次",
                "to": "/analysis/charts?entity=track",
                "cover_url": top_tracks[0].get("cover_url"),
            }
        )
    cards.append(
        {
            "key": "behavior",
            "title": "行为分析",
            "metric": f"{behavior['forward_rate']:.1f}%",
            "detail": "快进结束占比",
            "to": "/analysis/stats",
            "cover_url": None,
        }
    )
    if listening["peak_hour"] is not None:
        cards.append(
            {
                "key": "listening-hours",
                "title": "听歌时段",
                "metric": f"{listening['peak_hour']:02d}:00",
                "detail": f"高峰时段 {listening['peak_hour_count']:,} 次",
                "to": "/analysis/stats",
                "cover_url": None,
            }
        )
    if top_artists:
        cards.append(
            {
                "key": "artists",
                "title": "艺人排行",
                "metric": top_artists[0]["artist_name"],
                "detail": f"{top_artists[0]['plays']:,} 次个人播放",
                "to": "/analysis/charts?entity=artist",
                "cover_url": top_artists[0].get("cover_url"),
            }
        )
    return cards


def get_analysis_overview(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
) -> dict:
    """Build the playback analysis landing-page aggregate."""
    df = load_plays(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    if df.empty:
        return _empty_overview()

    summary = get_dashboard_summary(conn, min_ms, music_only, merge_enabled, df=df)
    monthly = get_monthly_trend(conn, min_ms, music_only, merge_enabled, df=df)
    hourly = get_hourly_dist(conn, min_ms, music_only, merge_enabled, df=df)
    trend = _trend_summary(monthly)
    listening = _listening_summary(df, hourly)
    tracks = _top_tracks(conn, df)
    df_artists = load_plays_for_artists(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    artists = _top_artists(conn, df_artists)
    albums = _top_albums(conn, df)
    behavior = _behavior_summary(conn, music_only)

    return {
        "summary": summary,
        "monthly_trend": monthly,
        "trend_summary": trend,
        "listening_summary": listening,
        "top_tracks": tracks,
        "top_artists": artists,
        "top_albums": albums,
        "behavior_summary": behavior,
        "module_cards": _module_cards(trend, listening, behavior, tracks, artists),
    }
