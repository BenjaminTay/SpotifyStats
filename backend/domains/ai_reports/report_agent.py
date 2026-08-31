"""Agent-based yearly report generation with multi-turn tool calling.

Replaces the single-call report_writer.py with a true agent loop:
  Plan research → Execute snapshot-backed tools → Review coverage → Write sections.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.domains.agent_runtime.native_loop import (
    NativeObservationLoop,
    NativeToolObservation,
)
from backend.domains.ai_reports.agentic_tools import (
    REPORT_TOOL_NAMES,
    execute_report_tool,
    list_report_tools,
    report_tool_schemas,
)
from backend.domains.ai_reports.report_section_protocol import (
    audit_report_sections,
    strip_unsupported_numeric_sentences,
)
from backend.domains.ai_reports.section_writer import (
    SectionAuditResult,
    SectionCompletion,
    SectionWritePlan,
    write_report_sections,
)

logger = logging.getLogger(__name__)

# ── Agent prompts ─────────────────────────────────────────────────────────────

REPORT_PLANNER_SYSTEM_PROMPT = """你是 SpotifyStats 的年度音乐报告研究员。你的任务是为用户的年度音乐报告制定研究计划并执行数据调查。

## 可用工具
{tools_description}

## 工作流程
1. 阅读研究任务，制定调查计划
2. 调用工具获取数据，每次调用后分析结果
3. 根据发现深入追查——如果数据暗示有趣的故事，继续深挖
4. 只使用本任务提供的本地只读播放数据工具，不访问外部网络
5. 当所有重要维度都调查充分后，输出最终研究摘要

## 输出格式（JSON）
{{
  "plan": ["要调查的维度列表，如：年度总览、艺人排名、月度趋势、专辑分析、曲风分布、新发现、高光时刻"],
  "investigations": [
    {{
      "dimension": "维度名",
      "tools_called": ["tool_name"],
      "findings": "调查发现的关键事实和数据",
      "insight": "从数据中发现的值得写入报告的故事或趋势"
    }}
  ],
  "research_summary": "综合所有调查得出的完整研究摘要，包含关键数字和发现，供后续写作使用。"
}}

## 规则
- 每个维度至少调用 1 个数据工具，重要维度（艺人、专辑）至少调用 2-3 个
- 不得补写本地数据没有提供的艺人背景、专辑背景或外部事件
- 调查深度优先于调查广度——宁可有 5 个深入分析的维度，不要 10 个浅尝辄止的
- 发现异常数据（如月度逆转、双榜差异）必须深入追查
"""

REPORT_WRITER_INSTRUCTION = """
## 研究完成，现在撰写年度报告

基于以上所有工具调查结果和图表数据，撰写一份信息密度高、有洞察力的年度音乐回顾。

核心原则：
- 写 6 至 8 节，总正文不少于 3000 个中文字符；每节围绕一个清晰问题展开
- 每节只选 1 至 3 个最有解释力的数字，必须逐字来自工具或图表数据，不能计算或猜测新数字
- 从数据中找故事——有趣的异常和趋势比全面覆盖更重要
- 艺人/专辑/歌曲名完整写出，数字带单位，时间带月份
- 必须明确提到年度 Top 单曲与 Top 专辑，并解释它们与艺人、月份或个人 Billboard 的关系
- 禁止废话：不要写"反复回到的声音""低阻力回访""不同场景里都能成立"等模板表述
- is_partial_year 时用"截至 X""阶段性"，不说"全年"；Billboard 时说明"基于本地播放记录的个人 Billboard"
- 禁止：前者/后者指代、推断艺人性别（她/他）、艺人名加括号附注英文

