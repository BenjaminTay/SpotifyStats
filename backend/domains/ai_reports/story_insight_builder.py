"""Section-level insight builder for visual yearly reports."""

from __future__ import annotations

from typing import Any

CHINESE_GENRE_TERMS = (
    "mandopop",
    "c-pop",
    "cantopop",
    "taiwanese",
    "chinese",
    "华语",
    "粤语",
    "国语",
)


def build_story_insights(context: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic story guidance from local yearly-report evidence."""
    album_relation = _album_relation(context)
    second_thread = _second_thread(context)
    highlight_day = _highlight_day(context)
    discovery = _discovery(context, narrative)
    closing = _closing(context)
    top_track = _track_axis(context)

    return {
        "year_type": _year_type(context),
        "opening_thesis": _opening_thesis(context, narrative),
        "first_artist": _top_name(context, "top_artists", 0),
        "second_artist": second_thread["entity"],
        "second_thread_kind": second_thread["kind"],
        "discovery_artist": discovery["entity"],
        "artist_axis": _artist_axis(context, second_thread),
        "top_album": album_relation["playback_leader"] or album_relation["chart_leader"],
        "album_axis": album_relation["interpretation"],
        "peak_day_axis": highlight_day["interpretation"],
        "top_track_axis": top_track["interpretation"],
        "style_universe": _style_universe(context),
        "time_comparison": _time_comparison(context),
        "closing_watchlist": closing["interpretation"],
        "album_relation": album_relation,
        "second_thread": second_thread,
        "highlight_day": highlight_day,
        "discovery": discovery,
        "top_track": top_track,
        "closing": closing,
    }


def _album_relation(context: dict[str, Any]) -> dict[str, Any]:
    playback_row = _first(_list(context.get("top_albums")))
    chart_row = _first(_list(_dict(context.get("personal_billboard_year_end")).get("albums")))
    playback = _name(playback_row)
    chart = _name(chart_row)
    if not playback and not chart:
        return {
            "mode": "missing",
            "playback_leader": "",
            "chart_leader": "",
            "claim": "专辑偏好证据还不够完整",
            "interpretation": "这一段不适合强行比较专辑。",
        }
    if playback and not chart:
        return {
            "mode": "playback_only",
            "playback_leader": playback,
            "chart_leader": "",
            "claim": f"{playback} 是播放侧最清晰的专辑",
            "interpretation": "目前只能从播放次数判断它的热度，不能补写个人榜单结论。",
        }
    if chart and not playback:
        return {
            "mode": "chart_only",
            "playback_leader": "",
            "chart_leader": chart,
            "claim": f"{chart} 是个人榜单里更稳定留下的专辑",
            "interpretation": "目前只能从个人榜单侧说明它的持续性。",
        }
    if _same_name(playback, chart):
        weeks = chart_row.get("weeks_on_chart")
        week_text = (
            f"，并在个人榜单里停留 {int(weeks)} 周" if isinstance(weeks, (int, float)) else ""
        )
        return {
            "mode": "aligned",
            "playback_leader": playback,
            "chart_leader": chart,
            "claim": f"{playback} 让播放量和个人 Billboard 指向同一个重心并发生重合",
            "interpretation": f"这不是两种偏爱的分裂，而是播放热度与榜单长留指向同一个专辑{week_text}。",
        }
    return {
        "mode": "divergent",
        "playback_leader": playback,
        "chart_leader": chart,
        "claim": f"{playback} 和 {chart} 不完全相同",
        "interpretation": "播放量更像短期高频回到，个人榜单更强调跨周持续和排名稳定。",
    }


def _second_thread(context: dict[str, Any]) -> dict[str, Any]:
    top_artists = _list(context.get("top_artists"))
    second_row = _at(top_artists, 1)
    lead = _name(_at(top_artists, 0))
    second = _name(second_row)
    if not second:
        return {
            "mode": "fallback",
            "kind": "情绪/叙事线",
            "entity": "",
            "claim": "第二条声音线还不明显",
            "interpretation": "这一年更适合围绕主线艺人展开。",
        }
    if _looks_chinese_artist(second_row):
        return {
            "mode": "same_language_family",
            "kind": "华语语境",
            "entity": second,
            "claim": f"{second} 打开了另一条华语语境",
            "interpretation": "这条线索可以和艺人自身的语种/流派证据一起解释，但仍要避免把标签当作互斥分类。",
        }
    if _looks_english_pop_artist(second_row):
        kind = "英文/流行"
        interpretation = (
            "这里更适合写成英文流行里的情绪与叙事支线，不应把全局流派标签套到这个艺人身上。"
        )
    else:
        kind = "情绪/叙事线"
        interpretation = (
            "这里可以写成年度画像里的第二条声音线，但不应强行绑定语种、舞台或怀旧场景。"
        )
    claim = (
        f"{second} 提供了不同于 {lead} 的另一种情绪重心"
        if lead
        else f"{second} 是另一条值得保留的声音线"
    )
    return {
        "mode": "artist_contrast" if lead else "fallback",
        "kind": kind,
        "entity": second,
        "claim": claim,
        "interpretation": interpretation,
    }


def _highlight_day(context: dict[str, Any]) -> dict[str, Any]:
    highlight = _dict(context.get("highlight_day_detail"))
    date = str(highlight.get("date") or "")
    plays = _int(highlight.get("plays"))
    raw_guidance = str(highlight.get("interpretation_guidance") or "")
    if "不高" in raw_guidance or "不要写成" in raw_guidance:
        mode = "multi_track_dense_day"
        interpretation = "这一天更像许多歌曲密集经过，而不是某一首歌支配整天。"
    elif "循环" in raw_guidance:
        mode = "repeat_day"
        interpretation = "这一天有更明显的重复播放特征，可以谨慎写成单曲回到。"
    else:
        mode = "low_confidence"
        interpretation = "这一天的播放密度值得记录，但不适合推断具体生活事件。"
    return {
        "mode": mode,
        "date": date,
        "plays": plays,
        "claim": f"{date} 是播放最密集的一天" if date else "这一年有一个播放密度很高的日子",
        "interpretation": interpretation,
    }


def _discovery(context: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    rows = _list(_dict(context.get("discovery_and_returns")).get("new_artists"))
    first = _first(rows)
    name = _name(first) or str(_dict(narrative.get("discovery_thread")).get("entity") or "")
    plays = _int(first.get("plays")) if first else 0
    first_date = str(first.get("first_date") or "") if first else ""
    if plays >= 300:
        mode = "strong_new_thread"
        interpretation = f"{name} 已经不只是一次尝鲜，而是在这一年形成了清晰的新支线。"
    elif plays >= 80:
        mode = "emerging_signal"
        interpretation = f"{name} 是值得继续观察的新入口，已经留下可见播放痕迹。"
    else:
        mode = "small_signal"
        interpretation = f"{name} 更像一个刚出现的信号，还不适合写成年度主角。"
    return {
        "mode": mode,
        "entity": name,
        "plays": plays,
        "first_date": first_date,
        "claim": f"{name} 是这一年出现的新声音" if name else "这一年的新发现还不够清晰",
        "interpretation": interpretation if name else "新发现证据不足时，章节应降级为简短观察。",
    }


def _track_axis(context: dict[str, Any]) -> dict[str, Any]:
    track_row = _first(_list(context.get("top_tracks")))
    chart_row = _first(_list(_dict(context.get("personal_billboard_year_end")).get("tracks")))
    track = _name(track_row)
    chart = _name(chart_row)
    plays = _int(track_row.get("plays")) if track_row else 0
    if track and chart and _same_name(track, chart):
        interpretation = f"{track} 同时是高频播放和个人榜单里的核心单曲。"
    elif track and chart:
        interpretation = f"{track} 代表播放热度，{chart} 代表个人榜单里的长期位置。"
    elif track:
        interpretation = f"{track} 是播放侧最清晰的单曲信号。"
    elif chart:
        interpretation = f"{chart} 是个人榜单里最清晰的单曲信号。"
    else:
        interpretation = "单曲证据还不够完整，适合降级为简短观察。"
    return {"entity": track or chart, "plays": plays, "interpretation": interpretation}


def _closing(context: dict[str, Any]) -> dict[str, Any]:
    period = _dict(context.get("reporting_period"))
    discovery = _name(_first(_list(_dict(context.get("discovery_and_returns")).get("new_artists"))))
    second = _top_name(context, "top_artists", 1)
    if period.get("is_partial_year"):
        watchlist = [item for item in (second, discovery) if item]
        watch_text = "、".join(watchlist) if watchlist else "哪些声音会留下来"
        return {
            "mode": "partial_year",
            "claim": "这还是一份阶段性年记",
            "interpretation": f"下阶段更适合继续观察 {watch_text}，而不是把半年的证据写成全年定论。",
        }
    return {
        "mode": "full_year",
        "claim": "这一年已经形成完整轮廓",
        "interpretation": "可以收束为陪伴、回到和新入口并存的年度画像。",
    }


def _year_type(context: dict[str, Any]) -> str:
    return (
        "partial_year"
        if _dict(context.get("reporting_period")).get("is_partial_year")
        else "full_year"
    )


def _opening_thesis(context: dict[str, Any], narrative: dict[str, Any]) -> str:
    main_story = str(narrative.get("main_story") or "")
    if main_story:
        return main_story
    period = _dict(context.get("reporting_period"))
    year = period.get("year") or str(period.get("start_date") or "")[:4] or "这一年"
    if period.get("is_partial_year"):
        end_date = period.get("end_date")
        return (
            f"截至 {end_date}，{year} 是一段仍在展开的音乐记录。"
            if end_date
            else f"{year} 是一段仍在展开的音乐记录。"
        )
    return f"{year} 是音乐稳定在场的一年。"


def _artist_axis(context: dict[str, Any], second_thread: dict[str, Any]) -> str:
    lead = _top_name(context, "top_artists", 0)
    second = str(second_thread.get("entity") or "")
    if lead and second:
        return f"{lead} 是年度主线，{second} 提供第二条{second_thread.get('kind') or '声音'}。"
    if lead:
        return f"{lead} 是年度最清晰的艺人主线。"
    return "艺人主线证据还不够完整。"


def _style_universe(context: dict[str, Any]) -> str:
    genres = [
        str(row.get("name"))
        for row in _list(_dict(context.get("genre_distribution")).get("top_genres"))[:3]
        if row.get("name")
    ]
    if not genres:
        return "流派/语种证据不足，不能强行外推风格宇宙。"
    return f"主要风格标签包括 {'、'.join(genres)}，但这些是全局语境，不能直接套到单个艺人身上。"


def _time_comparison(context: dict[str, Any]) -> str:
    hero = _dict(context.get("hero"))
    active_days = _int(hero.get("active_days"))
    plays = _int(hero.get("total_plays"))
    minutes = _int(hero.get("total_minutes"))
    if active_days or plays or minutes:
        return "活跃日、播放次数和聆听时长构成时间侧证据。"
    return "时间侧证据不足，适合保守描述。"


def _looks_chinese_artist(row: dict[str, Any]) -> bool:
    name = _name(row)
    if any("\u4e00" <= char <= "\u9fff" for char in name):
        return True
    local_terms = _artist_terms(row)
    return any(term in local_terms for term in CHINESE_GENRE_TERMS)


def _looks_english_pop_artist(row: dict[str, Any]) -> bool:
    terms = _artist_terms(row)
    return any(term in terms for term in ("pop", "english", "us", "uk", "american"))


def _artist_terms(row: dict[str, Any]) -> str:
    fields: list[str] = []
    for key in ("genre", "language", "country", "locale"):
        value = row.get(key)
        if value:
            fields.append(str(value))
    genres = row.get("genres")
    if isinstance(genres, list):
        fields.extend(str(item) for item in genres)
    elif genres:
        fields.append(str(genres))
    return " ".join(fields).lower()


def _same_name(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _at(rows: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return rows[index] if index < len(rows) else {}


def _name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "")


def _top_name(context: dict[str, Any], key: str, index: int) -> str:
    return _name(_at(_list(context.get(key)), index))


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
