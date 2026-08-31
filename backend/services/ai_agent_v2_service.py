"""Native tool-calling, observation-driven chat agent runtime."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, Protocol

from backend.core.config import (
    AI_AGENT_CONTEXT_SOURCE,
    AI_AGENT_LLM_RETRIES,
    AI_AGENT_LLM_TIMEOUT_SECONDS,
    AI_AGENT_MAX_STEPS,
    AI_AGENT_MAX_TOOL_CALLS,
    AI_AGENT_TURN_TIMEOUT_SECONDS,
    HTTP_PROXY,
    HTTPS_PROXY,
)
from backend.core.db import get_db
from backend.domains.agent_runtime.context_compaction import compact_session_events
from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.metrics import RuntimeMetrics
from backend.domains.agent_runtime.native_loop import assistant_message, tool_message
from backend.domains.agent_runtime.projections import ContextSource, select_context_messages
from backend.domains.agent_runtime.provider_reliability import (
    BudgetCaps,
    DynamicAgentBudget,
    ModelStepAttempt,
    ModelStepExecutor,
    ModelStepExhaustedError,
    ProviderCandidate,
    ProviderCircuitBreaker,
    dynamic_agent_budget,
)
from backend.domains.agent_runtime.recovery import build_resume_checkpoint
from backend.domains.agent_runtime.serialization import compact_json
from backend.domains.agent_runtime.session_state import (
    AgentSessionState,
    apply_session_input,
    filters_for_session_state,
    initial_session_state,
    restore_session_state,
)
from backend.domains.agent_runtime.tool_runtime import ToolRuntime
from backend.domains.agent_runtime.tool_selector import (
    select_agent_profile,
    tool_schemas_for_profile,
)
from backend.domains.ai_agent.claim_ledger import render_grounded_fallback
from backend.domains.ai_agent.project_context import PROJECT_CONTEXT_VERSION
from backend.domains.ai_agent.temporal_context import (
    apply_temporal_guard,
    clip_custom_range_to_data,
)
from backend.domains.ai_agent.tool_registry import AgentToolRegistry, get_default_registry
from backend.domains.ai_tasks.cancellation import cancellation_registry
from backend.domains.ai_tasks.repository import AiTaskRepository
from backend.providers.base import ProviderConfig
from backend.providers.llm.client import LLMCompletion
from backend.services import ai_insights_service
from backend.services.ai_agent_service import (
    ChatAgentError,
    _apply_obligation_fallback_notes,
    _combined_answer_issues,
    _final_payload,
    _is_terminal,
    _mark_done,
    _mark_error,
    _question_context,
    _result_payload,
    _safety_boundary_answer,
    _temporal_context,
    _thinking_mode_enabled,
)


class AgentModel(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        thinking: bool,
    ) -> LLMCompletion: ...


_PROVIDER_CIRCUIT_BREAKER = ProviderCircuitBreaker()


class ConfiguredNativeToolModel:
    """Resolve the configured provider and require its native tool protocol."""

    def __init__(self, budget: DynamicAgentBudget | None = None) -> None:
        runtime_managed_retries = budget is not None
        if budget is None:
            budget = dynamic_agent_budget(
                {
                    "question_intent": {
                        "task_type": "comparison",
                        "entities": ["report", "context"],
                        "requested_metrics": ["plays", "hours"],
                    }
                },
                caps=BudgetCaps(
                    max_steps=AI_AGENT_MAX_STEPS,
                    max_tool_calls=AI_AGENT_MAX_TOOL_CALLS,
                    turn_timeout_seconds=AI_AGENT_TURN_TIMEOUT_SECONDS,
                    model_timeout_seconds=AI_AGENT_LLM_TIMEOUT_SECONDS,
                    max_model_retries=AI_AGENT_LLM_RETRIES,
                    max_output_tokens=6144,
                ),
            )
        cfg = ai_insights_service._get_config()
        initial = ai_insights_service._get_llm(cfg)
        if initial is None:
            raise ChatAgentError("LLM 未配置，无法启动 Agent V2")
        provider_config = ProviderConfig(
            name=f"agent-v2-{initial.provider}",
            base_url=initial.base_url,
            timeout=budget.model_timeout_seconds,
            retries=0 if runtime_managed_retries else AI_AGENT_LLM_RETRIES,
            rate_limit_rps=3.0,
            http_proxy=HTTP_PROXY or "",
            https_proxy=HTTPS_PROXY or "",
        )
        resolved = ai_insights_service._get_llm(cfg, provider_config=provider_config)
        if resolved is None:
            raise ChatAgentError("LLM 未配置，无法启动 Agent V2")
        self.llm = resolved
        self.max_tokens = budget.max_output_tokens
        self.provider_id = f"{resolved.provider}:{resolved.model}"

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        thinking: bool,
    ) -> LLMCompletion:
        return self.llm.complete_with_tools(
            messages,
            tools,
            temperature=0.2,
            max_tokens=self.max_tokens,
            thinking=thinking,
        )


class AgentCancelledError(ChatAgentError):
    pass


class AgentBudgetExceededError(ChatAgentError):
    pass


def _dynamic_budget(
    question_context: dict[str, Any],
    *,
    max_steps: int = AI_AGENT_MAX_STEPS,
    max_tool_calls: int = AI_AGENT_MAX_TOOL_CALLS,
    timeout_seconds: int = AI_AGENT_TURN_TIMEOUT_SECONDS,
) -> DynamicAgentBudget:
    return dynamic_agent_budget(
        question_context,
        caps=BudgetCaps(
            max_steps=max_steps,
            max_tool_calls=max_tool_calls,
            turn_timeout_seconds=timeout_seconds,
            model_timeout_seconds=AI_AGENT_LLM_TIMEOUT_SECONDS,
            max_model_retries=AI_AGENT_LLM_RETRIES,
            max_output_tokens=6144,
        ),
    )


def _record_model_attempts(
    metrics: RuntimeMetrics,
    attempts: tuple[ModelStepAttempt, ...],
    *,
    usage: dict[str, Any] | None,
    input_chars: int,
) -> int:
    actual_attempts = [attempt for attempt in attempts if attempt.outcome != "circuit_open"]
    for attempt in actual_attempts:
        metrics.record_model(
            elapsed_ms=attempt.elapsed_ms,
            usage=usage if attempt.outcome == "success" else {},
            input_chars=input_chars,
        )
    return sum(attempt.elapsed_ms for attempt in actual_attempts)


def _safe_attempt_payload(attempts: tuple[ModelStepAttempt, ...]) -> list[dict[str, Any]]:
    return [asdict(attempt) for attempt in attempts]


def _agent_default_filters(request: dict[str, Any]) -> dict[str, Any]:
    question_context = _question_context(request)
    intent = question_context.get("question_intent") or {}
    time_scope = str(intent.get("time_scope") or "lifetime")
    period_filters: dict[str, Any]
    explicit_year = time_scope[5:] if time_scope.startswith("year:") else ""
    temporal_context = (
        _temporal_context(request) if explicit_year.isdigit() or time_scope == "this_year" else {}
    )
    current_year = str(temporal_context.get("today") or "")[:4]
    selected_year = (
        explicit_year
        if explicit_year.isdigit()
        else current_year
        if time_scope == "this_year" and current_year.isdigit()
        else ""
    )
    if selected_year:
        year = selected_year
        clipped = clip_custom_range_to_data(
            f"{year}-01-01",
            f"{year}-12-31",
            temporal_context,
        )
        clipped.update(
            {
                "label": f"{year}年",
                "expected_year": int(year),
                "anchor_date": temporal_context.get("today"),
            }
        )
        request["_temporal_guard"] = {
            "time_interpretation": clipped,
            "had_corrections": clipped.get("coverage_clipped") is True,
            "corrections": [],
        }
        period_filters = {
            "period": "custom",
            "start_date": clipped.get("effective_start_date") or f"{year}-01-01",
            "end_date": clipped.get("effective_end_date") or f"{year}-12-31",
        }
    elif time_scope in {
        "lifetime",
        "today",
        "this_week",
        "this_year",
        "last_4_weeks",
        "last_6_months",
        "custom",
    }:
        period_filters = {"period": time_scope}
    else:
        period_filters = {"period": "lifetime"}
    routing_signals = question_context.get("routing_signals") or {}
    return {
        "min_ms": request.get("min_ms", 30000),
        "music_only": request.get("music_only", True),
        "merge_enabled": request.get("merge_enabled", True),
        "dynamic_threshold": request.get("dynamic_threshold", True),
        "max_merge_gap_minutes": request.get("max_merge_gap_minutes"),
        "merge_level": request.get("merge_level", 2),
        "include_billboard": routing_signals.get("explicit_billboard") is True,
        **period_filters,
    }


def _system_prompt() -> str:
    """Stable, provider-cacheable instructions without per-turn values."""

    return f"""你是 SpotifyStats 应用内的只读数据 Agent。你运行在真实的“思考—调用工具—观察结果—继续决策”循环中。

