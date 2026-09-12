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
                "quality_dimension": "constraint_compliant",
                "required_claim_types": ["safe_refusal"],
            },
        )
        _append_once(
            obligations,
            {
                "kind": "safe_alternative",
                "description": "安全拒绝必须给出允许的只读替代能力，不能只说做不到。",
                "required_tokens_any": ["只读", "允许", "可以", "你可以", "改为"],
                "required_values": [],
                "quality_dimension": "informative",
                "required_claim_types": ["safe_alternative"],
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
                "quality_dimension": "complete",
                "required_claim_types": ["limitation"],
            },
        )
        _append_once(
            obligations,
            {
                "kind": "no_data_explanation",
                "description": "无数据或证据不足时必须解释缺失边界，而不是只报告查询状态。",
                "required_tokens_any": [
                    "证据不足",
                    "数据不足",
                    "缺少",
                    "未覆盖",
                    "无法确定",
                    "限制",
                ],
                "required_values": [],
                "quality_dimension": "informative",
                "required_claim_types": ["no_data"],
            },
        )

    if sufficiency.get("sufficient") is not False:
        if family in {"simple_ranking", "scoped_ranking", "time_of_day_ranking"}:
            _append_once(
                obligations,
                {
                    "kind": "ranking_result",
                    "description": "排行回答必须给出实际排名实体、排序指标和直接结论。",
                    "required_tokens_any": [
                        "排名",
                        "排行",
                        "第",
                        "Top",
                        "最常",
                        "最高",
                        "播放次数",
                        "播放时长",
                    ],
                    "required_values": [],
                    "quality_dimension": "informative",
                    "required_claim_types": ["ranking"],
                },
            )
        if family in {"preference_comparison", "period_comparison", "identity_preference"}:
            entities = [
                entity
                for entity in frame.get("entities", [])
                if isinstance(entity, str) and entity.strip()
            ]
            _append_once(
                obligations,
                {
                    "kind": "comparison_coverage",
                    "description": "比较回答必须覆盖全部比较对象。",
                    "required_tokens_any": [],
                    "required_values": entities,
                    "quality_dimension": "complete",
                    "required_claim_types": ["comparison"],
                },
            )
            _append_once(
                obligations,
                {
                    "kind": "comparison_conclusion",
                    "description": "比较回答必须给出直接或分口径结论。",
                    "required_tokens_any": [
                        "更高",
                        "更低",
                        "更多",
                        "更少",
                        "领先",
                        "胜出",
                        "占优",
                        "相近",
                        "持平",
                        "不同口径",
                        "更喜欢",
                    ],
                    "required_values": [],
                    "quality_dimension": "informative",
                    "required_claim_types": ["comparison"],
                },
            )
        if family in {"trend_preference", "change_explanation"}:
            _append_once(
                obligations,
                {
                    "kind": "trend_direction",
                    "description": "趋势回答必须说明方向和时间口径。",
                    "required_tokens_any": [
                        "上升",
                        "下降",
                        "增加",
                        "减少",
                        "回升",
                        "回落",
                        "稳定",
                        "持平",
                        "波动",
                    ],
                    "required_values": [],
                    "quality_dimension": "informative",
                    "required_claim_types": ["direction", "time_range"],
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
                "quality_dimension": "constraint_compliant",
                "required_claim_types": ["time_range"],
            },
        )

    if interpretation.get("coverage_clipped") is True:
        effective_start = interpretation.get("effective_start_date")
        effective_end = interpretation.get("effective_end_date")
        effective_values = [
            value for value in (effective_start, effective_end) if isinstance(value, str) and value
        ]
        if len(effective_values) == 2:
            _append_once(
                obligations,
                {
                    "kind": "effective_data_range",
                    "description": (
                        "请求范围超出本地数据覆盖时，必须明确说明实际分析范围，"
                        "不能把未观察到的日期写成已分析范围。"
                    ),
                    "required_tokens_any": ["实际分析范围", "实际数据范围", "只覆盖到"],
                    "required_values": effective_values,
                    "quality_dimension": "constraint_compliant",
                    "required_claim_types": ["time_range"],
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
                "quality_dimension": "constraint_compliant",
                "required_claim_types": ["time_range"],
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
                "quality_dimension": "constraint_compliant",
                "required_claim_types": ["scope_boundary"],
            },
        )

    return obligations