输出严格 JSON：{"sections": [{"heading": "标题", "prose": "正文(Markdown)", "chart_refs": ["chart_id"], "evidence_refs": ["tool_name"]}]}
每节必须在 evidence_refs 中列出实际支撑该节的工具名；没有使用某工具时不得填写。
"""


# ── Agent loop ────────────────────────────────────────────────────────────────


def _summarize_chart_data(
    chart_data: dict[str, Any], chart_specs: list[dict[str, Any]]
) -> dict[str, Any]:
    summary = {}
    for spec in chart_specs:
        cid = spec.get("id", "")
        data = chart_data.get(cid, {})
        if isinstance(data, dict):
            obs = data.get("observations", [])
            if obs:
                summary[cid] = {"title": spec.get("title", cid), "key_facts": obs[:3]}
    return summary


def _extract_tool_calls(text: str) -> list[dict[str, Any]]:
    import re

    calls = []
    try:
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                return [c for c in parsed if isinstance(c, dict) and "tool_name" in c]
    except (json.JSONDecodeError, AttributeError):
        pass
    for m in re.finditer(r'"tool_name"\s*:\s*"(\w+)"\s*,\s*"params"\s*:\s*(\{[^}]+\})', text):
        try:
            calls.append({"tool_name": m.group(1), "params": json.loads(m.group(2))})
        except json.JSONDecodeError:
            pass
    return calls[:8]


def _format_tool_results(results: list[dict[str, Any]]) -> str:
    lines = []
    for r in results:
        name = r.get("_tool_name", "unknown")
        summary = r.get("result_summary", "") or str(r.get("data", ""))[:300]
        lines.append(f"- [{name}] {summary}")
    return "\n".join(lines)


def _compile_research_from_tools(tool_results: list[dict[str, Any]]) -> str:
    lines = ["## 工具调查结果"]
    for r in tool_results:
        name = r.get("_tool_name", "unknown")
        summary = r.get("result_summary", "")
        lines.append(f"\n### {name}\n{summary}")
    return "\n".join(lines)


def _native_report_research(
    *,
    planner_prompt: str,
    planner_user: str,
    base_filters: dict[str, Any],
    year: int,
    end_date: str,
    research_context: dict[str, Any],
    emit_event: Any,
) -> tuple[str, list[dict[str, Any]]]:
    """Run report research through the same native observation loop as chat."""

    from backend.core.config import AI_AGENT_MAX_STEPS, AI_AGENT_MAX_TOOL_CALLS
    from backend.services.ai_agent_v2_service import ConfiguredNativeToolModel

    schemas = report_tool_schemas()
    model = ConfiguredNativeToolModel()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": planner_prompt},
        {"role": "user", "content": planner_user},
    ]
    results: list[dict[str, Any]] = []
    identities: set[str] = set()

    def execute_tool(call, _step: int) -> NativeToolObservation:
        try:
            params = dict(call.arguments)
            if call.name not in REPORT_TOOL_NAMES:
                raise ValueError(f"Tool is outside the report snapshot profile: {call.name}")
            params.update({key: value for key, value in base_filters.items() if value is not None})
            params["year"] = year
            identity = f"{call.name}:{json.dumps(params, ensure_ascii=False, sort_keys=True)}"
            if identity in identities:
                duplicate = {
                    "status": "duplicate",
                    "tool_name": call.name,
                    "error": "相同参数已查询，请基于已有结果继续推理",
                }
                return NativeToolObservation(
                    model_payload=duplicate,
                    result_payload=duplicate,
                    counted=False,
                )
            identities.add(identity)
            raw = execute_report_tool(call.name, params, context=research_context)
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            status = "empty" if data.get("found") is False else "ok"
            item = {
                **raw,
                "status": status,
                "_tool_name": call.name,
                "_params": params,
                "result_summary": raw.get("summary") or raw.get("result_summary") or "",
            }
            results.append(item)
            return NativeToolObservation(
                model_payload={
                    "status": status,
                    "tool_name": call.name,
                    "result_summary": item["result_summary"],
                    "source_range": raw.get("source_range"),
                    "data": data,
                },
                result_payload=item,
            )
        except Exception as exc:
            item = {
                "_tool_name": call.name,
                "_params": call.arguments,
                "status": "error",
                "error": str(exc) or exc.__class__.__name__,
            }
            results.append(item)
            return NativeToolObservation(model_payload=item, result_payload=item)

    def on_step(step: int, tool_count: int) -> None:
        if emit_event:
            emit_event(
                "stage_started",
                f"研究步骤 {step}：累计调用 {tool_count} 个工具",
                {
                    "stage": "researching",
                    "progress_pct": min(0.75, 0.25 + step * 0.08),
                    "runtime": "v2",
                    "agent_profile": "yearly_snapshot_readonly",
                },
            )

    loop_result = NativeObservationLoop(
        model=model,
        schemas=schemas,
        thinking=True,
    ).run(
        messages=messages,
        execute_tool=execute_tool,
        max_steps=AI_AGENT_MAX_STEPS,
        max_tool_calls=AI_AGENT_MAX_TOOL_CALLS,
        on_step=on_step,
    )
    research = loop_result.content or _compile_research_from_tools(results)
    return research, results


def run_report_agent(
    *,
    year: int,
    is_partial_year: bool,
    end_date: str,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    chart_data: dict[str, Any],
    chart_specs: list[dict[str, Any]],
    research_context: dict[str, Any] | None = None,
    runtime_metrics: Any = None,
    fallback_sections: list[dict[str, Any]] | None = None,
    emit_event: Any = None,
) -> dict[str, Any]:
    """Run the multi-turn agent loop to research and write a yearly report.

    Returns: {"sections": [...], "research_summary": str, "evidence": [...]}
    """
    from backend.services.ai_insights_service import _llm_chat

    # ── Build tool description for the planner ──
    tools_desc = "\n".join(
        f"- **{item['name']}**: {item['description']}" for item in list_report_tools()
    )

    # ── Phase 1: Research Planning + Execution ──
    base_filters = {
        "min_ms": min_ms,
        "music_only": music_only,
        "merge_enabled": merge_enabled,
        "dynamic_threshold": dynamic_threshold,
        "max_merge_gap_minutes": max_merge_gap_minutes,
    }

    task_description = (
        f"为用户撰写 {year} 年个人音乐年度报告。\n"
        f"数据范围：{year}-01-01 至 {end_date}。\n"
        f"{'这是部分年份（不完全），报告中使用阶段性表述。' if is_partial_year else '这是完整年份。'}\n"
        f"可用图表：{', '.join(s.get('id', '') for s in chart_specs)}。\n"
        "请只基于本任务的本地只读快照工具调查，不补写外部背景信息。"
    )

    planner_prompt = REPORT_PLANNER_SYSTEM_PROMPT.format(tools_description=tools_desc)
    planner_user = (
        f"## 研究任务\n{task_description}\n\n"
        f"## 图表数据（由确定性后端生成，可直接引用）\n"
        f"{json.dumps(_summarize_chart_data(chart_data, chart_specs), ensure_ascii=False, indent=2)}\n\n"
        "请制定研究计划并执行数据调查。每个维度调用工具后分析结果，发现异常深入追查。"
    )

    if emit_event:
        try:
            emit_event(
                "stage_started",
                "正在制定研究计划并调查数据",
                {"stage": "researching", "progress_pct": 0.25},
            )
        except Exception:
            pass

    from backend.core.config import AI_AGENT_RUNTIME

    if AI_AGENT_RUNTIME != "legacy":
        research_text, all_tool_results = _native_report_research(
            planner_prompt=planner_prompt,
            planner_user=planner_user,
            base_filters=base_filters,
            year=year,
            end_date=end_date,
            research_context=research_context or {},
            emit_event=emit_event,
        )
    else:
        # Explicit rollback path for providers without native tool calling.
        all_tool_results = []
        research_text = ""
        for round_num in range(1, 6):
            planner_response = _llm_chat(
                planner_prompt,
                planner_user,
                temperature=0.35,
                thinking=True,
            )
            if not planner_response:
                break

            tool_calls = _extract_tool_calls(planner_response)
            if not tool_calls:
                research_text = planner_response
                break

            round_results = []
            for tc in tool_calls[:6]:
                tool_name = tc.get("tool_name", "")
                params = {**base_filters, **(tc.get("params", {}))}
                params["year"] = year

                try:
                    result = execute_report_tool(
                        tool_name,
                        params,
                        context=research_context or {},
                    )
                    result["result_summary"] = result.get("summary") or ""
                    result["_tool_name"] = tool_name
                    result["_params"] = params
                    round_results.append(result)
                    all_tool_results.append(result)
                except Exception as exc:
                    logger.warning("Tool %s failed: %s", tool_name, exc)
                    round_results.append(
                        {
                            "_tool_name": tool_name,
                            "_params": params,
                            "status": "error",
                            "error": str(exc),
                        }
                    )
                    all_tool_results.append(round_results[-1])

            if emit_event:
                try:
                    emit_event(
                        "stage_started",
                        f"研究轮次 {round_num}：已调用 {len(round_results)} 个工具",
                        {"stage": "researching", "progress_pct": 0.25 + round_num * 0.10},
                    )
                except Exception:
                    pass

            results_summary = _format_tool_results(round_results)
            planner_user += f"\n\n## 第 {round_num} 轮工具结果\n{results_summary}\n\n请继续调查。如果所有维度都已充分覆盖，输出最终研究摘要（JSON 格式，包含 research_summary 字段）。"

    # If no research text from planner, compile from tool results
    if not research_text:
        research_text = _compile_research_from_tools(all_tool_results)

    # ── Phase 2: Write the report directly from all collected data ──
    if emit_event:
        try:
            emit_event(
                "stage_started",
                "正在撰写年度报告",
                {"stage": "writing_report", "progress_pct": 0.85},
            )
        except Exception:
            pass

    raw_tool_text = _format_tool_results(all_tool_results)
    chart_summary = _summarize_chart_data(chart_data, chart_specs)
    write_instruction = (
        REPORT_WRITER_INSTRUCTION + "\n\n"
        f"## 原始工具数据\n{raw_tool_text}\n\n"
        f"## 图表数据\n{json.dumps(chart_summary, ensure_ascii=False, indent=2)}\n\n"
        f"## 参数\nis_partial_year={is_partial_year}, end_date={end_date}\n"
        f"可用图表: {', '.join(s.get('id', '') for s in chart_specs)}\n"
    )

    from backend.core.config import AI_REPORT_SECTION_WRITER_V2

    section_writer_metadata: dict[str, Any] | None = None
    sections: list[dict[str, Any]] = []
    if AI_REPORT_SECTION_WRITER_V2 and fallback_sections and len(fallback_sections) >= 6:
        sections, section_writer_metadata = _write_sections_v2(
            fallback_sections=fallback_sections[:6],
            research_text=research_text,
            all_tool_results=all_tool_results,
            chart_data=chart_data,
            chart_specs=chart_specs,
            year=year,
            end_date=end_date,
            runtime_metrics=runtime_metrics,
            emit_event=emit_event,
        )
    else:
        sections = _write_full_report_legacy(
            write_instruction=write_instruction,
            chart_specs=chart_specs,
            emit_event=emit_event,
        )

    sections, checkpoints, tool_evidence = audit_report_sections(
        sections,
        tool_results=all_tool_results,
        chart_data=chart_data,
        chart_specs=chart_specs,
        year=year,
        end_date=end_date,
    )
    failed_indexes = [
        int(item["section_index"]) for item in checkpoints if item.get("status") == "fail"
    ]
    if failed_indexes:
        compact_evidence = [
            {
                "tool_name": item.get("tool_name"),
                "tool_call_id": item.get("tool_call_id"),
                "source_range": item.get("source_range"),
                "facts": item.get("facts", [])[:12],
                "limitations": item.get("limitations", []),
            }
            for item in tool_evidence
        ]
        for index in failed_indexes:
            checkpoint = checkpoints[index]
            if emit_event:
                emit_event(
                    "report_section_repair",
                    f"正在修复章节：{checkpoint.get('heading') or index + 1}",
                    {
                        "stage": "reviewing_sections",
                        "progress_pct": min(0.96, 0.88 + index * 0.01),
                        "section_index": index,
                        "issues": checkpoint.get("issues", []),
                    },
                )
            try:
                repair_response = _llm_chat(
                    "你是年度报告章节修复器。只能使用给定证据，禁止新增数字或实体。只输出单节 JSON。",
                    json.dumps(
                        {
                            "section": sections[index],
                            "checkpoint": checkpoint,
                            "tool_evidence": compact_evidence,
                            "chart_data": chart_summary,
                            "instruction": (
                                "删除或改正无法追溯的数字；保留有信息量的分析；"
                                "chart_refs 只能使用已有图表，evidence_refs 使用 tool_name。"
                            ),
                        },
                        ensure_ascii=False,
                        default=str,
                    )[:14000],
                    temperature=0.0,
                    max_tokens=2048,
                )
            except Exception as exc:
                logger.warning("Report section repair failed at index %s: %s", index, exc)
                repair_response = ""
            repaired = _parse_single_section(repair_response or "", chart_specs)
            if repaired is not None:
                sections[index] = repaired

        sections, checkpoints, tool_evidence = audit_report_sections(
            sections,
            tool_results=all_tool_results,
            chart_data=chart_data,
            chart_specs=chart_specs,
            year=year,
            end_date=end_date,
        )

    # The deterministic final safety net removes only sentences that still
    # contain unsupported numbers after one bounded repair attempt.
    for checkpoint in checkpoints:
        if checkpoint.get("status") != "fail":
            continue
        index = int(checkpoint["section_index"])
        sections[index]["prose"] = strip_unsupported_numeric_sentences(
            str(sections[index].get("prose") or ""),
            [str(item) for item in checkpoint.get("unsupported_numbers") or []],
        )
    sections, checkpoints, tool_evidence = audit_report_sections(
        sections,
        tool_results=all_tool_results,
        chart_data=chart_data,
        chart_specs=chart_specs,
        year=year,
        end_date=end_date,
    )
    if emit_event:
        for checkpoint in checkpoints:
            emit_event(
                "report_section_checkpoint",
                f"章节检查：{checkpoint.get('heading') or int(checkpoint['section_index']) + 1}",
                {
                    "stage": "reviewing_sections",
                    "progress_pct": 0.97,
                    **checkpoint,
                },
            )

    return {
        "sections": sections,
        "research_summary": research_text,
        "evidence": all_tool_results,
        "tool_evidence": tool_evidence,
        "section_checkpoints": checkpoints,
        "section_writer_metadata": section_writer_metadata,
    }


def _write_full_report_legacy(
    *,
    write_instruction: str,
    chart_specs: list[dict[str, Any]],
    emit_event: Any,
) -> list[dict[str, Any]]:
    """Rollback path for providers where section writing is disabled."""
    from backend.services.ai_insights_service import _llm_chat

    sections: list[dict[str, Any]] = []
    for writer_attempt in range(2):
        retry_instruction = ""
        if writer_attempt:
            retry_instruction = (
                "\n\n上一次输出没有达到 6 节且 3000 字的结构门槛。"
                "请重新完整输出，不要解释失败原因，不要省略 JSON 尾部。"
            )
        writer_response = _llm_chat(
            "你是 SpotifyStats 年度音乐报告作者。基于工具数据撰写报告。只输出 JSON。",
            write_instruction + retry_instruction,
            temperature=0.35,
            max_tokens=6144,
        )
        candidate: list[dict[str, Any]] = []
        if writer_response:
            candidate = _parse_json_sections(writer_response, chart_specs)
            if not candidate:
                candidate = _parse_markdown_sections(writer_response)
            if not candidate and len(writer_response.strip()) > 50:
                candidate = [
                    {"heading": "年度报告", "prose": writer_response.strip(), "chart_refs": []}
                ]
        candidate_chars = sum(len(str(item.get("prose") or "")) for item in candidate)
        current_chars = sum(len(str(item.get("prose") or "")) for item in sections)
        if (len(candidate), candidate_chars) > (len(sections), current_chars):
            sections = candidate
        if len(candidate) >= 6 and candidate_chars >= 2800:
            break
        if writer_attempt == 0 and emit_event:
            emit_event(
                "report_writer_retry",
                f"初稿结构不足（{len(candidate)} 节/{candidate_chars} 字），正在重写",
                {
                    "stage": "writing_report",
                    "progress_pct": 0.87,
                    "section_count": len(candidate),
                    "article_length": candidate_chars,
                },
            )

    return sections


def _write_sections_v2(
    *,
    fallback_sections: list[dict[str, Any]],
    research_text: str,
    all_tool_results: list[dict[str, Any]],
    chart_data: dict[str, Any],
    chart_specs: list[dict[str, Any]],
    year: int,
    end_date: str,
    runtime_metrics: Any,
    emit_event: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Write six isolated sections with bounded concurrency and local fallback."""
    from backend.core.config import AI_REPORT_SECTION_WRITER_CONCURRENCY
    from backend.services.ai_insights_service import _llm_text_completion

    plans = tuple(
        SectionWritePlan(
            section_id=str(section.get("id") or f"section_{index + 1}"),
            heading=str(section.get("heading") or f"第 {index + 1} 节"),
            payload={
                "index": index,
                "fallback": dict(section),
                "evidence_refs": list(section.get("evidence_refs") or []),
                "chart_refs": list(section.get("chart_refs") or []),
            },
        )
        for index, section in enumerate(fallback_sections)
    )
    chart_summary = _summarize_chart_data(chart_data, chart_specs)

    def complete(plan: SectionWritePlan, attempt: int) -> SectionCompletion:
        fallback = dict(plan.payload["fallback"])
        refs = set(plan.payload.get("evidence_refs") or [])
        evidence = [
            {
                "tool_name": item.get("_tool_name"),
                "result_summary": item.get("result_summary") or item.get("summary"),
                "data": item.get("data"),
            }
            for item in all_tool_results
            if not refs or item.get("_tool_name") in refs
        ]
        chart_refs = set(plan.payload.get("chart_refs") or [])
        charts = {key: value for key, value in chart_summary.items() if key in chart_refs}
        prompt = json.dumps(
            {
                "year": year,
                "end_date": end_date,
                "section_id": plan.section_id,
                "heading": plan.heading,
                "role": fallback.get("role"),
                "deck": fallback.get("deck"),
                "research_summary": research_text[:2400],
                "evidence": evidence,
                "charts": charts,
                "allowed_chart_refs": list(chart_refs),
                "allowed_evidence_refs": sorted(refs),
                "attempt": attempt,
                "instruction": (
                    "围绕本节问题写 500 至 800 个中文字符；每个数字必须逐字来自 evidence 或 charts；"
                    "不得补写外部背景和用户生活事件；只输出一个章节 JSON 对象。"
                ),
            },
            ensure_ascii=False,
            default=str,
        )[:16000]
        completion = _llm_text_completion(
            "你是 SpotifyStats 年度报告分章节作者。只输出 JSON："
            '{"heading":"...","prose":"...","chart_refs":[],"evidence_refs":[]}。',
            prompt,
            temperature=0.35,
            # Reasoning-capable providers may spend roughly 1.8k completion
            # tokens before emitting visible JSON. A 1.8k ceiling therefore
            # produced an empty length stop for every section. Keep enough
            # room for that internal work plus the requested 500-800 Chinese
            # characters while still bounding one section independently.
            max_tokens=4096,
        )
        if completion is None:
            return SectionCompletion(empty_reason="provider_unavailable")
        if runtime_metrics is not None:
            runtime_metrics.record_provider_call(completion, stage=f"section:{plan.section_id}")
        return SectionCompletion(
            content=completion.content,
            finish_reason=completion.finish_reason,
            usage=completion.usage,
            empty_reason=completion.empty_reason or None,
        )

    def parse(plan: SectionWritePlan, content: str) -> dict[str, Any]:
        parsed = _parse_single_section(content, chart_specs)
        if parsed is None:
            raise ValueError("invalid_section_json")
        fallback = dict(plan.payload["fallback"])
        return {
            **fallback,
            **parsed,
            "id": fallback.get("id") or plan.section_id,
            "heading": parsed.get("heading") or fallback.get("heading") or plan.heading,
            "role": fallback.get("role") or "opening",
            "deck": fallback.get("deck") or "",
            "insight_refs": list(fallback.get("insight_refs") or []),
            "pull_quote": fallback.get("pull_quote"),
        }

    def audit(plan: SectionWritePlan, section: dict[str, Any]) -> SectionAuditResult:
        audited, checkpoints, _evidence = audit_report_sections(
            [section],
            tool_results=all_tool_results,
            chart_data=chart_data,
            chart_specs=chart_specs,
            year=year,
            end_date=end_date,
        )
        checkpoint = checkpoints[0] if checkpoints else {"status": "fail", "issues": ["no_audit"]}
        unsupported = [str(item) for item in checkpoint.get("unsupported_numbers") or []]
        if unsupported and audited:
            sanitized = dict(audited[0])
            sanitized["prose"] = strip_unsupported_numeric_sentences(
                str(sanitized.get("prose") or ""),
                unsupported,
            )
            audited, checkpoints, _evidence = audit_report_sections(
                [sanitized],
                tool_results=all_tool_results,
                chart_data=chart_data,
                chart_specs=chart_specs,
                year=year,
                end_date=end_date,
            )
            checkpoint = (
                checkpoints[0]
                if checkpoints
                else {"status": "fail", "issues": ["no_audit_after_sanitize"]}
            )
        if audited:
            section.clear()
            section.update(audited[0])
        accepted = checkpoint.get("status") != "fail"
        return SectionAuditResult(
            accepted=accepted,
            issues=tuple(str(issue) for issue in checkpoint.get("issues") or []),
        )

    def fallback(plan: SectionWritePlan, _attempts: tuple[Any, ...]) -> dict[str, Any]:
        return dict(plan.payload["fallback"])

    if emit_event:
        emit_event(
            "stage_started",
            "正在分章节撰写年度报告",
            {
                "stage": "writing_sections",
                "progress_pct": 0.85,
                "section_count": len(plans),
            },
        )
    run = write_report_sections(
        plans,
        complete=complete,
        parse=parse,
        audit=audit,
        fallback=fallback,
        max_workers=AI_REPORT_SECTION_WRITER_CONCURRENCY,
        max_attempts=2,
    )
    if emit_event:
        for result in run.results:
            emit_event(
                "report_section_written",
                f"章节完成：{result.plan.heading}",
                {
                    "stage": "writing_sections",
                    "progress_pct": 0.90,
                    "section_id": result.plan.section_id,
                    "status": result.status,
                    "attempt_count": len(result.attempts),
                },
            )
    return list(run.sections), run.metadata.to_dict()


