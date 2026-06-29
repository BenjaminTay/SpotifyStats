"""Bounded read-only AI chat agent runner."""

from __future__ import annotations

import json
from typing import Any

from backend.core.db import get_db
from backend.domains.ai_agent.analytical_brief import build_analytical_brief
from backend.domains.ai_agent.answer_critic import critique_answer
from backend.domains.ai_agent.coverage_review import review_evidence_sufficiency
from backend.domains.ai_agent.evidence import compact_evidence_cards
from backend.domains.ai_agent.evidence_builders import build_evidence_cards
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.project_context import (
    PROJECT_CONTEXT_VERSION,
    build_final_answer_system_prompt,
    build_planner_system_prompt,
    project_context_payload,
)
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.domains.ai_agent.tool_registry import describe_for_model, dispatch_tool
from backend.domains.ai_tasks.repository import AiTaskRepository
from backend.services import ai_insights_service

MAX_TOOL_CALLS = 8
MAX_COVERAGE_REVIEW_ROUNDS = 2
FINAL_LLM_FAILURE_MESSAGE = "LLM 未配置或调用失败，无法生成回答"
TERMINAL_STATUSES = {"done", "error", "cancelled"}

BASE_PLANNER_SYSTEM_PROMPT = """你是 SpotifyStats 的只读数据工具规划器。
你只能选择后端提供的 read_only 工具，不要编造工具名、SQL、URL 或 API route。
所有 Billboard 工具都表示用户本地播放数据计算出的个人榜单，不是外部官方 Billboard 或市场成绩。
返回 ONLY JSON 数组，每项形如 {"tool_name":"analysis_stats","params":{...}}。
最多返回 8 个工具调用。
DATA.question_intent 是系统给出的结构化提示。
DATA.question_frame 是硬约束，family 决定问题类型，analysis_axes 决定必须覆盖的证据维度。
DATA.evidence_recipe 是最低证据要求；规划工具时优先满足 required_axes 和 required_tool_patterns。
如果 family=preference_comparison，必须优先使用 compare_entities，并尽量补 last_6_months 或 last_4_weeks 的 entity_stats。
如果 family=trend_preference，不得只查询 lifetime。
如果 family=time_of_day_ranking，必须使用 listening_hours 且 view=late_night_tracks。
如果 task_type=comparison 且 compare_entities 出现在 available_tools，优先调用 compare_entities；2-4 个同类实体比较不要拆成大量单实体工具。
如果问题点名比较歌曲、专辑或艺人，优先同时查询 entity_stats 与 billboard_entity_detail。
如果 task_type=comparison 且 entities 非空，必须为每个实体查询比较所需工具。
如果 family=scoped_ranking，必须优先调用 entity_stats，并使用 scope_entity_type/scope_entity_name 对应的指定范围；不要用全局 Top10 代替范围内排行。
如果 requested_metrics 包含 personal_billboard，必须使用 available_tools 中的 billboard_entity_detail 或 compare_entities。
如果 time_scope 不是 lifetime，至少一个工具调用必须使用对应 period 或自定义窗口。
如果 thinking_mode=true，请优先规划 2-4 个互补工具用于交叉核对，例如总体统计、排行、记录或听歌时段。"""

BASE_FINAL_ANSWER_SYSTEM_PROMPT = """你是友好的 Spotify 听歌数据助手。
只基于 DATA 中的工具结果回答用户问题。不要声称访问了 DATA 之外的数据。
DATA.coverage 是硬约束：coverage 标记为 found 的实体或榜单，不得说缺少、未查询或无法比较。
DATA.question_frame.family 决定回答形状，DATA.answer_contract 或 DATA.analytical_brief.answer_contract 是硬约束。
DATA.analytical_brief 是回答底稿；必须覆盖 must_explain，不得出现 forbidden_claims。
DATA.answer_style 是硬约束，用来决定回答长短和结构。
如果 DATA.answer_style.style=concise，用 3-6 句或最多 3 个 bullet 直接回答；不要输出「我查了什么」「依据」「自检与限制」等固定小节，除非证据不足。
如果 DATA.answer_style.style=structured，可使用少量小节或列表，但仍要围绕结论、关键数字和必要限制，不要写工具调用流水账。
如果 DATA.answer_style.style=detailed，才可以展开为较完整的分析、表格或依据说明。
如果 DATA.evidence_sufficiency.sufficient=false，必须说明缺失证据和限制，避免给出确定性单一结论。
如果 DATA.analytical_brief.conflict=true，必须分层回答，不要说所有指标都指向同一个对象。
SpotifyStats Billboard 是本地个人榜单，不能把它表述成外部官方 Billboard、市场影响力或权威商业成绩。
如果 answer_contract=scoped_ranking_answer，主结论必须来自 entity_stats 的 top_albums/top_tracks；按播放次数说明专辑和歌曲，可补充时长或近期窗口；top_albums/top_tracks 里的 share_pct 表示播放次数占比，不是时长占比；不要用 billboard_entity_detail 或全局 analysis_charts 替代主依据。
比较多个对象时，不要只看单一累计值；如果发行时间、数据窗口或统计口径影响公平性，要主动说明。
用中文回答，引用关键数字；如果工具结果不足，直接说明限制。"""

