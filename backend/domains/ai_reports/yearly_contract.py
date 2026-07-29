"""Yearly AI report data contract helpers."""

# ruff: noqa: UP045

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Optional

PERSONALITY_LABELS = {
    "explorer": "探索者",
    "loyalist": "专一者",
    "binger": "能量引擎",
    "night_owl": "夜猫子",
    "collector": "收藏家",
    "trend_chaser": "潮流追踪者",
    "globetrotter": "环球旅人",
}

UNSUPPORTED_SCENE_TERMS = ("下雨", "失眠", "告别", "转折", "崩溃", "治愈了你")


def item_name(item: dict[str, Any], *fallback_keys: str) -> str:
    for key in ("name", *fallback_keys):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def item_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def build_reporting_period(conn: sqlite3.Connection, year: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT min(ts_date) AS start_date,
               max(ts_date) AS end_date,
               count(DISTINCT ts_date) AS active_days
          FROM plays
         WHERE ts_date >= ? AND ts_date <= ?
        """,
        (f"{year}-01-01", f"{year}-12-31"),
    ).fetchone()
    start_date = row["start_date"] if row else None
    end_date = row["end_date"] if row else None
    active_days = int(row["active_days"] or 0) if row else 0
    return _build_reporting_period_payload(year, start_date, end_date, active_days)


def build_reporting_period_from_frame(df, year: int) -> dict[str, Any]:
    """Build reporting period from the effective yearly plays frame."""
    if df is None or getattr(df, "empty", True) or "ts_date" not in df:
        return _build_reporting_period_payload(year, None, None, 0)

    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    dates = sorted(
        {
            date_text
            for value in df["ts_date"].dropna()
            if (date_text := _normalize_date_text(value)) and year_start <= date_text <= year_end
        }
    )
    if not dates:
        return _build_reporting_period_payload(year, None, None, 0)
    return _build_reporting_period_payload(
        year,
        start_date=dates[0],
        end_date=dates[-1],
        active_days=len(dates),
    )


def _build_reporting_period_payload(
    year: int,
    start_date: Optional[str],
    end_date: Optional[str],
    active_days: int,
) -> dict[str, Any]:
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    is_partial = bool(start_date and end_date and (start_date > year_start or end_date < year_end))
    if is_partial and end_date and end_date < year_end:
        label = f"{year} 年截至 {end_date}"
    elif is_partial and start_date:
        label = f"{year} 年自 {start_date} 起"
    else:
        label = f"{year} 年全年"
    return {
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "latest_data_date": end_date,
        "active_days": active_days,
        "days_covered": _inclusive_days(start_date, end_date),
        "is_partial_year": is_partial,
        "label": label,
    }


def _normalize_date_text(value: Any) -> Optional[str]:
    text = str(value)[:10]
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def normalize_top_artists(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    normalized = []
    for index, item in enumerate(items[:limit]):
        name = item_name(item, "artist_name")
        if not name:
            continue
        normalized.append(
            {
                "rank": int(item.get("rank") or index + 1),
                "name": name,
                "plays": int(item.get("plays") or 0),
                "hours": item.get("hours"),
            }
        )
    return normalized


def normalize_top_tracks(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    normalized = []
    for index, item in enumerate(items[:limit]):
        name = item_name(item, "track_name")
        if not name:
            continue
        normalized.append(
            {
                "rank": int(item.get("rank") or index + 1),
                "name": name,
                "artist": item_text(item, "artist_name", "artist"),
                "plays": int(item.get("plays") or 0),
                "hours": item.get("hours"),
            }
        )
    return normalized


def normalize_top_albums(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    normalized = []
    for index, item in enumerate(items[:limit]):
        name = item_name(item, "album_name")
        if not name:
            continue
        normalized.append(
            {
                "rank": int(item.get("rank") or index + 1),
                "name": name,
                "artist": item_text(item, "artist_name", "artist"),
                "plays": int(item.get("plays") or 0),
                "hours": item.get("hours"),
            }
        )
    return normalized


def normalize_new_artists(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    normalized = []
    for item in items[:limit]:
        name = item_name(item, "artist_name")
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "plays": int(item.get("plays") or 0),
                "first_date": item.get("first_date"),
            }
        )
    return normalized


def summarize_personality(personality: dict[str, Any]) -> dict[str, Any]:
    dimensions = personality.get("dimensions") if isinstance(personality, dict) else {}
    rows: list[dict[str, Any]] = []
    if isinstance(dimensions, dict):
        for key, payload in dimensions.items():
            if not isinstance(payload, dict):
                continue
            score = payload.get("score")
            if isinstance(score, (int, float)):
                rows.append(
                    {
                        "key": key,
                        "label": PERSONALITY_LABELS.get(key, key),
                        "score": round(float(score), 1),
                    }
                )
    rows.sort(key=lambda row: row["score"], reverse=True)
    primary_key = personality.get("primary") if isinstance(personality, dict) else None
    primary_label = (
        personality.get("primary_label") if isinstance(personality, dict) else None
    ) or PERSONALITY_LABELS.get(primary_key, "")
    return {
        "primary": primary_key,
        "primary_label": primary_label,
        "top_dimensions": rows[:4],
        "score_label_rule": "score belongs to the same key in top_dimensions; do not attach it to another label.",
    }


def summarize_genres(
    items: list[dict[str, Any]] | dict[str, Any], limit: int = 5
) -> dict[str, Any]:
    coverage = None
    source_hours = None
    caveat = None
    if isinstance(items, dict):
        coverage = items.get("coverage") if isinstance(items.get("coverage"), dict) else None
        if coverage:
            source_hours = (
                coverage.get("source_hours")
                if isinstance(coverage.get("source_hours"), dict)
                else None
            )
        caveat = str(items.get("caveat") or "").strip() or None
        genre_items = items.get("top_genres") if isinstance(items.get("top_genres"), list) else []
    else:
        genre_items = items
    top_genres = []
    for item in genre_items[:limit]:
        name = str(item.get("name") or "")
        if not name:
            continue
        top_genres.append({"name": name, "share": round(float(item.get("play_share") or 0), 1)})
    summary = {
        "top_genres": top_genres,
        "has_other_bucket": any(item["name"] == "其他流派" for item in top_genres),
        "caveat": caveat
        or (
            "canonical genre 是统计标签，可能重叠且可能分属 style/scene/context/role，"
            "百分比不互斥；高占比标签也可能由少数艺人或某个来源驱动。"
        ),
    }
    if coverage:
        summary["coverage"] = coverage
    if source_hours:
        summary["source_hours"] = source_hours
    return summary


def summarize_highlight_strength(
    most_active_day: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not isinstance(most_active_day, dict):
        return None
    top_track = most_active_day.get("top_track")
    if not isinstance(top_track, dict):
        top_track = {}
    top_track_plays = int(top_track.get("plays") or 0)
    day_plays = int(most_active_day.get("plays") or 0)
    share = round(top_track_plays / day_plays * 100, 1) if day_plays else 0.0
    guidance = (
        "当天最高单曲播放不高，不要写成重度单曲循环。"
        if top_track_plays < 8
        else "可以描述为当天有明显单曲重复收听。"
    )
    return {
        **most_active_day,
        "top_track_share_pct": share,
        "interpretation_guidance": guidance,
    }


def summarize_billboard_year_end(
    payload: Optional[dict[str, Any]], limit: int = 5
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _empty_billboard_year_end("personal Billboard Year-End data unavailable.")

    tracks = [
        row
        for index, item in enumerate((payload.get("tracks") or [])[:limit])
        if (row := _normalize_year_end_row(item, "track", index))
    ]
    albums = [
        row
        for index, item in enumerate((payload.get("albums") or [])[:limit])
        if (row := _normalize_year_end_row(item, "album", index))
    ]
    artists = [
        row
        for index, item in enumerate((payload.get("artists") or [])[:limit])
        if (row := _normalize_year_end_row(item, "artist", index))
    ]
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    available = bool(tracks or albums or artists)
    return {
        "available": available,
        "meta": {
            "year": meta.get("year"),
            "total_weeks": meta.get("total_weeks"),
            "score_label": meta.get("score_label") or "Year-End Score",
            "semantics_version": meta.get("semantics_version"),
            "coverage_status": meta.get("coverage_status"),
            "is_complete_year": bool(meta.get("is_complete_year")),
            "period_start": meta.get("period_start"),
            "period_end": meta.get("period_end"),
            "first_billboard_week": meta.get("first_billboard_week"),
            "last_billboard_week": meta.get("last_billboard_week"),
            "observed_weeks": meta.get("observed_weeks"),
            "expected_weeks": meta.get("expected_weeks"),
            "weekly_top_n": meta.get("weekly_top_n"),
            "weekly_album_top_n": meta.get("weekly_album_top_n"),
            "weekly_artist_top_n": meta.get("weekly_artist_top_n"),
        },
        "tracks": tracks,
        "albums": albums,
        "artists": artists,
        "caveat": (
            "这是本地个人 Billboard Year-End，基于用户自己的播放记录计算，"
            "不是外部官方 Billboard 榜单。"
        ),
        "note": "" if available else "personal Billboard Year-End data unavailable.",
    }


def _empty_billboard_year_end(note: str) -> dict[str, Any]:
    return {
        "available": False,
        "meta": {},
        "tracks": [],
        "albums": [],
        "artists": [],
        "caveat": (
            "这是本地个人 Billboard Year-End，基于用户自己的播放记录计算，"
            "不是外部官方 Billboard 榜单。"
        ),
        "note": note,
    }


def _normalize_year_end_row(
    item: dict[str, Any],
    entity_type: str,
    index: int,
) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    if entity_type == "track":
        name = item_name(item, "track_name")
    elif entity_type == "album":
        name = item_name(item, "album_name")
    else:
        name = item_name(item, "artist_name")
    if not name:
        return None

    chart_plays = int(item.get("chart_plays") or 0)
    annual_plays = int(item.get("annual_plays") or item.get("plays") or chart_plays)
    row = {
        "rank": int(item.get("year_end_rank") or item.get("rank") or index + 1),
        "name": name,
        "score": int(item.get("year_end_score") or item.get("score") or 0),
        "peak_position": _optional_int(item.get("peak_position")),
        "weeks_on_chart": int(item.get("weeks_on_chart") or 0),
        "weeks_at_no1": int(item.get("weeks_at_no1") or 0),
        "plays": annual_plays,
        "annual_plays": annual_plays,
        "chart_plays": chart_plays,
    }
    if entity_type in {"track", "album"}:
        row["artist"] = item_text(item, "artist_name", "artist")
    return row


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_writing_constraints(reporting_period: dict[str, Any]) -> list[str]:
    constraints = [
        "所有结论必须基于 DATA，不要编造天气、失眠、告别、人生转折等未提供场景。",
        "如果实体名称存在，必须优先写出具体艺人名和歌曲名。",
        "解释人格分数时必须使用 personality_summary.top_dimensions 中同一行的 label 和 score。",
        "解释流派时必须保留 genre_summary.caveat，不要把 genre 百分比写成互斥类别；如果 caveat 提到少数艺人或来源驱动，必须保守表述。",
    ]
    if reporting_period.get("is_partial_year"):
        constraints.extend(
            [
                f"这是 partial-year report，必须写明数据截至 {reporting_period.get('end_date')}。",
                "不要使用暗示全年已结束的表达，如“这一年已经”“明年”“来年寄语”。",
                "结尾应写“下半年观察”或“接下来”，而不是“来年寄语”。",
            ]
        )
    return constraints


def build_editorial_brief(
    *,
    reporting_period: dict[str, Any],
    top_artists: list[dict[str, Any]],
    top_tracks: list[dict[str, Any]],
    top_albums: list[dict[str, Any]],
    new_artists: list[dict[str, Any]],
    billboard_year_end: dict[str, Any],
    year_over_year: dict[str, Any],
) -> dict[str, Any]:
    lead_artist = _safe_ranked_name(top_artists, 0)
    second_artist = _safe_ranked_name(top_artists, 1)
    new_artist = _safe_ranked_name(new_artists, 0)
    top_album = _safe_ranked_name(top_albums, 0)
    top_track = _safe_ranked_name(top_tracks, 0)

    thesis_parts = []
    if lead_artist:
        thesis_parts.append(f"{lead_artist} 是稳定中心")
    if second_artist:
        thesis_parts.append(f"{second_artist} 贡献另一条主线")
    if new_artist:
        thesis_parts.append(f"{new_artist} 打开今年最清晰的新发现入口")
    thesis = "，".join(thesis_parts) if thesis_parts else "围绕播放强度、探索面和回访行为组织报告。"

    required_angles = [
        "period_cutoff" if reporting_period.get("is_partial_year") else "full_year_period",
        "artist",
        "track",
        "genre",
        "personality",
        "highlight",
    ]
    if top_album:
        required_angles.append("album")
    if billboard_year_end.get("available"):
        required_angles.append("personal_billboard")
    if (year_over_year.get("same_period") or {}).get("available"):
        required_angles.append("same_period_comparison")

    return {
        "thesis": thesis,
        "anchor_entities": {
            "lead_artist": lead_artist,
            "second_artist": second_artist,
            "top_track": top_track,
            "top_album": top_album,
            "new_artist": new_artist,
        },
        "required_angles": required_angles,
        "comparison_summary": _same_period_summary(year_over_year.get("same_period")),
        "writing_guidance": [
            "先用一句 thesis 统领全文，再分维度展开，不要把每个 section 都写成同一种数字复述。",
            "year_over_year.same_period 只允许出现一次，避免在不同小节重复同一组同比数字。",
            "不要用“有意识地”“主动选择”“学会了选择”等词推断用户主观意图，除非 DATA 明确提供。",
        ],
    }


def _safe_ranked_name(items: list[dict[str, Any]], index: int) -> str:
    if index >= len(items):
        return ""
    item = items[index]
    if not isinstance(item, dict):
        return ""
    return item_name(item)


def _same_period_summary(value: Any) -> str:
    if not isinstance(value, dict) or not value.get("available"):
        return ""
    changes = value.get("changes")
    if not isinstance(changes, dict):
        return ""
    fields = [
        ("plays_change", "播放次数"),
        ("hours_change", "时长"),
        ("tracks_change", "曲目数"),
        ("artists_change", "艺人数"),
    ]
    fragments = []
    for key, label in fields:
        metric = changes.get(key)
        if isinstance(metric, (int, float)):
            fragments.append(f"{label}{metric:+.1f}%")
    if not fragments:
        return ""
    return "去年同期同日起止窗口：" + "，".join(fragments) + "。"


def same_day_previous_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def pct_change(new_value: float, old_value: float) -> Optional[float]:
    if old_value == 0:
        return None
    return round((new_value - old_value) / old_value * 100, 1)


def summarize_period_frame(df) -> dict[str, Any]:
    if df.empty:
        return {"hours": 0.0, "plays": 0, "tracks": 0, "artists": 0, "active_days": 0}
    track_col = "track_id" if "track_id" in df else "track_name" if "track_name" in df else None
    return {
        "hours": round(float(df["ms_played"].sum() / 3_600_000), 1) if "ms_played" in df else 0.0,
        "plays": int(len(df)),
        "tracks": int(df[track_col].dropna().nunique()) if track_col else 0,
        "artists": int(df["artist_name"].dropna().nunique()) if "artist_name" in df else 0,
        "active_days": int(df["ts_date"].nunique()) if "ts_date" in df else 0,
    }


def build_same_period_comparison(
    conn: sqlite3.Connection,
    *,
    year: int,
    start_date: Optional[str],
    end_date: Optional[str],
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool,
    max_merge_gap_minutes: Optional[int],
    all_plays_df=None,
) -> Optional[dict[str, Any]]:
    if not end_date:
        return None

    if all_plays_df is None:
        from backend.core.db import load_plays

        all_plays_df = load_plays(
            conn,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
    return build_same_period_comparison_from_frame(
        all_plays_df,
        year=year,
        start_date=start_date,
        end_date=end_date,
    )


def build_same_period_comparison_from_frame(
    all_plays_df,
    *,
    year: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if (
        not end_date
        or all_plays_df is None
        or getattr(all_plays_df, "empty", True)
        or "ts_date" not in all_plays_df
    ):
        return None

    current_start = date.fromisoformat(start_date) if start_date else date(year, 1, 1)
    current_end = date.fromisoformat(end_date)
    previous_start = same_day_previous_year(current_start)
    previous_end = same_day_previous_year(current_end)
    ts_dates = all_plays_df["ts_date"].astype(str).str[:10]

    current_df = all_plays_df[
        (ts_dates >= current_start.isoformat()) & (ts_dates <= current_end.isoformat())
    ]
    previous_df = all_plays_df[
        (ts_dates >= previous_start.isoformat()) & (ts_dates <= previous_end.isoformat())
    ]
    current = summarize_period_frame(current_df)
    previous = summarize_period_frame(previous_df)
    periods = {
        "current_period": {
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
        },
        "previous_period": {
            "start_date": previous_start.isoformat(),
            "end_date": previous_end.isoformat(),
        },
    }
    if previous["plays"] == 0:
        return {
            "mode": "same_period_ytd",
            **periods,
            "current": current,
            "previous": previous,
            "changes": None,
            "available": False,
            "note": "上一年同期数据不足，不应做强对比。",
        }
    return {
        "mode": "same_period_ytd",
        **periods,
        "current": current,
        "previous": previous,
        "changes": {
            "hours_change": pct_change(current["hours"], previous["hours"]),
            "plays_change": pct_change(current["plays"], previous["plays"]),
            "tracks_change": pct_change(current["tracks"], previous["tracks"]),
            "artists_change": pct_change(current["artists"], previous["artists"]),
            "active_days_change": pct_change(current["active_days"], previous["active_days"]),
        },
        "available": True,
        "note": "这是同日起止窗口的 YTD 对比，可用于 partial-year report。",
    }


def _inclusive_days(start_date: Optional[str], end_date: Optional[str]) -> int:
    if not start_date or not end_date:
        return 0
    return (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
