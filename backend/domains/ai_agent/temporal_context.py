"""Temporal grounding helpers for AI Agent planning."""

from __future__ import annotations

import copy
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Shanghai"
_EXPLICIT_YEAR_PATTERN = re.compile(r"(20\d{2}|2100)")
_RECENT_MONTHS_PATTERN = re.compile(r"最近\s*([一二三四五六七八九十\d]+)\s*个?月")
_RECENT_DAYS_PATTERN = re.compile(r"最近\s*([一二三四五六七八九十\d]+)\s*天")
_ANSWER_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？!?；;\n]+")
_DATA_CUTOFF_ANSWER_TOKENS = ("数据截止", "截至", "只覆盖到", "最新播放数据", "播放数据")
_BOUNDED_PERIOD_TOOLS = {
    "analysis_stats",
    "analysis_charts",
    "playback_records",
    "entity_stats",
}
_YEAR_TOOL_NAMES = {"wrapped_yearly"}
_YEAR_BOUND_TOOL_NAMES = {"billboard_entity_detail"}
_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _timezone(value: Any) -> ZoneInfo:
    name = str(value or DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _parse_question_time(raw: Any, timezone_name: str) -> datetime:
    tz = _timezone(timezone_name)
    if isinstance(raw, datetime):
        parsed = raw
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = datetime.now(tz)
    else:
        parsed = datetime.now(tz)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _iso_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def build_temporal_context(
    request: dict[str, Any],
    *,
    data_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the explicit temporal context sent to the planner and final answer."""

    timezone_name = str(request.get("timezone") or DEFAULT_TIMEZONE)
    question_dt = _parse_question_time(request.get("question_time"), timezone_name)
    range_payload = data_range or {}
    data_start_date = _iso_date(range_payload.get("data_start_date"))
    data_end_date = _iso_date(range_payload.get("data_end_date"))
    return {
        "question_time": question_dt.isoformat(),
        "timezone": timezone_name,
        "today": question_dt.date().isoformat(),
        "latest_play_date": data_end_date,
        "data_start_date": data_start_date,
        "data_end_date": data_end_date,
        "relative_time_policy": (
            "今年、去年、上个月、最近、夏天等相对时间以 question_time 为准；"
            "latest_play_date 只表示本地播放数据截止日期。"
        ),
    }


def _parse_chinese_number(value: str) -> int | None:
    text = value.strip()
    if text.isdigit():
        return int(text)
    if text in _CHINESE_NUMBERS:
        return _CHINESE_NUMBERS[text]
    if text.startswith("十") and len(text) == 2:
        tail = _CHINESE_NUMBERS.get(text[1])
        return 10 + tail if tail is not None else None
    if text.endswith("十") and len(text) == 2:
        head = _CHINESE_NUMBERS.get(text[0])
        return head * 10 if head is not None else None
    if "十" in text and len(text) == 3:
        head = _CHINESE_NUMBERS.get(text[0])
        tail = _CHINESE_NUMBERS.get(text[2])
        if head is not None and tail is not None:
            return head * 10 + tail
    return None


def _season_range(year: int, question: str) -> tuple[str, str, str] | None:
    if "夏天" in question or "夏季" in question:
        return f"{year}-06-01", f"{year}-08-31", "夏天"
    if "春天" in question or "春季" in question:
        return f"{year}-03-01", f"{year}-05-31", "春天"
    if "秋天" in question or "秋季" in question:
        return f"{year}-09-01", f"{year}-11-30", "秋天"
    if "冬天" in question or "冬季" in question:
        return f"{year}-12-01", f"{year + 1}-02-28", "冬天"
    if "上半年" in question:
        return f"{year}-01-01", f"{year}-06-30", "上半年"
    if "下半年" in question:
        return f"{year}-07-01", f"{year}-12-31", "下半年"
    return None


def _interpretation_payload(
    *,
    label: str,
    anchor: str,
    start_date: str,
    end_date: str,
    expected_year: int,
    confidence: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": label,
        "anchor_date": anchor,
        "start_date": start_date,
        "end_date": end_date,
        "expected_year": expected_year,
        "confidence": confidence,
    }
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    if start_year != end_year:
        season = label.replace("去年", "").replace("今年", "").replace("本年", "")
        payload["display_label"] = f"{start_year}-{end_year} {season}".strip()
        payload["is_cross_year_season"] = True
    return payload


def infer_time_interpretation(
    question: str,
    temporal_context: dict[str, Any],
) -> dict[str, Any] | None:
    """Infer only high-confidence relative time windows for guardrails."""

    if _EXPLICIT_YEAR_PATTERN.search(question):
        return None
    anchor = _iso_date(temporal_context.get("today"))
    if not anchor:
        return None
    anchor_date = date.fromisoformat(anchor)
    expected_year: int | None = None
    label = ""
    if "去年" in question:
        expected_year = anchor_date.year - 1
        label = "去年"
    elif "今年" in question or "本年" in question:
        expected_year = anchor_date.year
        label = "今年"
    elif "上个月" in question:
        first_this_month = anchor_date.replace(day=1)
        last_previous_month = first_this_month - timedelta(days=1)
        start = last_previous_month.replace(day=1)
        return {
            "label": "上个月",
            "anchor_date": anchor,
            "start_date": start.isoformat(),
            "end_date": last_previous_month.isoformat(),
            "expected_year": last_previous_month.year,
            "confidence": "high",
        }

    recent_months = _RECENT_MONTHS_PATTERN.search(question)
    if recent_months:
        count = _parse_chinese_number(recent_months.group(1))
        if count is not None and 1 <= count <= 24:
            start = anchor_date - timedelta(days=30 * count)
            return _interpretation_payload(
                label=f"最近{recent_months.group(1)}个月",
                anchor=anchor,
                start_date=start.isoformat(),
                end_date=anchor,
                expected_year=anchor_date.year,
                confidence="medium",
            )

    recent_days = _RECENT_DAYS_PATTERN.search(question)
    if recent_days:
        count = _parse_chinese_number(recent_days.group(1))
        if count is not None and 1 <= count <= 366:
            start = anchor_date - timedelta(days=count)
            return _interpretation_payload(
                label=f"最近{recent_days.group(1)}天",
                anchor=anchor,
                start_date=start.isoformat(),
                end_date=anchor,
                expected_year=anchor_date.year,
                confidence="medium",
            )

    if expected_year is None:
        return None

    seasonal = _season_range(expected_year, question)
    if seasonal is not None:
        start_date, end_date, season_label = seasonal
        return _interpretation_payload(
            label=f"{label}{season_label}",
            anchor=anchor,
            start_date=start_date,
            end_date=end_date,
            expected_year=expected_year,
            confidence="high",
        )
    return _interpretation_payload(
        label=label,
        anchor=anchor,
        start_date=f"{expected_year}-01-01",
        end_date=f"{expected_year}-12-31",
        expected_year=expected_year,
        confidence="high",
    )


def _range_label(params: dict[str, Any]) -> str:
    start = params.get("start_date")
    end = params.get("end_date")
    if start or end:
        return f"{start or ''}..{end or ''}"
    period = params.get("period")
    if period:
        return str(period)
    year = params.get("year")
    if year:
        return str(year)
    return ""


def _apply_custom_range(params: dict[str, Any], interpretation: dict[str, Any]) -> bool:
    start = str(interpretation["start_date"])
    end = str(interpretation["end_date"])
    needs_change = (
        params.get("period") != "custom"
        or params.get("start_date") != start
        or params.get("end_date") != end
    )
    if needs_change:
        params["period"] = "custom"
        params["start_date"] = start
        params["end_date"] = end
    return needs_change


def _answer_sentences(answer: str) -> list[str]:
    return [part.strip() for part in _ANSWER_SENTENCE_SPLIT_PATTERN.split(answer) if part.strip()]


def _temporal_sentence_tokens(interpretation: dict[str, Any]) -> tuple[str, ...]:
    label = str(interpretation.get("label") or "")
    tokens = [label] if label else []
    for token in (
        "去年",
        "今年",
        "本年",
        "上个月",
        "最近",
        "夏天",
        "夏季",
        "春天",
        "春季",
        "秋天",
        "秋季",
        "冬天",
        "冬季",
        "上半年",
        "下半年",
    ):
        if token in label:
            tokens.append(token)
    return tuple(dict.fromkeys(token for token in tokens if token))


def _cross_year_sentence_matches_interpretation(
    sentence: str,
    interpretation: dict[str, Any],
) -> bool:
    if interpretation.get("is_cross_year_season") is not True:
        return False
    display_label = str(interpretation.get("display_label") or "")
    start_date = str(interpretation.get("start_date") or "")
    end_date = str(interpretation.get("end_date") or "")
    start_year = start_date[:4]
    end_year = end_date[:4]
    if display_label and display_label in sentence:
        return True
    if start_date and end_date and start_date in sentence and end_date in sentence:
        return True
    if start_year and end_year and start_year != end_year:
        return start_year in sentence and end_year in sentence
    return False


def _year_match_is_data_cutoff(sentence: str, start: int, end: int) -> bool:
    context = sentence[max(0, start - 12) : min(len(sentence), end + 12)]
    return any(token in context for token in _DATA_CUTOFF_ANSWER_TOKENS)


def apply_temporal_guard(
    question: str,
    temporal_context: dict[str, Any],
    plan: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Correct obvious relative-date planning mistakes before tools run."""

    interpretation = infer_time_interpretation(question, temporal_context)
    guarded_plan = copy.deepcopy(plan)
    corrections: list[dict[str, Any]] = []
    if interpretation is None:
        return (
            guarded_plan,
            {
                "time_interpretation": None,
                "had_corrections": False,
                "corrections": [],
            },
        )

    expected_year = interpretation.get("expected_year")
    for item in guarded_plan:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool_name") or "")
        params = item.get("params") if isinstance(item.get("params"), dict) else {}
        before = _range_label(params)
        changed = False
        if tool_name in _BOUNDED_PERIOD_TOOLS and interpretation.get("start_date"):
            changed = _apply_custom_range(params, interpretation)
        elif tool_name in _YEAR_TOOL_NAMES and expected_year is not None:
            if params.get("year") != expected_year:
                params["year"] = expected_year
                changed = True
        elif tool_name in _YEAR_BOUND_TOOL_NAMES and expected_year is not None:
            if params.get("year_start") != expected_year or params.get("year_end") != expected_year:
                params["year_start"] = expected_year
                params["year_end"] = expected_year
                changed = True
        if changed:
            corrections.append(
                {
                    "tool_name": tool_name,
                    "from": before,
                    "to": _range_label(params),
                    "reason": (
                        f"{interpretation['label']} 基于 {interpretation['anchor_date']} "
                        f"应解释为 {interpretation['start_date']}..{interpretation['end_date']}"
                    ),
                }
            )

    return (
        guarded_plan,
        {
            "time_interpretation": interpretation,
            "had_corrections": bool(corrections),
            "corrections": corrections,
        },
    )


def temporal_answer_issues(answer: str, guard: dict[str, Any]) -> list[str]:
    """Validate that final text does not contradict the guarded time window."""

    interpretation = guard.get("time_interpretation") if isinstance(guard, dict) else None
    if not isinstance(interpretation, dict):
        return []
    expected_year = interpretation.get("expected_year")
    if not isinstance(expected_year, int):
        return []
    tokens = _temporal_sentence_tokens(interpretation)
    issues: list[str] = []
    for sentence in _answer_sentences(answer):
        if tokens and not any(token in sentence for token in tokens):
            continue
        if _cross_year_sentence_matches_interpretation(sentence, interpretation):
            continue
        for match in _EXPLICIT_YEAR_PATTERN.finditer(sentence):
            year = int(match.group(1))
            if _year_match_is_data_cutoff(sentence, match.start(), match.end()):
                continue
            if abs(year - expected_year) == 1 and year != expected_year:
                issues.append(
                    f"回答年份 {year} 与 {interpretation['label']}={expected_year} 不一致"
                )
                return issues
    return issues