# ── Fact Auditor (DETERMINISTIC) ──────────────────────────────────────────────


def _audit_sections(
    sections: list[dict[str, Any]],
    all_tool_results: list[dict[str, Any]],
    is_partial_year: bool,
    end_date: str,
) -> list[dict[str, Any]]:
    """Audit report sections using an LLM with temperature=0.

    Provides the LLM with both raw tool data AND an explicit whitelist of
    known entity names. The LLM must strip any sentence mentioning entities
    not in the whitelist.
    """
    from backend.services.ai_insights_service import _llm_chat

    # ── Build whitelist from tool data ──
    whitelist: set[str] = set()
    for r in all_tool_results[:40]:
        summary = str(r.get("result_summary", ""))
        # Extract all words that look like entity names
        import re as _re

        for token in _re.split(r"[,|，：:=\n]+", summary):
            token = token.strip()
            if not token:
                continue
            # Keep name portions (before parentheticals)
            name = token.split("(")[0].strip().rstrip(" weeks peak plays hours first").strip()
            if name and len(name) >= 2:
                whitelist.add(name)
        # Also extract from data dict
        data = r.get("data", {})
        if isinstance(data, dict):
            data_str = str(data)[:1000]
            for token in _re.findall(r"'([^']+)'|\"([^\"]+)\"", data_str):
                if len(token) >= 2:
                    whitelist.add(token)

    whitelist_str = "\n".join(sorted(whitelist))[:2000]

    # Tool data for context
    tool_lines = []
    for r in all_tool_results[:40]:
        summary = r.get("result_summary", "")
        if summary:
            tool_lines.append(f"[{r.get('_tool_name', '?')}] {summary}")
    tool_data = "\n".join(tool_lines)[:3000]

    if not tool_data.strip():
        return sections

    audit_prompt = (
        "你是严格的事实核查员。\n\n"
        "## 已知实体白名单（只有这些名称是真实数据中存在的）\n"
        f"{whitelist_str}\n\n"
        "## 原始工具数据\n"
        f"{tool_data}\n\n"
        "## 核查规则\n"
        "1. 逐句检查：如果句子中提到的艺人名、专辑名、歌曲名不在「白名单」中，删除整句\n"
        "2. 如果句子中的数字不在「原始工具数据」中，删除整句\n"
        "3. 删除推断用户动机/情绪/事件的句子\n"
        "4. 删除提到曲风分类（独立电子/独立民谣等）和外部事件的句子\n"
        "5. 只保留白名单和数据中有证据的句子\n\n"
        "## 输出格式\n"
        '只输出 JSON：{"heading": "...", "prose": "...", "chart_refs": []}\n'
        "如果某句中的艺人/专辑/歌曲不在白名单中，整句删除。"
    )

    audited: list[dict[str, Any]] = []
    for s in sections:
        prose = s.get("prose", "")
        if len(prose) < 50:
            audited.append(s)
            continue

        audit_user = f"待审核章节:\n{prose}\n\n只输出 JSON。如果整章都无法验证，prose 留空。"

        response = _llm_chat(audit_prompt, audit_user, temperature=0.0, max_tokens=2048)
        if response:
            cleaned = _parse_json_sections(response, [])
            if cleaned and len(cleaned) == 1 and cleaned[0].get("prose", "").strip():
                audited.append(cleaned[0])
                continue
            elif cleaned and len(cleaned) >= 1:
                audited.extend(cleaned)
                continue
        audited.append(s)

    return audited


