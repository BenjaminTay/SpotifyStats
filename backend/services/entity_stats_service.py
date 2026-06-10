"""Personal listening statistics for tracks, albums, and artists."""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from backend.core.db import (
    base_filters,
    get_track_artist_names_map,
    load_plays_for_artists,
)
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
    resolve_period_dates,
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
    rows: list[dict],
    entity: str,
    *,
    track_id=None,
    album_name=None,
    album_names: list[str] | None = None,
    artist_name=None,
) -> int | None:
    for row in rows:
        if entity == "track" and row.get("track_id") == track_id:
            return row["rank"]
        if entity == "album":
            if album_names:
                if row.get("album_name") in album_names and row.get("artist_name") == artist_name:
                    return row["rank"]
            elif row.get("album_name") == album_name and row.get("artist_name") == artist_name:
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
    album_names: list[str] | None = None,
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
            rows,
            entity,
            track_id=track_id,
            album_name=album_name,
            album_names=album_names,
            artist_name=artist_name,
        )
    _, rows = chart_rows(conn, current_df, entity, "plays", None, 0)
    result["current_period"] = _rank_for(
        rows,
        entity,
        track_id=track_id,
        album_name=album_name,
        album_names=album_names,
        artist_name=artist_name,
    )
    return result


def _top250_count(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    *,
    album_name: str | None = None,
    album_names: list[str] | None = None,
    artist_name: str | None = None,
) -> int:
    _, rows = chart_rows(conn, df, "track", "plays", 250, 0)
    count = 0
    for row in rows:
        row_album = row.get("album_name")
        row_artist = row.get("artist_name")
        if album_names is not None:
            if row_album in album_names and row_artist == artist_name:
                count += 1
        elif album_name is not None:
            if row_album == album_name and row_artist == artist_name:
                count += 1
        elif row_artist == artist_name:
            count += 1
    return count


