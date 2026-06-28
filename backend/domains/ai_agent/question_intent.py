"""Deterministic question-intent hints for the read-only AI Agent planner."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["comparison", "trend", "ranking", "entity_detail", "general"]
EntityType = Literal["track", "album", "artist", "unknown"]

_NAME_PATTERN = re.compile(r"[A-Z][A-Za-z0-9:'’!?.&-]*(?: [A-Za-z0-9][A-Za-z0-9:'’!?.&-]*){0,8}")
_CONNECTOR_SPLIT_PATTERN = re.compile(r"\s+(?:and|vs|v|VS|Vs|V)\s+")
_IGNORED_ENTITIES = {
    "AI",
    "Album",
    "Artist",
    "Billboard",
    "DATA",
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
    if _contains_any(question, ("哪张", "哪个", "哪首", "更", "比较", "vs", "对比")):
        return "comparison"
    if _contains_any(question, ("最近", "趋势", "越来越", "变化", "回升", "下降")):
        return "trend"
    if _contains_any(question, ("排名", "排行", "top", "最高")):
        return "ranking"
    if _contains_any(question, ("分析", "详情", "表现", "成绩")):
        return "entity_detail"
    return "general"


def _time_scope(question: str) -> str:
    if _contains_any(question, ("六个月", "6个月", "半年")):
        return "last_6_months"
    if _contains_any(question, ("今年", "本年", "2026")):
        return "this_year"
    if _contains_any(question, ("最近", "近期")):
        return "last_4_weeks"
    return "lifetime"


def _append_metric(metrics: list[str], metric: str) -> None:
    if metric not in metrics:
        metrics.append(metric)


def _metrics(question: str, time_scope: str) -> list[str]:
    metrics: list[str] = []
    if _contains_any(question, ("播放次数", "播放量", "听了多少", "plays")):
        _append_metric(metrics, "plays")
    if _contains_any(question, ("时长", "小时", "hours")):
        _append_metric(metrics, "hours")
    if _contains_any(question, ("billboard", "榜单", "排名", "冠军")):
        _append_metric(metrics, "personal_billboard")
    if time_scope != "lifetime":
        _append_metric(metrics, "recent_window")
    return metrics or ["summary"]


def _clean_entity(value: str) -> str | None:
    cleaned = value.strip(" \t\r\n,，。？?：:；;（）()[]【】")
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


def _named_entities(question: str) -> list[str]:
    entities: list[str] = []
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
    if _contains_any(question, ("专辑", "album")):
        return "album"
    if _contains_any(question, ("艺人", "歌手", "artist")):
        return "artist"
    if _contains_any(question, ("歌曲", "单曲", "track", "song")):
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
