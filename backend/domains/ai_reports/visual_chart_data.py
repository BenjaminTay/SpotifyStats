"""Deterministic chart data builders for visual yearly reports."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.core.db import get_db
from backend.services.ai_insights_service import _load_yearly_report_plays_frame


def build_visual_chart_data(
    context: dict[str, Any],
    chart_specs: list[dict[str, Any]],
    *,
    plays_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    df = plays_df if plays_df is not None else _load_plays_for_context(context)
    builders = {
        "listening_calendar_heatmap": _calendar_data,
        "artist_monthly_trend": _artist_monthly_trend,
        "album_duality_compare": _album_duality_compare,
        "highlight_day_timeline": _highlight_day_timeline,
        "genre_language_mix": _genre_language_mix,
        "discovery_timeline": _discovery_timeline,
        "playback_billboard_matrix": _playback_billboard_matrix,
    }
    result: dict[str, Any] = {}
    for spec in chart_specs:
        chart_type = str(spec.get("chart_type") or "")
        builder = builders.get(chart_type)
        if builder is None:
            continue
        data = builder(context, spec, df)
        if data:
            result[str(spec["id"])] = data
    return result


def chart_coverage(
    context: dict[str, Any], *, plays_df: pd.DataFrame | None = None
) -> dict[str, bool]:
    df = plays_df if plays_df is not None else _load_plays_for_context(context)
    billboard = _dict(context.get("personal_billboard_year_end"))
    discovery = _dict(context.get("discovery_and_returns"))
    genre = _dict(context.get("genre_distribution"))
    highlight = _dict(context.get("highlight_day_detail"))
    return {
        "listening_calendar": not df.empty and "ts_date" in df.columns,
        "artist_monthly_trend": not df.empty and {"ts_date", "artist_name"}.issubset(df.columns),
        "album_duality_compare": bool(context.get("top_albums")) and bool(billboard.get("albums")),
        "highlight_day_timeline": bool(highlight.get("date")) and not df.empty,
        "genre_language_mix": bool(_dict(genre.get("primary_styles")).get("buckets")),
        "discovery_timeline": bool(discovery.get("new_artists")),
        "playback_billboard_matrix": bool(
            billboard.get("tracks") or billboard.get("albums") or billboard.get("artists")
        ),
    }


def _load_plays_for_context(context: dict[str, Any]) -> pd.DataFrame:
    period = _dict(context.get("reporting_period"))
    year = int(period.get("year") or str(period.get("start_date") or "0")[:4] or 0)
    filters = _dict(context.get("request_filters"))
    conn = get_db(readonly=True)
    try:
        df = _load_yearly_report_plays_frame(
            conn,
            min_ms=_int_filter(filters, "min_ms", 30000),
            music_only=_bool_filter(filters, "music_only", True),
            merge_enabled=_bool_filter(filters, "merge_enabled", True),
            dynamic_threshold=_bool_filter(filters, "dynamic_threshold", True),
            max_merge_gap_minutes=filters.get("max_merge_gap_minutes"),
        )
    finally:
        conn.close()
    if df is None or getattr(df, "empty", True):
        return pd.DataFrame()
    return _filter_report_period(df, period, year)


def _filter_report_period(df: pd.DataFrame, period: dict[str, Any], year: int) -> pd.DataFrame:
    if "ts_date" not in df.columns:
        return df.copy()
    dates = df["ts_date"].astype(str).str[:10]
    start = str(period.get("start_date") or f"{year}-01-01")
    end = str(period.get("end_date") or f"{year}-12-31")
    mask = (dates >= start) & (dates <= end)
    return df.loc[mask].copy()


def _bool_filter(filters: dict[str, Any], key: str, default: bool) -> bool:
    value = filters.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _int_filter(filters: dict[str, Any], key: str, default: int) -> int:
    value = filters.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _calendar_data(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del context, spec
    if df.empty or "ts_date" not in df.columns:
        return {}
    grouped = (
        df.groupby("ts_date", dropna=False)
        .agg(
            plays=("ts_date", "size"),
            minutes=("ms_played", lambda s: round(float(s.sum()) / 60000, 1)),
        )
        .reset_index()
    )
    days: list[dict[str, Any]] = [
        {"date": str(row.ts_date), "plays": int(row.plays), "minutes": float(row.minutes)}
        for row in grouped.itertuples()
    ]
    max_day = max(days, key=lambda row: int(row["plays"])) if days else None
    return {"days": days, "active_days": len(days), "max_day": max_day}


def _artist_monthly_trend(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del context
    entities = [str(name) for name in spec.get("entities") or [] if name]
    if df.empty or not entities or "artist_name" not in df.columns or "ts_date" not in df.columns:
        return {}
    work = df[df["artist_name"].isin(entities)].copy()
    if work.empty:
        return {}
    work["month"] = work["ts_date"].astype(str).str.slice(0, 7)
    rows: list[dict[str, Any]] = []
    for month, group in work.groupby("month"):
        row: dict[str, Any] = {"month": str(month)}
        counts = group.groupby("artist_name").size()
        for entity in entities:
            row[entity] = int(counts.get(entity, 0))
        rows.append(row)
    return {
        "entities": entities,
        "months": rows,
        "observations": _artist_trend_observations(rows, entities),
    }


def _album_duality_compare(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del spec, df
    top_albums = _list(context.get("top_albums"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    chart_albums = _list(billboard.get("albums"))
    if not top_albums or not chart_albums:
        return {}
    playback_name = str(top_albums[0].get("name") or "")
    chart_name = str(chart_albums[0].get("name") or "")
    aligned = bool(
        playback_name
        and chart_name
        and playback_name.strip().casefold() == chart_name.strip().casefold()
    )
    return {
        "playback_leader": top_albums[0],
        "chart_leader": chart_albums[0],
        "relation": "aligned" if aligned else "divergent",
        "interpretation": "播放量和持续在榜指向同一张专辑。"
        if aligned
        else "播放量和持续在榜衡量的是两种不同偏爱。",
    }


def _highlight_day_timeline(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del spec
    highlight = _dict(context.get("highlight_day_detail"))
    date = str(highlight.get("date") or "")
    if not date or df.empty or "ts_date" not in df.columns:
        return {}
    day = df[df["ts_date"].astype(str) == date]
    hourly = []
    if "hour" in day.columns:
        hourly = [
            {"hour": int(hour), "plays": int(count)}
            for hour, count in day.groupby("hour").size().items()
        ]
    top_tracks: list[dict[str, Any]] = []
    if {"track_name", "artist_name"}.issubset(day.columns):
        for (track, artist), count in (
            day.groupby(["track_name", "artist_name"])
            .size()
            .sort_values(ascending=False)
            .head(5)
            .items()
        ):
            top_tracks.append({"name": str(track), "artist": str(artist), "plays": int(count)})
    max_repeats = max((int(row["plays"]) for row in top_tracks), default=0)
    concentration = "high" if max_repeats >= max(8, len(day) * 0.2) else "low"
    return {
        "date": date,
        "total_plays": int(len(day) or highlight.get("plays") or 0),
        "hourly": hourly,
        "top_tracks": top_tracks,
        "repeat_concentration": concentration,
        "observations": _highlight_day_observations(
            date=date,
            total_plays=int(len(day) or highlight.get("plays") or 0),
            max_repeats=max_repeats,
            concentration=concentration,
        ),
    }


def _genre_language_mix(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del spec, df
    genre = _dict(context.get("genre_distribution"))
    primary_styles = _dict(genre.get("primary_styles"))
    return {
        "items": [
            {
                "label": row.get("label"),
                "percent": row.get("share_pct"),
            }
            for row in _list(primary_styles.get("buckets"))
            if row.get("key") != "unknown"
        ],
        "caveat": "主曲风允许多标签，占比以全部可归属有效聆听时长为分母。",
    }


def _discovery_timeline(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del spec, df
    discovery = _dict(context.get("discovery_and_returns"))
    return {"new_artists": _list(discovery.get("new_artists"))}


def _playback_billboard_matrix(
    context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame
) -> dict[str, Any]:
    del spec, df
    billboard = _dict(context.get("personal_billboard_year_end"))
    items = _typed_matrix_items(
        tracks=_list(billboard.get("tracks")),
        albums=_list(billboard.get("albums")),
        artists=_list(billboard.get("artists")),
    )
    return {"items": items[:12], "observations": _matrix_observations(items)}


def _artist_trend_observations(months: list[dict[str, Any]], entities: list[str]) -> list[str]:
    if len(entities) < 2:
        return []
    leader, challenger = entities[0], entities[1]
    for month in months:
        month_name = str(month.get("month") or "")
        leader_value = _to_int(month.get(leader))
        challenger_value = _to_int(month.get(challenger))
        if month_name and challenger_value > leader_value:
            return [
                f"{challenger} 在 {month_name} 达到 {challenger_value} 次，超过 {leader} 的 {leader_value} 次。"
            ]
    return []


def _highlight_day_observations(
    *,
    date: str,
    total_plays: int,
    max_repeats: int,
    concentration: str,
) -> list[str]:
    if not date or total_plays <= 0 or max_repeats <= 0:
        return []
    if concentration == "high":
        return [
            f"{date} 有 {total_plays} 次播放，最高单曲重复 {max_repeats} 次，是围绕少数歌曲的集中重听。"
        ]
    return [
        f"{date} 有 {total_plays} 次播放，但最高单曲只有 {max_repeats} 次，更像多曲目密集漫游。"
    ]


def _typed_matrix_items(
    *,
    tracks: list[dict[str, Any]],
    albums: list[dict[str, Any]],
    artists: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item_type, rows in (("track", tracks), ("album", albums), ("artist", artists)):
        for row in rows:
            item = _matrix_item(row, item_type)
            if item:
                items.append(item)
    return items


def _matrix_item(row: dict[str, Any], item_type: str) -> dict[str, Any]:
    name = row.get("name")
    if not name:
        return {}
    plays = row.get("plays") or row.get("chart_plays")
    weeks_on_chart = row.get("weeks_on_chart")
    item = {
        "name": name,
        "type": item_type,
        "plays": plays,
        "weeks_on_chart": weeks_on_chart,
        "peak_rank": row.get("peak_rank") or row.get("peak_position") or row.get("peak"),
        "rank": row.get("rank"),
    }
    item["chart_profile"] = _matrix_profile(plays=plays, weeks_on_chart=weeks_on_chart)
    return item


def _matrix_profile(*, plays: Any, weeks_on_chart: Any) -> str:
    play_count = _to_int(plays)
    week_count = _to_int(weeks_on_chart)
    if play_count >= 100 and week_count >= 12:
        return "high_play_long_stay"
    if week_count >= 12:
        return "long_stay"
    if play_count >= 100:
        return "short_burst"
    return "limited_signal"


def _matrix_observations(items: list[dict[str, Any]]) -> list[str]:
    observations: list[str] = []
    labels = {
        "track": ("单曲", "作品"),
        "album": ("专辑", "作品"),
        "artist": ("艺人", "对象"),
    }
    for item_type in ("track", "album", "artist"):
        item = next((row for row in items if row.get("type") == item_type), None)
        if not item:
            continue
        name = str(item.get("name") or "")
        type_label, object_label = labels[item_type]
        profile = str(item.get("chart_profile") or "")
        if profile == "high_play_long_stay":
            observations.append(f"{name} 是{type_label}里兼具高播放和长在榜的核心{object_label}。")
        elif profile == "long_stay":
            observations.append(
                f"{name} 是{type_label}里播放不一定最高、但长时间留在个人榜上的{object_label}。"
            )
        elif profile == "short_burst":
            observations.append(
                f"{name} 是{type_label}里播放量突出、但在榜时间更短的爆发型{object_label}。"
            )
    return observations


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]
