"""Agent-based yearly report generation with multi-turn tool calling.

Replaces the single-call report_writer.py with a true agent loop:
  Plan research → Execute tools → Review coverage → Synthesize report.

Shares the same tool registry as the chat agent (14 local data tools + web_search).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.domains.ai_agent.tool_registry import dispatch_tool, list_tools

logger = logging.getLogger(__name__)

# ── Agent prompts ─────────────────────────────────────────────────────────────

REPORT_PLANNER_SYSTEM_PROMPT = """你是 SpotifyStats 的年度音乐报告研究员。你的任务是为用户的年度音乐报告制定研究计划并执行数据调查。

## 可用工具
{tools_description}

## 工作流程
1. 阅读研究任务，制定调查计划
2. 调用工具获取数据，每次调用后分析结果
3. 根据发现深入追查——如果数据暗示有趣的故事，继续深挖
4. 也可以使用 web_search 查询艺人背景、专辑信息等补充资料
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
- web_search 用于补充艺人背景、专辑背景、曲风解释等本地数据没有的信息
- 调查深度优先于调查广度——宁可有 5 个深入分析的维度，不要 10 个浅尝辄止的
- 发现异常数据（如月度逆转、双榜差异）必须深入追查
"""

REPORT_WRITER_INSTRUCTION = """
## 研究完成，现在撰写年度报告

基于以上所有工具调查结果和图表数据，撰写一份信息密度高、有洞察力的年度音乐回顾。

核心原则：
- 每节至少 3 个具体数字（播放次数、时长、占比、排名、在榜周数）
- 从数据中找故事——有趣的异常和趋势比全面覆盖更重要
- 艺人/专辑/歌曲名完整写出，数字带单位，时间带月份
- 禁止废话：不要写"反复回到的声音""低阻力回访""不同场景里都能成立"等模板表述
- is_partial_year 时用"截至 X""阶段性"，不说"全年"；Billboard 时说明"基于本地播放记录的个人 Billboard"
- 禁止：前者/后者指代、推断艺人性别（她/他）、艺人名加括号附注英文

输出严格 JSON：{"sections": [{"heading": "标题", "prose": "正文(Markdown)", "chart_refs": ["chart_id"]}]}
"""


# ── Agent loop ────────────────────────────────────────────────────────────────


def _build_tools_description() -> str:
    tools = list_tools()
    lines = []
    for t in tools:
        name = t.get("name", "?")
        desc = t.get("description", "")
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


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
    emit_event: Any = None,
) -> dict[str, Any]:
    """Run the multi-turn agent loop to research and write a yearly report.

    Returns: {"sections": [...], "research_summary": str, "evidence": [...]}
    """
    from backend.services.ai_insights_service import _llm_chat

    # ── Build tool description for the planner ──
    tools_desc = _build_tools_description()

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
        f"请在本地数据工具和 web_search 之间灵活切换，深入调查艺人和专辑的背景信息。"
    )

    planner_prompt = REPORT_PLANNER_SYSTEM_PROMPT.format(tools_description=tools_desc)
    planner_user = (
        f"## 研究任务\n{task_description}\n\n"
        f"## 图表数据（由确定性后端生成，可直接引用）\n"
        f"{json.dumps(_summarize_chart_data(chart_data, chart_specs), ensure_ascii=False, indent=2)}\n\n"
        f"请制定研究计划并执行数据调查。每个维度调用工具后分析结果，发现异常深入追查。"
        f"也可以使用 web_search 补充艺人/专辑背景信息。"
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

    # Phase 1: Multi-turn research (up to 5 rounds)
    all_tool_results: list[dict[str, Any]] = []
    research_text = ""
    for round_num in range(1, 6):
        planner_response = _llm_chat(planner_prompt, planner_user, temperature=0.35, thinking=True)
        if not planner_response:
            break

        # Try to extract tool calls from the planner response
        tool_calls = _extract_tool_calls(planner_response)
        if not tool_calls:
            # No more tools to call — planner is done investigating
            research_text = planner_response
            break

        # Execute tool calls
        round_results = []
        for tc in tool_calls[:6]:  # Max 6 tools per round
            tool_name = tc.get("tool_name", "")
            params = tc.get("params", {})
            # Apply base filters
            params = {**base_filters, **params}
            # Add year context
            if "year" not in params and tool_name in (
                "wrapped_yearly",
                "analysis_stats",
                "analysis_charts",
            ):
                params["year"] = year

            try:
                result = dispatch_tool(tool_name, params)
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

        # Feed results back to planner for next round
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

    writer_response = _llm_chat(
        "你是 SpotifyStats 年度音乐报告作者。基于工具数据撰写报告。只输出 JSON。",
        write_instruction,
        temperature=0.40,
    )
    sections: list[dict[str, Any]] = []
    if writer_response:
        sections = _parse_json_sections(writer_response, chart_specs)
        if not sections:
            sections = _parse_markdown_sections(writer_response)
        if not sections and len(writer_response.strip()) > 50:
            sections = [{"heading": "年度报告", "prose": writer_response.strip(), "chart_refs": []}]

    return {
        "sections": sections,
        "research_summary": research_text,
        "evidence": all_tool_results,
    }


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
        sections.append({"heading": heading, "prose": prose, "chart_refs": chart_refs or []})
    return sections


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
