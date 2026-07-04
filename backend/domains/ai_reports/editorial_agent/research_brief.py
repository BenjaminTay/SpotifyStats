"""Build research material for the yearly editorial agent."""

from __future__ import annotations

import re
from typing import Any

from backend.domains.ai_reports.editorial_agent.models import (
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
)

FORBIDDEN_INFERENCES = (
    "不能编造通勤、考试、天气、地点、分手、旅行或加班。",
    "不能把个人 Billboard 写成外部官方 Billboard。",
    "不能把 Spotify 流派标签写成互斥类别。",
)


def build_research_brief(context: dict[str, Any]) -> ResearchBrief:
    evidence: list[EvidenceItem] = []
    candidates: list[StoryCandidate] = []
    tensions: list[dict[str, Any]] = []

    period = _dict(context.get("reporting_period"))
    top_artists = _list(context.get("top_artists"))
    top_tracks = _list(context.get("top_tracks"))
    top_albums = _list(context.get("top_albums"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    chart_data = _dict(context.get("chart_data"))

    top_artist = _first(top_artists)
    if top_artist:
        name = _name(top_artist)
        evidence_id = f"top_artist_{_slug(name)}"
        evidence.append(
            EvidenceItem(
                id=evidence_id,
                claim=f"{name} 以 {_int(top_artist.get('plays'))} 次播放位列艺人榜第一。",
                source="top_artists[0]",
                kind="playback_rank",
            )
        )
        candidates.append(
            StoryCandidate(
                id="stable_top_artist",
                title=f"{name} 是最稳定的回访对象",
                why_it_matters="它解释年度重心，而不是只复述艺人榜第一。",
                evidence_refs=(evidence_id,),
                risk_notes=("不能把第一名写成唯一偏好。",),
            )
        )

    monthly_observation = _first_observation(chart_data, "artist_monthly_trend")
    if monthly_observation:
        evidence.append(
            EvidenceItem(
                id="artist_monthly_turning_point",
                claim=monthly_observation,
                source="chart_data.artist_monthly_trend.observations[0]",
                kind="monthly_shift",
            )
        )
        candidates.append(
            StoryCandidate(
                id="monthly_turning_point",
                title="阶段性变化让年度主线不只看累计排名",
                why_it_matters="它能解释某个阶段的偏好变亮，而不是只看全年累计。",
                evidence_refs=("artist_monthly_turning_point",),
                risk_notes=("不能把阶段反超写成全年取代。",),
            )
        )

    top_album = _first(top_albums)
    chart_album = _first(_list(billboard.get("albums")))
    if top_album and chart_album:
        playback_name = _name(top_album)
        chart_name = _name(chart_album)
        aligned = playback_name.casefold() == chart_name.casefold()
        evidence_id = f"album_{_slug(playback_name)}_alignment"
        relation = "对齐" if aligned else "分歧"
        weeks = _int(chart_album.get("weeks_on_chart"))
        evidence.append(
            EvidenceItem(
                id=evidence_id,
                claim=f"{playback_name} 的播放量和个人 Billboard 专辑表现{relation}，个人榜在榜 {weeks} 周。",
                source="top_albums[0]+personal_billboard_year_end.albums[0]",
                kind="playback_billboard_relation",
            )
        )
        candidates.append(
            StoryCandidate(
                id="album_playback_billboard_alignment"
                if aligned
                else "album_playback_billboard_tension",
                title="专辑热度和长留关系值得单独解释",
                why_it_matters="播放量回答当下反复选择，个人 Billboard 回答跨周留下。",
                evidence_refs=(evidence_id,),
                risk_notes=("如果对象相同，不能写成两种不同偏好的冲突。",),
            )
        )
        tensions.append(
            {
                "id": "playback_billboard_album_relation",
                "summary": "播放量和个人 Billboard 专辑榜指向同一对象。"
                if aligned
                else "播放量和个人 Billboard 专辑榜指向不同对象。",
                "evidence_refs": [evidence_id],
            }
        )

    top_track = _first(top_tracks)
    if top_track:
        name = _name(top_track)
        evidence.append(
            EvidenceItem(
                id=f"top_track_{_slug(name)}",
                claim=f"{name} 以 {_int(top_track.get('plays'))} 次播放位列单曲榜第一。",
                source="top_tracks[0]",
                kind="playback_rank",
            )
        )

    highlight = _dict(context.get("highlight_day_detail"))
    if highlight.get("date"):
        top_track_plays = _int(highlight.get("top_track_plays"))
        highlight_claim = f"{highlight.get('date')} 有 {_int(highlight.get('plays'))} 次播放"
        if top_track_plays:
            highlight_claim += f"，最高单曲约 {top_track_plays} 次。"
        else:
            highlight_claim += "，更适合看作播放密度变化。"
        evidence.append(
            EvidenceItem(
                id="highlight_day_density",
                claim=highlight_claim,
                source="highlight_day_detail",
                kind="day_density",
            )
        )
        candidates.append(
            StoryCandidate(
                id="highlight_day_density",
                title="最密集的一天更像播放密度变化",
                why_it_matters="它保留异常日的音乐存在感，但不编造当天发生了什么。",
                evidence_refs=("highlight_day_density",),
                risk_notes=("不能写现实事件，只能写播放密度。",),
            )
        )

    discovery = _first(_list(_dict(context.get("discovery_and_returns")).get("new_artists")))
    if discovery:
        name = _name(discovery)
        first_seen = discovery.get("first_seen") or discovery.get("first_date") or "当前统计期内"
        evidence.append(
            EvidenceItem(
                id="new_artist_discovery",
                claim=f"{name} 首次出现于 {first_seen}，累计 {_int(discovery.get('plays'))} 次播放。",
                source="discovery_and_returns.new_artists[0]",
                kind="discovery",
            )
        )
        candidates.append(
            StoryCandidate(
                id="discovery_signal",
                title=f"{name} 是新声音进入结构的证据",
                why_it_matters="它说明年度记录不只由熟悉对象构成。",
                evidence_refs=("new_artist_discovery",),
                risk_notes=("不能把新发现夸大成全年唯一主角。",),
            )
        )

    return ResearchBrief(
        period=period,
        evidence_ledger=tuple(evidence),
        story_candidates=tuple(candidates),
        tensions=tuple(tensions),
        forbidden_inferences=FORBIDDEN_INFERENCES,
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    while tokens and tokens[0] in {"the", "a", "an"}:
        tokens.pop(0)
    return "_".join(tokens) or "unknown"


def _first_observation(chart_data: dict[str, Any], chart_id: str) -> str:
    observations = _dict(chart_data.get(chart_id)).get("observations")
    if isinstance(observations, list):
        for item in observations:
            text = str(item or "").strip()
            if text:
                return text
    return ""
