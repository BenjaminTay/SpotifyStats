"""Hard final-answer obligations derived from deterministic context."""

from __future__ import annotations

from typing import Any

_RELATIVE_TIME_TOKENS = (
    "今年",
    "本年",
    "去年",
    "上个月",
    "最近",
    "近期",
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
)


def _contains_relative_time(question: str) -> bool:
    return any(token in question for token in _RELATIVE_TIME_TOKENS)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _append_once(obligations: list[dict[str, Any]], item: dict[str, Any]) -> None:
    kind = item.get("kind")
    if not kind or any(existing.get("kind") == kind for existing in obligations):
        return
    obligations.append(item)


def build_answer_obligations(
    *,
    question: str,
    question_frame: dict[str, Any],
    temporal_context: dict[str, Any],
    temporal_guard: dict[str, Any],
    evidence_sufficiency: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return deterministic, concise obligations the final answer must satisfy."""

    obligations: list[dict[str, Any]] = []
    frame = _as_dict(question_frame)
    family = str(frame.get("family") or "")
    temporal = _as_dict(temporal_context)
    guard = _as_dict(temporal_guard)
    interpretation = _as_dict(guard.get("time_interpretation"))

    if family == "safety_boundary":
        _append_once(
            obligations,
            {
                "kind": "readonly_refusal",
                "description": "用户请求超出只读查询分析边界时，必须明确拒绝写操作。",
                "required_tokens_any": ["只读", "不能", "无法", "不会"],
                "required_values": [],
            },
        )
        return obligations

    sufficiency = _as_dict(evidence_sufficiency)
    if sufficiency.get("sufficient") is False:
        _append_once(
            obligations,
            {
                "kind": "evidence_limitation",
                "description": "证据不足时必须明确说明限制，不能给出强确定单一结论。",
                "required_tokens_any": [
                    "证据不足",
                    "数据不足",
                    "限制",
                    "无法确定",
                    "只能",
                ],
                "required_values": [],
            },
        )

    latest_play_date = temporal.get("latest_play_date")
    today = temporal.get("today")
    if (
        isinstance(latest_play_date, str)
        and latest_play_date
        and isinstance(today, str)
        and latest_play_date < today
        and (_contains_relative_time(question) or interpretation)
    ):
        _append_once(
            obligations,
            {
                "kind": "data_cutoff",
                "description": "相对时间问题必须说明本地播放数据截止日期，避免把 today 当作数据最新日期。",
                "required_tokens_any": ["数据截止", "截至", "只覆盖到", "最新播放数据"],
                "required_values": [latest_play_date],
            },
        )

    if interpretation.get("is_cross_year_season") is True:
        values = [
            value
            for value in (
                interpretation.get("display_label"),
                interpretation.get("start_date"),
                interpretation.get("end_date"),
            )
            if isinstance(value, str) and value
        ]
        _append_once(
            obligations,
            {
                "kind": "cross_year_season",
                "description": "跨年季节必须使用显示标签或完整日期范围，避免只写单一年份。",
                "required_tokens_any": [],
                "required_values": values,
            },
        )

    if "personal_billboard" in frame.get("analysis_axes", []):
        _append_once(
            obligations,
            {
                "kind": "local_personal_billboard",
                "description": "涉及 Billboard 口径时必须说明这是 SpotifyStats 本地个人榜单。",
                "required_tokens_any": [
                    "个人 Billboard",
                    "个人Billboard",
                    "本地个人榜单",
                    "个人榜单",
                ],
                "required_values": [],
            },
        )

    return obligations
