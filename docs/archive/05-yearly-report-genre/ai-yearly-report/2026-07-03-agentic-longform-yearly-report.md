# Agentic Longform Yearly Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an agentic longform yearly report workflow that lets a read-only Report Agent query SpotifyStats data, synthesize insights, create a dynamic outline, write a long article, and pass an editorial quality critic before caching the result.

**Implementation status (2026-07-03):** Implemented. The yearly AI report now defaults to `report_mode=agentic_longform`, runs through read-only research tools, evidence ledger, insight synthesis, dynamic outline, longform drafting, editorial critic, and yearly fact validation before caching. The legacy deterministic yearly summary remains available as `report_mode=basic_summary` and as the marked `fallback_level=basic_summary` safety path.

**Validation evidence (2026-07-03):**

- Backend targeted set: `55 passed` for agentic yearly report service/tools/critic, AI report task dispatch, API contracts, and task API contracts.
- Frontend regression set: Vitest `233 passed`; production build succeeded.
- HTTP probe: `scripts/probe_agentic_yearly_report.py --year 2026` returned `report_mode=agentic_longform`, `contract_version=agentic_yearly_v14`, `fallback_level=null`, 9 read-only tool calls, `critic.ok=true`, `fact_validation.ok=true`, and 1,846-character report.
- Browser acceptance: `/ai-insights` -> “年度叙事” -> “刷新报告” showed tool queries, insight synthesis, outline, draft, critic/fact-check progress, then rendered `Agentic 长文` / `已通过编辑审稿` / `1,846 字`.

**Architecture:** Keep the existing AI task/event/tool-call infrastructure and the V12 yearly report validator as the safety layer. Add a report-specific read-only tool registry, evidence ledger, insight synthesis, dynamic outline, longform draft prompt, and editorial critic, then route yearly report generation through this agentic workflow behind the existing AI Insights entry point. Treat the current deterministic yearly report as `basic_summary` fallback rather than the official AI longform report.

**Tech Stack:** FastAPI service layer, SQLite task/event persistence, existing `backend/domains/ai_agent` read-only tool registry patterns, existing `backend/domains/ai_reports` yearly contract/validator, pytest unit/contract tests, HTTP probes, React AI Insights task progress UI.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-07-03-agentic-longform-yearly-report-design.md`
- Existing related plans:
  - `docs/superpowers/plans/2026-06-28-ai-observable-agent-orchestrator.md`
  - `docs/superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md`
  - `docs/superpowers/plans/2026-07-03-ai-yearly-report-editorial-quality.md`

## Scope

This plan implements a V14 agentic yearly report vertical slice. It is intentionally narrower than a full AI platform rewrite:

- Reuse the existing `/ai-insights` user entry and AI task progress system.
- Add report-oriented tools rather than exposing arbitrary backend routes.
- Keep all tools read-only and allowlisted.
- Generate the official yearly report through research, evidence, insight, outline, draft, and critic stages.
- Keep V12 deterministic report generation as a marked `basic_summary` fallback.
- Do not implement token streaming in this iteration.
- Do not redesign the AI Insights page beyond progress/tool-trace labels and metadata display needed for this workflow.

## File Map

### Backend Create

- `backend/domains/ai_reports/agentic_models.py`
  Typed dataclasses and helpers for `EvidenceLedgerEntry`, `InsightSynthesis`, `DynamicOutline`, `EditorialCritique`, `AgenticYearlyMetadata`, and final report result shape.

- `backend/domains/ai_reports/agentic_tools.py`
  Report-oriented read-only tools wrapping existing services and AI Agent tools: period context, overview, top entities, same-period comparison, personal Billboard year-end, Billboard diagnostics, entity stats, genre distribution, discovery/returns, highlight day detail.

- `backend/domains/ai_reports/agentic_prompts.py`
  Mission prompt, insight synthesis prompt, dynamic outline prompt, longform draft prompt, and repair prompt.

- `backend/domains/ai_reports/editorial_critic.py`
  Deterministic heuristics plus optional LLM critic wrapper for longform quality checks.

- `backend/services/yearly_report_agent_service.py`
  Orchestrates the report agent workflow, task events, tool calls, LLM calls, fallback, cache, and metadata.

- `backend/tests/unit/test_agentic_yearly_report_tools.py`
- `backend/tests/unit/test_agentic_yearly_report_critic.py`
- `backend/tests/unit/test_agentic_yearly_report_service.py`
- `backend/tests/contract/test_agentic_yearly_report_contract.py`

- `scripts/probe_agentic_yearly_report.py`
  HTTP probe that forces a 2026 report, validates metadata, critic status, length, forbidden dashboard-restatement patterns, and tool traces.

### Backend Modify

- `backend/services/ai_task_service.py`
  Route yearly report tasks to `yearly_report_agent_service` when `report_mode=agentic_longform` or default V14 is enabled.

- `backend/api/ai_insights.py`
  Accept and return report mode metadata while preserving existing response compatibility.

- `backend/services/ai_insights_service.py`
  Keep V12 generation and `_build_yearly_report_fallback()` available as fallback/basic summary. Do not add new agent logic here beyond a thin compatibility function if needed.

- `backend/domains/ai_reports/yearly_validator.py`
  Reuse for fact safety. Add any missing helper entry points only if the new critic needs validator issue normalization.

- `backend/domains/ai_agent/tool_registry.py` and `backend/domains/ai_agent/tools.py` only if a report tool should reuse an existing general tool. Prefer keeping report-specific wrappers in `agentic_tools.py`.

### Frontend Modify

- `frontend/src/features/ai-insights/`
  Display `report_mode`, `fallback_level`, article length, and user-readable report research stages if already exposed through task events.

- `frontend/src/features/ai-tasks/`
  Ensure new stages such as `researching`, `synthesizing_insights`, `outlining`, `drafting`, and `critic_review` render with readable labels.

### Docs Modify

- `docs/README.md`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `CLAUDE.md`
- `backend/CLAUDE.md`
- `README.md` if user-facing AI feature summary needs an update.

## Acceptance Criteria

- A forced 2026 yearly report returns `report_mode="agentic_longform"`, `contract_version="agentic_yearly_v14"`, `fallback_level=null`, `critic_passed=true`, and `article_length >= 1400`.
- The report uses at least 6 read-only tool calls and at least 2 personal Billboard-related tool calls.
- Tool calls are persisted to `ai_tool_calls` and visible through existing task events/tool trace retrieval.
- The report contains a clear thesis and develops it across at least 3 sections.
- The report explains at least one relationship between playback data and personal Billboard data.
- The report includes at least one Billboard analysis dimension: dominance, stability, breakout, long-tail, cross-chart alignment, or playback/Billboard tension.
- The editorial critic rejects the current V12 fallback-style data listing report.
- If the agent fails, the response marks `fallback_level="basic_summary"` and does not present that text as the official longform report.
- No arbitrary SQL, arbitrary URL, write operation, settings mutation, import job, playlist write, or external official Billboard lookup is exposed to the model.

## Execution Notes

- Keep commits optional during execution unless the user explicitly requests git commits. If execution mode includes commits, use the checkpoint messages suggested at the end of each task.
- Preserve existing dirty worktree changes; do not revert files unrelated to this plan.
- Use `apply_patch` for manual edits.
- Run targeted tests after each task. Run the full validation matrix at the end.

---

## Task 1: Add Agentic Yearly Report Data Models

**Files:**
- Create: `backend/domains/ai_reports/agentic_models.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_service.py`

- [ ] **Step 1: Write model serialization tests**

Create `backend/tests/unit/test_agentic_yearly_report_service.py` with this initial content:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_models import (
    AgenticYearlyMetadata,
    DynamicOutline,
    EvidenceLedgerEntry,
    InsightSynthesis,
    OutlineSection,
)

pytestmark = pytest.mark.unit


def test_evidence_ledger_entry_serializes_for_task_payload():
    entry = EvidenceLedgerEntry(
        tool_name="yearly_overview",
        params={"year": 2026, "period_mode": "year_to_date"},
        result_summary="截至 2026-06-23，播放 7,860 次，累计 498 小时。",
        supports=("activity_level", "period_cutoff"),
        questions_raised=("播放下降但曲目增长，是否代表探索扩张？",),
        tool_call_id="tool_1",
    )

    assert entry.to_dict() == {
        "tool_name": "yearly_overview",
        "params": {"year": 2026, "period_mode": "year_to_date"},
        "result_summary": "截至 2026-06-23，播放 7,860 次，累计 498 小时。",
        "supports": ["activity_level", "period_cutoff"],
        "questions_raised": ["播放下降但曲目增长，是否代表探索扩张？"],
        "tool_call_id": "tool_1",
    }


def test_insight_outline_and_metadata_shape_are_stable():
    synthesis = InsightSynthesis(
        main_thesis="Taylor Swift 是稳定中心，Zhang Zhen Yue 打开新入口。",
        supporting_arguments=(
            {
                "claim": "Taylor Swift 是稳定中心",
                "evidence_refs": ["artist_rank_1", "album_rank_1"],
            },
        ),
        billboard_findings=("个人榜单显示 Taylor Swift 三榜联动强。",),
        playback_findings=("播放次数下降但曲目数上升。",),
        tensions=("总量下降与探索扩大并存。",),
        interesting_anomalies=("最活跃日不是单曲循环日。",),
    )
    outline = DynamicOutline(
        title="Taylor Swift 仍是中心，但你的音乐版图正在外扩",
        sections=(
            OutlineSection(
                heading="今年真正的变化",
                question="为什么播放下降不等于热情下降？",
                claims=("探索扩大", "核心循环减少"),
            ),
        ),
    )
    metadata = AgenticYearlyMetadata(
        report_mode="agentic_longform",
        contract_version="agentic_yearly_v14",
        fallback_level=None,
        tool_calls=8,
        data_range="2026-01-01 to 2026-06-23",
        is_partial_year=True,
        critic_passed=True,
        article_length=1650,
    )

    assert synthesis.to_dict()["main_thesis"].startswith("Taylor Swift")
    assert outline.to_dict()["sections"][0]["question"] == "为什么播放下降不等于热情下降？"
    assert metadata.to_dict()["fallback_level"] is None
    assert metadata.to_dict()["contract_version"] == "agentic_yearly_v14"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py -q
```

