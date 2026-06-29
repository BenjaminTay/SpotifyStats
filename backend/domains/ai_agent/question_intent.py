"""Deterministic question-intent hints for the read-only AI Agent planner."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["comparison", "trend", "ranking", "entity_detail", "general"]
EntityType = Literal["track", "album", "artist", "unknown"]

_NAME_PATTERN = re.compile(r"[A-Z][A-Za-z0-9:'’!?.&-]*(?: [A-Za-z0-9][A-Za-z0-9:'’!?.&-]*){0,8}")
_CONNECTOR_SPLIT_PATTERN = re.compile(r"\s+(?:and|vs|v|VS|Vs|V)\s+")
_FORMAT_PREFIX_PATTERN = re.compile(
    r"^(?:请)?用\s*(?:Markdown|markdown)?\s*(?:表格|列表)?\s*(?:来)?(?:比较|对比)\s*"
)
_CONTEXT_ENTITY_PATTERN = re.compile(
    r"(?:我对|对)?"
    r"(?P<left>[^，,。？！?；;：:\n]{1,100}?)"
    r"\s*(?:和|与|and|vs|VS|v)\s*"
    r"(?P<right>[^，,。？！?；;：:\n]{1,100}?)"
    r"(?:这两张专辑|这两个专辑|这两位(?:艺人|歌手)|这两个(?:艺人|歌手)|这两首(?:歌|歌曲|单曲))"
)
_YEAR_PATTERN = re.compile(r"(20\d{2}|2100)")
_IGNORED_ENTITIES = {
    "AI",
    "Album",
    "Artist",
    "Billboard",
    "DATA",
    "Markdown",
    "Song",
    "SpotifyStats",
    "Top",
    "Track",
    "V",
    "VS",
}


class QuestionIntent(BaseModel):
    task_type: TaskType = "general"
    entity_type: EntityType = "unknown"
    entities: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    time_scope: str = "lifetime"
    needs_fairness_note: bool = False


def _contains_any(question: str, tokens: tuple[str, ...]) -> bool:
    lower_question = question.casefold()
    return any(token.casefold() in lower_question for token in tokens)


def _task_type(question: str) -> TaskType:
    has_ranking_signal = _contains_any(
        question,
        (
            "排名",
            "排行",
            "top",
            "最高",
            "最多",
            "最常",
            "最常听",
            "最喜欢",
            "最爱",
            "前十",
            "前 10",
        ),
    )
    has_strong_comparison_signal = bool(_CONTEXT_ENTITY_PATTERN.search(question)) or _contains_any(
        question,
        ("更高", "更低", "更多", "更少", "更喜欢", "更甚", "比较", "vs", "对比"),
    )
    if has_ranking_signal and not has_strong_comparison_signal:
        return "ranking"
    if has_strong_comparison_signal or _contains_any(question, ("哪张", "哪个", "哪首", "更")):
        return "comparison"
    if _contains_any(question, ("最近", "趋势", "越来越", "变化", "回升", "下降")):
        return "trend"
    if has_ranking_signal:
        return "ranking"
    if _contains_any(question, ("分析", "详情", "表现", "成绩")):
        return "entity_detail"
    return "general"


def _time_scope(question: str) -> str:
    if _contains_any(question, ("六个月", "6个月", "半年")):
        return "last_6_months"
    if _contains_any(question, ("今年", "本年", "2026")):
        return "this_year"
    year_match = _YEAR_PATTERN.search(question)
    if year_match:
        return f"year:{year_match.group(1)}"
    if _contains_any(question, ("最近", "近期")):
        return "last_4_weeks"
    return "lifetime"


def _append_metric(metrics: list[str], metric: str) -> None:
    if metric not in metrics:
        metrics.append(metric)


def _metrics(question: str, time_scope: str) -> list[str]:
    metrics: list[str] = []
    if _contains_any(
        question,
        (
            "播放次数",
            "播放量",
            "播放趋势",
            "听了多少",
            "喜欢",
            "喜爱",
            "最爱",
            "爱听",
            "常听",
            "plays",
        ),
    ):
        _append_metric(metrics, "plays")
    if _contains_any(question, ("时长", "小时", "hours")):
        _append_metric(metrics, "hours")
    if _contains_any(question, ("billboard", "榜单", "排名", "冠军")):
        _append_metric(metrics, "personal_billboard")
    if _contains_any(question, ("深夜", "夜晚", "凌晨", "时段", "几点")):
        _append_metric(metrics, "time_of_day")
    if time_scope != "lifetime":
        _append_metric(metrics, "recent_window")
    return metrics or ["summary"]


def _clean_entity(value: str) -> str | None:
    cleaned = value.strip(" \t\r\n,，。？?：:；;（）()[]【】")
    cleaned = _FORMAT_PREFIX_PATTERN.sub("", cleaned).strip()
    for prefix in ("我对", "对"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    tokens = cleaned.split()
    while tokens and tokens[0] in _IGNORED_ENTITIES:
        tokens.pop(0)
    while tokens and tokens[-1] in _IGNORED_ENTITIES:
        tokens.pop()
    if not tokens:
        return None
    cleaned = " ".join(tokens)
    if not cleaned or cleaned in _IGNORED_ENTITIES:
        return None
    if cleaned.casefold() in {"and", "vs", "v"}:
        return None
    return cleaned


def _context_entities(question: str) -> list[str]:
    entities: list[str] = []
    for match in _CONTEXT_ENTITY_PATTERN.finditer(question):
        for group_name in ("left", "right"):
            entity = _clean_entity(match.group(group_name))
            if entity is not None and entity not in entities:
                entities.append(entity)
            if len(entities) >= 4:
                return entities
    return entities


def _named_entities(question: str) -> list[str]:
    entities = _context_entities(question)
    for match in _NAME_PATTERN.findall(question):
        for part in _CONNECTOR_SPLIT_PATTERN.split(match):
            entity = _clean_entity(part)
            if entity is not None and entity not in entities:
                entities.append(entity)
            if len(entities) >= 4:
                return entities
    return entities


def _entity_type(
    question: str,
    *,
    task_type: TaskType,
    entities: list[str],
) -> EntityType:
    if (
        task_type == "ranking"
        and len(entities) == 1
        and _contains_any(question, ("的专辑", "album"))
        and _contains_any(question, ("歌曲", "单曲", "歌是什么", "track", "song"))
    ):
        return "artist"
    if _contains_any(question, ("专辑", "album")):
        return "album"
    if _contains_any(question, ("艺人", "歌手", "artist")):
        return "artist"
    if _contains_any(question, ("歌曲", "单曲", "听什么歌", "哪些歌", "track", "song")):
        return "track"
    if task_type == "trend" and len(entities) == 1:
        return "artist"
    return "unknown"


def parse_question_intent(question: str) -> QuestionIntent:
    task_type = _task_type(question)
    time_scope = _time_scope(question)
    entities = _named_entities(question)
    metrics = _metrics(question, time_scope)
    return QuestionIntent(
        task_type=task_type,
        entity_type=_entity_type(question, task_type=task_type, entities=entities),
        entities=entities,
        requested_metrics=metrics,
        time_scope=time_scope,
        needs_fairness_note=task_type == "comparison" and "personal_billboard" in metrics,
    )