def _parse_json_sections(text: str, chart_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse JSON sections from LLM output, with fault tolerance."""
    import re

    valid_ids = {s.get("id", "") for s in chart_specs}

    # Extract JSON
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    # If the text itself starts with {, treat it as raw JSON
    if raw.startswith("{") and raw.endswith("}"):
        pass  # already looks like JSON

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Repair: close unclosed structures
        open_braces = raw.count("{") - raw.count("}")
        open_brackets = raw.count("[") - raw.count("]")
        raw = raw.rstrip(",\n\r\t ")
        raw += "]" * open_brackets + "}" * open_braces
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []

    raw_sections = parsed.get("sections", []) if isinstance(parsed, dict) else []
    if not isinstance(raw_sections, list):
        return []

    sections = []
    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading", "")).strip()
        prose = str(s.get("prose", "")).strip()
        if not heading or not prose:
            continue
        chart_refs = [r for r in s.get("chart_refs", []) if r in valid_ids]
        evidence_refs = [str(r) for r in s.get("evidence_refs", []) if str(r).strip()]
        sections.append(
            {
                "heading": heading,
                "prose": prose,
                "chart_refs": chart_refs or [],
                "evidence_refs": evidence_refs,
            }
        )
    return sections


def _parse_single_section(
    text: str,
    chart_specs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    sections = _parse_json_sections(text, chart_specs)
    if sections:
        return sections[0]
    raw = text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    wrapped = json.dumps({"sections": [parsed]}, ensure_ascii=False)
    sections = _parse_json_sections(wrapped, chart_specs)
    return sections[0] if sections else None


def _parse_markdown_sections(text: str) -> list[dict[str, Any]]:
    """Fallback: extract sections from markdown headings."""
    import re

    sections: list[dict[str, Any]] = []
    for prefix in ("## ", "### "):
        blocks = re.split(rf"\n(?={prefix})", text)
        if len(blocks) > 1:
            break
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = re.match(r"^(?:###|##)\s+(.+?)(?:\n|$)", block)
        if not m:
            continue
        sections.append(
            {"heading": m.group(1).strip(), "prose": block[m.end() :].strip(), "chart_refs": []}
        )
    return sections