Project Context Version: {PROJECT_CONTEXT_VERSION}

SpotifyStats 只分析用户本地 Spotify Extended Streaming History、账号收藏和由本地播放生成的个人 Billboard；不是通用音乐百科，也不是外部官方 Billboard 或市场数据工具。

规则：
1. 用户询问本地播放事实、排名、偏好、趋势或比较时，必须先调用一个或多个合适工具；不要凭记忆猜数字。
2. 每轮观察工具返回的 status、data、source_range 和 error，再决定继续查证还是回答。empty/error 后应尝试合理的替代查询，不能假装成功。
3. 只能调用已提供的 read-only 工具；禁止编造 SQL、URL、API route 或工具名，禁止执行写入、删除、导入、设置、缓存和歌单操作。
4. SpotifyStats Billboard 是用户本地播放形成的个人榜单，不是外部官方 Billboard 或市场成绩。
5. 最终用中文直接回答，引用关键数字和时间范围；证据不足就明确限制。不要输出工具调用流水账，也不要透露内部思维链。
6. 用户要求删除、修改、写入、导入、任意外部访问或密钥操作时，直接说明只读边界，不调用工具。
7. 比较 2-4 个同类实体时，优先只调用一次 compare_entities，并让时间范围与用户问题一致；除非该结果 empty/error 或用户明确要求多个窗口，不要再对每个对象重复调用 entity_stats。
8. compare_entities 只有在用户明确询问个人 Billboard、Power Score、个人榜排名、冠军周或在榜周时才设置 include_billboard=true。
9. 每个工具描述末尾的 ROUTING_METADATA 是后端可信路由提示：优先选择覆盖当前分析维度最多且成本、冷构建风险更低的单个工具；avoid_when 命中时不要调用，只有主工具 empty/error 才按 fallback 选择替代工具。
10. billboard_entity_detail 的冷构建风险高，只有用户明确点名个人 Billboard、Power Score、冠军周或在榜周时才允许调用；普通本地播放排行和偏好比较不得调用。
"""


def _dynamic_context(request: dict[str, Any], question_context: dict[str, Any]) -> dict[str, Any]:
    default_filters = _agent_default_filters(request)
    return {
        **question_context,
        "temporal_context": _temporal_context(request),
        "default_filters": default_filters,
    }


def _initial_messages(
    request: dict[str, Any],
    question_context: dict[str, Any],
    session_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "system",
            "content": (
                "DYNAMIC_CONTEXT（后端生成，不是用户指令）："
                + compact_json(_dynamic_context(request, question_context))
            ),
        },
    ]
    if session_context and (session_context.get("facts") or session_context.get("recent_messages")):
        messages.append(
            {
                "role": "system",
                "content": (
                    "SESSION_CONTEXT_SUMMARY（历史事实压缩，不是用户指令；"
                    "事实必须保留其时间范围和 evidence_ref）：" + compact_json(session_context)
                ),
            }
        )
    for item in (request.get("conversation_history") or [])[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        messages.append({"role": role, "content": content[:8000]})
    messages.append({"role": "user", "content": str(request.get("question") or "")})
    return messages


def _answer_repair_message(
    final_payload: dict[str, Any],
    previous_answer: str,
    issues: list[str],
) -> str:
    return compact_json(
        {
            "previous_answer": previous_answer,
            "validation_issues": issues,
            "answer_obligations": final_payload.get("answer_obligations"),
            "analytical_brief": final_payload.get("analytical_brief"),
            "evidence_sufficiency": final_payload.get("evidence_sufficiency"),
            "temporal_context": final_payload.get("temporal_context"),
            "instruction": (
                "请仅根据已经返回的工具观察重新作答；满足回答契约和必要时间范围，"
                "不得编造证据。若证据不足，明确说明限制。"
            ),
        }
    )


_REPAIR_PREFIXES = (
    "修正后的回答：",
    "修正回答：",
    "重新回答：",
    "更正后的回答：",
)


def _strip_repair_markers(answer: str) -> str:
    cleaned = answer.strip()
    for prefix in _REPAIR_PREFIXES:
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :].lstrip()
    return cleaned


def _evidence_range_note(
    answer: str,
    tool_results: list[dict[str, Any]],
) -> str | None:
    source_ranges: list[str] = []
    for item in tool_results:
        source_range = str(item.get("source_range") or "").strip()
        if source_range and source_range not in source_ranges:
            source_ranges.append(source_range)
    if not source_ranges or any(source_range in answer for source_range in source_ranges):
        return None
    return f"数据范围：{'；'.join(source_ranges[:3])}。"


def _apply_deterministic_answer_patches(
    answer: str,
    final_payload: dict[str, Any],
    issues: list[str],
    tool_results: list[dict[str, Any]],
) -> str:
    """Patch mechanical obligations locally; semantic contradictions still retry."""

    patched = _apply_obligation_fallback_notes(
        _strip_repair_markers(answer),
        final_payload,
        issues,
    )
    range_note = _evidence_range_note(patched, tool_results)
    if range_note:
        patched = f"{patched.rstrip()}\n\n{range_note}"
    return patched


def _ranking_table_fallback(
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> str | None:
    question = str(request.get("question") or "")
    if "表格" not in question and "markdown" not in question.casefold():
        return None
    rows: list[str] = []
    for item in tool_results:
        if item.get("tool_name") != "analysis_charts":
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        entity_type = str(data.get("entity") or "")
        if entity_type not in {"artist", "album", "track"}:
            continue
        metric = str(data.get("metric") or "plays")
        source_range = str(item.get("source_range") or "")
        period_label = source_range[:4] if len(source_range) >= 4 else source_range
        for row in (data.get("rows") or [])[:5]:
            if not isinstance(row, dict):
                continue
            name = (
                row.get("artist_name")
                if entity_type == "artist"
                else row.get("album_name")
                if entity_type == "album"
                else row.get("track_name")
            )
            value = row.get(metric)
            if not name or value is None:
                continue
            rows.append(f"| {period_label} | {row.get('rank')} | {name} | {value} |")
    if not rows:
        return None
    return "\n".join(
        [
            "根据本地只读排行证据，结果如下：",
            "",
            "| 年份 | 排名 | 艺人 | 播放次数 |",
            "|---|---:|---|---:|",
            *rows,
            "",
            "限制：表格只使用当前工具已经返回且可追溯的排行事实。",
        ]
    )


def _comparison_fallback(tool_results: list[dict[str, Any]]) -> str | None:
    for item in reversed(tool_results):
        if item.get("tool_name") != "compare_entities":
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        entities = data.get("entities")
        if not isinstance(entities, list) or not entities:
            continue
        includes_billboard = data.get("includes_personal_billboard") is True
        lines = (
            [
                "根据本地播放与个人 Billboard 的同口径证据，比较如下：",
                "",
                "| 对象 | 播放次数 | 播放时长（小时） | Power Score | 个人榜单排名 | 在榜周数 | 单位在榜周播放 |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
            if includes_billboard
            else [
                "根据本地播放的同口径证据，比较如下：",
                "",
                "| 对象 | 播放次数 | 播放时长（小时） | 所选窗口周均播放 |",
                "|---|---:|---:|---:|",
            ]
        )

        def display(value: Any) -> Any:
            return "—" if value is None else value

        for entity in entities:
            if not isinstance(entity, dict) or not entity.get("found"):
                continue
            name = entity.get("name") or entity.get("requested_name") or "未知对象"
            if includes_billboard:
                lines.append(
                    "| {name} | {plays} | {hours} | {power_score} | {power_rank} | "
                    "{weeks_on_chart} | {plays_per_chart_week} |".format(
                        name=name,
                        plays=display(entity.get("plays")),
                        hours=display(entity.get("hours")),
                        power_score=display(entity.get("power_score")),
                        power_rank=display(entity.get("power_rank")),
                        weeks_on_chart=display(entity.get("weeks_on_chart")),
                        plays_per_chart_week=display(entity.get("plays_per_chart_week")),
                    )
                )
            else:
                lines.append(
                    "| {name} | {plays} | {hours} | {plays_per_window_week} |".format(
                        name=name,
                        plays=display(entity.get("plays")),
                        hours=display(entity.get("hours")),
                        plays_per_window_week=display(entity.get("plays_per_window_week")),
                    )
                )
        conclusions = [
            f"累计播放更高：{display(data.get('winner_by_cumulative_plays'))}",
            f"播放时长更高：{display(data.get('winner_by_total_hours'))}",
        ]
        if includes_billboard:
            conclusions.extend(
                [
                    f"Power Score 更高：{display(data.get('winner_by_power_score'))}",
                    f"单位在榜周播放更高：{display(data.get('winner_by_intensity'))}",
                ]
            )
        else:
            conclusions.append(f"所选窗口周均播放更高：{display(data.get('winner_by_intensity'))}")
        lines.extend(["", "；".join(conclusions) + "。"])
        if includes_billboard:
            lines.append(
                "口径说明：这里的 Billboard 是 SpotifyStats 本地个人 Billboard，不是外部官方 Billboard。"
            )
        return "\n".join(lines)
    return None


def _render_evidence_fallback(
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
    final_payload: dict[str, Any],
) -> str:
    return (
        _comparison_fallback(tool_results)
        or _ranking_table_fallback(request, tool_results)
        or render_grounded_fallback(final_payload.get("fact_catalog") or [])
    )


def _ensure_v2_grounded_answer(
    answer: str,
    final_payload: dict[str, Any],
    issues: list[str],
    *,
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> tuple[str, list[str], bool]:
    unsupported_prefix = "回答包含无法追溯到事实目录的数字："
    if not any(issue.startswith(unsupported_prefix) for issue in issues):
        return answer, issues, False
    fallback = _render_evidence_fallback(request, tool_results, final_payload)
    fallback_issues = _combined_answer_issues(fallback, final_payload)
    fallback = _apply_obligation_fallback_notes(
        fallback,
        final_payload,
        fallback_issues,
    )
    fallback_issues = _combined_answer_issues(fallback, final_payload)
    if any(issue.startswith(unsupported_prefix) for issue in fallback_issues):
        interpretation = final_payload.get("temporal_guard") or {}
        interpretation = interpretation.get("time_interpretation") or {}
        label = str(interpretation.get("label") or "用户指定范围")
        temporal_context = final_payload.get("temporal_context") or {}
        cutoff = temporal_context.get("data_end_date")
        cutoff_note = f"本地播放数据截至 {cutoff}。" if cutoff else ""
        fallback = (
            f"已按“{label}”查询本地只读数据。{cutoff_note}"
            "限制：为避免发布无法完整追溯的数字，本次只确认工具已有可用结果。"
        )
        fallback_issues = _combined_answer_issues(fallback, final_payload)
    return fallback, fallback_issues, True


def _validate_answer(
    answer: str,
    final_payload: dict[str, Any],
) -> list[str]:
    return _combined_answer_issues(answer, final_payload)


def _session_id(conn, request: dict[str, Any]) -> int | None:
    value = request.get("session_id")
    if not isinstance(value, int):
        return None
    row = conn.execute("SELECT 1 FROM chat_sessions WHERE id = ?", (value,)).fetchone()
    return value if row else None


def _session_context(
    repo: AiTaskRepository,
    *,
    session_id: int | None,
    task_id: str,
) -> dict[str, Any] | None:
    if session_id is None:
        return None
    events = repo.list_agent_session_events(
        session_id,
        exclude_task_id=task_id,
    )
    return compact_session_events(events) if events else None


def _consume_session_inbox(
    repo: AiTaskRepository,
    log: AgentEventLog,
    messages: list[dict[str, Any]],
    *,
    task_id: str,
    step_index: int,
    state: AgentSessionState,
    temporal_context: dict[str, Any],
) -> tuple[int, AgentSessionState, bool]:
    inputs = repo.consume_agent_inputs(task_id)
    evidence_invalidated = False
    for item in inputs:
        update = apply_session_input(
            state,
            input_type=str(item["input_type"]),
            content=str(item["content"]),
            temporal_context=temporal_context,
        )
        if update.action == "cancel":
            cancellation_registry.request_cancel(task_id)
            raise AgentCancelledError("Agent 任务已取消")
        if update.action in {
            "replace_constraints",
            "remove_requirements",
            "replace_task",
        }:
            evidence_invalidated = True
        state = update.state
        message = {
            "role": "user",
            "content": (
                f"用户在运行中补充（{update.action}）：{str(item['content']).strip()}\n"
                f"{state.model_context()}"
            ),
        }
        messages.append(message)
        log.append_model_message(
            message,
            origin="session_inbox",
            step_index=step_index,
        )
        log.append(
            "session_input_consumed",
            {
                "inbox_id": int(item["inbox_id"]),
                "input_type": item["input_type"],
                "semantic_action": update.action,
                "patch": update.patch,
                "state": state.to_dict(),
            },
            step_index=step_index,
        )
        log.append(
            "session_state_updated",
            {
                "inbox_id": int(item["inbox_id"]),
                "input_type": item["input_type"],
                "semantic_action": update.action,
                "patch": update.patch,
                "state": state.to_dict(),
            },
            step_index=step_index,
        )
        repo.add_event(
            task_id=task_id,
            event_type="session_state_updated",
            stage="agent_running",
            message="Agent 已更新分析约束",
            payload={
                "inbox_id": int(item["inbox_id"]),
                "input_type": item["input_type"],
                "semantic_action": update.action,
                "state": state.public_constraints(),
            },
        )
    return len(inputs), state, evidence_invalidated


def _update_stage(
    repo: AiTaskRepository,
    *,
    task_id: str,
    stage: str,
    progress: float,
    message: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="running",
        stage=stage,
        progress_pct=progress,
        message=message,
    )
    if updated:
        repo.add_event(
            task_id=task_id,
            event_type=event_type,
            stage=stage,
            message=message,
            payload=payload,
        )
    return updated


class AgentRuntime:
    def __init__(
        self,
        *,
        model: AgentModel,
        registry: AgentToolRegistry,
        max_steps: int = AI_AGENT_MAX_STEPS,
        max_tool_calls: int = AI_AGENT_MAX_TOOL_CALLS,
        timeout_seconds: int = AI_AGENT_TURN_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        fallback_models: tuple[ProviderCandidate, ...] = (),
        circuit_breaker: ProviderCircuitBreaker | None = None,
    ) -> None:
        self.model = model
        self.registry = registry
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        provider_id = str(
            getattr(model, "provider_id", f"test:{model.__class__.__name__}:{id(model)}")
        )
        self.model_step_executor = ModelStepExecutor(
            primary=ProviderCandidate(provider_id, model),
            fallbacks=fallback_models,
            circuit_breaker=(
                circuit_breaker
                or (
                    _PROVIDER_CIRCUIT_BREAKER
                    if isinstance(model, ConfiguredNativeToolModel)
                    else ProviderCircuitBreaker()
                )
            ),
            clock=clock,
        )

    def run(
        self,
        task_id: str,
        request: dict[str, Any],
        *,
        resume: bool = False,
    ) -> None:
        conn = get_db(readonly=False)
        repo = AiTaskRepository(conn)
        persisted_events = repo.list_agent_turn_events(task_id) if resume else []
        checkpoint = build_resume_checkpoint(persisted_events) if persisted_events else None
        is_resuming = bool(checkpoint and checkpoint.resumable)
        turn_id = (
            str(persisted_events[-1]["turn_id"])
            if is_resuming and persisted_events
            else uuid.uuid4().hex
        )
        session_id = _session_id(conn, request)
        log = AgentEventLog(
            conn,
            task_id=task_id,
            turn_id=turn_id,
            session_id=session_id,
        )
        started_at = self.clock()
        metrics = RuntimeMetrics(clock=self.clock)
        temporal_context = _temporal_context(request)
        base_default_filters = _agent_default_filters(request)
        session_state = initial_session_state(
            request,
            default_filters=base_default_filters,
            temporal_context=temporal_context,
        )
        if is_resuming:
            session_state = restore_session_state(persisted_events, session_state)
        request["question"] = session_state.effective_question()
        request["_agent_session_state"] = session_state.to_dict()
        question_context = _question_context(request)
        turn_budget = _dynamic_budget(
            question_context,
            max_steps=self.max_steps,
            max_tool_calls=self.max_tool_calls,
            timeout_seconds=self.timeout_seconds,
        )
        tool_results: list[dict[str, Any]] = (
            list(checkpoint.recovered_tool_results) if is_resuming and checkpoint else []
        )
        executed_tool_calls = len(tool_results)
        answer_retried = False
        forced_tool_retry = False
        consecutive_duplicate_steps = 0
        last_step_index = 0
        try:
            if not _update_stage(
                repo,
                task_id=task_id,
                stage="agent_running",
                progress=0.05,
                message="Agent V2 正在恢复执行" if is_resuming else "Agent V2 正在理解问题",
                event_type="turn_resumed" if is_resuming else "turn_started",
                payload={"turn_id": turn_id, "runtime": "v2", "resumed": is_resuming},
            ):
                return
            if is_resuming:
                log.append(
                    "run_resumed",
                    {
                        "next_step": checkpoint.next_step if checkpoint else 1,
                        "completed_call_count": len(tool_results),
                    },
                )
            else:
                log.append(
                    "turn_started",
                    {
                        "runtime": "v2",
                        "budgets": {
                            **asdict(turn_budget),
                        },
                    },
                )
                log.append(
                    "session_state_initialized",
                    {"state": session_state.to_dict()},
                )
                repo.add_event(
                    task_id=task_id,
                    event_type="session_state_initialized",
                    stage="agent_running",
                    message="Agent 已建立分析约束",
                    payload={"state": session_state.public_constraints()},
                )

            profile = select_agent_profile(question_context, self.registry)
            log.append("agent_budget_selected", asdict(turn_budget))
            memory_messages = _initial_messages(
                request,
                question_context,
                _session_context(repo, session_id=session_id, task_id=task_id),
            )
            if not is_resuming:
                memory_messages.append({"role": "user", "content": session_state.model_context()})
            if is_resuming and checkpoint:
                messages = list(checkpoint.messages)
                log.append(
                    "context_projection_shadow",
                    {
                        "source": "event_log_recovery",
                        "matches": False,
                        "memory_message_count": len(memory_messages),
                        "event_log_message_count": len(messages),
                    },
                )
            else:
                for message in memory_messages:
                    log.append_model_message(message, origin="initial_context")
                context_source: ContextSource = (
                    "event_log" if AI_AGENT_CONTEXT_SOURCE == "event_log" else "memory"
                )
                messages, shadow_verdict = select_context_messages(
                    memory_messages=memory_messages,
                    events=log.list_events(),
                    source=context_source,
                )
                log.append("context_projection_shadow", shadow_verdict)
            log.append(
                "agent_profile_selected",
                {
                    "profile": profile.name,
                    "family": profile.family,
                    "tool_names": list(profile.tool_names),
                },
            )

            if profile.family == "safety_boundary":
                with metrics.measure_validation():
                    final_payload = _final_payload(request, [])
                    answer = _safety_boundary_answer(request)
                    issues = _combined_answer_issues(answer, final_payload)
                    answer = _apply_deterministic_answer_patches(answer, final_payload, issues, [])
                    validation_issues = _combined_answer_issues(answer, final_payload)
                result = _result_payload(
                    answer=answer,
                    tool_results=[],
                    request=request,
                    final_payload=final_payload,
                    answer_retried=False,
                    validation_issues=validation_issues,
                )
                runtime_metrics = metrics.snapshot()
                result.update(
                    {
                        "agent_runtime": "v2",
                        "turn_id": turn_id,
                        "steps": 0,
                        "stop_reason": "safety_boundary",
                        "runtime_metrics": runtime_metrics,
                    }
                )
                log.append(
                    "turn_ended",
                    {
                        "stop_reason": "safety_boundary",
                        "runtime_metrics": runtime_metrics,
                    },
                )
                _mark_done(repo, task_id=task_id, message="Agent Chat 已完成", result=result)
                return

            tool_runtime = ToolRuntime(
                registry=self.registry,
                task_repo=repo,
                event_log=log,
                task_id=task_id,
                default_filters=filters_for_session_state(
                    session_state,
                    base_default_filters,
                ),
                metrics=metrics,
                clock=self.clock,
                allowed_tool_names=set(profile.tool_names),
            )
            if is_resuming and checkpoint:
                tool_runtime.seed_outcomes(checkpoint.recovered_tool_results)
            schemas = tool_schemas_for_profile(self.registry, profile)

            if is_resuming and checkpoint and checkpoint.pending_tool_calls:
                resume_step = max(1, checkpoint.next_step - 1)
                for pending in checkpoint.pending_tool_calls:
                    self._check_continue(
                        repo,
                        task_id,
                        started_at,
                        timeout_seconds=turn_budget.turn_timeout_seconds,
                    )
                    outcome = tool_runtime.execute(
                        call_id=pending.call_id,
                        tool_name=pending.tool_name,
                        params=pending.params,
                        step_index=resume_step,
                    )
                    if not outcome.duplicate:
                        executed_tool_calls += 1
                        tool_results.append(outcome.legacy_payload())
                    recovered_message = {
                        "role": "tool",
                        "tool_call_id": pending.call_id,
                        "name": pending.tool_name,
                        "content": compact_json(outcome.model_payload()),
                    }
                    messages.append(recovered_message)
                    log.append_model_message(
                        recovered_message,
                        origin="recovered_tool_result",
                        step_index=resume_step,
                    )

            first_step = checkpoint.next_step if is_resuming and checkpoint else 1
            for step_index in range(first_step, self.max_steps + 1):
                last_step_index = step_index
                if step_index > turn_budget.max_steps:
                    break
                self._check_continue(
                    repo,
                    task_id,
                    started_at,
                    timeout_seconds=turn_budget.turn_timeout_seconds,
                )
                consumed_count, session_state, evidence_invalidated = _consume_session_inbox(
                    repo,
                    log,
                    messages,
                    task_id=task_id,
                    step_index=step_index,
                    state=session_state,
                    temporal_context=temporal_context,
                )
                if consumed_count:
                    if evidence_invalidated and tool_results:
                        invalidated_count = len(tool_results)
                        tool_results.clear()
                        log.append(
                            "tool_evidence_invalidated",
                            {
                                "reason": "session_state_updated",
                                "invalidated_result_count": invalidated_count,
                            },
                            step_index=step_index,
                        )
                    request["question"] = session_state.effective_question()
                    request["_agent_session_state"] = session_state.to_dict()
                    request.pop("_temporal_guard", None)
                    dynamic_context = _question_context(request)
                    profile = select_agent_profile(dynamic_context, self.registry)
                    schemas = tool_schemas_for_profile(self.registry, profile)
                    turn_budget = _dynamic_budget(
                        dynamic_context,
                        max_steps=self.max_steps,
                        max_tool_calls=self.max_tool_calls,
                        timeout_seconds=self.timeout_seconds,
                    )
                    tool_runtime.allowed_tool_names = set(profile.tool_names)
                    tool_runtime.default_filters = filters_for_session_state(
                        session_state,
                        _agent_default_filters(request),
                    )
                    log.append(
                        "agent_profile_updated",
                        {
                            "profile": profile.name,
                            "family": profile.family,
                            "tool_names": list(profile.tool_names),
                            "reason": "session_state_updated",
                            "budget": asdict(turn_budget),
                        },
                        step_index=step_index,
                    )
                progress = min(0.88, 0.1 + (step_index - 1) * 0.13)
                _update_stage(
                    repo,
                    task_id=task_id,
                    stage="agent_deciding",
                    progress=progress,
                    message=f"Agent 正在进行第 {step_index} 步决策",
                    event_type="step_started",
                    payload={"turn_id": turn_id, "step_index": step_index},
                )
                log.append("step_started", {}, step_index=step_index)
                model_input_chars = len(
                    json.dumps(messages, ensure_ascii=False, default=str)
                ) + len(json.dumps(schemas, ensure_ascii=False, default=str))
                model_call_id = f"{turn_id}:step:{step_index}:model"
                log.append(
                    "model_request",
                    {
                        "turn_id": turn_id,
                        "step_index": step_index,
                        "model_call_id": model_call_id,
                        "message_count": len(messages),
                        "tool_count": len(schemas),
                        "thinking": _thinking_mode_enabled(request),
                        "input_chars": model_input_chars,
                    },
                    step_index=step_index,
                )
                try:
                    model_step = self.model_step_executor.execute(
                        messages=messages,
                        tools=schemas,
                        thinking=_thinking_mode_enabled(request),
                        budget=turn_budget,
                    )
                except ModelStepExhaustedError as exc:
                    model_elapsed_ms = _record_model_attempts(
                        metrics,
                        exc.attempts,
                        usage=None,
                        input_chars=model_input_chars,
                    )
                    log.append(
                        "model_step_failed",
                        {
                            "model_call_id": model_call_id,
                            "attempts": _safe_attempt_payload(exc.attempts),
                            "elapsed_ms": model_elapsed_ms,
                        },
                        step_index=step_index,
                    )
                    if self._publish_provider_degraded_answer(
                        repo=repo,
                        log=log,
                        task_id=task_id,
                        turn_id=turn_id,
                        step_index=step_index,
                        request=request,
                        tool_results=tool_results,
                        metrics=metrics,
                        attempts=exc.attempts,
                        answer_retried=answer_retried,
                    ):
                        return
                    raise ChatAgentError("模型服务暂时不可用，且尚未取得可发布的本地证据") from exc
                completion = model_step.completion
                model_elapsed_ms = _record_model_attempts(
                    metrics,
                    model_step.attempts,
                    usage=completion.usage,
                    input_chars=model_input_chars,
                )
                log.append(
                    "model_step_attempts",
                    {
                        "model_call_id": model_call_id,
                        "provider_id": model_step.provider_id,
                        "attempts": _safe_attempt_payload(model_step.attempts),
                    },
                    step_index=step_index,
                )
                # Provider calls are synchronous today.  Re-check immediately
                # after they return so a cancellation can never be followed by
                # a fresh tool invocation or result publication.
                self._check_continue(
                    repo,
                    task_id,
                    started_at,
                    timeout_seconds=turn_budget.turn_timeout_seconds,
                )
                assistant = assistant_message(completion)
                messages.append(assistant)
                log.append_model_message(
                    assistant,
                    origin="model_response",
                    step_index=step_index,
                )
                log.append(
                    "assistant_message",
                    {
                        "turn_id": turn_id,
                        "step_index": step_index,
                        "model_call_id": model_call_id,
                        "has_content": bool(completion.content.strip()),
                        "tool_call_count": len(completion.tool_calls),
                        "finish_reason": completion.finish_reason,
                        "usage": completion.usage,
                        "elapsed_ms": model_elapsed_ms,
                    },
                    step_index=step_index,
                )

                if completion.tool_calls:
                    if (
                        executed_tool_calls + len(completion.tool_calls)
                        > turn_budget.max_tool_calls
                    ):
                        raise AgentBudgetExceededError("Agent 工具调用超过上限")
                    guarded_calls, temporal_guard = apply_temporal_guard(
                        str(request.get("question") or ""),
                        _temporal_context(request),
                        [
                            {"tool_name": call.name, "params": call.arguments}
                            for call in completion.tool_calls
                        ],
                    )
                    request["_temporal_guard"] = temporal_guard
                    duplicate_count = 0
                    paired_calls = list(zip(completion.tool_calls, guarded_calls))
                    for offset in range(0, len(paired_calls), 2):
                        self._check_continue(
                            repo,
                            task_id,
                            started_at,
                            timeout_seconds=turn_budget.turn_timeout_seconds,
                        )
                        chunk = paired_calls[offset : offset + 2]
                        outcomes = tool_runtime.execute_batch(
                            [
                                {
                                    "call_id": call.call_id,
                                    "tool_name": str(guarded.get("tool_name") or call.name),
                                    "params": guarded.get("params") or {},
                                }
                                for call, guarded in chunk
                            ],
                            step_index=step_index,
                        )
                        for (call, _guarded), outcome in zip(chunk, outcomes):
                            if outcome.duplicate:
                                duplicate_count += 1
                            else:
                                executed_tool_calls += 1
                                tool_results.append(outcome.legacy_payload())
                            observed_tool_message = tool_message(
                                call,
                                outcome.model_payload(),
                            )
                            messages.append(observed_tool_message)
                            log.append_model_message(
                                observed_tool_message,
                                origin="tool_result",
                                step_index=step_index,
                            )
                    if duplicate_count == len(completion.tool_calls):
                        consecutive_duplicate_steps += 1
                    else:
                        consecutive_duplicate_steps = 0
                    if consecutive_duplicate_steps >= 2:
                        raise AgentBudgetExceededError("Agent 连续重复同一工具调用，已停止循环")
                    log.append("step_ended", {"outcome": "tools"}, step_index=step_index)
                    continue

                proposed_answer = completion.content.strip()
                if not tool_results and not forced_tool_retry:
                    forced_tool_retry = True
                    correction = {
                        "role": "user",
                        "content": (
                            "你还没有查询任何本地数据。这个问题需要事实证据；"
                            "请先调用合适的只读工具，观察结果后再回答。"
                        ),
                    }
                    messages.append(correction)
                    log.append_model_message(
                        correction,
                        origin="runtime_guardrail",
                        step_index=step_index,
                    )
                    log.append(
                        "guardrail_retry",
                        {"reason": "answer_without_evidence"},
                        step_index=step_index,
                    )
                    continue
                if not proposed_answer:
                    if tool_results:
                        raise AgentBudgetExceededError("模型未返回最终文本，已切换到现有证据回答")
                    raise ChatAgentError("模型未返回回答或工具调用")

                with metrics.measure_validation():
                    final_payload = _final_payload(request, tool_results)
                    issues = _validate_answer(proposed_answer, final_payload)
                    proposed_answer = _apply_deterministic_answer_patches(
                        proposed_answer,
                        final_payload,
                        issues,
                        tool_results,
                    )
                    issues = _validate_answer(proposed_answer, final_payload)
                if issues and not answer_retried and step_index < turn_budget.max_steps:
                    answer_retried = True
                    correction = {
                        "role": "user",
                        "content": _answer_repair_message(
                            final_payload,
                            proposed_answer,
                            issues,
                        ),
                    }
                    messages.append(correction)
                    log.append_model_message(
                        correction,
                        origin="answer_validator",
                        step_index=step_index,
                    )
                    log.append(
                        "guardrail_retry",
                        {"reason": "answer_validation", "issues": issues},
                        step_index=step_index,
                    )
                    continue

                with metrics.measure_validation():
                    answer = _apply_deterministic_answer_patches(
                        proposed_answer,
                        final_payload,
                        issues,
                        tool_results,
                    )
                    validation_issues = _validate_answer(answer, final_payload)
                    answer, validation_issues, grounded_fallback_used = _ensure_v2_grounded_answer(
                        answer,
                        final_payload,
                        validation_issues,
                        request=request,
                        tool_results=tool_results,
                    )
                result = _result_payload(
                    answer=answer,
                    tool_results=tool_results,
                    request=request,
                    final_payload=final_payload,
                    answer_retried=answer_retried,
                    validation_issues=validation_issues,
                    grounded_fallback_used=grounded_fallback_used,
                )
                runtime_metrics = metrics.snapshot()
                result.update(
                    {
                        "agent_runtime": "v2",
                        "turn_id": turn_id,
                        "steps": step_index,
                        "stop_reason": "final_answer",
                        "runtime_metrics": runtime_metrics,
                    }
                )
                log.append(
                    "turn_ended",
                    {
                        "stop_reason": "final_answer",
                        "steps": step_index,
                        "tool_call_count": executed_tool_calls,
                        "validation_issues": validation_issues,
                        "runtime_metrics": runtime_metrics,
                    },
                )
                _mark_done(repo, task_id=task_id, message="Agent Chat 已完成", result=result)
                return

            raise AgentBudgetExceededError("Agent 达到最大步骤数，仍未形成可靠回答")
        except AgentCancelledError:
            log.append("run_cancelled", {"runtime_metrics": metrics.snapshot()})
        except AgentBudgetExceededError as exc:
            if self._publish_evidence_degraded_answer(
                repo=repo,
                log=log,
                task_id=task_id,
                turn_id=turn_id,
                step_index=last_step_index,
                request=request,
                tool_results=tool_results,
                metrics=metrics,
                answer_retried=answer_retried,
                stop_reason="budget_degraded_fallback",
                message="运行预算已到，已基于取得的本地证据完成保守回答",
                result_extra={"budget_degraded": True},
            ):
                return
            error_message = str(exc) or exc.__class__.__name__
            log.append(
                "run_failed",
                {"error": error_message, "runtime_metrics": metrics.snapshot()},
            )
            _mark_error(
                repo,
                task_id=task_id,
                message=error_message,
                result={"error": error_message},
            )
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            log.append(
                "run_failed",
                {"error": error_message, "runtime_metrics": metrics.snapshot()},
            )
            _mark_error(
                repo,
                task_id=task_id,
                message=error_message,
                result={"error": error_message},
            )
        finally:
            conn.close()

    def _publish_provider_degraded_answer(
        self,
        *,
        repo: AiTaskRepository,
        log: AgentEventLog,
        task_id: str,
        turn_id: str,
        step_index: int,
        request: dict[str, Any],
        tool_results: list[dict[str, Any]],
        metrics: RuntimeMetrics,
        attempts: tuple[ModelStepAttempt, ...],
        answer_retried: bool,
    ) -> bool:
        return self._publish_evidence_degraded_answer(
            repo=repo,
            log=log,
            task_id=task_id,
            turn_id=turn_id,
            step_index=step_index,
            request=request,
            tool_results=tool_results,
            metrics=metrics,
            answer_retried=answer_retried,
            stop_reason="provider_degraded_fallback",
            message="模型服务波动，已基于现有本地证据完成保守回答",
            result_extra={
                "provider_degraded": True,
                "provider_attempts": _safe_attempt_payload(attempts),
            },
        )

    def _publish_evidence_degraded_answer(
        self,
        *,
        repo: AiTaskRepository,
        log: AgentEventLog,
        task_id: str,
        turn_id: str,
        step_index: int,
        request: dict[str, Any],
        tool_results: list[dict[str, Any]],
        metrics: RuntimeMetrics,
        answer_retried: bool,
        stop_reason: str,
        message: str,
        result_extra: dict[str, Any],
    ) -> bool:
        usable_evidence = any(
            str(item.get("status") or "") not in {"", "error"} for item in tool_results
        )
        if not usable_evidence:
            return False
        with metrics.measure_validation():
            final_payload = _final_payload(request, tool_results)
            answer = _render_evidence_fallback(request, tool_results, final_payload)
            validation_issues = _validate_answer(answer, final_payload)
            answer = _apply_deterministic_answer_patches(
                answer,
                final_payload,
                validation_issues,
                tool_results,
            )
            validation_issues = _validate_answer(answer, final_payload)
            answer, validation_issues, _ = _ensure_v2_grounded_answer(
                answer,
                final_payload,
                validation_issues,
                request=request,
                tool_results=tool_results,
            )
        result = _result_payload(
            answer=answer,
            tool_results=tool_results,
            request=request,
            final_payload=final_payload,
            answer_retried=answer_retried,
            validation_issues=validation_issues,
            grounded_fallback_used=True,
        )
        runtime_metrics = metrics.snapshot()
        result.update(
            {
                "agent_runtime": "v2",
                "turn_id": turn_id,
                "steps": step_index,
                "stop_reason": stop_reason,
                "runtime_metrics": runtime_metrics,
                **result_extra,
            }
        )
        log.append(
            "turn_ended",
            {
                "stop_reason": stop_reason,
                "steps": step_index,
                "tool_call_count": len(tool_results),
                "validation_issues": validation_issues,
                "runtime_metrics": runtime_metrics,
            },
            step_index=step_index,
        )
        _mark_done(
            repo,
            task_id=task_id,
            message=message,
            result=result,
        )
        return True

    def _check_continue(
        self,
        repo: AiTaskRepository,
        task_id: str,
        started_at: float,
        *,
        timeout_seconds: int | None = None,
    ) -> None:
        if cancellation_registry.is_cancel_requested(task_id) or _is_terminal(repo, task_id):
            raise AgentCancelledError("Agent 任务已取消")
        if self.clock() - started_at > (timeout_seconds or self.timeout_seconds):
            raise AgentBudgetExceededError("Agent 回合执行超时")


def run_chat_agent_task_v2(
    task_id: str,
    request: dict[str, Any],
    *,
    resume: bool = False,
) -> None:
    initial_budget = _dynamic_budget(_question_context(request))
    runtime = AgentRuntime(
        model=ConfiguredNativeToolModel(initial_budget),
        registry=get_default_registry(),
    )
    runtime.run(task_id, request, resume=resume)
