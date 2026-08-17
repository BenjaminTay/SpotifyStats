"""Stats.fm-style playback statistics services."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from backend.core.db import get_db, get_track_artist_names_map, load_plays, load_plays_for_artists
from backend.domains.metadata.genre_display_taxonomy import build_consumer_taste_profile
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


def _resolve_album_category(conn: sqlite3.Connection, album_name: str, artist_name: str) -> str:
    """Look up album category from metadata. Returns 'lp', 'ep', 'compilation', 'single', or 'unknown'."""
    from backend.domains.playback.album_type import classify_album

    row = conn.execute(
        """SELECT sam.album_type, sam.total_tracks
           FROM albums al
           JOIN artists a ON al.artist_id = a.artist_id
           LEFT JOIN tracks t ON t.album_id = al.album_id
           LEFT JOIN spotify_track_meta stm
             ON t.spotify_track_id = stm.spotify_track_id
           LEFT JOIN spotify_album_meta sam ON (
             stm.spotify_album_id = sam.spotify_album_id
             OR 'spotify:album:' || stm.spotify_album_id = sam.spotify_album_id
           )
           WHERE al.album_name = ? AND a.artist_name = ?
           LIMIT 1""",
        (album_name, artist_name),
    ).fetchone()
    if row is None:
        # Check if this is a release group canonical name — resolve from a member album
        row = conn.execute(
            """SELECT sam.album_type, sam.total_tracks
               FROM release_groups rg
               JOIN release_group_members rgm ON rg.group_id = rgm.group_id
               JOIN albums al ON rgm.album_id = al.album_id
               LEFT JOIN tracks t ON t.album_id = al.album_id
               LEFT JOIN spotify_track_meta stm
                 ON t.spotify_track_id = stm.spotify_track_id
               LEFT JOIN spotify_album_meta sam ON (
                 stm.spotify_album_id = sam.spotify_album_id
                 OR 'spotify:album:' || stm.spotify_album_id = sam.spotify_album_id
               )
               WHERE rg.canonical_name = ? AND rg.scope = 'release'
               LIMIT 1""",
            (album_name,),
        ).fetchone()
    if row is None:
        return "unknown"
    album_type, total_tracks = row
    # Estimate total duration from album tracks if available
    total_ms = None
    if total_tracks:
        total_ms = total_tracks * 210_000  # rough estimate: ~3.5 min avg track
    return classify_album(album_type, total_tracks=total_tracks, total_ms=total_ms)


def _album_identity_lookup(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return album_id -> display album/artist names for source-album grouping."""
    return pd.read_sql_query(
        """SELECT al.album_id AS _album_container_id,
                  al.album_name AS _album_container_name,
                  ar.artist_name AS _album_container_artist
           FROM albums al
           LEFT JOIN artists ar ON ar.artist_id = al.artist_id""",
        conn,
    )