BASE_THINKING_FINAL_ANSWER_SYSTEM_PROMPT = """你是友好的 Spotify 听歌数据助手。
只基于 DATA 中的工具结果回答用户问题。不要声称访问了 DATA 之外的数据。
思考模式已开启：请输出可见分析摘要，而不是逐字内部思维链。
DATA.coverage 是硬约束：coverage 标记为 found 的实体或榜单，不得说缺少、未查询或无法比较。
DATA.question_frame.family 决定回答形状，DATA.answer_contract 或 DATA.analytical_brief.answer_contract 是硬约束。
DATA.analytical_brief 是回答底稿；必须覆盖 must_explain，不得出现 forbidden_claims。
DATA.answer_style 是硬约束；思考模式只表示工具核对更充分，不表示回答必须变长。
如果 DATA.answer_style.style=concise，用 3-6 句或最多 3 个 bullet 直接回答；不要输出「我查了什么」「依据」「自检与限制」等固定小节，除非证据不足。
如果 DATA.answer_style.style=structured，可使用少量小节或列表，但仍要围绕结论、关键数字和必要限制，不要写工具调用流水账。
如果 DATA.answer_style.style=detailed，才可以展开为较完整的分析、表格或依据说明。
如果 DATA.evidence_sufficiency.sufficient=false，必须说明缺失证据和限制，避免给出确定性单一结论。
如果 DATA.analytical_brief.conflict=true，必须分层回答，不要说所有指标都指向同一个对象。
SpotifyStats Billboard 是本地个人榜单，不能把它表述成外部官方 Billboard、市场影响力或权威商业成绩。
如果 answer_contract=scoped_ranking_answer，主结论必须来自 entity_stats 的 top_albums/top_tracks；按播放次数说明专辑和歌曲，可补充时长或近期窗口；top_albums/top_tracks 里的 share_pct 表示播放次数占比，不是时长占比；不要用 billboard_entity_detail 或全局 analysis_charts 替代主依据。
比较多个对象时，不要只看单一累计值；如果发行时间、数据窗口或统计口径影响公平性，要主动说明。
用中文回答，引用关键数字；如果工具结果不足，直接说明限制。"""

PLANNER_SYSTEM_PROMPT = build_planner_system_prompt(BASE_PLANNER_SYSTEM_PROMPT)
FINAL_ANSWER_SYSTEM_PROMPT = build_final_answer_system_prompt(BASE_FINAL_ANSWER_SYSTEM_PROMPT)
THINKING_FINAL_ANSWER_SYSTEM_PROMPT = build_final_answer_system_prompt(
    BASE_THINKING_FINAL_ANSWER_SYSTEM_PROMPT,
    thinking_mode=True,
)


class ChatAgentError(RuntimeError):
    """Raised for expected chat-agent execution failures."""


def _set_stage(
    repo: AiTaskRepository,
    *,
    task_id: str,
    stage: str,
    progress_pct: float,
    message: str,
    event_type: str = "stage_started",
    payload: dict[str, Any] | None = None,
) -> bool:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="running",
        stage=stage,
        progress_pct=progress_pct,
        message=message,
    )
    if not updated:
        return False
    repo.add_event(
        task_id=task_id,
        event_type=event_type,
        stage=stage,
        message=message,
        payload=payload,
    )
    return True


def _is_terminal(repo: AiTaskRepository, task_id: str) -> bool:
    task = repo.get_run(task_id)
    return task is None or task.get("status") in TERMINAL_STATUSES


def _mark_done(
    repo: AiTaskRepository,
    *,
    task_id: str,
    message: str,
    result: dict[str, Any],
) -> None:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="done",
        stage="done",
        progress_pct=1.0,
        message=message,
        result=result,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="result_ready",
        stage="done",
        message=message,
        payload={"tool_call_count": result.get("tool_call_count", 0)},
    )


