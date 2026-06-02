"""Stats.fm-style playback statistics services."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from backend.core.db import get_db, load_plays
from backend.services.play_service import (
    _album_cover_lookup,
    _artist_cover_lookup,
    _track_cover_urls,
)

PERIOD_LABELS = {
    "lifetime": "全部时间",
    "today": "今天",
    "this_week": "本周",
    "this_year": "今年",
    "last_4_weeks": "最近 4 周",
    "last_6_months": "最近 6 个月",
    "custom": "自定义",
}


def _hours(series) -> float:
    return float(series.sum() / 3_600_000)


def resolve_period(
    df: pd.DataFrame, period: str, start_date: str | None, end_date: str | None
) -> dict:
    """Resolve a named period to inclusive local-date boundaries."""
    period = period if period in PERIOD_LABELS else "lifetime"
    today = date.today()

    if period == "lifetime":
        start = str(df["ts_date"].min()) if not df.empty else None
        end = str(df["ts_date"].max()) if not df.empty else None
    elif period == "today":
        start = end = today.isoformat()
    elif period == "this_week":
        start = (today - timedelta(days=today.weekday())).isoformat()
        end = today.isoformat()
    elif period == "this_year":
        start = date(today.year, 1, 1).isoformat()
        end = today.isoformat()
    elif period == "last_4_weeks":
        start = (today - timedelta(days=27)).isoformat()
        end = today.isoformat()
    elif period == "last_6_months":
        start = (today - timedelta(days=182)).isoformat()
        end = today.isoformat()
    else:
        start = start_date
        end = end_date

    return {
        "period": period,
        "label": PERIOD_LABELS[period],
        "start_date": start,
        "end_date": end,
    }


def resolve_period_dates(
    period: str, start_date: str | None, end_date: str | None
) -> tuple[str | None, str | None]:
    """Resolve a named period to (start_date, end_date) strings without a DataFrame."""
    period = period if period in PERIOD_LABELS else "lifetime"
    today = date.today()

    if period == "lifetime":
        return None, None
    elif period == "today":
        return today.isoformat(), today.isoformat()
    elif period == "this_week":
        return (today - timedelta(days=today.weekday())).isoformat(), today.isoformat()
    elif period == "this_year":
        return date(today.year, 1, 1).isoformat(), today.isoformat()
    elif period == "last_4_weeks":
        return (today - timedelta(days=27)).isoformat(), today.isoformat()
    elif period == "last_6_months":
        return (today - timedelta(days=182)).isoformat(), today.isoformat()
    else:
        return start_date, end_date


def filter_period(df: pd.DataFrame, resolved: dict) -> pd.DataFrame:
    if df.empty:
        return df
    start = resolved.get("start_date")
    end = resolved.get("end_date")
    out = df
    if start:
        out = out[out["ts_date"].astype(str) >= start]
    if end:
        out = out[out["ts_date"].astype(str) <= end]
    return out


def load_period_plays(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = load_plays(conn, min_ms=min_ms, music_only=music_only, merge_enabled=merge_enabled)
    resolved = resolve_period(df, period, start_date, end_date)
    return df, filter_period(df, resolved), resolved


def _zero_summary() -> dict:
    return {
        "total_plays": 0,
        "total_hours": 0.0,
        "unique_tracks": 0,
        "unique_albums": 0,
        "unique_artists": 0,
        "active_days": 0,
    }


def _summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return _zero_summary()
    return {
        "total_plays": int(len(df)),
        "total_hours": round(float(df["ms_played"].sum() / 3_600_000), 1),
        "unique_tracks": int(df["track_id"].nunique()),
        "unique_albums": int(df["album_name"].dropna().nunique()),
        "unique_artists": int(df["artist_name"].dropna().nunique()),
        "active_days": int(df["ts_date"].nunique()),
    }


def _daily_metrics(summary: dict) -> dict:
    active_days = max(int(summary["active_days"]), 1)
    return {
        "avg_daily_plays": round(summary["total_plays"] / active_days, 2),
        "avg_daily_hours": round(summary["total_hours"] / active_days, 2),
        "avg_active_day_plays": round(summary["total_plays"] / active_days, 2),
        "avg_active_day_hours": round(summary["total_hours"] / active_days, 2),
    }


def _hourly_distribution(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        counts = pd.Series(dtype=int)
        hours = pd.Series(dtype=float)
    else:
        counts = df.groupby("ts_hour").size()
        hours = df.groupby("ts_hour")["ms_played"].sum() / 3_600_000
    return [
        {"hour": h, "plays": int(counts.get(h, 0)), "hours": round(float(hours.get(h, 0)), 2)}
        for h in range(24)
    ]


def _daily_trend(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    daily = (
        df.groupby("ts_date")
        .agg(plays=("play_id", "count"), hours=("ms_played", _hours))
        .reset_index()
        .sort_values("ts_date")
    )
    return [
        {"date": str(r.ts_date), "plays": int(r.plays), "hours": round(float(r.hours), 2)}
        for r in daily.itertuples(index=False)
    ]


def _cumulative_trend(daily: list[dict]) -> list[dict]:
    plays = 0
    hours = 0.0
    rows = []
    for item in daily:
        plays += item["plays"]
        hours += item["hours"]
        rows.append(
            {
                "date": item["date"],
                "cumulative_plays": int(plays),
                "cumulative_hours": round(hours, 2),
            }
        )
    return rows


def _weekday_distribution(df: pd.DataFrame) -> list[dict]:
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    counts = df.groupby("ts_dow").size() if not df.empty else pd.Series(dtype=int)
    hours = (
        df.groupby("ts_dow")["ms_played"].sum() / 3_600_000
        if not df.empty
        else pd.Series(dtype=float)
    )
    return [
        {
            "day": labels[d],
            "plays": int(counts.get(d, 0)),
            "hours": round(float(hours.get(d, 0)), 2),
        }
        for d in range(7)
    ]


def _month_distribution(df: pd.DataFrame) -> list[dict]:
    counts = df.groupby("ts_month").size() if not df.empty else pd.Series(dtype=int)
    hours = (
        df.groupby("ts_month")["ms_played"].sum() / 3_600_000
        if not df.empty
        else pd.Series(dtype=float)
    )
    return [
        {"month": m, "plays": int(counts.get(m, 0)), "hours": round(float(hours.get(m, 0)), 2)}
        for m in range(1, 13)
    ]


def _year_distribution(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    yearly = (
        df.groupby("ts_year")
        .agg(plays=("play_id", "count"), hours=("ms_played", _hours))
        .reset_index()
        .sort_values("ts_year")
    )
    return [
        {"year": int(r.ts_year), "plays": int(r.plays), "hours": round(float(r.hours), 2)}
        for r in yearly.itertuples(index=False)
    ]


def _behavior_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "forward_rate": 0.0,
            "shuffle_rate": 0.0,
            "primary_platform": "",
            "primary_platform_rate": 0.0,
            "top_start_reason": "",
            "top_end_reason": "",
        }
    total = max(len(df), 1)
    platform = df["platform"].fillna("unknown").value_counts()
    start = df["reason_start"].fillna("unknown").value_counts()
    end = df["reason_end"].fillna("unknown").value_counts()
    primary_count = int(platform.iloc[0]) if not platform.empty else 0
    return {
        "forward_rate": round(len(df[df["reason_end"] == "fwdbtn"]) / total * 100, 1),
        "shuffle_rate": round(df["shuffle"].fillna(False).mean() * 100, 1),
        "primary_platform": str(platform.index[0]) if not platform.empty else "",
        "primary_platform_rate": round(primary_count / total * 100, 1),
        "top_start_reason": str(start.index[0]) if not start.empty else "",
        "top_end_reason": str(end.index[0]) if not end.empty else "",
    }


def recent_plays(conn: sqlite3.Connection, df: pd.DataFrame, limit: int = 50) -> list[dict]:
    if df.empty:
        return []
    cover_map = _track_cover_urls(conn, df["track_id"])
    rows = df.sort_values("ts", ascending=False).head(limit)
    result = []
    for r in rows.itertuples(index=False):
        track_id = int(r.track_id) if pd.notna(r.track_id) else None
        result.append(
            {
                "play_id": int(r.play_id),
                "ts": str(r.ts),
                "date": str(r.ts_date),
                "track_id": track_id,
                "track_name": r.track_name,
                "artist_name": r.artist_name,
                "album_name": getattr(r, "album_name", None),
                "ms_played": int(r.ms_played),
                "hours": round(float(r.ms_played) / 3_600_000, 3),
                "platform": r.platform,
                "cover_url": cover_map.get(track_id) if track_id is not None else None,
            }
        )
    return result


def get_analysis_stats(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    if conn is not None:
        return _get_analysis_stats_cached(
            min_ms, music_only, merge_enabled, period, start_date, end_date
        )


@lru_cache(maxsize=64)
def _get_analysis_stats_cached(
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    conn = get_db()
    try:
        return _build_analysis_stats(
            conn, min_ms, music_only, merge_enabled, period, start_date, end_date
        )
    finally:
        conn.close()


def _build_analysis_stats(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    _, df, resolved = load_period_plays(
        conn, min_ms, music_only, merge_enabled, period, start_date, end_date
    )
    summary = _summary(df)
    daily = _daily_trend(df)
    return {
        "period": resolved,
        "summary": summary,
        "daily_metrics": _daily_metrics(summary),
        "hourly_distribution": _hourly_distribution(df),
        "daily_trend": daily,
        "cumulative_trend": _cumulative_trend(daily),
        "weekday_distribution": _weekday_distribution(df),
        "month_distribution": _month_distribution(df),
        "year_distribution": _year_distribution(df),
        "behavior_summary": _behavior_summary(df),
        "recent_plays": recent_plays(conn, df, 50),
    }


def _chart_agg(df: pd.DataFrame, entity: str) -> pd.DataFrame:
    if entity == "track":
        return (
            df.groupby(["track_id", "track_name", "artist_name", "album_name"])
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", _hours),
                first_played=("ts", "min"),
                last_played=("ts", "max"),
            )
            .reset_index()
        )
    if entity == "album":
        return (
            df.groupby(["album_name", "artist_name"])
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", _hours),
                unique_tracks=("track_id", "nunique"),
                first_played=("ts", "min"),
                last_played=("ts", "max"),
            )
            .reset_index()
        )
    if entity == "artist":
        return (
            df.groupby("artist_name")
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", _hours),
                unique_tracks=("track_id", "nunique"),
                unique_albums=("album_name", "nunique"),
                first_played=("ts", "min"),
                last_played=("ts", "max"),
            )
            .reset_index()
        )
    return pd.DataFrame()


def chart_rows(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    entity: str,
    metric: str,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    if df.empty:
        return 0, []
    entity = entity if entity in {"track", "album", "artist"} else "track"
    metric = metric if metric in {"plays", "hours"} else "plays"
    agg = _chart_agg(df, entity)
    if agg.empty:
        return 0, []

    total_plays = max(int(df.shape[0]), 1)
    total_hours = max(float(df["ms_played"].sum() / 3_600_000), 0.000001)
    sort_col = "plays" if metric == "plays" else "hours"
    agg = agg.sort_values([sort_col, "plays"], ascending=False).reset_index(drop=True)
    total = int(len(agg))
    sliced = agg.iloc[offset : offset + limit] if limit is not None else agg.iloc[offset:]

    track_covers = (
        _track_cover_urls(conn, sliced["track_id"])
        if entity == "track" and not sliced.empty
        else {}
    )
    album_covers = _album_cover_lookup(conn) if entity == "album" else {}
    artist_covers = _artist_cover_lookup(conn) if entity == "artist" else {}
    active_days = max(int(df["ts_date"].nunique()), 1)

    rows = []
    for idx, r in sliced.iterrows():
        row: dict[str, Any] = {
            "rank": int(idx) + 1,
            "plays": int(r["plays"]),
            "hours": round(float(r["hours"]), 2),
            "first_played": str(r["first_played"]),
            "last_played": str(r["last_played"]),
            "avg_daily_plays": round(float(r["plays"]) / active_days, 3),
            "avg_daily_hours": round(float(r["hours"]) / active_days, 3),
            "share_pct": round(
                (float(r[sort_col]) / (total_plays if sort_col == "plays" else total_hours)) * 100,
                2,
            ),
        }
        if entity == "track":
            row.update(
                {
                    "track_id": int(r["track_id"]),
                    "track_name": r["track_name"],
                    "artist_name": r["artist_name"],
                    "album_name": r["album_name"],
                    "cover_url": track_covers.get(int(r["track_id"])),
                }
            )
        elif entity == "album":
            row.update(
                {
                    "album_name": r["album_name"],
                    "artist_name": r["artist_name"],
                    "unique_tracks": int(r["unique_tracks"]),
                    "cover_url": album_covers.get((r["album_name"], r["artist_name"])),
                }
            )
        else:
            row.update(
                {
                    "artist_name": r["artist_name"],
                    "unique_tracks": int(r["unique_tracks"]),
                    "unique_albums": int(r["unique_albums"]),
                    "cover_url": artist_covers.get(r["artist_name"]),
                }
            )
        rows.append(row)
    return total, rows


def get_analysis_charts(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    entity: str = "track",
    metric: str = "plays",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    if conn is not None:
        return _get_analysis_charts_cached(
            min_ms,
            music_only,
            merge_enabled,
            period,
            start_date,
            end_date,
            entity,
            metric,
            limit,
            offset,
        )


@lru_cache(maxsize=128)
def _get_analysis_charts_cached(
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    entity: str = "track",
    metric: str = "plays",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    conn = get_db()
    try:
        return _build_analysis_charts(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            period,
            start_date,
            end_date,
            entity,
            metric,
            limit,
            offset,
        )
    finally:
        conn.close()


def _build_analysis_charts(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    entity: str = "track",
    metric: str = "plays",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    _, df, resolved = load_period_plays(
        conn, min_ms, music_only, merge_enabled, period, start_date, end_date
    )
    total, rows = chart_rows(conn, df, entity, metric, limit, offset)
    return {
        "period": resolved,
        "entity": entity if entity in {"track", "album", "artist"} else "track",
        "metric": metric if metric in {"plays", "hours"} else "plays",
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": rows,
    }


def entity_cover(conn: sqlite3.Connection, entity: str, row: dict) -> str | None:
    if entity == "track" and row.get("track_id") is not None:
        return _track_cover_urls(conn, [row["track_id"]]).get(int(row["track_id"]))
    if entity == "album":
        return _album_cover_lookup(conn).get((row.get("album_name"), row.get("artist_name")))
    if entity == "artist":
        return _artist_cover_lookup(conn).get(row.get("artist_name"))
    return None


def get_global_plays(
    conn: sqlite3.Connection,
    min_ms: int = 30000,
    music_only: bool = True,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return paginated play records across all entities using direct SQL."""
    from backend.core.db import base_filters

    bf, bf_params = base_filters(min_ms=min_ms, music_only=music_only, table_alias="p")

    period_start, period_end = resolve_period_dates(period, start_date, end_date)

    where_parts = [bf] if bf else []
    params: list[Any] = list(bf_params)

    if period_start:
        where_parts.append("p.ts_date >= ?")
        params.append(period_start)
    if period_end:
        where_parts.append("p.ts_date <= ?")
        params.append(period_end)

    if date is not None:
        where_parts.append("p.ts_date = ?")
        params.append(date)

    if search is not None:
        search_term = f"%{search}%"
        where_parts.append("(t.track_name LIKE ? OR a.artist_name LIKE ? OR al.album_name LIKE ?)")
        params.extend([search_term, search_term, search_term])

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    base_from = """
        FROM plays p
        LEFT JOIN tracks t ON p.track_id = t.track_id
        LEFT JOIN artists a ON t.artist_id = a.artist_id
        LEFT JOIN albums al ON t.album_id = al.album_id
    """

    count_sql = f"SELECT COUNT(*) {base_from} WHERE {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    select_sql = f"""
        SELECT p.play_id, p.ts, p.ts_date, p.track_id, t.track_name,
               a.artist_name, al.album_name, p.ms_played, p.platform
        {base_from}
        WHERE {where_clause}
        ORDER BY p.ts DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(select_sql, params + [limit, offset]).fetchall()

    track_ids = [int(r["track_id"]) for r in rows if r["track_id"] is not None]
    cover_map = _track_cover_urls(conn, track_ids) if track_ids else {}

    result = []
    for r in rows:
        tid = int(r["track_id"]) if r["track_id"] is not None else None
        result.append(
            {
                "play_id": int(r["play_id"]),
                "ts": str(r["ts"]),
                "date": str(r["ts_date"]),
                "track_id": tid,
                "track_name": r["track_name"] or "",
                "artist_name": r["artist_name"] or "",
                "album_name": r["album_name"],
                "ms_played": int(r["ms_played"]),
                "hours": round(float(r["ms_played"]) / 3_600_000, 3),
                "platform": r["platform"] or "",
                "cover_url": cover_map.get(tid) if tid is not None else None,
            }
        )

    return {"total": total, "limit": limit, "offset": offset, "rows": result}


def get_global_play_dates(
    conn: sqlite3.Connection,
    min_ms: int = 30000,
    music_only: bool = True,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Return [{date, count}] for calendar highlighting across all entities."""
    from backend.core.db import base_filters

    bf, bf_params = base_filters(min_ms=min_ms, music_only=music_only, table_alias="p")

    period_start, period_end = resolve_period_dates(period, start_date, end_date)

    where_parts = [bf] if bf else []
    params: list[Any] = list(bf_params)

    if period_start:
        where_parts.append("p.ts_date >= ?")
        params.append(period_start)
    if period_end:
        where_parts.append("p.ts_date <= ?")
        params.append(period_end)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql = f"""
        SELECT p.ts_date AS date, COUNT(*) AS count
        FROM plays p
        WHERE {where_clause}
        GROUP BY p.ts_date
        ORDER BY p.ts_date
    """
    rows = conn.execute(sql, params).fetchall()
    return [{"date": str(r["date"]), "count": int(r["count"])} for r in rows]


# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("analysis", "stats", _get_analysis_stats_cached)
register_lru("analysis", "charts", _get_analysis_charts_cached)