Expected: FAIL because `backend.domains.ai_reports.agentic_models` does not exist.

- [ ] **Step 3: Implement the model module**

Create `backend/domains/ai_reports/agentic_models.py`:

```python
"""Structured models for agentic yearly report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AGENTIC_YEARLY_CONTRACT_VERSION = "agentic_yearly_v14"
AGENTIC_YEARLY_REPORT_MODE = "agentic_longform"
BASIC_SUMMARY_FALLBACK_LEVEL = "basic_summary"


def _list(value: tuple[Any, ...] | list[Any]) -> list[Any]:
    return list(value)


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    tool_name: str
    params: dict[str, Any]
    result_summary: str
    supports: tuple[str, ...] = ()
    questions_raised: tuple[str, ...] = ()
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "result_summary": self.result_summary,
            "supports": _list(self.supports),
            "questions_raised": _list(self.questions_raised),
            "tool_call_id": self.tool_call_id,
        }


@dataclass(frozen=True)
class InsightSynthesis:
    main_thesis: str
    supporting_arguments: tuple[dict[str, Any], ...] = ()
    billboard_findings: tuple[str, ...] = ()
    playback_findings: tuple[str, ...] = ()
    tensions: tuple[str, ...] = ()
    interesting_anomalies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_thesis": self.main_thesis,
            "supporting_arguments": _list(self.supporting_arguments),
            "billboard_findings": _list(self.billboard_findings),
            "playback_findings": _list(self.playback_findings),
            "tensions": _list(self.tensions),
            "interesting_anomalies": _list(self.interesting_anomalies),
        }


@dataclass(frozen=True)
class OutlineSection:
    heading: str
    question: str
    claims: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "question": self.question,
            "claims": _list(self.claims),
        }


@dataclass(frozen=True)
class DynamicOutline:
    title: str
    sections: tuple[OutlineSection, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sections": [section.to_dict() for section in self.sections],
        }


@dataclass(frozen=True)
class EditorialIssue:
    code: str
    message: str
    severity: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class EditorialCritique:
    ok: bool
    issues: tuple[EditorialIssue, ...] = ()
    repair_instructions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "repair_instructions": _list(self.repair_instructions),
        }


@dataclass(frozen=True)
class AgenticYearlyMetadata:
    report_mode: str
    contract_version: str
    fallback_level: str | None
    tool_calls: int
    data_range: str
    is_partial_year: bool
    critic_passed: bool
    article_length: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_mode": self.report_mode,
            "contract_version": self.contract_version,
            "fallback_level": self.fallback_level,
            "tool_calls": self.tool_calls,
            "data_range": self.data_range,
            "is_partial_year": self.is_partial_year,
            "critic_passed": self.critic_passed,
            "article_length": self.article_length,
        }
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled for this execution:

```bash
git add backend/domains/ai_reports/agentic_models.py backend/tests/unit/test_agentic_yearly_report_service.py
git commit -m "feat: add agentic yearly report models"
```

---

## Task 2: Add Report-Oriented Read-Only Tools

**Files:**
- Create: `backend/domains/ai_reports/agentic_tools.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_tools.py`

- [ ] **Step 1: Write tests for report tool allowlist and static execution**

Create `backend/tests/unit/test_agentic_yearly_report_tools.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_tools import (
    REPORT_TOOL_NAMES,
    execute_report_tool,
    list_report_tools,
)

pytestmark = pytest.mark.unit


def test_report_tool_registry_is_read_only_and_report_scoped():
    tools = list_report_tools()
    names = {tool["name"] for tool in tools}

    assert REPORT_TOOL_NAMES <= names
    assert all(tool["read_only"] is True for tool in tools)
    assert "arbitrary_sql" not in names
    assert "fetch_url" not in names
    assert "settings_update" not in names


def test_report_period_context_tool_uses_supplied_latest_play_date():
    result = execute_report_tool(
        "report_period_context",
        {"year": 2026, "latest_play_date": "2026-06-23"},
    )

    assert result["ok"] is True
    assert result["data"]["year"] == 2026
    assert result["data"]["is_partial_year"] is True
    assert result["data"]["start_date"] == "2026-01-01"
    assert result["data"]["end_date"] == "2026-06-23"
    assert "2025-06-23" in result["summary"]


