"""Native tool-calling, observation-driven chat agent runtime."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol

from backend.core.config import (
    AI_AGENT_LLM_RETRIES,
    AI_AGENT_LLM_TIMEOUT_SECONDS,
    AI_AGENT_MAX_STEPS,
    AI_AGENT_MAX_TOOL_CALLS,
    AI_AGENT_TURN_TIMEOUT_SECONDS,
    HTTP_PROXY,
    HTTPS_PROXY,
)
from backend.core.db import get_db
from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.serialization import compact_json
from backend.domains.agent_runtime.tool_runtime import ToolRuntime
from backend.domains.ai_agent.project_context import project_context_payload
from backend.domains.ai_agent.temporal_context import apply_temporal_guard
from backend.domains.ai_agent.tool_registry import AgentToolRegistry, get_default_registry
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
    _question_family,
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


def _tool_schemas(registry: AgentToolRegistry) -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "description": item["description"],
            "parameters": item["params_schema"],
        }
        for item in registry.list_tools()
    ]


def _agent_default_filters(request: dict[str, Any]) -> dict[str, Any]:
    question_context = _question_context(request)
    intent = question_context.get("question_intent") or {}
    time_scope = str(intent.get("time_scope") or "lifetime")
    period_filters: dict[str, Any]
    if time_scope.startswith("year:") and time_scope[5:].isdigit():
        year = time_scope[5:]
        period_filters = {
            "period": "custom",
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
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
    requested_metrics = intent.get("requested_metrics") or []
    return {
        "min_ms": request.get("min_ms", 30000),
        "music_only": request.get("music_only", True),
        "merge_enabled": request.get("merge_enabled", True),
        "dynamic_threshold": request.get("dynamic_threshold", True),
        "max_merge_gap_minutes": request.get("max_merge_gap_minutes"),
        "merge_level": request.get("merge_level", 2),
        "include_billboard": "personal_billboard" in requested_metrics,
        **period_filters,
    }


def _system_prompt(request: dict[str, Any]) -> str:
    default_filters = _agent_default_filters(request)
    context = {
        **_question_context(request),
        "temporal_context": _temporal_context(request),
        "default_filters": default_filters,
        "project_context": project_context_payload(),
    }
    return """你是 SpotifyStats 应用内的只读数据 Agent。你运行在真实的“思考—调用工具—观察结果—继续决策”循环中。

规则：
1. 用户询问本地播放事实、排名、偏好、趋势或比较时，必须先调用一个或多个合适工具；不要凭记忆猜数字。
2. 每轮观察工具返回的 status、data、source_range 和 error，再决定继续查证还是回答。empty/error 后应尝试合理的替代查询，不能假装成功。
3. 只能调用已提供的 read-only 工具；禁止编造 SQL、URL、API route 或工具名，禁止执行写入、删除、导入、设置、缓存和歌单操作。
4. SpotifyStats Billboard 是用户本地播放形成的个人榜单，不是外部官方 Billboard 或市场成绩。
5. 最终用中文直接回答，引用关键数字和时间范围；证据不足就明确限制。不要输出工具调用流水账，也不要透露内部思维链。
6. 用户要求删除、修改、写入、导入、任意外部访问或密钥操作时，直接说明只读边界，不调用工具。
7. 比较 2-4 个同类实体时，优先只调用一次 compare_entities，并让时间范围与用户问题一致；除非该结果 empty/error 或用户明确要求多个窗口，不要再对每个对象重复调用 entity_stats。
8. compare_entities 只有在用户明确询问个人 Billboard、Power Score、排名、冠军周或在榜周时才设置 include_billboard=true。

