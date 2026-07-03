"""Narrative brief construction for visual yearly reports."""

from __future__ import annotations

from typing import Any


def build_narrative_brief(context: dict[str, Any]) -> dict[str, Any]:
    period = _dict(context.get("reporting_period"))
    year = period.get("year") or str(period.get("start_date") or "")[:4]
    end_date = str(period.get("end_date") or "")
    is_partial = bool(period.get("is_partial_year"))
    hero = _dict(context.get("hero"))
    top_artists = _list(context.get("top_artists"))
    top_albums = _list(context.get("top_albums"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    discovery = _dict(context.get("discovery_and_returns"))
    genres = _dict(context.get("genre_distribution"))
    highlight = _dict(context.get("highlight_day_detail"))

    lead_artist = _name(top_artists, 0)
    second_artist = _name(top_artists, 1)
    new_artist = _name(_list(discovery.get("new_artists")), 0)
    playback_album = _name(top_albums, 0)
    chart_album = _name(_list(billboard.get("albums")), 0)

    main_story = (
        f"截至 {end_date}，{year} 是一段仍在展开的音乐记录。"
        if is_partial
        else f"{year} 是音乐几乎全年在场的一年。"
    )

    return {
        "is_partial_year": is_partial,
        "main_story": main_story,
        "opening_scene": _opening_scene(hero, is_partial, end_date),
        "companionship_thread": {
            "entity": lead_artist,
            "interpretation": f"{lead_artist} 更像你这一年反复回到的声音。",
            "evidence_refs": ["top_artist_1", "personal_chart_artist_1"],
        },
        "second_thread": {
            "entity": second_artist,
            "interpretation": f"{second_artist} 提供了另一条不同于主线艺人的声音线。",
            "evidence_refs": ["top_artist_2", "genre_mix"],
        },
        "discovery_thread": {
            "entity": new_artist,
            "interpretation": f"{new_artist} 是新出现并留下痕迹的入口。" if new_artist else "",
            "confidence": _discovery_confidence(_list(discovery.get("new_artists"))),
            "evidence_refs": ["new_artist_1"],
        },
        "life_rhythm": {
            "active_days": int(hero.get("active_days") or 0),
            "total_hours": round(float(hero.get("total_minutes") or 0) / 60, 1),
            "interpretation": _life_rhythm(hero, is_partial),
            "tone": "companionate",
        },
        "tensions": _album_tensions(playback_album, chart_album),
        "genre_identity": _genre_identity(genres),
        "highlight_day": {
            "date": highlight.get("date"),
            "interpretation": highlight.get("interpretation_guidance")
            or "这一天更适合被看作一个音乐密度很高的片段。",
        },
        "closing_direction": "下阶段继续观察哪些声音会留下来。"
        if is_partial
        else "这一年最终留下的是陪伴、回望和新入口并存的画像。",
        "safe_speculation_rules": [
            "可以写陪伴、回到、节奏、出口、背景声。",
            "不能编造天气、失眠、分手、考试、旅行等具体事件。",
            "生活推断必须使用像是、更像、也许、这更接近于等克制语气。",
        ],
    }


def _opening_scene(hero: dict[str, Any], is_partial: bool, end_date: str) -> str:
    active_days = int(hero.get("active_days") or 0)
    if is_partial:
        return f"截至 {end_date}，你已经有 {active_days} 个活跃听歌日。"
    return f"{active_days} 个活跃日说明音乐几乎每天都在场。"


def _life_rhythm(hero: dict[str, Any], is_partial: bool) -> str:
    active_days = int(hero.get("active_days") or 0)
    if is_partial:
        return "音乐正在构成这一阶段的日常背景。"
    if active_days >= 330:
        return "音乐几乎贯穿全年生活，不像偶尔打开的娱乐，更像日常节奏的一部分。"
    return "音乐在这一年反复出现，但不是每天都占据中心。"


def _album_tensions(playback_album: str, chart_album: str) -> list[dict[str, Any]]:
    if not playback_album or not chart_album or playback_album == chart_album:
        return []
    return [
        {
            "title": "最常播放和最稳定在榜的专辑不是同一张",
            "playback_leader": playback_album,
            "chart_leader": chart_album,
            "interpretation": "这说明重复聆听和持续在场衡量的是两种不同偏爱。",
            "evidence_refs": ["top_album_1", "personal_chart_album_1"],
        }
    ]


def _genre_identity(genres: dict[str, Any]) -> dict[str, Any]:
    top = _list(genres.get("top_genres"))
    names = [str(row.get("name")) for row in top[:3] if row.get("name")]
    return {
        "top_genres": names,
        "interpretation": "你的音乐地理不只停在单一流行语境里。" if names else "",
        "caveat": genres.get("caveat") or "Spotify 流派标签可能重叠，百分比不互斥。",
    }


def _discovery_confidence(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "low"
    plays = int(rows[0].get("plays") or 0)
    if plays >= 300:
        return "high"
    if plays >= 80:
        return "medium"
    return "low"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _name(rows: list[dict[str, Any]], index: int) -> str:
    if index >= len(rows):
        return ""
    return str(rows[index].get("name") or "")
