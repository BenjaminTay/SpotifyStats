"""Report writer: Agent-synthesis style LLM report generation.

Replaces the 6-stage editorial_agent pipeline with a single high-quality LLM
synthesis call following the Agent Answer Philosophy pattern:
  data-first, specific numbers, no abstract fluff, flexible structure.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

WRITER_PIPELINE_VERSION = "agent_synthesis_v2"
WRITER_PIPELINE_REQUEST_VALUE = "agent_synthesis_v2"

_MIN_PARTIAL_YEAR_CHARS = 800
_MIN_FULL_YEAR_CHARS = 1200
_MAX_PARTIAL_YEAR_CHARS = 1500
_MAX_FULL_YEAR_CHARS = 2200

_SECTION_ROLES: dict[str, str] = {
    "opening": "opening",
    "overview": "opening",
    "main_artist": "main_artist",
    "companion": "main_artist",
    "stable_core": "main_artist",
    "second_thread": "second_thread",
    "turning_point": "turning_point",
    "monthly_shift": "turning_point",
    "album_story": "album_story",
    "album": "album_story",
    "playback_billboard": "billboard_divergence",
    "billboard_divergence": "billboard_divergence",
    "highlight_day": "highlight_day",
    "peak_day": "highlight_day",
    "discovery": "discovery",
    "new_voices": "discovery",
    "genre_language": "genre_language",
    "habits": "habits",
    "closing": "closing",
    "summary": "closing",
}


# ── System Prompt ────────────────────────────────────────────────────────────

REPORT_WRITER_SYSTEM_PROMPT = """你是 SpotifyStats 的年度音乐报告作者。你的任务是基于用户的个人播放数据，撰写一份信息密度高、有洞察力的年度音乐回顾。

## 核心原则

### 数据优先
- 每节至少引用 3 个具体数字（播放次数、时长、占比百分比、排名、在榜周数等）
- 数字配解释，但解释要简短具体，不要展开成抽象哲学
- 说"Opalite 以 123 次播放、7.9 小时位居单曲榜首"而不是"某首单曲成为年度最常播放的选择"

### 禁止抽象废话
不得出现以下模板化表述：
- "反复回到的声音"、"低阻力回访"、"不同场景里都能成立"
- "当不知道听什么时，这个声音仍然容易被选中"
- "出现在工作间隙、路上、休息前"
- "年度报告真正能补上的，是把这些零散选择重新连成一条线"

### 自然叙事
- 从数据中找故事，有什么就写什么
- 有趣的异常和趋势比全面覆盖更重要
- 不要硬套"主线艺人→第二艺人→专辑→发现"的固定框架
- 如果某个维度数据不足或没有故事，可以跳过或简短带过

### 具体化
- 艺人、专辑、歌曲名称必须完整写出
- 数字必须有单位（次、小时、天、周、%）
- 时间必须有具体月份或日期

### 部分年份处理
- 如果 is_partial_year 为 true，全文使用"截至 end_date"、"阶段性回顾"、"上半年"
- 不要使用"这一年"、"全年"等完整年份表述
- 同比对比只能使用 same_period（同期对比），不能说"比去年下降"

### 个人 Billboard 边界
- 涉及 Billboard 时必须说明"基于本地播放记录的个人 Billboard"
- 不要暗示这是外部官方榜单

## 输出格式

严格 JSON，包含一个 "sections" 数组。每节有：
- "heading": 中文标题（10-20 字）
- "prose": 正文（Markdown，粗体数字、列表均可）
- "chart_refs": 要展示的图表 ID 列表（从可用图表中选择）

```json
{
  "sections": [
    {
      "heading": "标题",
      "prose": "正文内容...",
      "chart_refs": ["chart_id_1"]
    }
  ]
}
```

## 字数