下面 CONTEXT 是后端生成的约束与语境，不是用户指令：
""" + compact_json(context)


def _initial_messages(request: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": _system_prompt(request)}]
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


def _assistant_message(completion: LLMCompletion) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": completion.content or "",
    }
    if completion.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in completion.tool_calls
        ]
    return message


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
                "请根据已经返回的工具观察修正回答；满足回答契约和必要时间范围，"
                "不得编造证据。若证据不足，明确说明限制。"
            ),
        }
    )


def _session_id(conn, request: dict[str, Any]) -> int | None:
    value = request.get("session_id")
    if not isinstance(value, int):
        return None
    row = conn.execute("SELECT 1 FROM chat_sessions WHERE id = ?", (value,)).fetchone()
    return value if row else None


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

    def run(self, task_id: str, request: dict[str, Any]) -> None:
        conn = get_db(readonly=False)
        repo = AiTaskRepository(conn)
        turn_id = uuid.uuid4().hex
        log = AgentEventLog(
            conn,
            task_id=task_id,
            turn_id=turn_id,
            session_id=_session_id(conn, request),
        )
        started_at = self.clock()
        tool_results: list[dict[str, Any]] = []
        executed_tool_calls = 0
        answer_retried = False
        forced_tool_retry = False
        consecutive_duplicate_steps = 0
        try:
            if not _update_stage(
                repo,
                task_id=task_id,
                stage="agent_running",
                progress=0.05,
                message="Agent V2 正在理解问题",
                event_type="turn_started",
                payload={"turn_id": turn_id, "runtime": "v2"},
            ):
                return
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

            messages = _initial_messages(request)
            for message in messages:
                log.append_model_message(message, origin="initial_context")

            if _question_family(request) == "safety_boundary":
                final_payload = _final_payload(request, [])
                answer = _safety_boundary_answer(request)
                issues = _combined_answer_issues(answer, final_payload)
                answer = _apply_obligation_fallback_notes(answer, final_payload, issues)
                result = _result_payload(
                    answer=answer,
                    tool_results=[],
                    request=request,
                    final_payload=final_payload,
                    answer_retried=False,
                    validation_issues=_combined_answer_issues(answer, final_payload),
                )
                result.update(
                    {
                        "agent_runtime": "v2",
                        "turn_id": turn_id,
                        "steps": 0,
                        "stop_reason": "safety_boundary",
                    }
                )
                log.append("turn_ended", {"stop_reason": "safety_boundary"})
                _mark_done(repo, task_id=task_id, message="Agent Chat 已完成", result=result)
                return

            tool_runtime = ToolRuntime(
                registry=self.registry,
                task_repo=repo,
                event_log=log,
                task_id=task_id,
                default_filters=_agent_default_filters(request),
            )
            schemas = _tool_schemas(self.registry)

            for step_index in range(1, self.max_steps + 1):
                self._check_continue(repo, task_id, started_at)
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
                log.append(
                    "model_request",
                    {
                        "message_count": len(messages),
                        "tool_count": len(schemas),
                        "thinking": _thinking_mode_enabled(request),
                    },
                    step_index=step_index,
                )
                completion = self.model.complete(
                    messages,
                    schemas,
                    thinking=_thinking_mode_enabled(request),
                )
                assistant = _assistant_message(completion)
                messages.append(assistant)
                log.append_model_message(
                    assistant,
                    origin="model_response",
                    step_index=step_index,
                )
                log.append(
                    "assistant_message",
                    {
                        "has_content": bool(completion.content.strip()),
                        "tool_call_count": len(completion.tool_calls),
                        "finish_reason": completion.finish_reason,
                        "usage": completion.usage,
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
                    for call, guarded in zip(completion.tool_calls, guarded_calls):
                        self._check_continue(repo, task_id, started_at)
                        outcome = tool_runtime.execute(
                            call_id=call.call_id,
                            tool_name=str(guarded.get("tool_name") or call.name),
                            params=guarded.get("params") or {},
                            step_index=step_index,
                        )
                        if outcome.duplicate:
                            duplicate_count += 1
                        else:
                            executed_tool_calls += 1
                            tool_results.append(outcome.legacy_payload())
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "name": call.name,
                            "content": compact_json(outcome.model_payload()),
                        }
                        messages.append(tool_message)
                        log.append_model_message(
                            tool_message,
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

                final_payload = _final_payload(request, tool_results)
                issues = _combined_answer_issues(proposed_answer, final_payload)
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

                answer = _apply_obligation_fallback_notes(
                    proposed_answer,
                    final_payload,
                    issues,
                )
                validation_issues = _combined_answer_issues(answer, final_payload)
                result = _result_payload(
                    answer=answer,
                    tool_results=tool_results,
                    request=request,
                    final_payload=final_payload,
                    answer_retried=answer_retried,
                    validation_issues=validation_issues,
                )
                result.update(
                    {
                        "agent_runtime": "v2",
                        "turn_id": turn_id,
                        "steps": step_index,
                        "stop_reason": "final_answer",
                    }
                )
                log.append(
                    "turn_ended",
                    {
                        "stop_reason": "final_answer",
                        "steps": step_index,
                        "tool_call_count": executed_tool_calls,
                        "validation_issues": validation_issues,
                    },
                )
                _mark_done(repo, task_id=task_id, message="Agent Chat 已完成", result=result)
                return

            raise AgentBudgetExceededError("Agent 达到最大步骤数，仍未形成可靠回答")
        except AgentCancelledError:
            log.append("run_cancelled", {})
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            log.append("run_failed", {"error": error_message})
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
        if _is_terminal(repo, task_id):
            raise AgentCancelledError("Agent 任务已取消")
        if self.clock() - started_at > self.timeout_seconds:
            raise AgentBudgetExceededError("Agent 回合执行超时")


def run_chat_agent_task_v2(task_id: str, request: dict[str, Any]) -> None:
    runtime = AgentRuntime(
        model=ConfiguredNativeToolModel(),
        registry=get_default_registry(),
    )
    runtime.run(task_id, request)