def _track_album_name_lookup(conn: sqlite3.Connection, track_ids) -> dict[int, str]:
    ids = [int(v) for v in pd.Series(track_ids).dropna().unique().tolist()]
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""SELECT t.track_id, al.album_name
              FROM tracks t
              LEFT JOIN albums al ON al.album_id = t.album_id
             WHERE t.track_id IN ({placeholders})""",
        ids,
    ).fetchall()
    return {int(row["track_id"]): row["album_name"] for row in rows if row["album_name"]}


def _album_container_ids(df: pd.DataFrame) -> pd.Series:
    source_ids = (
        pd.to_numeric(df["source_album_id"], errors="coerce")
        if "source_album_id" in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="Float64")
    )
    fallback_column = "track_album_id" if "track_album_id" in df.columns else "album_id"
    fallback_ids = (
        pd.to_numeric(df[fallback_column], errors="coerce")
        if fallback_column in df.columns
        else pd.Series(pd.NA, index=df.index, dtype="Float64")
    )
    return source_ids.fillna(fallback_ids).astype("Int64")


def resolve_period(
    df: pd.DataFrame, period: str, start_date: str | None, end_date: str | None
) -> dict:
    """Resolve a named period to inclusive local-date boundaries."""
    period = period if period in PERIOD_LABELS else "lifetime"
    today = date.today()
    latest_data_date = str(df["ts_date"].max()) if not df.empty else today.isoformat()
    latest_data = date.fromisoformat(latest_data_date)

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
        start = (latest_data - timedelta(days=27)).isoformat()
        end = latest_data.isoformat()
    elif period == "last_6_months":
        start = (latest_data - timedelta(days=182)).isoformat()
        end = latest_data.isoformat()
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


def build_duration_frame(
    df: pd.DataFrame,
    resolved: dict | None = None,
) -> pd.DataFrame:
    """Build duration slices from an explicitly scoped logical-event frame.

    ``DataFrame.attrs`` is intentionally not consulted here.  Pandas preserves
    attrs when filtering a frame, which previously allowed a track, album, or
    artist detail response to inherit the full-library duration slices.
    ``df`` must therefore already be scoped to the entity whose duration is
    being calculated.  The full entity lifetime frame should be supplied when
    a period boundary must retain a slice from a session crossing that
    boundary.
    """
    from backend.domains.playback.logical_timeline import explode_listening_slices

    slices = explode_listening_slices(df, granularity="hour")
    if slices.empty or resolved is None:
        return slices.reset_index(drop=True)
    start = resolved.get("start_date")
    end = resolved.get("end_date")
    if start:
        slices = slices[slices["ts_date"].astype(str) >= str(start)]
    if end:
        slices = slices[slices["ts_date"].astype(str) <= str(end)]
    return slices.reset_index(drop=True)


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
    # Counts belong to logical-event completion time, while duration belongs
    # to the local wall-clock slices where listening occurred. Build slices
    # from the unfiltered timeline so a session crossing a query boundary does
    # not lose the portion on either side.
    duration_slices = build_duration_frame(df, resolved)
    out = out.copy()
    out.attrs["listening_duration_slices"] = duration_slices.reset_index(drop=True)
    return out


def _duration_frame(df: pd.DataFrame, *, granularity: str = "day") -> pd.DataFrame:
    slices = df.attrs.get("listening_duration_slices")
    if isinstance(slices, pd.DataFrame):
        return slices
    from backend.domains.playback.logical_timeline import explode_listening_slices

    return explode_listening_slices(df, granularity=granularity)


def _analysis_weighted_frame(
    df: pd.DataFrame,
    *,
    duration_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Combine event-count rows with independently attributed duration rows."""
    events = df.copy()
    events["play_count"] = 1
    events["total_ms"] = 0
    slices = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="hour")
    )
    if slices.empty:
        events["total_ms"] = pd.to_numeric(events["ms_played"], errors="coerce").fillna(0)
        return events
    slices = slices.copy()
    slices["play_count"] = 0
    slices["total_ms"] = pd.to_numeric(slices["ms_played"], errors="coerce").fillna(0)
    # Slices retain their source event timestamp so first/last-play facts stay
    # tied to counted events rather than inferred interval starts.
    return pd.concat([events, slices], ignore_index=True, sort=False)


def load_period_plays(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    _loader=None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    loader = _loader or load_plays
    df = loader(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
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


def _summary(df: pd.DataFrame, duration_frame: pd.DataFrame | None = None) -> dict:
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="day")
    )
    if df.empty and duration_frame.empty:
        return _zero_summary()
    return {
        "total_plays": int(len(df)),
        "total_hours": round(float(duration_frame["ms_played"].sum() / 3_600_000), 1),
        "unique_tracks": int(df["track_id"].nunique()) if not df.empty else 0,
        "unique_albums": int(df["album_name"].dropna().nunique()) if not df.empty else 0,
        "unique_artists": int(df["artist_name"].dropna().nunique()) if not df.empty else 0,
        "active_days": int(duration_frame["ts_date"].nunique()),
    }


def _daily_metrics(summary: dict) -> dict:
    active_days = max(int(summary["active_days"]), 1)
    return {
        "avg_daily_plays": round(summary["total_plays"] / active_days, 2),
        "avg_daily_hours": round(summary["total_hours"] / active_days, 2),
        "avg_active_day_plays": round(summary["total_plays"] / active_days, 2),
        "avg_active_day_hours": round(summary["total_hours"] / active_days, 2),
    }


def _hourly_distribution(
    df: pd.DataFrame, duration_frame: pd.DataFrame | None = None
) -> list[dict]:
    counts = df.groupby("ts_hour").size() if not df.empty else pd.Series(dtype=int)
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="hour")
    )
    if not duration_frame.empty:
        hours = duration_frame.groupby("ts_hour")["ms_played"].sum() / 3_600_000
    else:
        hours = pd.Series(dtype=float)
    return [
        {"hour": h, "plays": int(counts.get(h, 0)), "hours": round(float(hours.get(h, 0)), 2)}
        for h in range(24)
    ]