def _mark_error(
    repo: AiTaskRepository,
    *,
    task_id: str,
    message: str,
    result: dict[str, Any] | None = None,
) -> None:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="error",
        stage="error",
        progress_pct=1.0,
        message=message,
        result=result,
        error=message,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="stage_failed",
        stage="error",
        message=message,
        payload=result or {"error": message},
    )


def _base_filter_params(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "min_ms": request.get("min_ms", 30000),
        "music_only": request.get("music_only", True),
        "merge_enabled": request.get("merge_enabled", True),
        "dynamic_threshold": request.get("dynamic_threshold", True),
        "max_merge_gap_minutes": request.get("max_merge_gap_minutes"),
    }


def _thinking_mode_enabled(request: dict[str, Any]) -> bool:
    return bool(request.get("thinking_mode"))


_DETAILED_ANSWER_TOKENS = (
    "详细",
    "完整",
    "全面",
    "展开",
    "深度",
    "报告",
    "依据",
    "证据",
    "过程",
    "自检",
    "限制",
    "为什么",
    "原因",
    "解释",
)

_STRUCTURED_ANSWER_TOKENS = (
    "比较",
    "对比",
    "维度",
    "表格",
    "markdown",
    "列出",
    "排行",
    "排名",
    "前十",
    "top",
)

_STRUCTURED_DEFAULT_FAMILIES = {
    "preference_comparison",
    "identity_preference",
    "period_comparison",
    "change_explanation",
    "trend_preference",
}


def _question_contains_any(question: str, tokens: tuple[str, ...]) -> bool:
    lowered = question.casefold()
    return any(token.casefold() in lowered for token in tokens)


def _answer_style_payload(style: str, *, evidence_sufficient: bool) -> dict[str, Any]:
    if style == "detailed":
        return {
            "style": "detailed",
            "allow_sections": True,
            "max_sections": 5,
            "instruction": "用户明确要求详细时，给完整分析、关键数字和必要限制。",
        }
    if style == "structured":
        return {
            "style": "structured",
            "allow_sections": True,
            "max_sections": 3,
            "avoid_sections": ["我查了什么", "工具调用过程"],
            "instruction": "用短小结构回答复杂问题，保留结论、关键数字和必要限制。",
            "must_include_limitations": not evidence_sufficient,
        }
    return {
        "style": "concise",
        "allow_sections": False,
        "max_sentences": 6,
        "max_bullets": 3,
        "avoid_sections": ["我查了什么", "依据", "自检与限制", "工具调用过程"],
        "instruction": "直接回答用户问题，再补最关键的数字；只有证据不足时才补限制。",
        "must_include_limitations": not evidence_sufficient,
    }


def _answer_style(
    request: dict[str, Any],
    *,
    question_frame: dict[str, Any],
    evidence_sufficiency: dict[str, Any],
) -> dict[str, Any]:
    question = str(request.get("question") or "")
    evidence_sufficient = bool(evidence_sufficiency.get("sufficient", True))
    if not evidence_sufficient:
        return _answer_style_payload("structured", evidence_sufficient=evidence_sufficient)
    if _question_contains_any(question, _DETAILED_ANSWER_TOKENS):
        return _answer_style_payload("detailed", evidence_sufficient=evidence_sufficient)

    family = str(question_frame.get("family") or "")
    if family in _STRUCTURED_DEFAULT_FAMILIES:
        return _answer_style_payload("structured", evidence_sufficient=evidence_sufficient)
    if _question_contains_any(question, _STRUCTURED_ANSWER_TOKENS):
        return _answer_style_payload("structured", evidence_sufficient=evidence_sufficient)
    return _answer_style_payload("concise", evidence_sufficient=evidence_sufficient)


def _question_context(request: dict[str, Any]) -> dict[str, Any]:
    question = str(request.get("question", ""))
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    recipe = recipe_for_frame(frame)
    return {
        "question_intent": intent.model_dump(),
        "question_frame": frame.model_dump(),
        "evidence_recipe": recipe.model_dump(),
    }


def _thinking_fallback_plan(request: dict[str, Any]) -> list[dict[str, Any]]:
    base = _base_filter_params(request)
    merge_level = request.get("merge_level", 1)
    return [
        {"tool_name": "analysis_stats", "params": {**base, "period": "this_year"}},
        {
            "tool_name": "analysis_charts",
            "params": {
                **base,
                "period": "this_year",
                "entity": "artist",
                "metric": "plays",
                "limit": 10,
                "merge_level": merge_level,
            },
        },
        {
            "tool_name": "listening_hours",
            "params": {**base, "view": "platform_hourly"},
        },
    ]