def test_unknown_report_tool_is_rejected():
    with pytest.raises(ValueError, match="Unknown report tool"):
        execute_report_tool("arbitrary_sql", {"sql": "select * from plays"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_tools.py -q
```

Expected: FAIL because `agentic_tools.py` does not exist.

- [ ] **Step 3: Implement initial report tool registry**

Create `backend/domains/ai_reports/agentic_tools.py`:

```python
"""Read-only report-oriented tools for agentic yearly reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

REPORT_TOOL_NAMES = {
    "report_period_context",
    "yearly_overview",
    "yearly_top_entities",
    "yearly_same_period_comparison",
    "personal_billboard_year_end",
    "billboard_yearly_diagnostics",
    "entity_stats",
    "genre_distribution",
    "discovery_and_returns",
    "highlight_day_detail",
}


@dataclass(frozen=True)
class ReportToolDefinition:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    read_only: bool = True

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "read_only": self.read_only,
        }


def _period_context(params: dict[str, Any]) -> dict[str, Any]:
    year = int(params.get("year") or date.today().year)
    latest = str(params.get("latest_play_date") or f"{year}-12-31")
    end_date = latest if latest.startswith(f"{year}-") else f"{year}-12-31"
    is_partial = end_date < f"{year}-12-31"
    previous_end = f"{year - 1}-{end_date[5:]}"
    data = {
        "year": year,
        "start_date": f"{year}-01-01",
        "end_date": end_date,
        "latest_play_date": latest,
        "is_partial_year": is_partial,
        "same_period_previous": {
            "start_date": f"{year - 1}-01-01",
            "end_date": previous_end,
        },
    }
    return {
        "ok": True,
        "data": data,
        "summary": (
            f"{year} report period is {data['start_date']} to {end_date}; "
            f"same-period comparison ends {previous_end}."
        ),
    }


def _not_implemented_summary(tool_name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {"params": params, "pending_live_implementation": True},
            "summary": f"{tool_name} stub returned no live data in this task.",
        }

    return handler


_TOOLS: dict[str, ReportToolDefinition] = {
    "report_period_context": ReportToolDefinition(
        name="report_period_context",
        description="Return report year, start/end dates, partial-year status, and same-period comparison window.",
        handler=_period_context,
    ),
}

for _name in sorted(REPORT_TOOL_NAMES - set(_TOOLS)):
    _TOOLS[_name] = ReportToolDefinition(
        name=_name,
        description=f"Read-only yearly report tool: {_name}.",
        handler=_not_implemented_summary(_name),
    )


def list_report_tools() -> list[dict[str, Any]]:
    return [_TOOLS[name].describe() for name in sorted(_TOOLS)]


def execute_report_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        definition = _TOOLS[tool_name]
    except KeyError as exc:
        raise ValueError(f"Unknown report tool: {tool_name}") from exc
    if not definition.read_only:
        raise ValueError(f"Report tool is not read-only: {tool_name}")
    return definition.handler(params or {})
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_tools.py -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/domains/ai_reports/agentic_tools.py backend/tests/unit/test_agentic_yearly_report_tools.py
git commit -m "feat: add report agent read-only tool registry"
```

---

## Task 3: Implement Live Yearly Report Tool Wrappers

**Files:**
- Modify: `backend/domains/ai_reports/agentic_tools.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_tools.py`

- [ ] **Step 1: Add tests for live yearly data wrappers with monkeypatches**

Append to `backend/tests/unit/test_agentic_yearly_report_tools.py`:

```python
def test_yearly_overview_tool_summarizes_wrapped_payload(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "reporting_period": {
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-06-23",
                "is_partial_year": True,
            },
            "hero": {
                "total_plays": 7860,
                "total_minutes": 29882,
                "unique_tracks": 2060,
                "unique_artists": 328,
                "active_days": 174,
            },
        },
    )

    result = execute_report_tool("yearly_overview", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["hero"]["total_plays"] == 7860
    assert "7,860" in result["summary"]
    assert "498" in result["summary"]


def test_yearly_top_entities_tool_returns_artists_tracks_and_albums(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
            "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
            "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        },
    )

    result = execute_report_tool("yearly_top_entities", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["top_albums"][0]["name"] == "The Life of a Showgirl"
    assert "Taylor Swift" in result["summary"]
    assert "The Life of a Showgirl" in result["summary"]


def test_personal_billboard_year_end_tool_returns_caveat(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "billboard_year_end": {
                "available": True,
                "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
                "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
                "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
                "caveat": "这是本地个人 Billboard Year-End，不是外部官方 Billboard 榜单。",
            }
        },
    )

    result = execute_report_tool("personal_billboard_year_end", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["available"] is True
    assert "不是外部官方" in result["data"]["caveat"]
    assert "Opalite" in result["summary"]
```

- [ ] **Step 2: Run tests to verify missing behavior**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_tools.py -q
```

Expected: FAIL because the tools still return initial stub data.

- [ ] **Step 3: Implement `_gather_yearly_data_for_tool()` and wrappers**

Modify `backend/domains/ai_reports/agentic_tools.py`:

```python
def _gather_yearly_data_for_tool(params: dict[str, Any]) -> dict[str, Any]:
    from backend.core.db import get_db
    from backend.services.ai_insights_service import _gather_yearly_data

    conn = get_db(readonly=True)
    try:
        return _gather_yearly_data(
            conn,
            min_ms=int(params.get("min_ms") or 30000),
            music_only=bool(params.get("music_only", True)),
            merge_enabled=bool(params.get("merge_enabled", True)),
            year=int(params.get("year") or date.today().year),
            dynamic_threshold=bool(params.get("dynamic_threshold", True)),
            max_merge_gap_minutes=params.get("max_merge_gap_minutes"),
        )
    finally:
        conn.close()


def _yearly_overview(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    period = data.get("reporting_period") or {}
    hero = data.get("hero") or {}
    total_minutes = float(hero.get("total_minutes") or 0)
    summary = (
        f"{period.get('start_date')} to {period.get('end_date')}: "
        f"{int(hero.get('total_plays') or 0):,} plays, "
        f"{round(total_minutes / 60, 1):g} hours, "
        f"{int(hero.get('unique_tracks') or 0):,} tracks, "
        f"{int(hero.get('unique_artists') or 0):,} artists."
    )
    return {"ok": True, "data": {"reporting_period": period, "hero": hero}, "summary": summary}


def _yearly_top_entities(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    payload = {
        "top_artists": data.get("top_artists") or [],
        "top_tracks": data.get("top_tracks") or [],
        "top_albums": data.get("top_albums") or [],
    }
    artist = _name(payload["top_artists"])
    track = _name(payload["top_tracks"])
    album = _name(payload["top_albums"])
    return {
        "ok": True,
        "data": payload,
        "summary": f"Top artist: {artist}; top track: {track}; top album: {album}.",
    }


def _personal_billboard_year_end(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    billboard = data.get("billboard_year_end") or {}
    summary = (
        f"Personal Billboard: track {_name(billboard.get('tracks') or [])}, "
        f"album {_name(billboard.get('albums') or [])}, "
        f"artist {_name(billboard.get('artists') or [])}."
    )
    return {"ok": True, "data": billboard, "summary": summary}


def _name(rows: Any) -> str:
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return str(rows[0].get("name") or "")
    return ""
```

Then update `_TOOLS` entries:

```python
_TOOLS: dict[str, ReportToolDefinition] = {
    "report_period_context": ReportToolDefinition(...),
    "yearly_overview": ReportToolDefinition(
        name="yearly_overview",
        description="Return yearly or year-to-date playback overview.",
        handler=_yearly_overview,
    ),
    "yearly_top_entities": ReportToolDefinition(
        name="yearly_top_entities",
        description="Return top artists, tracks, and albums for the report period.",
        handler=_yearly_top_entities,
    ),
    "personal_billboard_year_end": ReportToolDefinition(
        name="personal_billboard_year_end",
        description="Return local personal Billboard year-end or year-to-date track, album, and artist charts.",
        handler=_personal_billboard_year_end,
    ),
}
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_tools.py -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/domains/ai_reports/agentic_tools.py backend/tests/unit/test_agentic_yearly_report_tools.py
git commit -m "feat: wire report agent tools to yearly data"
```

---

## Task 4: Add Billboard Yearly Diagnostics

**Files:**
- Modify: `backend/domains/ai_reports/agentic_tools.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_tools.py`

- [ ] **Step 1: Add diagnostics test**

Append:

```python
def test_billboard_yearly_diagnostics_extracts_dominance_and_alignment(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "billboard_year_end": {
                "available": True,
                "tracks": [{"name": "Opalite", "artist": "Taylor Swift", "rank": 1, "weeks_on_chart": 19, "weeks_at_no1": 6}],
                "albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "rank": 1, "weeks_on_chart": 24, "weeks_at_no1": 5}],
                "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25, "weeks_at_no1": 9}],
            },
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}],
        },
    )

    result = execute_report_tool("billboard_yearly_diagnostics", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["dominance"]["artist"] == "Taylor Swift"
    assert result["data"]["cross_chart_alignment"][0]["entity"] == "Taylor Swift"
    assert "artist_album_track_all_strong" in result["data"]["cross_chart_alignment"][0]["alignment"]
    assert result["data"]["breakout_leaders"][0]["entity"] == "Zhang Zhen Yue"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_tools.py::test_billboard_yearly_diagnostics_extracts_dominance_and_alignment -q
```

Expected: FAIL because diagnostics still returns initial stub data.

- [ ] **Step 3: Implement diagnostics**

Add helpers in `agentic_tools.py`:

```python
def _billboard_yearly_diagnostics(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    billboard = data.get("billboard_year_end") or {}
    artists = billboard.get("artists") or []
    albums = billboard.get("albums") or []
    tracks = billboard.get("tracks") or []
    top_artist = artists[0] if artists else {}
    artist_name = str(top_artist.get("name") or "")
    diagnostics = {
        "dominance": {
            "artist": artist_name,
            "reason": (
                f"artist rank #{top_artist.get('rank')}, "
                f"{top_artist.get('weeks_on_chart')} weeks on chart, "
                f"{top_artist.get('weeks_at_no1')} weeks at No.1"
            )
            if artist_name
            else "",
        },
        "stability_leaders": _stability_leaders(artists, albums, tracks),
        "breakout_leaders": _breakout_leaders(data.get("new_artists") or []),
        "cross_chart_alignment": _cross_chart_alignment(artists, albums, tracks),
        "playback_billboard_tensions": [],
    }
    return {
        "ok": True,
        "data": diagnostics,
        "summary": f"Billboard diagnostics: dominance={artist_name or 'none'}; alignments={len(diagnostics['cross_chart_alignment'])}.",
    }


def _stability_leaders(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    labels = ("artist", "album", "track")
    for label, group in zip(labels, groups):
        for row in group[:3]:
            rows.append(
                {
                    "entity": row.get("name"),
                    "type": label,
                    "weeks_on_chart": row.get("weeks_on_chart"),
                }
            )
    return sorted(rows, key=lambda row: int(row.get("weeks_on_chart") or 0), reverse=True)[:5]


def _breakout_leaders(new_artists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "entity": row.get("name"),
            "type": "artist",
            "plays": row.get("plays"),
            "first_seen": row.get("first_date"),
        }
        for row in new_artists[:3]
        if row.get("name")
    ]


def _cross_chart_alignment(
    artists: list[dict[str, Any]],
    albums: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    artist_names = {str(row.get("name") or "") for row in artists[:3]}
    album_artists = {str(row.get("artist") or "") for row in albums[:3]}
    track_artists = {str(row.get("artist") or "") for row in tracks[:3]}
    aligned = sorted(name for name in artist_names & album_artists & track_artists if name)
    return [
        {
            "entity": name,
            "alignment": "artist_album_track_all_strong",
            "evidence": ["artist top 3", "album top 3", "track top 3"],
        }
        for name in aligned
    ]
```

Register:

```python
"billboard_yearly_diagnostics": ReportToolDefinition(
    name="billboard_yearly_diagnostics",
    description="Analyze personal Billboard dominance, stability, breakout signals, and cross-chart alignment.",
    handler=_billboard_yearly_diagnostics,
),
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_tools.py -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/domains/ai_reports/agentic_tools.py backend/tests/unit/test_agentic_yearly_report_tools.py
git commit -m "feat: add personal Billboard yearly diagnostics"
```

---

## Task 5: Add Editorial Critic

**Files:**
- Create: `backend/domains/ai_reports/editorial_critic.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_critic.py`

- [ ] **Step 1: Write critic tests**

Create `backend/tests/unit/test_agentic_yearly_report_critic.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.editorial_critic import critique_yearly_article

pytestmark = pytest.mark.unit


def test_critic_rejects_data_listing_report():
    report = """
## 2026 年中音乐报告（截至 2026-06-23）
Taylor Swift 以 1115 次播放排在艺人榜首。Olivia Rodrigo 以 769 次播放位列第二。
单曲榜首是 Opalite（123 次）。专辑榜首是 The Life of a Showgirl（445 次）。
Opalite 位列单曲年榜第 1，在榜 19 周。The Life of a Showgirl 位列专辑年榜第 1，在榜 24 周。
人格维度前三是 能量引擎 71.6 分、专一者 70.9 分、环球旅人 68.3 分。
"""

    critique = critique_yearly_article(
        report,
        {
            "is_partial_year": True,
            "min_length": 1400,
            "requires_billboard": True,
            "requires_playback_billboard_connection": True,
        },
    )

    codes = {issue.code for issue in critique.issues}
    assert critique.ok is False
    assert "too_short_for_longform" in codes
    assert "data_listing_too_heavy" in codes
    assert "billboard_underused" in codes


def test_critic_accepts_interpretive_longform_report():
    paragraph = (
        "Taylor Swift 的领先不是单点爆发，而是横跨艺人、专辑、单曲和个人 Billboard 的稳定中心。"
        "播放记录显示其艺人播放居首，个人 Billboard 又通过在榜周数和榜首周数说明这种中心并非短期波动。"
        "这意味着你的 2026 上半年仍有明确坐标，但 Zhang Zhen Yue 的进入改变了另一条线索。"
    )
    report = "## Taylor Swift 仍是中心，但你的音乐版图正在外扩\n\n" + paragraph * 18

    critique = critique_yearly_article(
        report,
        {
            "is_partial_year": True,
            "min_length": 1400,
            "requires_billboard": True,
            "requires_playback_billboard_connection": True,
        },
    )

    assert critique.ok is True
    assert critique.issues == ()
```

- [ ] **Step 2: Run failing critic tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_critic.py -q
```

Expected: FAIL because `editorial_critic.py` does not exist.

- [ ] **Step 3: Implement deterministic critic**

Create `backend/domains/ai_reports/editorial_critic.py`:

```python
"""Editorial quality critic for agentic yearly reports."""

from __future__ import annotations

import re
from typing import Any

from backend.domains.ai_reports.agentic_models import EditorialCritique, EditorialIssue

INTERPRETATION_TERMS = (
    "说明",
    "意味着",
    "反映",
    "不是",
    "而是",
    "共同指向",
    "形成",
    "支撑",
    "改变",
    "转向",
    "稳定",
    "扩张",
    "收束",
    "分化",
    "矛盾",
)

LISTING_PATTERNS = (
    r"以\s*[\d,]+",
    r"位列",
    r"排在",
    r"榜首",
    r"播放\s*[\d,]+",
)


def critique_yearly_article(report: str, context: dict[str, Any] | None = None) -> EditorialCritique:
    context = context or {}
    issues: list[EditorialIssue] = []
    min_length = int(context.get("min_length") or 1400)
    text = str(report or "").strip()

    if len(text) < min_length:
        issues.append(
            EditorialIssue(
                code="too_short_for_longform",
                message=f"正式长文报告至少需要 {min_length} 中文字符，当前为 {len(text)}。",
            )
        )

    if _listing_ratio(text) > 0.4 or _has_listing_run(text):
        issues.append(
            EditorialIssue(
                code="data_listing_too_heavy",
                message="报告过度罗列排名和播放次数，缺少解释段落。",
            )
        )

    if context.get("requires_billboard") and _billboard_underused(text):
        issues.append(
            EditorialIssue(
                code="billboard_underused",
                message="个人 Billboard 只被列为排名或在榜周数，缺少统治力、稳定性或三榜联动解释。",
            )
        )

    if context.get("requires_playback_billboard_connection") and not _connects_playback_and_billboard(text):
        issues.append(
            EditorialIssue(
                code="playback_billboard_not_connected",
                message="报告没有解释播放数据和个人 Billboard 数据之间的关系。",
            )
        )

    if context.get("is_partial_year") and any(
        term in text for term in ("年度专辑", "年度单曲", "年度冠军", "来年寄语")
    ):
        issues.append(
            EditorialIssue(
                code="partial_year_annual_label",
                message="阶段性报告不应使用完整年度实体标签。",
            )
        )

    repair = tuple(_repair_instruction(issue.code) for issue in issues)
    return EditorialCritique(ok=not issues, issues=tuple(issues), repair_instructions=repair)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]


def _listing_ratio(text: str) -> float:
    sentences = _sentences(text)
    if not sentences:
        return 1.0
    listing = 0
    for sentence in sentences:
        has_number = bool(re.search(r"\d", sentence))
        has_listing = any(re.search(pattern, sentence) for pattern in LISTING_PATTERNS)
        has_interpretation = any(term in sentence for term in INTERPRETATION_TERMS)
        if has_number and has_listing and not has_interpretation:
            listing += 1
    return listing / len(sentences)


def _has_listing_run(text: str) -> bool:
    run = 0
    for sentence in _sentences(text):
        if any(re.search(pattern, sentence) for pattern in LISTING_PATTERNS):
            run += 1
        else:
            run = 0
        if run >= 3:
            return True
    return False


def _billboard_underused(text: str) -> bool:
    if "Billboard" not in text and "个人榜" not in text:
        return True
    return not any(term in text for term in ("统治", "稳定", "持续", "峰值", "三榜", "联动", "在榜能力"))


def _connects_playback_and_billboard(text: str) -> bool:
    if "播放" not in text or ("Billboard" not in text and "个人榜" not in text):
        return False
    return any(term in text for term in ("共同", "同时", "印证", "说明", "不是单点", "互相"))


def _repair_instruction(code: str) -> str:
    return {
        "too_short_for_longform": "扩写为文章级长文，增加解释段落而不是填充榜单。",
        "data_listing_too_heavy": "把连续榜单句合并成论点段落，每段写出判断、证据和解释。",
        "billboard_underused": "补充个人 Billboard 的统治力、稳定性、三榜联动或播放/Billboard 分歧分析。",
        "playback_billboard_not_connected": "解释播放次数、播放时长和个人 Billboard 指标如何互相印证或冲突。",
        "partial_year_annual_label": "把完整年度措辞改为年中、阶段性或截至日期表达。",
    }.get(code, "根据 critic 问题重写对应段落。")
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_critic.py -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/domains/ai_reports/editorial_critic.py backend/tests/unit/test_agentic_yearly_report_critic.py
git commit -m "feat: add yearly report editorial critic"
```

---

## Task 6: Add Agentic Prompts

**Files:**
- Create: `backend/domains/ai_reports/agentic_prompts.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_service.py`

- [ ] **Step 1: Add prompt content tests**

Append to `backend/tests/unit/test_agentic_yearly_report_service.py`:

```python
def test_agentic_yearly_prompts_define_mission_and_boundaries():
    from backend.domains.ai_reports.agentic_prompts import (
        LONGFORM_DRAFT_SYSTEM_PROMPT,
        REPORT_MISSION_SYSTEM_PROMPT,
    )

    assert "只读" in REPORT_MISSION_SYSTEM_PROMPT
    assert "自主调用" in REPORT_MISSION_SYSTEM_PROMPT
    assert "个人 Billboard" in REPORT_MISSION_SYSTEM_PROMPT
    assert "不是外部官方 Billboard" in REPORT_MISSION_SYSTEM_PROMPT
    assert "播放分析年度总结页的文字复述" in REPORT_MISSION_SYSTEM_PROMPT
    assert "1400-2200" in LONGFORM_DRAFT_SYSTEM_PROMPT
    assert "判断 -> 证据 -> 解释" in LONGFORM_DRAFT_SYSTEM_PROMPT
    assert "不要只是罗列" in LONGFORM_DRAFT_SYSTEM_PROMPT
```

- [ ] **Step 2: Run failing prompt test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py::test_agentic_yearly_prompts_define_mission_and_boundaries -q
```

Expected: FAIL because `agentic_prompts.py` does not exist.

- [ ] **Step 3: Implement prompt module**

Create `backend/domains/ai_reports/agentic_prompts.py`:

```python
"""Prompts for agentic longform yearly report generation."""

from __future__ import annotations

REPORT_MISSION_SYSTEM_PROMPT = """你是 SpotifyStats 的只读年度报告研究员和音乐数据编辑。
SpotifyStats 分析用户本地 Spotify Extended Streaming History。播放分析数据代表用户个人播放行为。
SpotifyStats 的个人 Billboard 是基于用户自己的播放记录计算出的本地个人榜单，不是外部官方 Billboard、市场影响力或全球热度。
你的任务不是复述播放分析年度总结页的文字，而是自主调用后端提供的只读工具，研究播放分析与个人 Billboard 共同说明了什么。
你必须先查询证据，再形成 Evidence Ledger、Insight Synthesis 和 Dynamic Outline，最后写长篇 Markdown 分析文章。
只能基于工具返回的数据写作，不得编造歌词含义、人生事件、艺人性别、外部市场结论、任意 SQL、URL 或写操作。
"""

INSIGHT_SYNTHESIS_SYSTEM_PROMPT = """根据 DATA.evidence_ledger 生成结构化洞见。
输出 ONLY JSON，包含 main_thesis、supporting_arguments、billboard_findings、playback_findings、tensions、interesting_anomalies。
每个 claim 必须引用 evidence_refs。不要写最终文章。
"""

DYNAMIC_OUTLINE_SYSTEM_PROMPT = """根据 DATA.insight_synthesis 生成动态文章大纲。
输出 ONLY JSON，包含 title 和 sections。每个 section 必须包含 heading、question、claims。
大纲应服务于今年的数据主线，不要固定成 概览/艺人/歌曲/专辑/Billboard/流派 的仪表盘顺序。
"""

LONGFORM_DRAFT_SYSTEM_PROMPT = """你是可信的个人音乐年度分析文章作者。
根据 DATA.insight_synthesis、DATA.dynamic_outline 和 DATA.evidence_ledger 写中文 Markdown 长文。
年中/阶段性报告目标长度 1400-2200 中文字；完整年度报告目标长度 1800-3000 中文字。
每个主要段落都要遵循：判断 -> 证据 -> 解释 -> 对用户意味着什么。
必须把播放分析和个人 Billboard 联系起来解释，不要只是罗列排名、播放次数和在榜周数。
必须说明个人 Billboard 是本地个人榜，不是外部官方 Billboard。
如果 DATA.reporting_period.is_partial_year=true，必须写截至日期，不要使用完整年度标签。
"""

REPAIR_DRAFT_SYSTEM_PROMPT = """根据 DATA.critic.issues 和 DATA.critic.repair_instructions 修订年度报告。
保持事实不变，修复文章质量问题。不要新增 DATA 外事实。
输出完整 Markdown 报告，不要解释修订过程。
"""
```

- [ ] **Step 4: Run prompt tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py::test_agentic_yearly_prompts_define_mission_and_boundaries -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/domains/ai_reports/agentic_prompts.py backend/tests/unit/test_agentic_yearly_report_service.py
git commit -m "feat: add agentic yearly report prompts"
```

---

## Task 7: Implement Agentic Yearly Report Service Skeleton

**Files:**
- Create: `backend/services/yearly_report_agent_service.py`
- Modify: `backend/tests/unit/test_agentic_yearly_report_service.py`

- [ ] **Step 1: Add service skeleton tests**

Append:

```python
def test_agentic_service_generates_basic_metadata_with_injected_llm(monkeypatch):
    from backend.services import yearly_report_agent_service as svc

    monkeypatch.setattr(
        svc,
        "_run_research_plan",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="播放 7,860 次，累计 498 小时。",
                    supports=("activity_level",),
                ),
                EvidenceLedgerEntry(
                    tool_name="personal_billboard_year_end",
                    params={"year": 2026},
                    result_summary="个人 Billboard 显示 Taylor Swift 三榜联动。",
                    supports=("personal_billboard",),
                ),
            ],
            {"year": 2026, "reporting_period": {"start_date": "2026-01-01", "end_date": "2026-06-23", "is_partial_year": True}},
        ),
    )
    monkeypatch.setattr(
        svc,
        "_call_llm_json",
        lambda *args, **kwargs: {
            "main_thesis": "Taylor Swift 是稳定中心，Zhang Zhen Yue 打开新入口。",
            "supporting_arguments": [],
            "billboard_findings": ["个人 Billboard 说明稳定中心。"],
            "playback_findings": ["播放下降但探索扩大。"],
            "tensions": [],
            "interesting_anomalies": [],
            "title": "Taylor Swift 仍是中心",
            "sections": [
                {
                    "heading": "稳定中心",
                    "question": "中心如何成立？",
                    "claims": ["播放和榜单共同支持"],
                }
            ],
        },
    )
    long_report = (
        "## Taylor Swift 仍是中心\n\n"
        + "Taylor Swift 的领先不是单点爆发，而是播放分析和个人 Billboard 共同指向的稳定中心。这说明你的上半年有明确坐标，同时 Zhang Zhen Yue 打开新入口。"
        * 30
    )
    monkeypatch.setattr(svc, "_call_llm_text", lambda *args, **kwargs: long_report)

    result = svc.generate_agentic_yearly_report(
        {
            "year": 2026,
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
        }
    )

    assert result["success"] is True
    assert result["metadata"]["report_mode"] == "agentic_longform"
    assert result["metadata"]["contract_version"] == "agentic_yearly_v14"
    assert result["metadata"]["fallback_level"] is None
    assert result["metadata"]["tool_calls"] == 2
    assert result["metadata"]["critic_passed"] is True
```

- [ ] **Step 2: Run failing test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py::test_agentic_service_generates_basic_metadata_with_injected_llm -q
```

Expected: FAIL because service module does not exist.

- [ ] **Step 3: Implement service skeleton**

Create `backend/services/yearly_report_agent_service.py`:

```python
"""Agentic longform yearly report orchestration."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from backend.domains.ai_reports.agentic_models import (
    AGENTIC_YEARLY_CONTRACT_VERSION,
    AGENTIC_YEARLY_REPORT_MODE,
    AgenticYearlyMetadata,
    DynamicOutline,
    EvidenceLedgerEntry,
    InsightSynthesis,
    OutlineSection,
)
from backend.domains.ai_reports.agentic_prompts import (
    DYNAMIC_OUTLINE_SYSTEM_PROMPT,
    INSIGHT_SYNTHESIS_SYSTEM_PROMPT,
    LONGFORM_DRAFT_SYSTEM_PROMPT,
)
from backend.domains.ai_reports.agentic_tools import execute_report_tool
from backend.domains.ai_reports.editorial_critic import critique_yearly_article
from backend.services.ai_insights_service import _llm_chat

DEFAULT_RESEARCH_PLAN = (
    "report_period_context",
    "yearly_overview",
    "yearly_top_entities",
    "yearly_same_period_comparison",
    "personal_billboard_year_end",
    "billboard_yearly_diagnostics",
    "genre_distribution",
    "discovery_and_returns",
    "highlight_day_detail",
)


def generate_agentic_yearly_report(
    request: dict[str, Any],
    *,
    emit_event: Callable[[str, str, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    evidence, context = _run_research_plan(request, emit_event=emit_event)
    synthesis = _build_insight_synthesis(evidence)
    outline = _build_dynamic_outline(synthesis)
    report = _write_longform_report(context, evidence, synthesis, outline)
    critique = critique_yearly_article(
        report,
        {
            "is_partial_year": bool((context.get("reporting_period") or {}).get("is_partial_year")),
            "min_length": 1400,
            "requires_billboard": True,
            "requires_playback_billboard_connection": True,
        },
    )
    metadata = AgenticYearlyMetadata(
        report_mode=AGENTIC_YEARLY_REPORT_MODE,
        contract_version=AGENTIC_YEARLY_CONTRACT_VERSION,
        fallback_level=None,
        tool_calls=len(evidence),
        data_range=_data_range(context),
        is_partial_year=bool((context.get("reporting_period") or {}).get("is_partial_year")),
        critic_passed=critique.ok,
        article_length=len(report),
    )
    if not critique.ok:
        return {
            "success": False,
            "report": report,
            "metadata": metadata.to_dict(),
            "critic": critique.to_dict(),
            "evidence_ledger": [entry.to_dict() for entry in evidence],
            "error": "年度报告文章质量校验未通过",
        }
    return {
        "success": True,
        "report": report,
        "metadata": metadata.to_dict(),
        "critic": critique.to_dict(),
        "insight_synthesis": synthesis.to_dict(),
        "dynamic_outline": outline.to_dict(),
        "evidence_ledger": [entry.to_dict() for entry in evidence],
        "error": None,
    }


def _run_research_plan(
    request: dict[str, Any],
    *,
    emit_event: Callable[[str, str, dict[str, Any] | None], None] | None = None,
) -> tuple[list[EvidenceLedgerEntry], dict[str, Any]]:
    evidence: list[EvidenceLedgerEntry] = []
    context: dict[str, Any] = {}
    for tool_name in DEFAULT_RESEARCH_PLAN:
        params = dict(request)
        result = execute_report_tool(tool_name, params)
        data = result.get("data") if isinstance(result, dict) else {}
        if isinstance(data, dict):
            context.update(_context_fragment(tool_name, data))
        entry = EvidenceLedgerEntry(
            tool_name=tool_name,
            params=params,
            result_summary=str(result.get("summary") or ""),
            supports=(tool_name,),
        )
        evidence.append(entry)
        if emit_event:
            emit_event("tool_call_completed", f"完成 {tool_name}", entry.to_dict())
    return evidence, context


def _context_fragment(tool_name: str, data: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "report_period_context":
        return {"reporting_period": data}
    if tool_name == "yearly_overview":
        return data
    return {tool_name: data}


def _build_insight_synthesis(evidence: list[EvidenceLedgerEntry]) -> InsightSynthesis:
    payload = {"evidence_ledger": [entry.to_dict() for entry in evidence]}
    parsed = _call_llm_json(INSIGHT_SYNTHESIS_SYSTEM_PROMPT, payload)
    return InsightSynthesis(
        main_thesis=str(parsed.get("main_thesis") or ""),
        supporting_arguments=tuple(parsed.get("supporting_arguments") or ()),
        billboard_findings=tuple(parsed.get("billboard_findings") or ()),
        playback_findings=tuple(parsed.get("playback_findings") or ()),
        tensions=tuple(parsed.get("tensions") or ()),
        interesting_anomalies=tuple(parsed.get("interesting_anomalies") or ()),
    )


def _build_dynamic_outline(synthesis: InsightSynthesis) -> DynamicOutline:
    parsed = _call_llm_json(DYNAMIC_OUTLINE_SYSTEM_PROMPT, {"insight_synthesis": synthesis.to_dict()})
    sections = tuple(
        OutlineSection(
            heading=str(row.get("heading") or ""),
            question=str(row.get("question") or ""),
            claims=tuple(row.get("claims") or ()),
        )
        for row in parsed.get("sections", [])
        if isinstance(row, dict)
    )
    return DynamicOutline(title=str(parsed.get("title") or ""), sections=sections)


def _write_longform_report(
    context: dict[str, Any],
    evidence: list[EvidenceLedgerEntry],
    synthesis: InsightSynthesis,
    outline: DynamicOutline,
) -> str:
    return _call_llm_text(
        LONGFORM_DRAFT_SYSTEM_PROMPT,
        {
            "context": context,
            "evidence_ledger": [entry.to_dict() for entry in evidence],
            "insight_synthesis": synthesis.to_dict(),
            "dynamic_outline": outline.to_dict(),
        },
    )


def _call_llm_json(system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _llm_chat(system_prompt, json.dumps(payload, ensure_ascii=False, indent=2), temperature=0.1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _call_llm_text(system_prompt: str, payload: dict[str, Any]) -> str:
    return str(
        _llm_chat(system_prompt, json.dumps(payload, ensure_ascii=False, indent=2), temperature=0.2)
        or ""
    ).strip()


def _data_range(context: dict[str, Any]) -> str:
    period = context.get("reporting_period") or {}
    start = period.get("start_date") or ""
    end = period.get("end_date") or ""
    return f"{start} to {end}".strip()
```

- [ ] **Step 4: Run service skeleton test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py::test_agentic_service_generates_basic_metadata_with_injected_llm -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/services/yearly_report_agent_service.py backend/tests/unit/test_agentic_yearly_report_service.py
git commit -m "feat: add agentic yearly report service skeleton"
```

---

## Task 8: Add Fallback Metadata And Basic Summary Path

**Files:**
- Modify: `backend/services/yearly_report_agent_service.py`
- Test: `backend/tests/unit/test_agentic_yearly_report_service.py`

- [ ] **Step 1: Add fallback test**

Append:

```python
def test_agentic_service_marks_basic_summary_fallback_when_critic_fails(monkeypatch):
    from backend.services import yearly_report_agent_service as svc

    monkeypatch.setattr(
        svc,
        "_run_research_plan",
        lambda request, emit_event=None: (
            [EvidenceLedgerEntry(tool_name="yearly_overview", params={"year": 2026}, result_summary="summary")],
            {"reporting_period": {"start_date": "2026-01-01", "end_date": "2026-06-23", "is_partial_year": True}},
        ),
    )
    monkeypatch.setattr(svc, "_call_llm_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(svc, "_call_llm_text", lambda *args, **kwargs: "Taylor Swift 以 1115 次播放排在第一。")
    monkeypatch.setattr(svc, "_build_basic_summary_fallback", lambda context, request: "## 基础摘要\nTaylor Swift 是第一。")

    result = svc.generate_agentic_yearly_report({"year": 2026})

    assert result["success"] is True
    assert result["metadata"]["fallback_level"] == "basic_summary"
    assert result["metadata"]["critic_passed"] is False
    assert result["report"].startswith("## 基础摘要")
```

- [ ] **Step 2: Run failing fallback test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py::test_agentic_service_marks_basic_summary_fallback_when_critic_fails -q
```

Expected: FAIL because the service currently returns `success=False` on critic failure.

- [ ] **Step 3: Implement fallback path**

Modify `generate_agentic_yearly_report()` critic failure branch:

```python
    if not critique.ok:
        fallback = _build_basic_summary_fallback(context, request)
        fallback_metadata = AgenticYearlyMetadata(
            report_mode=AGENTIC_YEARLY_REPORT_MODE,
            contract_version=AGENTIC_YEARLY_CONTRACT_VERSION,
            fallback_level=BASIC_SUMMARY_FALLBACK_LEVEL,
            tool_calls=len(evidence),
            data_range=_data_range(context),
            is_partial_year=bool((context.get("reporting_period") or {}).get("is_partial_year")),
            critic_passed=False,
            article_length=len(fallback),
        )
        return {
            "success": True,
            "report": fallback,
            "metadata": fallback_metadata.to_dict(),
            "critic": critique.to_dict(),
            "evidence_ledger": [entry.to_dict() for entry in evidence],
            "error": None,
        }
```

Import `BASIC_SUMMARY_FALLBACK_LEVEL` from `agentic_models`.

Add helper:

```python
def _build_basic_summary_fallback(context: dict[str, Any], request: dict[str, Any]) -> str:
    from backend.core.db import get_db
    from backend.services.ai_insights_service import _build_yearly_report_fallback, _gather_yearly_data

    conn = get_db(readonly=True)
    try:
        data = _gather_yearly_data(
            conn,
            min_ms=int(request.get("min_ms") or 30000),
            music_only=bool(request.get("music_only", True)),
            merge_enabled=bool(request.get("merge_enabled", True)),
            year=int(request.get("year") or 0) or None,
            dynamic_threshold=bool(request.get("dynamic_threshold", True)),
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
        )
    finally:
        conn.close()
    return _build_yearly_report_fallback(data)
```

- [ ] **Step 4: Run fallback test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py::test_agentic_service_marks_basic_summary_fallback_when_critic_fails -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/services/yearly_report_agent_service.py backend/tests/unit/test_agentic_yearly_report_service.py
git commit -m "feat: add basic summary fallback metadata"
```

---

## Task 9: Persist Agentic Task Events And Tool Calls

**Files:**
- Modify: `backend/services/yearly_report_agent_service.py`
- Modify: `backend/services/ai_task_service.py`
- Test: `backend/tests/unit/test_ai_report_tasks.py`

- [ ] **Step 1: Add task event expectations**

In `backend/tests/unit/test_ai_report_tasks.py`, add a test using the existing task repository test style:

```python
def test_yearly_agent_task_emits_research_outline_and_critic_events(monkeypatch):
    from backend.services import ai_task_service

    captured: list[tuple[str, dict]] = []

    def fake_generate(request, *, emit_event=None):
        if emit_event:
            emit_event("stage_started", "查询年度播放概览", {"stage": "researching"})
            emit_event("stage_started", "生成文章大纲", {"stage": "outlining"})
            emit_event("stage_started", "审稿与修订", {"stage": "critic_review"})
        captured.append(("request", request))
        return {
            "success": True,
            "report": "## Longform\n" + "解释" * 800,
            "metadata": {
                "report_mode": "agentic_longform",
                "contract_version": "agentic_yearly_v14",
                "fallback_level": None,
                "tool_calls": 6,
                "data_range": "2026-01-01 to 2026-06-23",
                "is_partial_year": True,
                "critic_passed": True,
                "article_length": 1600,
            },
            "evidence_ledger": [
                {
                    "tool_name": "yearly_overview",
                    "params": {"year": 2026},
                    "result_summary": "播放 7,860 次，累计 498 小时。",
                },
                {
                    "tool_name": "personal_billboard_year_end",
                    "params": {"year": 2026},
                    "result_summary": "个人 Billboard 显示 Taylor Swift 三榜联动。",
                },
            ],
            "critic": {"ok": True, "issues": []},
        }

    monkeypatch.setattr(
        "backend.services.yearly_report_agent_service.generate_agentic_yearly_report",
        fake_generate,
    )

    task = ai_task_service.start_report_task(
        {
            "report_type": "yearly",
            "action": "generate",
            "year": 2026,
            "report_mode": "agentic_longform",
        }
    )
    ai_task_service.run_report_task_inline_for_tests(task["task_id"])
    events, tool_calls = ai_task_service.get_task_events(task["task_id"])

    messages = [event["message"] for event in events]
    assert "查询年度播放概览" in messages
    assert "生成文章大纲" in messages
    assert "审稿与修订" in messages
    assert [call["tool_name"] for call in tool_calls] == [
        "yearly_overview",
        "personal_billboard_year_end",
    ]
```

If `run_report_task_inline_for_tests()` does not exist, add it in this task as a small test-only helper that calls `run_report_generation_task(task_id, request)` synchronously with the stored request.

- [ ] **Step 2: Run failing task test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_report_tasks.py::test_yearly_agent_task_emits_research_outline_and_critic_events -q
```

Expected: FAIL because yearly report tasks still route to the old report generator and/or helper is missing.

- [ ] **Step 3: Route yearly agent tasks**

Modify `backend/services/ai_task_service.py`:

```python
def _should_use_agentic_yearly_report(request: dict[str, Any]) -> bool:
    return request.get("report_type") == "yearly" and request.get(
        "report_mode", "agentic_longform"
    ) == "agentic_longform"
```

In `_run_report_generator()`, branch before the old yearly `generate_yearly_story()` call:

```python
if _should_use_agentic_yearly_report(request):
    from backend.services.yearly_report_agent_service import generate_agentic_yearly_report

    def emit_event(event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        stage = str((payload or {}).get("stage") or "researching")
        progress = float((payload or {}).get("progress_pct") or _AGENTIC_STAGE_PROGRESS.get(stage, 0.5))
        if progress_callback is not None:
            progress_callback(stage, progress, message)

    return generate_agentic_yearly_report(request, emit_event=emit_event)
```

Add the progress map near `ENRICHMENT_PROGRESS_BY_STAGE`:

```python
_AGENTIC_STAGE_PROGRESS = {
    "researching": 0.25,
    "synthesizing_insights": 0.45,
    "outlining": 0.6,
    "drafting": 0.75,
    "critic_review": 0.85,
}
```

Add `_persist_report_tool_calls()` near `_write_report_cache_from_task_result()`:

```python
def _persist_report_tool_calls(
    repo: AiTaskRepository,
    *,
    task_id: str,
    result: dict[str, Any],
) -> None:
    for entry in result.get("evidence_ledger") or []:
        if not isinstance(entry, dict):
            continue
        repo.add_tool_call(
            task_id=task_id,
            tool_name=str(entry.get("tool_name") or ""),
            status="done",
            params_summary=json.dumps(entry.get("params") or {}, ensure_ascii=False),
            result_summary=str(entry.get("result_summary") or ""),
            source_range=str((result.get("metadata") or {}).get("data_range") or ""),
        )
```

Import `json` at the top of `backend/services/ai_task_service.py`.

In `run_report_generation_task()`, after `result = _run_report_generator(...)` and before the success branch saves cache, call:

```python
        if result.get("metadata", {}).get("report_mode") == "agentic_longform":
            _persist_report_tool_calls(repo, task_id=task_id, result=result)
```

- [ ] **Step 4: Add inline test helper if needed**

If the test needs synchronous execution, add:

```python
def run_report_task_inline_for_tests(task_id: str) -> None:
    conn = get_db(readonly=True)
    try:
        task = AiTaskRepository(conn).get_run(task_id)
    finally:
        conn.close()
    if not task:
        raise ValueError(f"Unknown task: {task_id}")
    run_report_generation_task(task_id, task.get("request") or {})
```

- [ ] **Step 5: Run task test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_report_tasks.py::test_yearly_agent_task_emits_research_outline_and_critic_events -q
```

Expected: PASS.

- [ ] **Step 6: Checkpoint**

If commits are enabled:

```bash
git add backend/services/ai_task_service.py backend/services/yearly_report_agent_service.py backend/tests/unit/test_ai_report_tasks.py
git commit -m "feat: route yearly report tasks through agent workflow"
```

---

## Task 10: Preserve API Compatibility And Expose Metadata

**Files:**
- Modify: `backend/api/ai_insights.py`
- Modify: `backend/services/ai_insights_service.py` only if direct synchronous yearly endpoint still bypasses tasks.
- Test: `backend/tests/contract/test_agentic_yearly_report_contract.py`

- [ ] **Step 1: Write contract tests**

Create `backend/tests/contract/test_agentic_yearly_report_contract.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract


def test_yearly_story_response_includes_agentic_metadata(monkeypatch):
    monkeypatch.setattr(
        "backend.services.yearly_report_agent_service.generate_agentic_yearly_report",
        lambda request, emit_event=None: {
            "success": True,
            "report": "## Longform\n" + "解释" * 800,
            "metadata": {
                "report_mode": "agentic_longform",
                "contract_version": "agentic_yearly_v14",
                "fallback_level": None,
                "tool_calls": 8,
                "data_range": "2026-01-01 to 2026-06-23",
                "is_partial_year": True,
                "critic_passed": True,
                "article_length": 1600,
            },
            "critic": {"ok": True, "issues": []},
            "evidence_ledger": [],
            "error": None,
        },
    )
    client = TestClient(app)

    response = client.get("/api/ai-insights/yearly-story?year=2026&force=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["report"]
    assert payload["metadata"]["report_mode"] == "agentic_longform"
    assert payload["metadata"]["critic_passed"] is True
```

- [ ] **Step 2: Run failing contract test**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_agentic_yearly_report_contract.py -q
```

Expected: FAIL if API response does not include `metadata` or does not route to new service.

- [ ] **Step 3: Update API route**

In `backend/api/ai_insights.py`, when handling yearly report generation:

```python
if force and report_mode == "agentic_longform":
    from backend.services.yearly_report_agent_service import generate_agentic_yearly_report

    result = generate_agentic_yearly_report(
        {
            "year": year,
            "min_ms": min_ms,
            "music_only": music_only,
            "merge_enabled": merge_enabled,
            "dynamic_threshold": dynamic_threshold,
            "max_merge_gap_minutes": max_merge_gap_minutes,
            "report_mode": "agentic_longform",
        }
    )
    return result
```

Preserve existing response fields (`success`, `report`, `error`, `cached`) for frontend compatibility. Add `metadata`, `critic`, and `evidence_ledger` as optional fields.

- [ ] **Step 4: Run contract test**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_agentic_yearly_report_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add backend/api/ai_insights.py backend/tests/contract/test_agentic_yearly_report_contract.py
git commit -m "feat: expose agentic yearly report metadata"
```

---

## Task 11: Add HTTP Probe For Agentic Yearly Report Quality

**Files:**
- Create: `scripts/probe_agentic_yearly_report.py`
- Test manually with running backend.

- [ ] **Step 1: Create probe script**

Create `scripts/probe_agentic_yearly_report.py`:

```python
#!/usr/bin/env python3
"""Probe agentic yearly report quality through the HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FORBIDDEN_PARTIAL_TERMS = (
    "年度专辑",
    "年度单曲",
    "年度冠军",
    "来年寄语",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--min-length", type=int, default=1400)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    payload = _fetch(args.base_url, args.year, args.timeout)
    report = str(payload.get("report") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    issues = []
    if not payload.get("success"):
        issues.append("response_success_false")
    if metadata.get("report_mode") != "agentic_longform":
        issues.append("missing_agentic_report_mode")
    if metadata.get("fallback_level") is not None:
        issues.append(f"unexpected_fallback:{metadata.get('fallback_level')}")
    if len(report) < args.min_length:
        issues.append("report_too_short")
    if metadata.get("critic_passed") is not True:
        issues.append("critic_not_passed")
    if int(metadata.get("tool_calls") or 0) < 6:
        issues.append("too_few_tool_calls")
    forbidden_hits = [term for term in FORBIDDEN_PARTIAL_TERMS if term in report]
    if forbidden_hits:
        issues.append(f"forbidden_partial_terms:{','.join(forbidden_hits)}")
    if "个人 Billboard" not in report and "个人榜" not in report:
        issues.append("missing_personal_billboard")
    if "播放" not in report:
        issues.append("missing_playback_analysis")

    summary = {
        "ok": not issues,
        "issues": issues,
        "metadata": metadata,
        "report_length": len(report),
        "preview": report[:1000],
    }
    if args.json_output:
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


def _fetch(base_url: str, year: int, timeout: float) -> dict:
    query = urlencode({"year": year, "force": "true", "report_mode": "agentic_longform"})
    url = f"{base_url.rstrip('/')}/api/ai-insights/yearly-story?{query}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"success": False, "status": exc.code, "error": body}
    except (URLError, TimeoutError) as exc:
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run syntax check**

Run:

```bash
.venv/bin/python -m py_compile scripts/probe_agentic_yearly_report.py
```

Expected: PASS.

- [ ] **Step 3: Run probe against local backend**

With backend running on 8000:

```bash
.venv/bin/python scripts/probe_agentic_yearly_report.py --year 2026 --json-output /tmp/spotify_agentic_yearly_probe.json
```

Expected: PASS and JSON `ok: true`.

- [ ] **Step 4: Checkpoint**

If commits are enabled:

```bash
git add scripts/probe_agentic_yearly_report.py
git commit -m "test: add agentic yearly report HTTP probe"
```

---

## Task 12: Add Frontend Stage Labels And Metadata Display

**Files:**
- Modify: `frontend/src/features/ai-tasks/` task stage label module or nearest equivalent component.
- Modify: `frontend/src/features/ai-insights/` yearly report result component.
- Test: existing frontend interaction smoke and any relevant unit tests.

- [ ] **Step 1: Locate current stage label mapping**

Run:

```bash
rg -n "calling_llm|saving_cache|stage|progress_pct|tool_calls|AI 任务进度" frontend/src/features/ai-tasks frontend/src/features/ai-insights
```

Expected: identify the component that maps backend task stages to user-facing labels.

- [ ] **Step 2: Add stage labels**

Add labels for these stages in the discovered mapping:

```ts
const AI_TASK_STAGE_LABELS: Record<string, string> = {
  researching: "查询年度数据",
  synthesizing_insights: "分析报告主线",
  outlining: "生成文章大纲",
  drafting: "撰写长篇报告",
  critic_review: "审稿与修订",
};
```

Keep existing labels unchanged.

- [ ] **Step 3: Display report metadata if present**

In the yearly report result component, render compact metadata only when `result.metadata?.report_mode === "agentic_longform"`:

```tsx
{metadata?.report_mode === "agentic_longform" && (
  <div className="ai-report-meta" aria-label="AI 报告元信息">
    <span>{metadata.critic_passed ? "已通过文章质量审稿" : "基础摘要"}</span>
    <span>{metadata.article_length} 字</span>
    <span>{metadata.tool_calls} 次只读查询</span>
  </div>
)}
```

Use existing design primitives/classes in the file rather than introducing a new visual system.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd frontend && npm test -- --run
```

Expected: PASS.

- [ ] **Step 5: Run AI Insights interaction smoke**

Run:

```bash
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173 --scenario ai-insights-tabs
```

Expected: PASS, 0 console errors/warnings, 0 horizontal overflow.

- [ ] **Step 6: Checkpoint**

If commits are enabled:

```bash
git add frontend/src/features/ai-tasks frontend/src/features/ai-insights
git commit -m "feat: show agentic yearly report progress metadata"
```

---

## Task 13: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `backend/CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Update docs index**

In `docs/README.md`, add this row near AI yearly report docs if missing:

```markdown
| [`superpowers/plans/2026-07-03-agentic-longform-yearly-report.md`](superpowers/plans/2026-07-03-agentic-longform-yearly-report.md) | Agentic Longform Yearly Report 实施计划：只读 Report Agent、自主查询、Evidence Ledger、动态大纲、个人 Billboard 深度分析、长文 critic 与验收探针 |
```

- [ ] **Step 2: Update changelog**

Add a `2026-07-03 — Agentic Longform Yearly Report` section to `docs/CHANGELOG.md`:

```markdown
## 2026-07-03 — Agentic Longform Yearly Report

### 计划与设计

- 新增 Agentic Longform Yearly Report V14 实施计划，目标是把年度报告从播放分析页面复述升级为只读 Report Agent 自主查询、分析、审稿后生成的长篇个人音乐分析文章。
- 计划保留 V12 年度报告事实安全 validator 和 basic summary fallback，同时新增 Evidence Ledger、Insight Synthesis、Dynamic Outline、Billboard diagnostics 与 Editorial Critic。
- 年度报告验收标准提升为：长文长度、明确 thesis、播放与个人 Billboard 关系解释、动态结构、工具轨迹可见和反数据罗列 critic。
```

- [ ] **Step 3: Update AI context docs after implementation**

After code lands, update these docs with the actual final behavior:

- `README.md`: user-facing AI Insights description.
- `AGENTS.md`: AI report agent architecture and read-only boundary.
- `CLAUDE.md`: quick developer status.
- `backend/CLAUDE.md`: backend service/module table.

Use concrete implemented names: `yearly_report_agent_service.py`, `agentic_tools.py`, `editorial_critic.py`, and `agentic_yearly_v14`.

- [ ] **Step 4: Check docs for stale version references**

Run:

```bash
rg -n "contract_v12|agentic_yearly_v14|Agentic Longform|basic_summary" README.md AGENTS.md CLAUDE.md backend/CLAUDE.md docs/README.md docs/CHANGELOG.md docs/superpowers
```

Expected: V12 appears only as safety/fallback context; V14 appears as the new agentic report workflow.

- [ ] **Step 5: Checkpoint**

If commits are enabled:

```bash
git add README.md AGENTS.md CLAUDE.md backend/CLAUDE.md docs/README.md docs/CHANGELOG.md docs/superpowers/plans/2026-07-03-agentic-longform-yearly-report.md
git commit -m "docs: plan agentic longform yearly reports"
```

---

## Task 14: Final Validation Matrix

**Files:**
- No new files unless a validation failure requires a focused fix.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
.venv/bin/pytest \
  backend/tests/unit/test_agentic_yearly_report_tools.py \
  backend/tests/unit/test_agentic_yearly_report_critic.py \
  backend/tests/unit/test_agentic_yearly_report_service.py \
  backend/tests/unit/test_ai_insights_yearly_quality.py \
  backend/tests/unit/test_ai_report_tasks.py \
  backend/tests/contract/test_agentic_yearly_report_contract.py \
  backend/tests/contract/test_ai_insights_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run lint and format checks**

Run:

```bash
.venv/bin/ruff check \
  backend/domains/ai_reports \
  backend/services/yearly_report_agent_service.py \
  backend/services/ai_task_service.py \
  backend/api/ai_insights.py \
  backend/tests/unit/test_agentic_yearly_report_tools.py \
  backend/tests/unit/test_agentic_yearly_report_critic.py \
  backend/tests/unit/test_agentic_yearly_report_service.py \
  backend/tests/contract/test_agentic_yearly_report_contract.py \
  scripts/probe_agentic_yearly_report.py

.venv/bin/ruff format --check \
  backend/domains/ai_reports \
  backend/services/yearly_report_agent_service.py \
  backend/services/ai_task_service.py \
  backend/api/ai_insights.py \
  backend/tests/unit/test_agentic_yearly_report_tools.py \
  backend/tests/unit/test_agentic_yearly_report_critic.py \
  backend/tests/unit/test_agentic_yearly_report_service.py \
  backend/tests/contract/test_agentic_yearly_report_contract.py \
  scripts/probe_agentic_yearly_report.py
```

Expected: PASS.

- [ ] **Step 3: Run agentic HTTP probe**

With backend running:

```bash
.venv/bin/python scripts/probe_agentic_yearly_report.py --year 2026 --json-output /tmp/spotify_agentic_yearly_probe.json
cat /tmp/spotify_agentic_yearly_probe.json
```

Expected:

- `ok: true`
- `metadata.report_mode: agentic_longform`
- `metadata.contract_version: agentic_yearly_v14`
- `metadata.fallback_level: null`
- `metadata.critic_passed: true`
- `metadata.article_length >= 1400`
- `metadata.tool_calls >= 6`

- [ ] **Step 4: Run existing yearly text probe**

Run:

```bash
.venv/bin/python scripts/probe_ai_yearly_report_text_quality.py --year 2026 --force --json-output /tmp/spotify_ai_yearly_text_after_agentic.json
```

Expected: PASS. If this probe still validates through the V12 validator only, inspect output manually and use `probe_agentic_yearly_report.py` as the stronger V14 gate.

- [ ] **Step 5: Run frontend interaction smoke**

Run:

```bash
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173 --scenario ai-insights-tabs
```

Expected: PASS with 0 console errors, 0 warnings, 0 page errors, 0px scroll overflow.

- [ ] **Step 6: Manual browser acceptance**

In the in-app browser:

1. Open `http://localhost:5173/ai-insights`.
2. Navigate to yearly report.
3. Click the manual generate/refresh button for 2026.
4. Confirm progress stages include data research, Billboard query, insight synthesis, outline, draft, and critic review.
5. Confirm final report is article-length and not a dashboard restatement.
6. Confirm report mentions local personal Billboard boundary.
7. Confirm report explains at least one relationship between playback behavior and personal Billboard evidence.

- [ ] **Step 7: Final workspace and docs check**

Run:

```bash
git status --short
rg -n "contract_v11|contract_v10" docs/superpowers/plans/2026-07-03-agentic-longform-yearly-report.md backend/domains/ai_reports backend/services/yearly_report_agent_service.py
```

Expected:

- No accidental runtime files staged.
- No unresolved planning markers in new plan/code.
- Old contract versions do not appear in new V14 files except historical docs.

---

## Self-Review Checklist

- [ ] Spec goal is covered: report generation is agentic, tool-driven, and longform.
- [ ] Read-only boundary is covered: report tools are allowlisted and reject unknown tool names.
- [ ] Evidence Ledger is covered: every tool call becomes an `EvidenceLedgerEntry`.
- [ ] Insight Synthesis is covered: service builds structured synthesis before drafting.
- [ ] Dynamic Outline is covered: service builds outline before drafting.
- [ ] Billboard analysis is covered: diagnostics include dominance, stability, breakout, and cross-chart alignment.
- [ ] Critic is covered: deterministic critic rejects data listing, Billboard underuse, and partial-year annual labels.
- [ ] Fallback distinction is covered: critic failure returns `fallback_level=basic_summary`.
- [ ] Frontend is covered: progress labels and metadata display are planned.
- [ ] Verification is covered: backend tests, lint, HTTP probe, frontend smoke, manual browser acceptance.