def _daily_trend(df: pd.DataFrame, duration_frame: pd.DataFrame | None = None) -> list[dict]:
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="day")
    )
    if df.empty and duration_frame.empty:
        return []
    counts = (
        df.groupby("ts_date").size().rename("plays")
        if not df.empty
        else pd.Series(dtype="int64", name="plays")
    )
    counts.index.name = "ts_date"
    hours = (
        duration_frame.groupby("ts_date")["ms_played"].sum().div(3_600_000).rename("hours")
        if not duration_frame.empty
        else pd.Series(dtype="float64", name="hours")
    )
    daily = pd.concat([counts, hours], axis=1).fillna(0).reset_index().sort_values("ts_date")
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


def _weekday_distribution(
    df: pd.DataFrame, duration_frame: pd.DataFrame | None = None
) -> list[dict]:
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    counts = df.groupby("ts_dow").size() if not df.empty else pd.Series(dtype=int)
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="day")
    )
    if not duration_frame.empty:
        hours = duration_frame.groupby("ts_dow")["ms_played"].sum() / 3_600_000
    else:
        hours = pd.Series(dtype=float)
    return [
        {
            "day": labels[d],
            "plays": int(counts.get(d, 0)),
            "hours": round(float(hours.get(d, 0)), 2),
        }
        for d in range(7)
    ]


def _month_distribution(df: pd.DataFrame, duration_frame: pd.DataFrame | None = None) -> list[dict]:
    counts = df.groupby("ts_month").size() if not df.empty else pd.Series(dtype=int)
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="day")
    )
    if not duration_frame.empty:
        hours = duration_frame.groupby("ts_month")["ms_played"].sum() / 3_600_000
    else:
        hours = pd.Series(dtype=float)
    return [
        {"month": m, "plays": int(counts.get(m, 0)), "hours": round(float(hours.get(m, 0)), 2)}
        for m in range(1, 13)
    ]


def _year_distribution(df: pd.DataFrame, duration_frame: pd.DataFrame | None = None) -> list[dict]:
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="day")
    )
    if df.empty and duration_frame.empty:
        return []
    counts = (
        df.groupby("ts_year").size().rename("plays")
        if not df.empty
        else pd.Series(dtype="int64", name="plays")
    )
    counts.index.name = "ts_year"
    hours = (
        duration_frame.groupby("ts_year")["ms_played"].sum().div(3_600_000).rename("hours")
        if not duration_frame.empty
        else pd.Series(dtype="float64", name="hours")
    )
    yearly = pd.concat([counts, hours], axis=1).fillna(0).reset_index().sort_values("ts_year")
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
    names_map = get_track_artist_names_map()
    rows = df.sort_values("ts", ascending=False).head(limit)
    result = []
    for r in rows.itertuples(index=False):
        track_id = int(r.track_id) if pd.notna(r.track_id) else None
        entry = {
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
        if track_id is not None and track_id in names_map:
            entry["artist_names"] = names_map[track_id]
        result.append(entry)
    return result


def get_analysis_stats(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
) -> dict:
    if conn is not None:
        from backend.services.wrapped_service import _artist_metadata_revision

        return _get_analysis_stats_cached(
            min_ms,
            music_only,
            merge_enabled,
            period,
            start_date,
            end_date,
            dynamic_threshold,
            max_merge_gap_minutes,
            _artist_metadata_revision(conn),
        )


@lru_cache(maxsize=64)
def _get_analysis_stats_cached(
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    artist_metadata_revision: str = "",
) -> dict:
    _ = artist_metadata_revision
    conn = get_db()
    try:
        return _build_analysis_stats(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            period,
            start_date,
            end_date,
            dynamic_threshold,
            max_merge_gap_minutes,
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
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
) -> dict:
    _, df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
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
        "taste_profile": build_consumer_taste_profile(conn, df),
        "recent_plays": recent_plays(conn, df, 50),
    }