def _fallback_plan(request: dict[str, Any]) -> list[dict[str, Any]]:
    if _thinking_mode_enabled(request):
        return _thinking_fallback_plan(request)
    return [{"tool_name": "analysis_stats", "params": _base_filter_params(request)}]


def _compact_json(value: Any, *, limit: int = 12000) -> str:
    rendered = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(rendered) <= limit:
        return rendered
    return rendered[:limit] + "...[truncated]"


def _raw_params_summary(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    rendered = json.dumps(params, ensure_ascii=False, default=str)
    return rendered[:500]


def _tool_call_identity(tool_call: dict[str, Any]) -> tuple[str, str]:
    params = tool_call.get("params") if isinstance(tool_call.get("params"), dict) else {}
    identity_keys = (
        "entity",
        "track_id",
        "album_name",
        "artist_name",
        "track_name",
        "names",
        "query",
        "entity_type",
        "period",
        "view",
        "metric",
        "start_date",
        "end_date",
        "min_ms",
        "music_only",
        "merge_enabled",
        "dynamic_threshold",
        "max_merge_gap_minutes",
        "merge_level",
        "year_start",
        "year_end",
    )
    identity_params = {key: params[key] for key in identity_keys if key in params}
    names = identity_params.get("names")
    if isinstance(names, list):
        identity_params["names"] = sorted(str(name) for name in names)
    if not identity_params:
        identity_params = params
    return (
        str(tool_call.get("tool_name") or ""),
        json.dumps(identity_params, ensure_ascii=False, sort_keys=True, default=str),
    )


def _execute_tool_call(
    repo: AiTaskRepository,
    *,
    task_id: str,
    tool_call: dict[str, Any],
    index: int,
    progress_pct: float,
) -> dict[str, Any] | None:
    tool_name = str(tool_call["tool_name"])
    params = tool_call.get("params") if isinstance(tool_call.get("params"), dict) else {}
    if not _set_stage(
        repo,
        task_id=task_id,
        stage="calling_tool",
        progress_pct=progress_pct,
        message=f"正在调用只读工具：{tool_name}",
        payload={"tool_name": tool_name, "index": index},
    ):
        return None
    try:
        result = dispatch_tool(tool_name, params)
    except Exception as exc:
        if _is_terminal(repo, task_id):
            return None
        error_message = str(exc) or exc.__class__.__name__
        repo.add_tool_call(
            task_id=task_id,
            tool_name=tool_name,
            status="error",
            params_summary=_raw_params_summary(params),
            result_summary="",
            source_range="",
            error=error_message,
        )
        return {
            "tool_name": tool_name,
            "status": "error",
            "params_summary": _raw_params_summary(params),
            "error": error_message,
        }

    if _is_terminal(repo, task_id):
        return None
    repo.add_tool_call(
        task_id=task_id,
        tool_name=result["tool_name"],
        status="done",
        params_summary=result.get("params_summary", ""),
        result_summary=result.get("result_summary", ""),
        source_range=result.get("source_range", ""),
        error=None,
    )
    return {
        "tool_name": result["tool_name"],
        "status": "done",
        "params_summary": result.get("params_summary", ""),
        "result_summary": result.get("result_summary", ""),
        "source_range": result.get("source_range", ""),
        "data": result.get("data"),
    }


def _prepare_followup_tool_call(
    followup: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any] | None:
    prepared = _sanitize_plan([followup], request)
    return prepared[0] if prepared else None


def _extract_json_array(raw: str | None) -> list[Any] | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _sanitize_plan(raw_items: list[Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    default_filters = _base_filter_params(request)
    merge_level = request.get("merge_level", 1)
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        tool_name = item.get("tool_name") or item.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            continue
        params = item.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        merged_params = {**default_filters, **params}
        if tool_name in {
            "analysis_charts",
            "playback_records",
            "entity_stats",
            "billboard_entity_detail",
            "compare_entities",
            "wrapped_yearly",
        }:
            merged_params.setdefault("merge_level", merge_level)
        plan.append({"tool_name": tool_name, "params": merged_params})
        if len(plan) >= MAX_TOOL_CALLS:
            break
    return plan


def _augment_plan_for_thinking_mode(
    plan: list[dict[str, Any]],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    if not _thinking_mode_enabled(request):
        return plan
    augmented = list(plan)
    existing = {item["tool_name"] for item in augmented}
    for item in _thinking_fallback_plan(request):
        if len(augmented) >= 3:
            break
        if item["tool_name"] in existing:
            continue
        augmented.append(item)
        existing.add(item["tool_name"])
    return augmented[:MAX_TOOL_CALLS]


def _planner_user_content(request: dict[str, Any]) -> str:
    question = str(request.get("question", ""))
    context = _question_context(request)
    payload = {
        "question": question,
        **context,
        "conversation_history": (request.get("conversation_history") or [])[-6:],
        "thinking_mode": _thinking_mode_enabled(request),
        "default_filters": {
            **_base_filter_params(request),
            "merge_level": request.get("merge_level", 1),
        },
        "available_tools": describe_for_model(),
    }
    return _compact_json(payload, limit=16000)


def _plan_tool_calls(request: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    raw = ai_insights_service._llm_chat(
        PLANNER_SYSTEM_PROMPT,
        _planner_user_content(request),
        temperature=0.1,
    )
    parsed = _extract_json_array(raw)
    if parsed is None:
        return _fallback_plan(request), "fallback"
    plan = _sanitize_plan(parsed, request)
    if not plan:
        return _fallback_plan(request), "fallback"
    return _augment_plan_for_thinking_mode(plan, request), "planned"


def _named_param(params_summary: str, key: str) -> str | None:
    prefix = f"{key}="
    for part in params_summary.split(", "):
        if part.startswith(prefix):
            value = part[len(prefix) :].strip()
            return value or None
    return None


def _list_summary(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    return {"count": len(rows)}


def _weekly_rank_summary(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    ranked = [row for row in rows if isinstance(row, dict)]
    if not ranked:
        return {"weeks": 0}
    ranks = [int(row.get("rank") or 0) for row in ranked if row.get("rank") is not None]
    play_counts = [int(row.get("play_count") or 0) for row in ranked]
    return {
        "weeks": len(ranked),
        "plays": sum(play_counts),
        "no1_weeks": sum(1 for rank in ranks if rank == 1),
        "top5_weeks": sum(1 for rank in ranks if 0 < rank <= 5),
        "top10_weeks": sum(1 for rank in ranks if 0 < rank <= 10),
        "avg_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
        "first_week": ranked[0].get("week") or ranked[0].get("billboard_week"),
        "latest_week": ranked[-1].get("week") or ranked[-1].get("billboard_week"),
    }


def _album_project_evidence(project: Any) -> dict[str, Any]:
    if not isinstance(project, dict):
        return {}
    source_breakdown = project.get("source_breakdown")
    compact_sources = []
    if isinstance(source_breakdown, list):
        for source in source_breakdown[:8]:
            if not isinstance(source, dict):
                continue
            compact_sources.append(
                {
                    "source_album_name": source.get("source_album_name"),
                    "source_bucket": source.get("source_bucket"),
                    "play_count": source.get("play_count"),
                    "total_ms": source.get("total_ms"),
                }
            )
    return {
        "album_project_name": project.get("album_project_name"),
        "artist_name": project.get("artist_name"),
        "release_date": project.get("release_date"),
        "play_count": project.get("play_count"),
        "total_ms": project.get("total_ms"),
        "unique_canonical_songs": project.get("unique_canonical_songs"),
        "source_breakdown": compact_sources,
    }


def _top_track_evidence(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    compact = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        compact.append(
            {
                "track_name": row.get("track_name"),
                "peak_position": row.get("peak_position"),
                "weeks_on_chart": row.get("weeks_on_chart"),
                "total_chart_plays": row.get("total_chart_plays"),
                "power_score": row.get("power_score"),
                "power_rank": row.get("power_rank"),
            }
        )
    return compact


def _compare_entities_evidence(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get("entities")
    compact_entities = []
    if isinstance(rows, list):
        for row in rows[:4]:
            if not isinstance(row, dict):
                continue
            compact_entities.append(
                {
                    key: row.get(key)
                    for key in (
                        "name",
                        "requested_name",
                        "entity_type",
                        "found",
                        "error",
                        "plays",
                        "hours",
                        "first_play_date",
                        "latest_play_date",
                        "power_score",
                        "power_rank",
                        "no1_weeks",
                        "weeks_on_chart",
                        "peak_position",
                        "plays_per_chart_week",
                    )
                    if row.get(key) is not None
                }
            )
    evidence = {
        key: data.get(key)
        for key in (
            "entity_type",
            "winner_by_cumulative_plays",
            "winner_by_total_hours",
            "winner_by_power_score",
            "winner_by_power_rank",
            "winner_by_intensity",
        )
        if data.get(key) is not None
    }
    if compact_entities:
        evidence["entities"] = compact_entities
    fairness_notes = data.get("fairness_notes")
    if isinstance(fairness_notes, list):
        evidence["fairness_notes"] = [str(note) for note in fairness_notes[:6]]
    return evidence


def _tool_data_evidence(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _list_summary(data)
    if isinstance(data.get("entities"), list) and any(
        key in data
        for key in (
            "winner_by_cumulative_plays",
            "winner_by_power_score",
            "winner_by_intensity",
        )
    ):
        return _compare_entities_evidence(data)
    evidence: dict[str, Any] = {}
    for key in (
        "found",
        "album_name",
        "track_name",
        "artist_name",
        "entity",
        "period",
        "summary",
        "chart_summary",
        "info",
    ):
        value = data.get(key)
        if isinstance(value, (str, int, float, bool)) or isinstance(value, dict):
            evidence[key] = value
    album_project = _album_project_evidence(data.get("album_project"))
    if album_project:
        evidence["album_project"] = album_project
    weekly = _weekly_rank_summary(data.get("album_weekly_history") or data.get("history"))
    if weekly:
        evidence["weekly_rank_summary"] = weekly
    tracks = _top_track_evidence(data.get("tracks"))
    if tracks:
        evidence["top_tracks"] = tracks
    top_albums = data.get("top_albums")
    if isinstance(top_albums, list):
        evidence["top_albums"] = top_albums[:10]
    top_tracks = data.get("top_tracks")
    if isinstance(top_tracks, list):
        evidence["top_tracks"] = top_tracks[:10]
    rows = data.get("rows")
    if isinstance(rows, list):
        evidence["rows"] = rows[:20]
        evidence["row_count"] = len(rows)
    return evidence


def _compact_tool_result_for_llm(item: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "tool_name": item.get("tool_name"),
        "status": item.get("status"),
        "params_summary": item.get("params_summary", ""),
        "result_summary": item.get("result_summary", ""),
        "source_range": item.get("source_range", ""),
    }
    if item.get("error"):
        compact["error"] = item.get("error")
    evidence = _tool_data_evidence(item.get("data"))
    if evidence:
        compact["evidence"] = evidence
    return compact


def _tool_found_status(item: dict[str, Any]) -> str:
    if item.get("status") == "error":
        return "error"
    summary = str(item.get("result_summary") or "").lower()
    data = item.get("data")
    found_value = data.get("found") if isinstance(data, dict) else None
    if found_value is True or "found=true" in summary:
        return "found"
    if found_value is False or "found=false" in summary:
        return "missing"
    return "done"


def _build_coverage(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[str, dict[str, str]] = {}
    requested_entities: list[str] = []
    comparison: dict[str, str] = {}
    for item in tool_results:
        if item.get("tool_name") == "compare_entities":
            data = item.get("data")
            rows = data.get("entities") if isinstance(data, dict) else None
            if isinstance(rows, list) and rows:
                found_statuses: list[str] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    entity_name = str(row.get("requested_name") or row.get("name") or "").strip()
                    if not entity_name:
                        continue
                    if entity_name not in entities:
                        entities[entity_name] = {}
                        requested_entities.append(entity_name)
                    status = "found" if row.get("found") is True else "missing"
                    entities[entity_name]["compare_entities"] = status
                    found_statuses.append(status)
                if found_statuses:
                    comparison["compare_entities"] = (
                        "found"
                        if all(status == "found" for status in found_statuses)
                        else "missing"
                    )
            continue

        params_summary = str(item.get("params_summary") or "")
        entity_name = (
            _named_param(params_summary, "album_name")
            or _named_param(params_summary, "artist_name")
            or _named_param(params_summary, "track_name")
        )
        if not entity_name:
            continue
        if entity_name not in entities:
            entities[entity_name] = {}
            requested_entities.append(entity_name)
        entities[entity_name][str(item.get("tool_name") or "unknown_tool")] = _tool_found_status(
            item
        )
    coverage = {"requested_entities": requested_entities, "entities": entities}
    if comparison:
        coverage["comparison"] = comparison
    return coverage


def _final_payload(
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    compact_results = [_compact_tool_result_for_llm(item) for item in tool_results]
    evidence_cards = build_evidence_cards(tool_results)
    compact_cards = compact_evidence_cards(evidence_cards)
    context = _question_context(request)
    coverage = _build_coverage(tool_results)
    evidence_sufficiency = review_evidence_sufficiency(
        question_frame=context["question_frame"],
        evidence_recipe=context["evidence_recipe"],
        tool_results=tool_results,
        coverage=coverage,
    )
    analytical_brief = build_analytical_brief(
        question_frame=context["question_frame"],
        evidence_recipe=context["evidence_recipe"],
        tool_results=tool_results,
        coverage=coverage,
        evidence_cards=compact_cards,
    )
    answer_style = _answer_style(
        request,
        question_frame=context["question_frame"],
        evidence_sufficiency=evidence_sufficiency,
    )
    return {
        "question": request.get("question", ""),
        "conversation_history": (request.get("conversation_history") or [])[-6:],
        **context,
        **project_context_payload(),
        "answer_style": answer_style,
        "coverage": coverage,
        "evidence_sufficiency": evidence_sufficiency,
        "analytical_brief": analytical_brief,
        "evidence_cards": compact_cards,
        "tool_results": compact_results,
    }


def _final_user_content(
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> str:
    return _compact_json(_final_payload(request, tool_results), limit=16000)


def _answer_validation_issues(answer: str, coverage: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    entities = coverage.get("entities") if isinstance(coverage, dict) else {}
    if not isinstance(entities, dict):
        return issues
    sentences = [
        part.strip()
        for chunk in answer.replace("。", "\n").replace("；", "\n").replace("，", "\n").splitlines()
        for part in [chunk.strip()]
        if part.strip()
    ]
    strong_missing_tokens = ("缺少", "未查询", "无法比较", "数据不足", "只能提供")
    weak_missing_tokens = ("没有", "无")
    missing_context_tokens = ("数据", "播放", "榜单", "成绩", "信息", "结果")
    for entity_name, tool_statuses in entities.items():
        if not isinstance(entity_name, str) or not isinstance(tool_statuses, dict):
            continue
        has_found = any(status == "found" for status in tool_statuses.values())
        if has_found:
            for sentence in sentences:
                has_strong_missing = any(token in sentence for token in strong_missing_tokens)
                has_contextual_missing = any(
                    token in sentence for token in weak_missing_tokens
                ) and any(token in sentence for token in missing_context_tokens)
                if entity_name in sentence and (has_strong_missing or has_contextual_missing):
                    issues.append(f"{entity_name} 已由工具查到，但回答声称缺少或未查询")
                    break
        has_billboard = tool_statuses.get("billboard_entity_detail") == "found"
        lower_answer = answer.lower()
        if has_billboard and any(
            token in lower_answer
            for token in (
                "没有 billboard",
                "没有billboard",
                "缺少 billboard",
                "缺少billboard",
                "未进行 billboard",
                "未进行billboard",
                "无法提供榜单",
            )
        ):
            issues.append(f"{entity_name} 已有 Billboard 工具结果，但回答声称缺少榜单成绩")
    return issues


def _retry_user_content(
    payload: dict[str, Any],
    previous_answer: str,
    issues: list[str],
) -> str:
    retry_payload = {
        **payload,
        "previous_answer": previous_answer,
        "validation_issues": issues,
        "instruction": (
            "上一版回答与工具证据或回答契约矛盾。请只基于 coverage、"
            "evidence_sufficiency、analytical_brief 和 tool_results 重新回答；"
            "不要声称 found 的实体或榜单数据缺失，不要忽略 analytical_brief.must_explain，"
            "并严格遵守 project_context_version、answer_style 和 Project Context 的项目语境要求。"
        ),
    }
    return _compact_json(retry_payload, limit=16000)


def run_chat_agent_task(task_id: str, request: dict[str, Any]) -> None:
    """Run a bounded read-only tool plan and persist observable task progress."""
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        if not _set_stage(
            repo,
            task_id=task_id,
            stage="planning_tools",
            progress_pct=0.1,
            message="正在规划可用数据工具",
        ):
            return

        tool_plan, plan_mode = _plan_tool_calls(request)
        if _is_terminal(repo, task_id):
            return
        repo.add_event(
            task_id=task_id,
            event_type="stage_completed",
            stage="planning_tools",
            message="工具规划完成",
            payload={"mode": plan_mode, "tool_count": len(tool_plan)},
        )

        tool_results: list[dict[str, Any]] = []
        for index, tool_call in enumerate(tool_plan[:MAX_TOOL_CALLS], start=1):
            result = _execute_tool_call(
                repo,
                task_id=task_id,
                tool_call=tool_call,
                index=index,
                progress_pct=min(0.7, 0.35 + (index - 1) * 0.08),
            )
            if result is None:
                return
            tool_results.append(result)

        context = _question_context(request)
        executed_identities = {
            _tool_call_identity(planned_call) for planned_call in tool_plan[:MAX_TOOL_CALLS]
        }
        for review_round in range(MAX_COVERAGE_REVIEW_ROUNDS):
            coverage = _build_coverage(tool_results)
            coverage_review = review_evidence_sufficiency(
                question_frame=context["question_frame"],
                evidence_recipe=context["evidence_recipe"],
                tool_results=tool_results,
                coverage=coverage,
            )
            if coverage_review["sufficient"]:
                break
            if not _set_stage(
                repo,
                task_id=task_id,
                stage="reviewing_coverage",
                progress_pct=min(0.86, 0.76 + review_round * 0.05),
                message="正在补查缺失证据",
                payload={"reasons": coverage_review["reasons"], "round": review_round + 1},
            ):
                return
            added_followups = 0
            for offset, followup in enumerate(
                coverage_review["followup_tool_calls"],
                start=1,
            ):
                if len(tool_results) >= MAX_TOOL_CALLS:
                    break
                prepared_followup = _prepare_followup_tool_call(followup, request)
                if prepared_followup is None:
                    continue
                identity = _tool_call_identity(prepared_followup)
                if identity in executed_identities:
                    continue
                executed_identities.add(identity)
                result = _execute_tool_call(
                    repo,
                    task_id=task_id,
                    tool_call=prepared_followup,
                    index=len(tool_results) + 1,
                    progress_pct=min(0.88, 0.78 + review_round * 0.04 + offset * 0.02),
                )
                if result is None:
                    return
                tool_results.append(result)
                added_followups += 1
            if added_followups == 0:
                break

        if _thinking_mode_enabled(request) and not _set_stage(
            repo,
            task_id=task_id,
            stage="reviewing_evidence",
            progress_pct=0.87,
            message="正在交叉核对查询结果",
        ):
            return

        if not _set_stage(
            repo,
            task_id=task_id,
            stage="calling_llm",
            progress_pct=0.9,
            message="正在生成最终回答",
        ):
            return

        final_payload = _final_payload(request, tool_results)
        final_user_content = _compact_json(final_payload, limit=16000)
        answer = ai_insights_service._llm_chat(
            THINKING_FINAL_ANSWER_SYSTEM_PROMPT
            if _thinking_mode_enabled(request)
            else FINAL_ANSWER_SYSTEM_PROMPT,
            final_user_content,
            temperature=0.4,
        )
        if not answer or not answer.strip():
            raise ChatAgentError(FINAL_LLM_FAILURE_MESSAGE)
        answer = answer.strip()
        answer_retried = False
        validation_issues = _answer_validation_issues(answer, final_payload["coverage"])
        critic_result = critique_answer(answer, final_payload)
        if not critic_result["ok"]:
            validation_issues.extend(str(issue) for issue in critic_result.get("issues", []))
        if validation_issues:
            retry_answer = ai_insights_service._llm_chat(
                THINKING_FINAL_ANSWER_SYSTEM_PROMPT
                if _thinking_mode_enabled(request)
                else FINAL_ANSWER_SYSTEM_PROMPT,
                _retry_user_content(final_payload, answer, validation_issues),
                temperature=0.25,
            )
            if retry_answer and retry_answer.strip():
                answer = retry_answer.strip()
                answer_retried = True

        _mark_done(
            repo,
            task_id=task_id,
            message="Agent Chat 已完成",
            result={
                "answer": answer,
                "tool_call_count": len(tool_results),
                "thinking_mode": _thinking_mode_enabled(request),
                "answer_retried": answer_retried,
                "project_context_version": PROJECT_CONTEXT_VERSION,
                "validation_issues": validation_issues,
                "coverage": final_payload["coverage"],
                "question_frame": final_payload["question_frame"],
                "evidence_sufficiency": final_payload["evidence_sufficiency"],
                "analytical_brief": final_payload["analytical_brief"],
                "evidence_cards": final_payload["evidence_cards"],
                "tools": [
                    {
                        "tool_name": item["tool_name"],
                        "status": item["status"],
                        "result_summary": item.get("result_summary", ""),
                        "source_range": item.get("source_range", ""),
                        "error": item.get("error"),
                    }
                    for item in tool_results
                ],
            },
        )
    except ChatAgentError as exc:
        _mark_error(
            repo,
            task_id=task_id,
            message=str(exc),
            result={"error": str(exc)},
        )
    except Exception as exc:
        _mark_error(
            repo,
            task_id=task_id,
            message=str(exc) or exc.__class__.__name__,
            result={"error": str(exc) or exc.__class__.__name__},
        )
    finally:
        conn.close()
