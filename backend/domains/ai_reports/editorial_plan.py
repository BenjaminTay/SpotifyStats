"""Editorial planning primitives for visual yearly reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EDITORIAL_PLAN_VERSION = "yearly_editorial_v1"

LANGUAGE_BUDGET = {
    "入口": 2,
    "坐标": 1,
    "地图": 1,
    "声音线": 1,
    "情绪线": 1,
    "纹理": 1,
    "陪伴": 4,
    "主线": 3,
    "稳定中心": 0,
}

SECTION_CONTRACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "opening": {
        "required_axes": ("thesis", "period"),
        "forbidden_moves": ("rank_dump", "top_entities_full_list"),
    },
    "year_rhythm": {
        "required_axes": ("life_rhythm",),
        "forbidden_moves": ("repeat_overview_numbers",),
    },
    "main_artist": {
        "required_axes": ("companionship",),
        "forbidden_moves": ("artist_top_five_dump",),
    },
    "second_thread": {
        "required_axes": ("secondary_preference",),
        "forbidden_moves": ("unsupported_language_claim",),
    },
    "turning_point": {
        "required_axes": ("phase_shift",),
        "forbidden_moves": ("vague_trend_without_month",),
    },
    "album_story": {
        "required_axes": ("playback_billboard_relation",),
        "forbidden_moves": ("same_entity_false_contrast",),
    },
    "billboard_divergence": {
        "required_axes": ("playback_billboard_relation",),
        "forbidden_moves": ("same_entity_false_contrast",),
    },
    "highlight_day": {
        "required_axes": ("day_density",),
        "forbidden_moves": ("invent_life_event",),
    },
    "discovery": {
        "required_axes": ("discovery_signal",),
        "forbidden_moves": ("overstate_small_signal",),
    },
    "closing": {
        "required_axes": ("synthesis",),
        "forbidden_moves": ("rank_dump", "empty_watchlist"),
    },
}

DEFAULT_SECTION_ROLES = (
    "opening",
    "main_artist",
    "turning_point",
    "album_story",
    "highlight_day",
    "discovery",
    "closing",
)

HEADING_HINTS = {
    "opening": "先建立这份年报的时间边界和主论点",
    "year_rhythm": "解释音乐如何进入日常节奏",
    "main_artist": "写清楚年度主线声音",
    "second_thread": "呈现第二条偏好线索",
    "turning_point": "解释阶段性变化，而不是复述图表",
    "album_story": "说明播放量和个人 Billboard 的关系",
    "billboard_divergence": "说明播放量和长留榜单的分歧",
    "highlight_day": "记录高密度播放日，但不编造生活事件",
    "discovery": "解释新声音是信号还是支线",
    "closing": "收束为可继续观察的年度音乐画像",
}


@dataclass(frozen=True)
class EditorialFact:
    id: str
    claim: str
    source: str
    home_section_role: str
    allowed_reuse: str
    interpretation_axis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "source": self.source,
            "home_section_role": self.home_section_role,
            "allowed_reuse": self.allowed_reuse,
            "interpretation_axis": self.interpretation_axis,
        }


@dataclass(frozen=True)
class SectionPlan:
    role: str
    heading_hint: str
    owned_fact_ids: tuple[str, ...]
    referenced_fact_ids: tuple[str, ...]
    required_interpretation_axes: tuple[str, ...]
    forbidden_moves: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "heading_hint": self.heading_hint,
            "owned_fact_ids": list(self.owned_fact_ids),
            "referenced_fact_ids": list(self.referenced_fact_ids),
            "required_interpretation_axes": list(self.required_interpretation_axes),
            "forbidden_moves": list(self.forbidden_moves),
        }


@dataclass(frozen=True)
class EditorialPlan:
    version: str
    thesis: str
    facts: tuple[EditorialFact, ...]
    sections: tuple[SectionPlan, ...]
    language_budget: dict[str, int]
    inference_rules: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        section_roles = [section.role for section in self.sections]
        return {
            "version": self.version,
            "thesis": self.thesis,
            "facts": [fact.to_dict() for fact in self.facts],
            "sections": [section.to_dict() for section in self.sections],
            "language_budget": dict(self.language_budget),
            "inference_rules": {key: list(value) for key, value in self.inference_rules.items()},
            "metadata": {
                "editorial_plan_version": self.version,
                "fact_count": len(self.facts),
                "section_roles": section_roles,
            },
        }


def build_editorial_plan(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
    visual: dict[str, Any] | None = None,
) -> EditorialPlan:
    roles = _outline_roles(visual)
    facts = tuple(_build_facts(context, insights, roles))
    sections = tuple(_build_sections(roles, facts))
    thesis = str(
        narrative.get("main_story")
        or insights.get("opening_thesis")
        or "这一年的音乐偏好正在形成。"
    )
    return EditorialPlan(
        version=EDITORIAL_PLAN_VERSION,
        thesis=thesis,
        facts=facts,
        sections=sections,
        language_budget=dict(LANGUAGE_BUDGET),
        inference_rules={
            "allowed": (
                "听歌密度可以解释为日常在场。",
                "月度上升可以解释为阶段性关注增强。",
                "长期在榜可以解释为持续留下。",
            ),
            "forbidden": (
                "不得编造天气、地点、考试、分手、旅行、加班等具体事件。",
                "不得把个人 Billboard 写成外部官方 Billboard。",
                "不得把 Spotify 流派标签写成互斥类别。",
            ),
        },
    )


def _outline_roles(visual: dict[str, Any] | None) -> tuple[str, ...]:
    rows = _list(_dict(visual).get("outline_sections"))
    roles = tuple(
        role
        for role in (str(row.get("role") or "") for row in rows if isinstance(row, dict))
        if role
    )
    return _dedupe(roles) or DEFAULT_SECTION_ROLES


def _build_facts(
    context: dict[str, Any],
    insights: dict[str, Any],
    roles: tuple[str, ...],
) -> list[EditorialFact]:
    facts: list[EditorialFact] = []

    period = _dict(context.get("reporting_period"))
    hero = _dict(context.get("hero"))
    active_days = _int(hero.get("active_days"))
    total_plays = _int(hero.get("total_plays"))
    total_minutes = _int(hero.get("total_minutes"))
    if period or hero:
        year = period.get("year") or _year_from_date(period.get("start_date"))
        end_date = str(period.get("end_date") or "")
        hours = round(total_minutes / 60, 1) if total_minutes else 0
        prefix = f"截至 {end_date}，" if end_date else ""
        year_text = f"{year} " if year else ""
        facts.append(
            EditorialFact(
                id="yearly_overview_density",
                claim=(
                    f"{prefix}{year_text}共有 {active_days} 个活跃听歌日、"
                    f"{total_plays} 次播放，约 {hours} 小时。"
                ),
                source="context.hero",
                home_section_role="opening",
                allowed_reuse="summary",
                interpretation_axis="period",
            )
        )

    top_artist = _first_dict(context.get("top_artists"))
    artist_name = str(insights.get("first_artist") or top_artist.get("name") or "")
    if artist_name:
        plays = _int(top_artist.get("plays"))
        play_text = f"，共 {plays} 次播放" if plays else ""
        facts.append(
            EditorialFact(
                id="top_artist_primary",
                claim=f"{artist_name} 是播放侧最清晰的主线艺人{play_text}。",
                source="context.top_artists[0]",
                home_section_role="main_artist",
                allowed_reuse="summary",
                interpretation_axis="companionship",
            )
        )

    monthly_observation = _first_observation(context, "artist_monthly_trend")
    if monthly_observation:
        facts.append(
            EditorialFact(
                id="artist_monthly_trend_primary_observation",
                claim=monthly_observation,
                source="context.chart_data.artist_monthly_trend.observations[0]",
                home_section_role="turning_point" if "turning_point" in roles else "second_thread",
                allowed_reuse="evidence",
                interpretation_axis="phase_shift",
            )
        )

    album_relation = _dict(insights.get("album_relation"))
    album_home = "album_story" if "album_story" in roles else "billboard_divergence"
    album_claim = str(album_relation.get("claim") or album_relation.get("interpretation") or "")
    if album_claim:
        facts.append(
            EditorialFact(
                id="album_relation_primary",
                claim=album_claim,
                source="insights.album_relation",
                home_section_role=album_home,
                allowed_reuse="summary",
                interpretation_axis="playback_billboard_relation",
            )
        )

    matrix_observation = _first_observation(context, "playback_billboard_matrix")
    if matrix_observation:
        facts.append(
            EditorialFact(
                id="playback_billboard_matrix_primary_observation",
                claim=matrix_observation,
                source="context.chart_data.playback_billboard_matrix.observations[0]",
                home_section_role=album_home,
                allowed_reuse="evidence",
                interpretation_axis="playback_billboard_relation",
            )
        )

    highlight = _dict(insights.get("highlight_day")) or _dict(context.get("highlight_day_detail"))
    highlight_date = str(highlight.get("date") or "")
    highlight_plays = _int(highlight.get("plays"))
    if highlight_date or highlight_plays:
        claim = str(highlight.get("claim") or "")
        if not claim:
            claim = f"{highlight_date} 是播放最密集的一天，共 {highlight_plays} 次。"
        facts.append(
            EditorialFact(
                id="highlight_day_density",
                claim=claim,
                source="insights.highlight_day",
                home_section_role="highlight_day",
                allowed_reuse="summary",
                interpretation_axis="day_density",
            )
        )

    discovery = _dict(insights.get("discovery"))
    if not discovery:
        discovery = _first_dict(_dict(context.get("discovery_and_returns")).get("new_artists"))
    discovery_entity = str(discovery.get("entity") or discovery.get("name") or "")
    if discovery_entity:
        discovery_claim = str(discovery.get("claim") or discovery.get("interpretation") or "")
        if not discovery_claim:
            plays = _int(discovery.get("plays"))
            play_text = f"，累计 {plays} 次播放" if plays else ""
            discovery_claim = f"{discovery_entity} 是这一年出现的新声音{play_text}。"
        facts.append(
            EditorialFact(
                id="discovery_primary",
                claim=discovery_claim,
                source="insights.discovery",
                home_section_role="discovery",
                allowed_reuse="summary",
                interpretation_axis="discovery_signal",
            )
        )

    return facts


def _build_sections(roles: tuple[str, ...], facts: tuple[EditorialFact, ...]) -> list[SectionPlan]:
    section_roles = [role for role in _dedupe(roles) if role in SECTION_CONTRACTS]
    for required in ("opening", "closing"):
        if required not in section_roles:
            section_roles.append(required)

    reusable_fact_ids = tuple(fact.id for fact in facts if fact.allowed_reuse != "none")
    sections: list[SectionPlan] = []
    for role in section_roles:
        contract = SECTION_CONTRACTS[role]
        owned = tuple(fact.id for fact in facts if fact.home_section_role == role)
        referenced = tuple(fact_id for fact_id in reusable_fact_ids if fact_id not in owned)
        sections.append(
            SectionPlan(
                role=role,
                heading_hint=HEADING_HINTS.get(role, role),
                owned_fact_ids=owned,
                referenced_fact_ids=referenced,
                required_interpretation_axes=tuple(contract["required_axes"]),
                forbidden_moves=tuple(contract["forbidden_moves"]),
            )
        )
    return sections


def _first_observation(context: dict[str, Any], chart_key: str) -> str:
    chart = _dict(_dict(context.get("chart_data")).get(chart_key))
    for item in _list(chart.get("observations")):
        text = str(item or "").strip()
        if text:
            return text
    return ""


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return tuple(result)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_dict(value: Any) -> dict[str, Any]:
    for item in _list(value):
        if isinstance(item, dict):
            return item
    return {}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _year_from_date(value: Any) -> str:
    text = str(value or "")
    return text[:4] if len(text) >= 4 else ""