def _chart_agg(
    df: pd.DataFrame,
    entity: str,
    conn: sqlite3.Connection | None = None,
    merge_level: int = 2,
    include_compilations: bool = False,
    duration_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    weighted = _analysis_weighted_frame(df, duration_frame=duration_frame)
    if entity == "track":
        df_agg = weighted
        group_cols = ["track_id", "track_name", "artist_name", "album_name"]

        # Apply track group canonicalization before grouping
        if merge_level > 1 and conn is not None:
            from backend.domains.playback.track_groups import load_track_group_keys

            keys = load_track_group_keys(conn, merge_level=merge_level)
            if not keys.empty:
                keys = keys.copy()
                keys["_scope_rank"] = keys["track_group_scope"].map(
                    {"composition": 0, "recording": 1} if merge_level >= 3 else {"recording": 0}
                )
                keys = keys.sort_values(
                    ["track_id", "_scope_rank", "track_agg_id"]
                ).drop_duplicates("track_id")
                key_map = keys.set_index("track_id")
                df_agg["_track_agg_id"] = df_agg["track_id"].map(key_map["track_agg_id"])
                df_agg["_track_agg_name"] = df_agg["track_id"].map(key_map["track_agg_name"])
                mask = df_agg["_track_agg_id"].notna()
                df_agg["track_id"] = df_agg["track_id"].astype("int64", copy=False)
                df_agg.loc[mask, "track_id"] = df_agg.loc[mask, "_track_agg_id"].astype(int)
                df_agg.loc[mask, "track_name"] = df_agg.loc[mask, "_track_agg_name"]
                df_agg = df_agg.drop(columns=["_track_agg_id", "_track_agg_name"])
                # Drop album_name from groupby — canonical tracks span albums
                group_cols = ["track_id", "track_name", "artist_name"]

        return (
            df_agg.groupby(group_cols)
            .agg(
                plays=("play_count", "sum"),
                hours=("total_ms", _hours),
                first_played=("ts", "min"),
                last_played=("ts", "max"),
            )
            .reset_index()
        )
    if entity == "album":
        if conn is not None and merge_level > 1:
            from backend.domains.playback.album_projects import compute_album_project_plays

            project_rows = compute_album_project_plays(
                weighted,
                conn,
                merge_level=merge_level,
                include_compilations=include_compilations,
                billboard_mode=False,
            )
            if project_rows.empty:
                return project_rows
            return project_rows.rename(
                columns={
                    "album_project_id": "album_project_id",
                    "album_project_name": "album_name",
                    "play_count": "plays",
                }
            ).assign(
                hours=lambda x: x["total_ms"] / 3_600_000,
                unique_tracks=lambda x: x["unique_canonical_songs"],
                unique_albums=1,
            )

        df_agg = weighted
        if conn is not None:
            df_agg["_album_container_id"] = _album_container_ids(df_agg)
            identity = _album_identity_lookup(conn)
            identity["_album_container_id"] = identity["_album_container_id"].astype("Int64")
            df_agg = df_agg.merge(identity, on="_album_container_id", how="left")
            df_agg["_album_container_name"] = (
                df_agg["_album_container_name"]
                .fillna(df_agg.get("source_album_name"))
                .fillna(df_agg.get("album_name"))
            )
            df_agg["_album_container_artist"] = df_agg["_album_container_artist"].fillna(
                df_agg["artist_name"]
            )
            return (
                df_agg.groupby(
                    [
                        "_album_container_id",
                        "_album_container_name",
                        "_album_container_artist",
                    ],
                    dropna=False,
                )
                .agg(
                    plays=("play_count", "sum"),
                    hours=("total_ms", _hours),
                    unique_tracks=("track_id", "nunique"),
                    first_played=("ts", "min"),
                    last_played=("ts", "max"),
                )
                .reset_index()
                .rename(
                    columns={
                        "_album_container_id": "album_id",
                        "_album_container_name": "album_name",
                        "_album_container_artist": "artist_name",
                    }
                )
            )
        return (
            df_agg.groupby(["album_name", "artist_name"])
            .agg(
                plays=("play_count", "sum"),
                hours=("total_ms", _hours),
                unique_tracks=("track_id", "nunique"),
                first_played=("ts", "min"),
                last_played=("ts", "max"),
            )
            .reset_index()
        )
    if entity == "artist":
        return (
            weighted.groupby("artist_name")
            .agg(
                plays=("play_count", "sum"),
                hours=("total_ms", _hours),
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
    merge_level: int = 2,
    include_compilations: bool = False,
    duration_frame: pd.DataFrame | None = None,
) -> tuple[int, list[dict]]:
    duration_frame = (
        duration_frame if duration_frame is not None else _duration_frame(df, granularity="hour")
    )
    if df.empty and duration_frame.empty:
        return 0, []
    entity = entity if entity in {"track", "album", "artist"} else "track"
    metric = metric if metric in {"plays", "hours"} else "plays"
    agg = _chart_agg(
        df,
        entity,
        conn=conn,
        merge_level=merge_level,
        include_compilations=include_compilations,
        duration_frame=duration_frame,
    )
    if agg.empty:
        return 0, []

    if metric == "plays":
        agg = agg[pd.to_numeric(agg["plays"], errors="coerce").fillna(0) > 0]
    else:
        agg = agg[pd.to_numeric(agg["hours"], errors="coerce").fillna(0) > 0]
    if agg.empty:
        return 0, []

    # Filter singles + compilations from default album chart (R13/R14)
    if entity == "album" and conn is not None and merge_level <= 1:
        from backend.domains.playback.album_type import is_album_chart_eligible

        agg["_category"] = agg.apply(
            lambda r: _resolve_album_category(conn, r["album_name"], r["artist_name"]), axis=1
        )
        agg = agg[agg["_category"].apply(is_album_chart_eligible)]
        if not include_compilations:
            agg = agg[agg["_category"] != "compilation"]
        agg = agg.drop(columns=["_category"])
    # end filter

    if agg.empty:
        return 0, []

    total_plays = max(int(df.shape[0]), 1)
    total_hours = max(float(duration_frame["ms_played"].sum() / 3_600_000), 0.000001)
    sort_col = "plays" if metric == "plays" else "hours"
    agg = agg.sort_values([sort_col, "plays"], ascending=False).reset_index(drop=True)
    total = int(len(agg))
    sliced = agg.iloc[offset : offset + limit] if limit is not None else agg.iloc[offset:]

    track_covers = (
        _track_cover_urls(conn, sliced["track_id"])
        if entity == "track" and not sliced.empty
        else {}
    )
    track_album_names = (
        _track_album_name_lookup(conn, sliced["track_id"])
        if entity == "track" and conn is not None and not sliced.empty
        else {}
    )
    album_covers = _album_cover_lookup(conn) if entity == "album" else {}
    artist_covers = _artist_cover_lookup(conn) if entity == "artist" else {}
    active_days = max(
        int(duration_frame["ts_date"].nunique()) if not duration_frame.empty else 0,
        1,
    )

    track_names_map = get_track_artist_names_map() if entity == "track" else {}

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
            tid = int(r["track_id"])
            album_name = r.get("album_name", "")
            if pd.isna(album_name):
                album_name = ""
            album_name = str(album_name) if album_name else track_album_names.get(tid, "")
            row.update(
                {
                    "track_id": tid,
                    "track_name": r["track_name"],
                    "artist_name": r["artist_name"],
                    "album_name": album_name,
                    "cover_url": track_covers.get(tid),
                }
            )
            if tid in track_names_map:
                row["artist_names"] = track_names_map[tid]
        elif entity == "album":
            category = (
                _resolve_album_category(conn, r["album_name"], r["artist_name"])
                if conn is not None
                else "unknown"
            )
            row.update(
                {
                    "album_project_id": int(r["album_project_id"])
                    if "album_project_id" in r and pd.notna(r["album_project_id"])
                    else None,
                    "album_name": r["album_name"],
                    "artist_name": r["artist_name"],
                    "unique_tracks": int(r["unique_tracks"]),
                    "unique_albums": int(r["unique_albums"])
                    if "unique_albums" in r and pd.notna(r["unique_albums"])
                    else 1,
                    "cover_url": album_covers.get((r["album_name"], r["artist_name"])),
                    "album_category": category,
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
    merge_level: int = 2,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    include_compilations: bool = False,
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
            merge_level,
            dynamic_threshold,
            max_merge_gap_minutes,
            include_compilations,
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
    merge_level: int = 2,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    include_compilations: bool = False,
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
            merge_level,
            dynamic_threshold,
            max_merge_gap_minutes,
            include_compilations,
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
    merge_level: int = 2,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    include_compilations: bool = False,
) -> dict:
    _, df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    if entity == "artist":
        _, df_artist, _ = load_period_plays(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            period,
            start_date,
            end_date,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            _loader=load_plays_for_artists,
        )
        total, rows = chart_rows(conn, df_artist, entity, metric, limit, offset, merge_level)
    else:
        total, rows = chart_rows(
            conn,
            df,
            entity,
            metric,
            limit,
            offset,
            merge_level,
            include_compilations=include_compilations,
        )
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