- 部分年份（is_partial_year=true）: 800-1500 字
- 完整年份: 1200-2200 字
- 注：这是 prose 总字数，不含 heading 和 chart_refs
"""


# ── Report Writer Context Builder ────────────────────────────────────────────


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _name(entities: list[dict[str, Any]], idx: int, fallback: str = "") -> str:
    if idx < len(entities):
        return str(entities[idx].get("name") or fallback)
    return fallback


def _num(value: Any, default: Any = 0) -> Any:
    if isinstance(value, (int, float)):
        return value
    return default


def _pct(value: float, total: float) -> str:
    if not total or total == 0:
        return ""
    return f"{value / total * 100:.1f}%"


def build_report_writer_context(
    context: dict[str, Any],
    chart_data: dict[str, Any],
    chart_specs: list[dict[str, Any]],
) -> str:
    """Build a rich markdown data summary for the LLM report writer.

    Converts the research context (from _run_visual_research), deterministic
    chart data, and chart specs into a dense but readable text summary that
    lets the LLM find stories in the data instead of abstract templates.
    """
    period = _dict(context.get("reporting_period"))
    hero = _dict(context.get("hero"))
    top_artists = _list(context.get("top_artists"))
    top_albums = _list(context.get("top_albums"))
    top_tracks = _list(context.get("top_tracks"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    discovery = _dict(context.get("discovery_and_returns"))
    genres = _dict(context.get("genre_distribution"))
    highlight = _dict(context.get("highlight_day_detail"))
    comparison = _dict(context.get("same_period_comparison"))
    monthly = _list(context.get("monthly_trend") or [])

    year = period.get("year") or ""
    start_date = str(period.get("start_date") or "")
    end_date = str(period.get("end_date") or "")
    is_partial = bool(period.get("is_partial_year"))
    active_days = hero.get("active_days") or 0
    total_plays = hero.get("total_plays") or 0
    total_minutes = hero.get("total_minutes") or 0
    total_hours = round(_num(total_minutes) / 60)
    unique_tracks = hero.get("unique_tracks") or 0
    unique_artists = hero.get("unique_artists") or 0
    unique_albums = hero.get("unique_albums") or 0

    parts: list[str] = []

    # ── Period Info ──
    parts.append("## 报告周期")
    parts.append(f"- 年份: {year}")
    parts.append(f"- 起止: {start_date} ~ {end_date}")
    parts.append(
        f"- 是否为部分年份: {'是' if is_partial else '否'}（{'是' if is_partial else '否'}则全文使用阶段性表述）"
    )
    parts.append(f"- 活跃天数: {active_days}")
    parts.append("")

    # ── Overview ──
    parts.append("## 总览数据")
    parts.append(f"- 总播放次数: {total_plays:,}")
    parts.append(f"- 总聆听时长: {total_hours:,} 小时（约 {round(total_hours / 24):,} 天）")
    parts.append(f"- 独立歌曲: {unique_tracks:,} 首")
    parts.append(f"- 独立艺人: {unique_artists:,} 位")
    parts.append(f"- 独立专辑: {unique_albums:,} 张")
    parts.append("")

    # ── Top Artists ──
    parts.append("## 年度 Top 艺人")
    for i, a in enumerate(top_artists[:8]):
        name = a.get("name", "?")
        plays = _num(a.get("plays"))
        hours = round(_num(a.get("hours") or _num(a.get("minutes", 0)) / 60, 0))
        pct_val = _pct(_num(plays), _num(total_plays))
        tracks = a.get("unique_tracks") or a.get("tracks") or ""
        albums = a.get("unique_albums") or a.get("albums") or ""
        detail = f"{plays:,} 次"
        if pct_val:
            detail += f"（{pct_val}）"
        if hours:
            detail += f"，{hours:,} 小时"
        if tracks:
            detail += f"，{tracks} 首歌"
        if albums:
            detail += f"，{albums} 张专辑"
        parts.append(f"{i + 1}. **{name}**: {detail}")
    parts.append("")

    # ── Top Albums ──
    parts.append("## 年度 Top 专辑")
    for i, a in enumerate(top_albums[:5]):
        name = a.get("name", "?")
        artist = a.get("artist", "")
        plays = _num(a.get("plays"))
        tracks = a.get("tracks") or a.get("track_count") or ""
        label = f"{plays:,} 次"
        if tracks:
            label += f"，{tracks} 首曲目"
        if artist:
            label = f"{artist} — {name}: {label}"
        else:
            label = f"{name}: {label}"
        parts.append(f"{i + 1}. {label}")
    parts.append("")

    # ── Top Tracks ──
    parts.append("## 年度 Top 单曲")
    for i, t in enumerate(top_tracks[:10]):
        name = t.get("name", "?")
        artist = t.get("artist", "")
        plays = _num(t.get("plays"))
        hours = round(_num(t.get("hours") or _num(t.get("minutes", 0)) / 60, 0))
        label = f"{plays:,} 次"
        if hours:
            label += f"，{hours:,} 小时"
        parts.append(f"{i + 1}. **{name}** — {artist}: {label}")
    parts.append("")

    # ── Monthly Trend ──
    if monthly:
        parts.append("## 月度艺人趋势")
        parts.append("每月播放次数最高的艺人：")
        for m in monthly[:12]:
            month_label = str(m.get("month") or "")
            top_name = _name(_list(m.get("top_artists")), 0)
            plays_val = _num(m.get("plays") or 0)
            if top_name:
                parts.append(f"- {month_label}: **{top_name}**（{plays_val:,} 次）")
        parts.append("")

    # ── Billboard Year-End ──
    billboard_artists = _list(billboard.get("artists"))
    billboard_albums = _list(billboard.get("albums"))
    billboard_tracks = _list(billboard.get("tracks"))
    if billboard_artists or billboard_albums or billboard_tracks:
        parts.append("## 个人 Billboard 年榜（基于本地播放记录）")
        if billboard_tracks:
            parts.append("### 单曲年榜 Top 5")
            for i, t in enumerate(billboard_tracks[:5]):
                name = t.get("name", "?")
                artist = t.get("artist", "")
                wks = t.get("weeks_on_chart") or t.get("weeks") or ""
                pk = t.get("peak_position") or ""
                ps = t.get("power_score") or ""
                detail = f"在榜 {wks} 周" if wks else ""
                if pk:
                    detail += f"，PK #{pk}"
                if ps:
                    detail += f"，Power Score {ps}"
                parts.append(f"{i + 1}. **{name}** — {artist}: {detail}")
        if billboard_albums:
            parts.append("### 专辑年榜 Top 3")
            for i, a in enumerate(billboard_albums[:3]):
                name = a.get("name", "?")
                artist = a.get("artist", "")
                wks = a.get("weeks_on_chart") or a.get("weeks") or ""
                pk = a.get("peak_position") or ""
                detail = f"在榜 {wks} 周" if wks else ""
                if pk:
                    detail += f"，PK #{pk}"
                parts.append(f"{i + 1}. **{name}** — {artist}: {detail}")
        if billboard_artists:
            parts.append("### 艺人生涯榜 Top 3")
            for i, a in enumerate(billboard_artists[:3]):
                name = a.get("name", "?")
                wks = a.get("weeks_on_chart") or ""
                pk = a.get("peak_position") or ""
                detail = f"在榜 {wks} 周" if wks else ""
                if pk:
                    detail += f"，PK #{pk}"
                parts.append(f"{i + 1}. **{name}**: {detail}")
        parts.append("")

    # ── Discovery ──
    new_artists = _list(discovery.get("new_artists"))
    if new_artists:
        parts.append("## 新发现艺人")
        for a in new_artists[:5]:
            name = a.get("name", "?")
            first = a.get("first_date") or ""
            plays = _num(a.get("plays"))
            label = f"{plays:,} 次" if plays else ""
            if first:
                label = f"首次出现 {first}" + (f"，{label}" if label else "")
            parts.append(f"- **{name}**: {label}")
        parts.append("")

    # ── Genre / Language ──
    top_genres = _list(genres.get("top_genres"))
    if top_genres:
        parts.append("## 曲风分布")
        for g in top_genres[:8]:
            name = g.get("name") or g.get("genre") or "?"
            share = g.get("share") or g.get("percentage") or ""
            label = f"{share}%" if share else ""
            parts.append(f"- {name}: {label}")
        parts.append("")

    # ── Highlight Day ──
    if highlight.get("date"):
        parts.append("## 高光日")
        parts.append(f"- 日期: {highlight.get('date')}")
        plays_val = highlight.get("plays") or highlight.get("total_plays") or ""
        if plays_val:
            parts.append(f"- 当日播放: {plays_val} 次")
        top_on_day = _list(highlight.get("top_tracks"))
        if top_on_day:
            parts.append("- 当日 Top 曲目:")
            for t in top_on_day[:5]:
                parts.append(
                    f"  - {t.get('name', '?')} — {t.get('artist', '?')}: {_num(t.get('plays'))} 次"
                )
        parts.append("")

    # ── Same-Period Comparison ──
    if comparison:
        parts.append("## 同期对比数据")
        comp_plays = comparison.get("plays_change_pct") or comparison.get("total_plays_change_pct")
        comp_hours = comparison.get("hours_change_pct") or comparison.get("total_hours_change_pct")
        if comp_plays is not None:
            direction = "增长" if _num(comp_plays) >= 0 else "减少"
            parts.append(f"- 播放次数同期{direction} {abs(_num(comp_plays))}%")
        if comp_hours is not None:
            direction = "增长" if _num(comp_hours) >= 0 else "减少"
            parts.append(f"- 聆听时长同期{direction} {abs(_num(comp_hours))}%")
        parts.append("")

    # ── Chart Observations ──
    if chart_data:
        parts.append("## 图表观察（来自确定性数据分析）")
        for spec in chart_specs:
            chart_id = str(spec.get("id") or "")
            data = _dict(chart_data.get(chart_id))
            observations = _list(data.get("observations"))
            if observations:
                parts.append(
                    f"### {spec.get('title', chart_id)}（chart_id: {chart_id}，类型: {spec.get('chart_type', '')}）"
                )
                for obs in observations:
                    parts.append(f"- {obs}")
                parts.append("")
    parts.append("")

    # ── Available Chart Refs ──
    parts.append("## 可用图表引用")
    parts.append("在每节的 chart_refs 中只能使用以下图表 ID：")
    for spec in chart_specs:
        parts.append(
            f"- `{spec.get('id')}`: {spec.get('title', '')}（{spec.get('chart_type', '')}）"
        )
    parts.append("")

    return "\n".join(parts)


# ── LLM Call ─────────────────────────────────────────────────────────────────


def call_report_writer_llm(
    system_prompt: str,
    writer_context: str,
    *,
    temperature: float = 0.40,
    max_tokens: int = 4096,
) -> str | None:
    """Call the LLM with the report writer prompt and data context.

    Returns the raw LLM response text, or None on failure.
    """
    from backend.services.ai_insights_service import _llm_chat  # lazy import (circular)

    try:
        result = _llm_chat(
            system_prompt,
            writer_context,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception:
        logger.warning("Report writer LLM call failed", exc_info=True)
        return None
    return result


# ── Section Parser ───────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from LLM text, with fault tolerance."""
    raw = text.strip()

    # Try markdown code fence first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try fixing truncated JSON by closing open structures
        logger.warning("JSON decode failed, attempting repair")
        raw = _repair_truncated_json(raw)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("JSON repair also failed")
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by balancing braces and quotes."""
    # Count braces
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    # Remove trailing incomplete content
    text = text.rstrip(",\n\r\t ")

    # Close unclosed string if last non-whitespace is a quote inside a string
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string

    if in_string:
        text += '"'

    # Close open brackets then braces
    text += "]" * open_brackets
    text += "}" * open_braces

    return text


def _parse_markdown_sections(text: str) -> list[dict[str, Any]]:
    """Fallback parser: extract sections from markdown ## headings."""
    sections: list[dict[str, Any]] = []
    # Split on ## headings
    blocks = re.split(r"\n(?=## )", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Extract heading from ## prefix
        heading_match = re.match(r"^##\s+(.+?)(?:\n|$)", block)
        if not heading_match:
            continue
        heading = heading_match.group(1).strip()
        # Everything after the heading line is prose
        prose = block[heading_match.end() :].strip()
        if not prose:
            continue
        sections.append(
            {
                "heading": heading,
                "prose": prose,
                "chart_refs": [],
            }
        )
    return sections


def _assign_role(heading: str, section_id: str) -> str:
    """Assign a section role based on heading text pattern matching."""
    heading_lower = heading.lower()

    # Check explicit role mapping first
    if section_id in _SECTION_ROLES:
        return _SECTION_ROLES[section_id]

    # Pattern-based role assignment
    patterns = [
        (r"总览|概览|全貌|这一年|年度总览|年度回顾|开场|打开|音乐在场", "opening"),
        (r"主线|核心|陪伴|第一|反复|回到|声音|年度艺人|稳定", "main_artist"),
        (r"第二|另一条|情绪线|对比|分叉|并行", "second_thread"),
        (r"变化|转折|切换|赶超|反超|转向|月度|五月|四月|三月|六月", "turning_point"),
        (r"专辑|双重|留存|热播|榜单|播放量.*Billboard|Billboard.*播放", "album_story"),
        (r"分开|分歧|错位|热度和|两种|不同", "billboard_divergence"),
        (r"高光|密度|峰值|那天|一天|时刻|时间线", "highlight_day"),
        (r"发现|新声|新.*艺人|新人|第一次|首次|进入", "discovery"),
        (r"曲风|语种|语言|风格|音乐地图|地理", "genre_language"),
        (r"习惯|节奏|作息|时段|深夜|白天", "habits"),
        (r"结尾|总结|展望|继续|未来|下阶段|年记|年志", "closing"),
    ]
    for pattern, role in patterns:
        if re.search(pattern, heading_lower):
            return role

    return "opening"  # default


def _first_sentence(text: str, max_len: int = 120) -> str:
    """Extract the first sentence from prose text as a deck/subtitle."""
    # Split on Chinese/English sentence endings
    match = re.match(r"(.+?[。！？.!?\n])", text.strip())
    if match:
        sentence = match.group(1).strip()
        if len(sentence) <= max_len:
            return sentence
    # Fallback: first max_len chars
    return text.strip()[:max_len]


def _extract_pull_quote(prose: str) -> str | None:
    """Try to find a quotable sentence in the prose."""
    # Look for short impactful sentences (15-50 chars)
    candidates = re.findall(r"[^。！？.!?\n]+[。！？.!?]", prose)
    for c in candidates:
        stripped = c.strip()
        if 15 <= len(stripped) <= 60 and not re.search(r"^\d+[、.．]", stripped):
            return stripped
    return None


def parse_report_sections(
    llm_output: str | None,
    chart_specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse LLM JSON output into section dicts compatible with _Section.to_dict().

    Returns a list of section dicts with: id, role, heading, deck, prose,
    chart_refs, insight_refs, evidence_refs, pull_quote.
    """
    if not llm_output or not llm_output.strip():
        return []

    parsed = _extract_json(llm_output)
    raw_sections = _list(parsed.get("sections"))

    if not raw_sections:
        # Fallback: try to parse sections from markdown headings
        raw_sections = _parse_markdown_sections(llm_output)
        if raw_sections:
            logger.info("Parsed %d sections from markdown fallback", len(raw_sections))
        else:
            logger.warning(
                "No sections found in LLM output (JSON=%s, preview=%s)",
                "ok" if parsed else "fail",
                llm_output[:200],
            )

    # Build set of valid chart IDs for validation
    valid_chart_ids = {str(s.get("id") or "") for s in chart_specs}

    sections: list[dict[str, Any]] = []
    seen_headings: set[str] = set()

    for i, raw in enumerate(raw_sections):
        if not isinstance(raw, dict):
            continue

        heading = str(raw.get("heading") or "").strip()
        prose = str(raw.get("prose") or "").strip()
        if not heading or not prose:
            continue

        # Deduplicate headings
        heading_key = heading.lower()
        if heading_key in seen_headings:
            continue
        seen_headings.add(heading_key)

        section_id = str(raw.get("id") or f"section_{i}")
        role = _assign_role(heading, section_id)
        deck = _first_sentence(prose)
        pull_quote = _extract_pull_quote(prose)

        # Validate and filter chart refs
        chart_refs = _list(raw.get("chart_refs"))
        valid_refs = [r for r in chart_refs if str(r) in valid_chart_ids]
        if not valid_refs:
            # Assign default chart refs based on role if none specified
            defaults: dict[str, list[str]] = {
                "opening": ["listening_calendar"],
                "main_artist": ["listening_calendar"],
                "turning_point": ["artist_monthly_trend"],
                "album_story": ["album_duality_compare"],
                "billboard_divergence": ["album_duality_compare", "playback_billboard_matrix"],
                "highlight_day": ["highlight_day_timeline"],
                "discovery": ["discovery_timeline"],
                "genre_language": ["genre_language_mix"],
            }
            valid_refs = defaults.get(role, [])

        sections.append(
            {
                "id": section_id,
                "role": role,
                "heading": heading,
                "deck": deck,
                "prose": prose,
                "chart_refs": valid_refs,
                "insight_refs": [],
                "evidence_refs": [],
                "pull_quote": pull_quote,
            }
        )

    return sections


# ── Quality Helpers ──────────────────────────────────────────────────────────


def report_writer_metadata(accepted: bool) -> dict[str, Any]:
    """Build writer metadata dict for the artifact."""
    return {
        "writer_pipeline": WRITER_PIPELINE_REQUEST_VALUE,
        "writer_pipeline_version": WRITER_PIPELINE_VERSION,
        "writer_pipeline_status": "accepted" if accepted else "fallback_visual_composer",
    }