def _top250_counts(
    conn: sqlite3.Connection,
    all_df: pd.DataFrame,
    *,
    album_name=None,
    album_names: list[str] | None = None,
    artist_name=None,
) -> dict:
    return {
        "lifetime": _top250_count(
            conn, all_df, album_name=album_name, album_names=album_names, artist_name=artist_name
        ),
        "last_6_months": _top250_count(
            conn,
            filter_period(all_df, resolve_period(all_df, "last_6_months", None, None)),
            album_name=album_name,
            album_names=album_names,
            artist_name=artist_name,
        ),
        "last_4_weeks": _top250_count(
            conn,
            filter_period(all_df, resolve_period(all_df, "last_4_weeks", None, None)),
            album_name=album_name,
            album_names=album_names,
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
    primary_artist = info["artist_name"]
    all_artists = get_track_artist_names_map()
    artist_names = all_artists.get(int(track_id), [primary_artist])
    display_artist = ", ".join(artist_names) if len(artist_names) > 1 else primary_artist
    data = _entity_base(all_df, entity_df)
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "track_id": int(track_id),
                "track_name": info["track_name"],
                "artist_name": display_artist,
                "artist_names": artist_names,
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


def _resolve_album_names(conn: sqlite3.Connection, album_name: str, artist_name: str) -> list[str]:
    """Return all album names in the same release group (including the input)."""
    row = conn.execute(
        """SELECT a.album_name FROM release_group_members rgm
           JOIN release_groups rg ON rg.group_id = rgm.group_id
           JOIN albums a ON a.album_id = rgm.album_id
           JOIN artists ar ON a.artist_id = ar.artist_id
           WHERE rg.canonical_name = ? AND ar.artist_name = ?
           UNION SELECT ?""",
        (album_name, artist_name, album_name),
    ).fetchall()
    if row:
        return list({r["album_name"] for r in row})
    return [album_name]


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

    # Resolve release group aliases (e.g. standard vs deluxe edition)
    if artist_name:
        album_names = _resolve_album_names(conn, album_name, artist_name)
    else:
        album_names = [album_name]

    entity_all = all_df[
        (all_df["album_name"].isin(album_names)) & (all_df["artist_name"] == artist_name)
    ]
    entity_df = current_df[
        (current_df["album_name"].isin(album_names)) & (current_df["artist_name"] == artist_name)
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
                conn,
                all_df,
                current_df,
                "album",
                album_name=album_name,
                album_names=album_names,
                artist_name=artist_name,
            ),
            "top250_counts": _top250_counts(
                conn,
                all_df,
                album_name=album_name,
                album_names=album_names,
                artist_name=artist_name,
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
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        _loader=load_plays_for_artists,
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


def get_entity_plays(
    conn: sqlite3.Connection,
    entity: str,
    track_id: int | None = None,
    album_name: str | None = None,
    artist_name: str | None = None,
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
    """Return paginated play records for a specific entity using direct SQL."""
    bf, bf_params = base_filters(min_ms=min_ms, music_only=music_only, table_alias="p")

    period_start, period_end = resolve_period_dates(period, start_date, end_date)

    where_parts = [bf] if bf else []
    params: list[Any] = list(bf_params)

    if entity == "track" and track_id is not None:
        where_parts.append("t.track_id = ?")
        params.append(track_id)
    elif entity == "album" and album_name is not None:
        where_parts.append("al.album_name = ?")
        params.append(album_name)
        if artist_name is not None:
            where_parts.append("a.artist_name = ?")
            params.append(artist_name)
    elif entity == "artist" and artist_name is not None:
        where_parts.append("a.artist_name = ?")
        params.append(artist_name)

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

    if entity == "artist":
        base_from = """
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN track_artists ta ON t.track_id = ta.track_id
            LEFT JOIN artists a ON ta.artist_id = a.artist_id
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
    from backend.core.db import get_track_artist_names_map

    names_map = get_track_artist_names_map()

    result = []
    for r in rows:
        tid = int(r["track_id"]) if r["track_id"] is not None else None
        entry = {
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
        if tid is not None and tid in names_map:
            entry["artist_names"] = names_map[tid]
        result.append(entry)

    return {"total": total, "limit": limit, "offset": offset, "rows": result}


def get_entity_play_dates(
    conn: sqlite3.Connection,
    entity: str,
    track_id: int | None = None,
    album_name: str | None = None,
    artist_name: str | None = None,
    min_ms: int = 30000,
    music_only: bool = True,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Return [{date, count}] for calendar highlighting."""
    bf, bf_params = base_filters(min_ms=min_ms, music_only=music_only, table_alias="p")

    period_start, period_end = resolve_period_dates(period, start_date, end_date)

    where_parts = [bf] if bf else []
    params: list[Any] = list(bf_params)

    if entity == "track" and track_id is not None:
        where_parts.append("t.track_id = ?")
        params.append(track_id)
    elif entity == "album" and album_name is not None:
        where_parts.append("al.album_name = ?")
        params.append(album_name)
        if artist_name is not None:
            where_parts.append("a.artist_name = ?")
            params.append(artist_name)
    elif entity == "artist" and artist_name is not None:
        where_parts.append("a.artist_name = ?")
        params.append(artist_name)

    if period_start:
        where_parts.append("p.ts_date >= ?")
        params.append(period_start)
    if period_end:
        where_parts.append("p.ts_date <= ?")
        params.append(period_end)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    if entity == "artist":
        sql = f"""
            SELECT p.ts_date AS date, COUNT(*) AS count
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN track_artists ta ON t.track_id = ta.track_id
            LEFT JOIN artists a ON ta.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            WHERE {where_clause}
            GROUP BY p.ts_date
            ORDER BY p.ts_date
        """
    else:
        sql = f"""
            SELECT p.ts_date AS date, COUNT(*) AS count
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            WHERE {where_clause}
            GROUP BY p.ts_date
            ORDER BY p.ts_date
        """
    rows = conn.execute(sql, params).fetchall()
    return [{"date": str(r["date"]), "count": int(r["count"])} for r in rows]
