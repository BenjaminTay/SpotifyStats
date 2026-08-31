"""Native tool-calling, observation-driven chat agent runtime."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
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
from backend.domains.agent_runtime.native_loop import NativeObservationLoop, tool_message
from backend.domains.agent_runtime.projections import ContextSource, select_context_messages
from backend.domains.agent_runtime.recovery import build_resume_checkpoint
from backend.domains.agent_runtime.serialization import compact_json
from backend.domains.agent_runtime.tool_runtime import ToolRuntime
from backend.domains.agent_runtime.tool_selector import (
    select_agent_profile,
    tool_schemas_for_profile,
)
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
    _ensure_grounded_answer,
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


class ConfiguredNativeToolModel:
    """Resolve the configured provider and require its native tool protocol."""

    def __init__(self) -> None:
        cfg = ai_insights_service._get_config()
        initial = ai_insights_service._get_llm(cfg)
        if initial is None:
            raise ChatAgentError("LLM 未配置，无法启动 Agent V2")
        provider_config = ProviderConfig(
            name=f"agent-v2-{initial.provider}",
            base_url=initial.base_url,
            timeout=AI_AGENT_LLM_TIMEOUT_SECONDS,
            retries=AI_AGENT_LLM_RETRIES,
            rate_limit_rps=3.0,
            http_proxy=HTTP_PROXY or "",
            https_proxy=HTTPS_PROXY or "",
        )
        resolved = ai_insights_service._get_llm(cfg, provider_config=provider_config)
        if resolved is None:
            raise ChatAgentError("LLM 未配置，无法启动 Agent V2")
        self.llm = resolved

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
            max_tokens=4096,
            thinking=thinking,
        )


class AgentCancelledError(ChatAgentError):
    pass


class AgentBudgetExceededError(ChatAgentError):
    pass


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
) -> int:
    inputs = repo.consume_agent_inputs(task_id)
    for item in inputs:
        message = {
            "role": "user",
            "content": (
                f"用户在运行中补充（{item['input_type']}）：{str(item['content']).strip()}"
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
            },
            step_index=step_index,
        )
    return len(inputs)


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
    ) -> None:
        self.model = model
        self.registry = registry
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.clock = clock

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
        tool_results: list[dict[str, Any]] = (
            list(checkpoint.recovered_tool_results) if is_resuming and checkpoint else []
        )
        executed_tool_calls = len(tool_results)
        answer_retried = False
        forced_tool_retry = False
        consecutive_duplicate_steps = 0
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
                            "max_steps": self.max_steps,
                            "max_tool_calls": self.max_tool_calls,
                            "timeout_seconds": self.timeout_seconds,
                        },
                    },
                )

            question_context = _question_context(request)
            profile = select_agent_profile(question_context, self.registry)
            memory_messages = _initial_messages(
                request,
                question_context,
                _session_context(repo, session_id=session_id, task_id=task_id),
            )
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
                default_filters=_agent_default_filters(request),
                metrics=metrics,
                clock=self.clock,
                allowed_tool_names=set(profile.tool_names),
            )
            if is_resuming and checkpoint:
                tool_runtime.seed_outcomes(checkpoint.recovered_tool_results)
            schemas = tool_schemas_for_profile(self.registry, profile)
            observation_loop = NativeObservationLoop(
                model=self.model,
                schemas=schemas,
                thinking=_thinking_mode_enabled(request),
                clock=self.clock,
            )

            if is_resuming and checkpoint and checkpoint.pending_tool_calls:
                resume_step = max(1, checkpoint.next_step - 1)
                for pending in checkpoint.pending_tool_calls:
                    self._check_continue(repo, task_id, started_at)
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
                self._check_continue(repo, task_id, started_at)
                _consume_session_inbox(
                    repo,
                    log,
                    messages,
                    task_id=task_id,
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
                model_started_at = self.clock()
                try:
                    model_step = observation_loop.complete_step(messages)
                except Exception:
                    metrics.record_model(
                        elapsed_ms=round((self.clock() - model_started_at) * 1000),
                        usage={},
                        input_chars=model_input_chars,
                    )
                    raise
                completion = model_step.completion
                model_elapsed_ms = model_step.elapsed_ms
                metrics.record_model(
                    elapsed_ms=model_elapsed_ms,
                    usage=completion.usage,
                    input_chars=model_input_chars,
                )
                # Provider calls are synchronous today.  Re-check immediately
                # after they return so a cancellation can never be followed by
                # a fresh tool invocation or result publication.
                self._check_continue(repo, task_id, started_at)
                assistant = model_step.assistant_message
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
                    if executed_tool_calls + len(completion.tool_calls) > self.max_tool_calls:
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
                        self._check_continue(repo, task_id, started_at)
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
                if issues and not answer_retried and step_index < self.max_steps:
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
                    answer, validation_issues, grounded_fallback_used = _ensure_grounded_answer(
                        answer,
                        final_payload,
                        validation_issues,
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

    def _check_continue(
        self,
        repo: AiTaskRepository,
        task_id: str,
        started_at: float,
    ) -> None:
        if cancellation_registry.is_cancel_requested(task_id) or _is_terminal(repo, task_id):
            raise AgentCancelledError("Agent 任务已取消")
        if self.clock() - started_at > self.timeout_seconds:
            raise AgentBudgetExceededError("Agent 回合执行超时")


def run_chat_agent_task_v2(
    task_id: str,
    request: dict[str, Any],
    *,
    resume: bool = False,
) -> None:
    runtime = AgentRuntime(
        model=ConfiguredNativeToolModel(),
        registry=get_default_registry(),
    )
    runtime.run(task_id, request, resume=resume)
