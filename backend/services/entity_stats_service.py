"""Personal listening statistics for tracks, albums, and artists."""

from __future__ import annotations

import sqlite3

import pandas as pd

from backend.services.analysis_stats_service import (
    _cumulative_trend,
    _daily_metrics,
    _daily_trend,
    _hourly_distribution,
    _month_distribution,
    _summary,
    _weekday_distribution,
    _year_distribution,
    chart_rows,
    filter_period,
    load_period_plays,
    recent_plays,
    resolve_period,
)
from backend.services.play_service import (
    _album_cover_lookup,
    _artist_cover_lookup,
    _track_cover_urls,
)


def _entity_base(df: pd.DataFrame, entity_df: pd.DataFrame) -> dict:
    summary = _summary(entity_df)
    daily = _daily_trend(entity_df)
    return {
        "summary": summary,
        "daily_metrics": _daily_metrics(summary),
        "hourly_distribution": _hourly_distribution(entity_df),
        "daily_trend": daily,
        "cumulative_trend": _cumulative_trend(daily),
        "weekday_distribution": _weekday_distribution(entity_df),
        "month_distribution": _month_distribution(entity_df),
        "year_distribution": _year_distribution(entity_df),
    }


def _rank_for(
    rows: list[dict], entity: str, *, track_id=None, album_name=None, artist_name=None
) -> int | None:
    for row in rows:
        if entity == "track" and row.get("track_id") == track_id:
            return row["rank"]
        if (
            entity == "album"
            and row.get("album_name") == album_name
            and row.get("artist_name") == artist_name
        ):
            return row["rank"]
        if entity == "artist" and row.get("artist_name") == artist_name:
            return row["rank"]
    return None


def _ranks(
    conn: sqlite3.Connection,
    all_df: pd.DataFrame,
    current_df: pd.DataFrame,
    entity: str,
    track_id=None,
    album_name=None,
    artist_name=None,
) -> dict:
    periods = {
        "lifetime": resolve_period(all_df, "lifetime", None, None),
        "last_6_months": resolve_period(all_df, "last_6_months", None, None),
        "last_4_weeks": resolve_period(all_df, "last_4_weeks", None, None),
    }
    result = {}
    for key, resolved in periods.items():
        _, rows = chart_rows(conn, filter_period(all_df, resolved), entity, "plays", None, 0)
        result[key] = _rank_for(
            rows, entity, track_id=track_id, album_name=album_name, artist_name=artist_name
        )
    _, rows = chart_rows(conn, current_df, entity, "plays", None, 0)
    result["current_period"] = _rank_for(
        rows, entity, track_id=track_id, album_name=album_name, artist_name=artist_name
    )
    return result


def _top250_count(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    *,
    album_name: str | None = None,
    artist_name: str | None = None,
) -> int:
    _, rows = chart_rows(conn, df, "track", "plays", 250, 0)
    count = 0
    for row in rows:
        if (
            album_name is not None
            and row.get("album_name") == album_name
            and row.get("artist_name") == artist_name
        ):
            count += 1
        elif album_name is None and row.get("artist_name") == artist_name:
            count += 1
    return count


def _top250_counts(
    conn: sqlite3.Connection, all_df: pd.DataFrame, *, album_name=None, artist_name=None
) -> dict:
    return {
        "lifetime": _top250_count(conn, all_df, album_name=album_name, artist_name=artist_name),
        "last_6_months": _top250_count(
            conn,
            filter_period(all_df, resolve_period(all_df, "last_6_months", None, None)),
            album_name=album_name,
            artist_name=artist_name,
        ),
        "last_4_weeks": _top250_count(
            conn,
            filter_period(all_df, resolve_period(all_df, "last_4_weeks", None, None)),
            album_name=album_name,
            artist_name=artist_name,
        ),
    }


def get_track_stats(
    conn: sqlite3.Connection,
    track_id: int,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    all_df, current_df, resolved = load_period_plays(
        conn, min_ms, music_only, merge_enabled, period, start_date, end_date
    )
    entity_all = all_df[all_df["track_id"] == track_id]
    entity_df = current_df[current_df["track_id"] == track_id]
    if entity_all.empty:
        return {"found": False}
    info = entity_all.iloc[0]
    data = _entity_base(all_df, entity_df)
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "track_id": int(track_id),
                "track_name": info["track_name"],
                "artist_name": info["artist_name"],
                "album_name": info["album_name"],
                "cover_url": _track_cover_urls(conn, [track_id]).get(int(track_id)),
            },
            "first_played": str(entity_all["ts"].min()),
            "last_played": str(entity_all["ts"].max()),
            "ranks": _ranks(conn, all_df, current_df, "track", track_id=int(track_id)),
            "recent_plays": recent_plays(conn, entity_df, 50),
        }
    )
    return data


def get_album_stats(
    conn: sqlite3.Connection,
    album_name: str,
    artist: str | None,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    all_df, current_df, resolved = load_period_plays(
        conn, min_ms, music_only, merge_enabled, period, start_date, end_date
    )
    artist_name = artist
    if not artist_name:
        matches = all_df[all_df["album_name"] == album_name]
        if not matches.empty:
            artist_name = str(matches.iloc[0]["artist_name"])
    entity_all = all_df[
        (all_df["album_name"] == album_name) & (all_df["artist_name"] == artist_name)
    ]
    entity_df = current_df[
        (current_df["album_name"] == album_name) & (current_df["artist_name"] == artist_name)
    ]
    if entity_all.empty:
        return {"found": False}
    data = _entity_base(all_df, entity_df)
    _, breakdown = chart_rows(conn, entity_df, "track", "plays", 250, 0)
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "album_name": album_name,
                "artist_name": artist_name,
                "cover_url": _album_cover_lookup(conn).get((album_name, artist_name)),
            },
            "first_played": str(entity_all["ts"].min()),
            "last_played": str(entity_all["ts"].max()),
            "ranks": _ranks(
                conn, all_df, current_df, "album", album_name=album_name, artist_name=artist_name
            ),
            "top250_counts": _top250_counts(
                conn, all_df, album_name=album_name, artist_name=artist_name
            ),
            "track_breakdown": breakdown,
            "recent_plays": recent_plays(conn, entity_df, 50),
        }
    )
    return data


def get_artist_stats(
    conn: sqlite3.Connection,
    artist_name: str,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    all_df, current_df, resolved = load_period_plays(
        conn, min_ms, music_only, merge_enabled, period, start_date, end_date
    )
    entity_all = all_df[all_df["artist_name"] == artist_name]
    entity_df = current_df[current_df["artist_name"] == artist_name]
    if entity_all.empty:
        return {"found": False}
    _, top_tracks = chart_rows(conn, entity_df, "track", "plays", 20, 0)
    _, top_albums = chart_rows(conn, entity_df, "album", "plays", 20, 0)
    recent_50_all = all_df.sort_values("ts", ascending=False).head(50)
    data = _entity_base(all_df, entity_df)
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "artist_name": artist_name,
                "cover_url": _artist_cover_lookup(conn).get(artist_name),
            },
            "first_played": str(entity_all["ts"].min()),
            "last_played": str(entity_all["ts"].max()),
            "ranks": _ranks(conn, all_df, current_df, "artist", artist_name=artist_name),
            "top250_counts": _top250_counts(conn, all_df, artist_name=artist_name),
            "recent_50_count": int((recent_50_all["artist_name"] == artist_name).sum()),
            "top_tracks": top_tracks,
            "top_albums": top_albums,
            "recent_plays": recent_plays(conn, entity_df, 50),
        }
    )
    return data
