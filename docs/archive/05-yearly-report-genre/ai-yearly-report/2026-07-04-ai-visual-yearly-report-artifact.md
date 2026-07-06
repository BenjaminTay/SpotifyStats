# AI Visual Yearly Report Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade yearly AI reports from text-only analysis into a structured visual music-year artifact with narrative sections, insight cards, chart blocks, real chart data, and style/fact validation.

**Architecture:** Keep the existing read-only Report Agent, evidence ledger, yearly contract, and fact validator. Add a `visual_yearly_artifact` pipeline after evidence gathering: deterministic Narrative Brief, Visual Brief, Chart Data Builder, Artifact Composer, Visual Critic, and frontend artifact renderer. Preserve `agentic_longform` and `basic_summary` as explicit fallback modes.

**Tech Stack:** FastAPI service layer, SQLite-backed AI task runs/events/tool calls, existing `backend/domains/ai_reports` package, pytest unit/contract tests, React 19 + TypeScript, TanStack Query, ECharts via existing `LazyEChart`, Vitest, Playwright/browser smoke probes.

---

## Implementation Status

Status: implemented and self-verified on 2026-07-04.

Delivered:

- Backend `visual_yearly_artifact` mode with `visual_yearly_v1` artifact schema, narrative brief, visual brief, deterministic chart data builder, visual critic, fact validation, cache isolation, AI task routing, and direct forced API support.
- Frontend artifact renderer for `/ai-insights` yearly reports, including hero, insight cards, sections, and 7 concrete chart blocks.
- Probe script `scripts/probe_visual_yearly_report_artifact.py` and targeted backend/frontend tests.
- Documentation updates in README, AGENTS, CLAUDE, backend CLAUDE, docs README, CHANGELOG, and this plan.

Acceptance evidence:

- Backend targeted pytest: 36 passed.
- Frontend targeted Vitest: 7 passed.
- `npm run build`: pass.
- Ruff targeted check and `git diff --check`: pass.
- Live artifact probes for 2025 and 2026: pass, each with 7 sections, 7 chart data blocks, and 3 insight cards.
- Browser acceptance via Chrome CDP: `/ai-insights` -> `年度叙事`, desktop 1440px and mobile 390px, 8 figures, 0 console warning/error, 0 horizontal overflow, no chart empty-state fallback, no `[object Object]`.
- Browser screenshots: `/tmp/spotify_visual_yearly_desktop.png`, `/tmp/spotify_visual_yearly_mobile.png`.

Not done:

- No commit was created in this execution; commit remains a separate explicit user action.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-07-03-ai-visual-yearly-report-artifact-design.md`
- Existing agentic yearly report plan: `docs/superpowers/plans/2026-07-03-agentic-longform-yearly-report.md`
- Existing implementation entry points:
  - `backend/services/yearly_report_agent_service.py`
  - `backend/domains/ai_reports/agentic_tools.py`
  - `backend/domains/ai_reports/yearly_contract.py`
  - `backend/domains/ai_reports/yearly_validator.py`
  - `backend/services/ai_task_service.py`
  - `frontend/src/features/ai-insights/ReportCard.tsx`
  - `frontend/src/features/ai-tasks/AITaskProgress.tsx`

## Scope

This plan implements one complete vertical slice:

- `visual_yearly_artifact` report mode for yearly reports.
- Structured backend artifact result with narrative brief, visual brief, sections, insight cards, chart specs, chart data, critic, and fact validation.
- Frontend renderer for yearly artifact on the existing `/ai-insights` report surface.
- Chart data generated only by deterministic backend code.
- HTTP probe and browser acceptance checks for 2025 full-year and 2026 partial-year reports.

This plan does not implement PDF export, social sharing, custom themes, generated images, or weekly/monthly artifact rendering.

## File Map

### Backend Create

- `backend/domains/ai_reports/visual_artifact_models.py`
  - Dataclasses and constants for `visual_yearly_v1`, sections, insight cards, chart specs, chart data, artifact metadata, and artifact result serialization.

- `backend/domains/ai_reports/narrative_brief.py`
  - Deterministic story-material builder that converts report context into companionship, second thread, discovery, life rhythm, tensions, and safe speculation rules.

- `backend/domains/ai_reports/visual_brief.py`
  - Deterministic visual-planning builder that selects chart specs from available evidence and chart-data coverage.

- `backend/domains/ai_reports/visual_chart_data.py`
  - Read-only chart-data builder for listening calendar, artist monthly trend, album duality, highlight day timeline, genre mix, discovery timeline, and playback/Billboard matrix.

- `backend/domains/ai_reports/visual_yearly_prompts.py`
  - Prompt text for artifact prose composition and repair, focused on personal music-year writing rather than business analysis.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Critic for artifact completeness, chart refs, business-report terms, internal terminology leakage, story obligations, and prose length.

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Orchestrates narrative brief, visual brief, chart data, prose sections, deterministic fallback, critic, fact validation, and result metadata.

- `backend/tests/unit/test_visual_yearly_artifact_models.py`
- `backend/tests/unit/test_narrative_brief.py`
- `backend/tests/unit/test_visual_brief.py`
- `backend/tests/unit/test_visual_chart_data.py`
- `backend/tests/unit/test_visual_yearly_critic.py`
- `backend/tests/unit/test_visual_yearly_artifact_service.py`
- `backend/tests/contract/test_visual_yearly_report_contract.py`

- `scripts/probe_visual_yearly_report_artifact.py`
  - Forces a visual yearly report through the real task API and validates artifact shape, chart refs, forbidden terms, critic, fact validation, and key 2025/2026 golden signals.

### Backend Modify

- `backend/models/ai_tasks.py`
  - Extend `ReportTaskRequest.report_mode` to include `visual_yearly_artifact`; default yearly UI should eventually send this mode explicitly.

- `backend/api/ai_insights.py`
  - Allow direct forced `/api/ai-insights/yearly-story` calls with `report_mode=visual_yearly_artifact` to return artifact metadata for debugging and probes.

- `backend/services/ai_task_service.py`
  - Route yearly `visual_yearly_artifact` tasks to the new service.
  - Persist artifact evidence/tool calls using the existing repository.
  - Add stage progress mapping for narrative/visual/chart/artifact review stages.

- `backend/services/yearly_report_agent_service.py`
  - Keep `agentic_longform` unchanged.
  - Expose reusable research-plan helpers or context construction only when the visual service needs them.
  - Do not move visual artifact code into this file.

### Frontend Create

- `frontend/src/features/ai-insights/yearly-artifact/yearlyArtifactTypes.ts`
- `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlyHero.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlySection.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlyInsightCards.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/ListeningCalendarChart.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/ArtistMonthlyTrendChart.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/AlbumDualityCompare.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/HighlightDayTimeline.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/GenreLanguageMixChart.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/DiscoveryTimeline.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/PlaybackBillboardMatrix.tsx`
- `frontend/src/tests/visual-yearly-report.test.tsx`

### Frontend Modify

- `frontend/src/features/ai-insights/AiReportsPanel.tsx`
  - Parse `artifact` from task result.
  - Send `report_mode: "visual_yearly_artifact"` for yearly cache/generate payloads.

- `frontend/src/features/ai-insights/ReportCard.tsx`
  - Render `VisualYearlyReport` when a valid artifact exists.
  - Keep Markdown fallback for old reports and non-yearly reports.

- `frontend/src/features/ai-tasks/AITaskProgress.tsx`
  - Add readable stage labels for narrative, visual, chart data, artifact composition, and artifact review.

- `frontend/src/hooks/useAiTasks.ts`
  - Extend `ReportTaskRequest.report_mode` union.

### Docs Modify

- `docs/README.md`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `CLAUDE.md`
- `backend/CLAUDE.md`
- `README.md`

## Acceptance Criteria

- 2025 generated yearly result has `metadata.report_mode == "visual_yearly_artifact"` and `metadata.contract_version == "visual_yearly_v1"`.
- 2025 artifact contains at least 6 sections, 4 chart specs, 4 resolved chart data entries, and 3 insight cards.
- 2025 artifact prose length is at least 2800 Chinese characters.
- 2025 artifact includes Taylor Swift, Michael Wong, JOLIN, The Life of a Showgirl, 光良「回憶裡的瘋狂」巡迴演唱會, and 2025-02-14.
- 2025 artifact explains the difference between playback-leading album and personal-chart-leading album.
- Final user prose does not contain forbidden internal/business terms: `稳定中心`, `三榜联动`, `第二层证据`, `evidence ledger`, `dynamic outline`, `综合来看`, `后续观察`.
- 2026 artifact is explicitly partial-year and includes `截至 2026-06-23`.
- Chart data is generated by backend code, not by LLM.
- Visual critic and yearly fact validator both pass for normal 2025/2026 data.
- Frontend renders the artifact instead of plain Markdown and shows at least four chart blocks.
- 390px mobile viewport has no horizontal overflow and browser console has no errors or warnings.

---

## Task 1: Add Visual Artifact Models

**Files:**
- Create: `backend/domains/ai_reports/visual_artifact_models.py`
- Create: `backend/tests/unit/test_visual_yearly_artifact_models.py`

- [ ] **Step 1: Write serialization and ref-integrity tests**

Create `backend/tests/unit/test_visual_yearly_artifact_models.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.visual_artifact_models import (
    VISUAL_YEARLY_CONTRACT_VERSION,
    VISUAL_YEARLY_REPORT_MODE,
    VisualYearlyArtifact,
    YearlyArtifactMetadata,
    YearlyArtifactSection,
    YearlyChartSpec,
    YearlyInsightCard,
)

pytestmark = pytest.mark.unit


def test_visual_yearly_artifact_serializes_stable_shape():
    artifact = VisualYearlyArtifact(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        title="你的 2025 音乐年记",
        subtitle="几乎没有离开音乐的一年",
        period={
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        narrative_brief={"main_story": "稳定陪伴与华语情绪线并行的一年。"},
        visual_brief={"required_chart_ids": ["listening_calendar"]},
        sections=(
            YearlyArtifactSection(
                id="opening",
                role="opening",
                heading="几乎没有离开音乐的一年",
                deck="364 个活跃日说明音乐几乎每天都在场。",
                prose="这一年，音乐几乎没有从你的日常里退场。",
                chart_refs=("listening_calendar",),
                insight_refs=("activity_density",),
                evidence_refs=("yearly_overview",),
                pull_quote="音乐不是偶尔打开的背景。",
            ),
        ),
        insight_cards=(
            YearlyInsightCard(
                id="activity_density",
                label="全年陪伴密度",
                value="364 天",
                caption="这一年几乎每天都有音乐在场。",
                tone="warm",
                evidence_refs=("yearly_overview",),
            ),
        ),
        chart_specs=(
            YearlyChartSpec(
                id="listening_calendar",
                chart_type="listening_calendar_heatmap",
                title="音乐铺满这一年",
                narrative_question="音乐是否几乎每天都在场？",
                entities=(),
                data_key="listening_calendar",
                insight="364 个活跃日让音乐成为全年背景。",
                fallback="数据不足时展示活跃日数字卡。",
            ),
        ),
        chart_data={"listening_calendar": {"days": [], "active_days": 364}},
        metadata=YearlyArtifactMetadata(
            report_mode=VISUAL_YEARLY_REPORT_MODE,
            contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
            fallback_level=None,
            section_count=1,
            chart_count=1,
            insight_card_count=1,
            article_length=23,
            critic_passed=True,
            fact_validation_passed=True,
        ),
    )

    payload = artifact.to_dict()

    assert payload["report_mode"] == "visual_yearly_artifact"
    assert payload["contract_version"] == "visual_yearly_v1"
    assert payload["sections"][0]["chart_refs"] == ["listening_calendar"]
    assert payload["metadata"]["section_count"] == 1
    assert payload["chart_data"]["listening_calendar"]["active_days"] == 364


def test_visual_artifact_reports_missing_chart_refs():
    artifact = VisualYearlyArtifact(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        title="你的 2025 音乐年记",
        subtitle="测试",
        period={"year": 2025},
        narrative_brief={},
        visual_brief={},
        sections=(
            YearlyArtifactSection(
                id="opening",
                role="opening",
                heading="开场",
                deck="",
                prose="文字",
                chart_refs=("missing_chart",),
                insight_refs=(),
                evidence_refs=(),
                pull_quote=None,
            ),
        ),
        insight_cards=(),
        chart_specs=(),
        chart_data={},
        metadata=YearlyArtifactMetadata(
            report_mode=VISUAL_YEARLY_REPORT_MODE,
            contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
            fallback_level=None,
            section_count=1,
            chart_count=0,
            insight_card_count=0,
            article_length=2,
            critic_passed=False,
            fact_validation_passed=False,
        ),
    )

    assert artifact.missing_chart_refs() == ["missing_chart"]
```

- [ ] **Step 2: Run the failing model tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_models.py -q
```

Expected: fail with `ModuleNotFoundError: backend.domains.ai_reports.visual_artifact_models`.

- [ ] **Step 3: Implement visual artifact models**

Create `backend/domains/ai_reports/visual_artifact_models.py`:

```python
"""Structured models for visual yearly report artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VISUAL_YEARLY_CONTRACT_VERSION = "visual_yearly_v1"
VISUAL_YEARLY_REPORT_MODE = "visual_yearly_artifact"


def _list(value: tuple[str, ...]) -> list[str]:
    return list(value)


@dataclass(frozen=True)
class YearlyArtifactSection:
    id: str
    role: str
    heading: str
    deck: str
    prose: str
    chart_refs: tuple[str, ...] = ()
    insight_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    pull_quote: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "heading": self.heading,
            "deck": self.deck,
            "prose": self.prose,
            "chart_refs": _list(self.chart_refs),
            "insight_refs": _list(self.insight_refs),
            "evidence_refs": _list(self.evidence_refs),
            "pull_quote": self.pull_quote,
        }


@dataclass(frozen=True)
class YearlyInsightCard:
    id: str
    label: str
    value: str
    caption: str
    tone: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "caption": self.caption,
            "tone": self.tone,
            "evidence_refs": _list(self.evidence_refs),
        }


@dataclass(frozen=True)
class YearlyChartSpec:
    id: str
    chart_type: str
    title: str
    narrative_question: str
    entities: tuple[str, ...]
    data_key: str
    insight: str
    fallback: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chart_type": self.chart_type,
            "title": self.title,
            "narrative_question": self.narrative_question,
            "entities": _list(self.entities),
            "data_key": self.data_key,
            "insight": self.insight,
            "fallback": self.fallback,
        }


@dataclass(frozen=True)
class YearlyArtifactMetadata:
    report_mode: str
    contract_version: str
    fallback_level: str | None
    section_count: int
    chart_count: int
    insight_card_count: int
    article_length: int
    critic_passed: bool
    fact_validation_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_mode": self.report_mode,
            "contract_version": self.contract_version,
            "fallback_level": self.fallback_level,
            "section_count": self.section_count,
            "chart_count": self.chart_count,
            "insight_card_count": self.insight_card_count,
            "article_length": self.article_length,
            "critic_passed": self.critic_passed,
            "fact_validation_passed": self.fact_validation_passed,
        }


@dataclass(frozen=True)
class VisualYearlyArtifact:
    report_mode: str
    contract_version: str
    title: str
    subtitle: str
    period: dict[str, Any]
    narrative_brief: dict[str, Any]
    visual_brief: dict[str, Any]
    sections: tuple[YearlyArtifactSection, ...]
    insight_cards: tuple[YearlyInsightCard, ...]
    chart_specs: tuple[YearlyChartSpec, ...]
    chart_data: dict[str, Any]
    metadata: YearlyArtifactMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_mode": self.report_mode,
            "contract_version": self.contract_version,
            "title": self.title,
            "subtitle": self.subtitle,
            "period": self.period,
            "narrative_brief": self.narrative_brief,
            "visual_brief": self.visual_brief,
            "sections": [section.to_dict() for section in self.sections],
            "insight_cards": [card.to_dict() for card in self.insight_cards],
            "chart_specs": [spec.to_dict() for spec in self.chart_specs],
            "chart_data": self.chart_data,
            "metadata": self.metadata.to_dict(),
        }

    def missing_chart_refs(self) -> list[str]:
        available = {spec.id for spec in self.chart_specs} & set(self.chart_data)
        refs = {
            ref
            for section in self.sections
            for ref in section.chart_refs
        }
        return sorted(ref for ref in refs if ref not in available)
```

- [ ] **Step 4: Run model tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_models.py -q
```

Expected: pass.

- [ ] **Step 5: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports/visual_artifact_models.py backend/tests/unit/test_visual_yearly_artifact_models.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/domains/ai_reports/visual_artifact_models.py backend/tests/unit/test_visual_yearly_artifact_models.py
git commit -m "feat: add visual yearly artifact models"
```

## Task 2: Build Narrative Brief

**Files:**
- Create: `backend/domains/ai_reports/narrative_brief.py`
- Create: `backend/tests/unit/test_narrative_brief.py`

- [ ] **Step 1: Write 2025 narrative brief tests**

Create `backend/tests/unit/test_narrative_brief.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.narrative_brief import build_narrative_brief

pytestmark = pytest.mark.unit


def _context_2025() -> dict:
    return {
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        "hero": {
            "total_plays": 17567,
            "total_minutes": 68100,
            "active_days": 364,
            "unique_tracks": 2758,
            "unique_artists": 445,
        },
        "top_artists": [
            {"name": "Taylor Swift", "plays": 2629},
            {"name": "Michael Wong", "plays": 2087},
        ],
        "top_tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "plays": 190}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "weeks_on_chart": 32,
                    "rank": 1,
                }
            ],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 50}],
        },
        "genre_distribution": {
            "top_genres": [
                {"name": "mandopop", "share": 16.7},
                {"name": "c-pop", "share": 16.6},
            ],
            "caveat": "Spotify 流派标签可能重叠，百分比不互斥。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}],
        },
        "highlight_day_detail": {
            "date": "2025-02-14",
            "plays": 154,
            "top_track": {"name": "15 Minutes", "artist": "Sabrina Carpenter", "plays": 9},
            "interpretation_guidance": "多曲目活跃日",
        },
    }


def test_narrative_brief_extracts_story_threads_for_2025():
    brief = build_narrative_brief(_context_2025())

    assert "几乎" in brief["opening_scene"]
    assert brief["companionship_thread"]["entity"] == "Taylor Swift"
    assert "反复回到" in brief["companionship_thread"]["interpretation"]
    assert brief["second_thread"]["entity"] == "Michael Wong"
    assert "华语" in brief["second_thread"]["interpretation"]
    assert brief["discovery_thread"]["entity"] == "JOLIN"
    assert brief["discovery_thread"]["confidence"] in {"medium", "low"}
    assert brief["life_rhythm"]["active_days"] == 364
    assert brief["tensions"][0]["playback_leader"] == "The Life of a Showgirl"
    assert brief["tensions"][0]["chart_leader"] == "光良「回憶裡的瘋狂」巡迴演唱會"


def test_narrative_brief_uses_partial_year_language_for_2026():
    context = _context_2025()
    context["reporting_period"] = {
        "year": 2026,
        "start_date": "2026-01-01",
        "end_date": "2026-06-23",
        "is_partial_year": True,
    }

    brief = build_narrative_brief(context)

    assert "截至 2026-06-23" in brief["main_story"]
    assert "全年定论" not in brief["main_story"]
    assert "下阶段" in brief["closing_direction"]
```

- [ ] **Step 2: Run failing narrative tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_narrative_brief.py -q
```

Expected: fail with missing module.

- [ ] **Step 3: Implement deterministic narrative brief**

Create `backend/domains/ai_reports/narrative_brief.py` with these public functions:

```python
"""Narrative brief construction for visual yearly reports."""

from __future__ import annotations

from typing import Any


def build_narrative_brief(context: dict[str, Any]) -> dict[str, Any]:
    period = _dict(context.get("reporting_period"))
    year = period.get("year") or str(period.get("start_date") or "")[:4]
    end_date = str(period.get("end_date") or "")
    is_partial = bool(period.get("is_partial_year"))
    hero = _dict(context.get("hero"))
    top_artists = _list(context.get("top_artists"))
    top_albums = _list(context.get("top_albums"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    discovery = _dict(context.get("discovery_and_returns"))
    genres = _dict(context.get("genre_distribution"))
    highlight = _dict(context.get("highlight_day_detail"))

    lead_artist = _name(top_artists, 0)
    second_artist = _name(top_artists, 1)
    new_artist = _name(_list(discovery.get("new_artists")), 0)
    playback_album = _name(top_albums, 0)
    chart_album = _name(_list(billboard.get("albums")), 0)

    main_story = (
        f"截至 {end_date}，{year} 是一段仍在展开的音乐记录。"
        if is_partial
        else f"{year} 是音乐几乎全年在场的一年。"
    )

    return {
        "main_story": main_story,
        "opening_scene": _opening_scene(hero, is_partial, end_date),
        "companionship_thread": {
            "entity": lead_artist,
            "interpretation": f"{lead_artist} 更像你这一年反复回到的声音。",
            "evidence_refs": ["top_artist_1", "personal_chart_artist_1"],
        },
        "second_thread": {
            "entity": second_artist,
            "interpretation": f"{second_artist} 提供了另一条更偏华语、记忆感或现场感的情绪线。",
            "evidence_refs": ["top_artist_2", "genre_mix"],
        },
        "discovery_thread": {
            "entity": new_artist,
            "interpretation": f"{new_artist} 是新出现并留下痕迹的入口。" if new_artist else "",
            "confidence": _discovery_confidence(_list(discovery.get("new_artists"))),
            "evidence_refs": ["new_artist_1"],
        },
        "life_rhythm": {
            "active_days": int(hero.get("active_days") or 0),
            "total_hours": round(float(hero.get("total_minutes") or 0) / 60, 1),
            "interpretation": _life_rhythm(hero, is_partial),
            "tone": "companionate",
        },
        "tensions": _album_tensions(playback_album, chart_album, top_albums, billboard),
        "genre_identity": _genre_identity(genres),
        "highlight_day": {
            "date": highlight.get("date"),
            "interpretation": highlight.get("interpretation_guidance") or "这一天更适合被看作一个音乐密度很高的片段。",
        },
        "closing_direction": "下阶段继续观察哪些声音会留下来。" if is_partial else "这一年最终留下的是陪伴、回望和新入口并存的画像。",
        "safe_speculation_rules": [
            "可以写陪伴、回到、节奏、出口、背景声。",
            "不能编造天气、失眠、分手、考试、旅行等具体事件。",
            "生活推断必须使用像是、更像、也许、这更接近于等克制语气。",
        ],
    }


def _opening_scene(hero: dict[str, Any], is_partial: bool, end_date: str) -> str:
    active_days = int(hero.get("active_days") or 0)
    if is_partial:
        return f"截至 {end_date}，你已经有 {active_days} 个活跃听歌日。"
    return f"{active_days} 个活跃日说明音乐几乎每天都在场。"


def _life_rhythm(hero: dict[str, Any], is_partial: bool) -> str:
    active_days = int(hero.get("active_days") or 0)
    if is_partial:
        return "音乐正在构成这一阶段的日常背景。"
    if active_days >= 330:
        return "音乐几乎贯穿全年生活，不像偶尔打开的娱乐，更像日常节奏的一部分。"
    return "音乐在这一年反复出现，但不是每天都占据中心。"


def _album_tensions(
    playback_album: str,
    chart_album: str,
    top_albums: list[dict[str, Any]],
    billboard: dict[str, Any],
) -> list[dict[str, Any]]:
    if not playback_album or not chart_album or playback_album == chart_album:
        return []
    return [
        {
            "title": "最常播放和最稳定在榜的专辑不是同一张",
            "playback_leader": playback_album,
            "chart_leader": chart_album,
            "interpretation": "这说明重复聆听和持续在场衡量的是两种不同偏爱。",
            "evidence_refs": ["top_album_1", "personal_chart_album_1"],
        }
    ]


def _genre_identity(genres: dict[str, Any]) -> dict[str, Any]:
    top = _list(genres.get("top_genres"))
    names = [str(row.get("name")) for row in top[:3] if isinstance(row, dict) and row.get("name")]
    return {
        "top_genres": names,
        "interpretation": "你的音乐地理不只停在单一流行语境里。" if names else "",
        "caveat": genres.get("caveat") or "Spotify 流派标签可能重叠，百分比不互斥。",
    }


def _discovery_confidence(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "low"
    plays = int(rows[0].get("plays") or 0)
    if plays >= 300:
        return "high"
    if plays >= 80:
        return "medium"
    return "low"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _name(rows: list[dict[str, Any]], index: int) -> str:
    if index >= len(rows):
        return ""
    return str(rows[index].get("name") or "")
```

- [ ] **Step 4: Run narrative tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_narrative_brief.py -q
```

Expected: pass.

- [ ] **Step 5: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports/narrative_brief.py backend/tests/unit/test_narrative_brief.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/domains/ai_reports/narrative_brief.py backend/tests/unit/test_narrative_brief.py
git commit -m "feat: add visual yearly narrative brief"
```

## Task 3: Build Visual Brief And Chart Specs

**Files:**
- Create: `backend/domains/ai_reports/visual_brief.py`
- Create: `backend/tests/unit/test_visual_brief.py`

- [ ] **Step 1: Write visual brief tests**

Create `backend/tests/unit/test_visual_brief.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.visual_brief import build_visual_brief

pytestmark = pytest.mark.unit


def test_visual_brief_selects_required_charts_for_complete_year():
    narrative = {
        "companionship_thread": {"entity": "Taylor Swift"},
        "second_thread": {"entity": "Michael Wong"},
        "discovery_thread": {"entity": "JOLIN", "confidence": "medium"},
        "tensions": [{"playback_leader": "The Life of a Showgirl", "chart_leader": "光良「回憶裡的瘋狂」巡迴演唱會"}],
        "life_rhythm": {"active_days": 364},
    }
    coverage = {
        "listening_calendar": True,
        "artist_monthly_trend": True,
        "album_duality_compare": True,
        "highlight_day_timeline": True,
        "genre_language_mix": True,
        "discovery_timeline": True,
        "playback_billboard_matrix": True,
    }

    brief = build_visual_brief(narrative, coverage)

    assert len(brief["chart_specs"]) >= 4
    ids = {chart["id"] for chart in brief["chart_specs"]}
    assert "listening_calendar" in ids
    assert "artist_monthly_trend" in ids
    assert "album_duality_compare" in ids
    assert "highlight_day_timeline" in ids
    assert brief["chart_specs"][1]["entities"] == ["Taylor Swift", "Michael Wong"]


def test_visual_brief_skips_unavailable_charts_and_records_reduced_visuals():
    narrative = {
        "companionship_thread": {"entity": "Taylor Swift"},
        "second_thread": {"entity": ""},
        "discovery_thread": {"entity": "", "confidence": "low"},
        "tensions": [],
        "life_rhythm": {"active_days": 12},
    }
    coverage = {
        "listening_calendar": True,
        "artist_monthly_trend": False,
        "album_duality_compare": False,
        "highlight_day_timeline": False,
        "genre_language_mix": False,
        "discovery_timeline": False,
        "playback_billboard_matrix": False,
    }

    brief = build_visual_brief(narrative, coverage)

    assert brief["fallback_level"] == "reduced_visuals"
    assert [chart["id"] for chart in brief["chart_specs"]] == ["listening_calendar"]
```

- [ ] **Step 2: Run failing visual brief tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_brief.py -q
```

Expected: missing module failure.

- [ ] **Step 3: Implement visual brief builder**

Create `backend/domains/ai_reports/visual_brief.py`:

```python
"""Visual chart planning for visual yearly report artifacts."""

from __future__ import annotations

from typing import Any


def build_visual_brief(
    narrative_brief: dict[str, Any],
    coverage: dict[str, bool],
) -> dict[str, Any]:
    lead = _thread_entity(narrative_brief, "companionship_thread")
    second = _thread_entity(narrative_brief, "second_thread")
    discovery = _thread_entity(narrative_brief, "discovery_thread")
    entities = tuple(entity for entity in (lead, second) if entity)
    specs = []

    def add(chart_id: str, chart_type: str, title: str, question: str, chart_entities: tuple[str, ...], insight: str, fallback: str) -> None:
        if coverage.get(chart_id):
            specs.append(
                {
                    "id": chart_id,
                    "chart_type": chart_type,
                    "title": title,
                    "narrative_question": question,
                    "entities": list(chart_entities),
                    "data_key": chart_id,
                    "insight": insight,
                    "fallback": fallback,
                }
            )

    add(
        "listening_calendar",
        "listening_calendar_heatmap",
        "音乐铺满这一年",
        "音乐是否几乎每天都在场？",
        (),
        "用每日播放强度展示全年陪伴密度。",
        "数据不足时展示活跃日数字卡。",
    )
    add(
        "artist_monthly_trend",
        "artist_monthly_trend",
        f"{lead} 与 {second} 的年度声音线索" if second else f"{lead} 的年度声音线索",
        "核心声音是否贯穿全年？",
        entities,
        "展示稳定陪伴与第二情绪线的月度变化。",
        "月度数据不足时展示艺人年度对照卡。",
    )
    add(
        "album_duality_compare",
        "album_duality_compare",
        "常听与持续在榜的两种偏爱",
        "播放量和个人榜单讲的是同一种喜欢吗？",
        (),
        "解释播放领先专辑和个人榜单领先专辑的差异。",
        "缺少个人榜单时隐藏该图表。",
    )
    add(
        "highlight_day_timeline",
        "highlight_day_timeline",
        "年度高光日拆解",
        "最密集的一天是循环还是漫游？",
        (),
        "把最高播放日拆成小时节奏和曲目集中度。",
        "缺少小时数据时展示高光日摘要。",
    )
    add(
        "genre_language_mix",
        "genre_language_mix",
        "你的音乐地理",
        "今年的声音来自哪些语境？",
        (),
        "把流派标签翻译成音乐地理。",
        "缺少流派时隐藏该图表。",
    )
    add(
        "discovery_timeline",
        "discovery_timeline",
        f"{discovery} 出现以后" if discovery else "新发现时间线",
        "新声音是路过还是留下？",
        (discovery,) if discovery else (),
        "展示新艺人的首次出现和后续播放。",
        "缺少新艺人时隐藏该图表。",
    )
    add(
        "playback_billboard_matrix",
        "playback_billboard_matrix",
        "常听与长留",
        "哪些作品既常听又稳定？",
        (),
        "展示播放量强度和个人榜单稳定性的关系。",
        "缺少个人榜单时隐藏该图表。",
    )

    return {
        "visual_thesis": "这份年报用陪伴密度、核心声音、专辑差异、高光日和新发现来呈现。",
        "chart_specs": specs,
        "required_chart_ids": [chart["id"] for chart in specs[:4]],
        "optional_chart_ids": [chart["id"] for chart in specs[4:]],
        "fallback_level": None if len(specs) >= 4 else "reduced_visuals",
        "chart_order_reasoning": [
            "先展示音乐如何铺满一年。",
            "再展示核心声音的时间变化。",
            "再解释常听和持续在榜的差异。",
            "最后用高光日、流派和新发现增加记忆点。",
        ],
    }


def _thread_entity(narrative_brief: dict[str, Any], key: str) -> str:
    thread = narrative_brief.get(key)
    return str(thread.get("entity") or "") if isinstance(thread, dict) else ""
```

- [ ] **Step 4: Run visual brief tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_brief.py -q
```

Expected: pass.

- [ ] **Step 5: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports/visual_brief.py backend/tests/unit/test_visual_brief.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/domains/ai_reports/visual_brief.py backend/tests/unit/test_visual_brief.py
git commit -m "feat: add visual yearly chart planning"
```

## Task 4: Build Deterministic Chart Data

**Files:**
- Create: `backend/domains/ai_reports/visual_chart_data.py`
- Create: `backend/tests/unit/test_visual_chart_data.py`

- [ ] **Step 1: Write chart data tests with compact context**

Create `backend/tests/unit/test_visual_chart_data.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.ai_reports.visual_chart_data import build_visual_chart_data

pytestmark = pytest.mark.unit


def _plays() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ts_date": "2025-01-01", "hour": 9, "track_name": "Song A", "artist_name": "Taylor Swift", "album_name": "The Life of a Showgirl", "ms_played": 180000},
            {"ts_date": "2025-01-01", "hour": 10, "track_name": "Song B", "artist_name": "Michael Wong", "album_name": "光良「回憶裡的瘋狂」巡迴演唱會", "ms_played": 200000},
            {"ts_date": "2025-02-14", "hour": 21, "track_name": "15 Minutes", "artist_name": "Sabrina Carpenter", "album_name": "Single", "ms_played": 190000},
            {"ts_date": "2025-02-14", "hour": 22, "track_name": "15 Minutes", "artist_name": "Sabrina Carpenter", "album_name": "Single", "ms_played": 190000},
        ]
    )


def test_visual_chart_data_builds_required_shapes():
    context = {
        "reporting_period": {"year": 2025, "start_date": "2025-01-01", "end_date": "2025-12-31", "is_partial_year": False},
        "top_artists": [{"name": "Taylor Swift"}, {"name": "Michael Wong"}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [{"name": "光良「回憶裡的瘋狂」巡迴演唱會", "artist": "Michael Wong", "weeks_on_chart": 32, "rank": 1}],
            "tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "plays": 190, "weeks_on_chart": 13, "peak": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 16.7}]},
        "discovery_and_returns": {"new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}]},
        "highlight_day_detail": {"date": "2025-02-14", "plays": 154},
    }
    chart_specs = [
        {"id": "listening_calendar", "chart_type": "listening_calendar_heatmap"},
        {"id": "artist_monthly_trend", "chart_type": "artist_monthly_trend", "entities": ["Taylor Swift", "Michael Wong"]},
        {"id": "album_duality_compare", "chart_type": "album_duality_compare"},
        {"id": "highlight_day_timeline", "chart_type": "highlight_day_timeline"},
        {"id": "genre_language_mix", "chart_type": "genre_language_mix"},
        {"id": "discovery_timeline", "chart_type": "discovery_timeline"},
        {"id": "playback_billboard_matrix", "chart_type": "playback_billboard_matrix"},
    ]

    chart_data = build_visual_chart_data(context, chart_specs, plays_df=_plays())

    assert chart_data["listening_calendar"]["active_days"] == 2
    assert chart_data["artist_monthly_trend"]["entities"] == ["Taylor Swift", "Michael Wong"]
    assert chart_data["album_duality_compare"]["playback_leader"]["name"] == "The Life of a Showgirl"
    assert chart_data["album_duality_compare"]["chart_leader"]["name"] == "光良「回憶裡的瘋狂」巡迴演唱會"
    assert chart_data["highlight_day_timeline"]["date"] == "2025-02-14"
    assert chart_data["genre_language_mix"]["genres"][0]["name"] == "mandopop"
    assert chart_data["discovery_timeline"]["new_artists"][0]["name"] == "JOLIN"
    assert chart_data["playback_billboard_matrix"]["items"][0]["name"] == "The Fate of Ophelia"
```

- [ ] **Step 2: Run failing chart data tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_chart_data.py -q
```

Expected: missing module failure.

- [ ] **Step 3: Implement chart data builder**

Create `backend/domains/ai_reports/visual_chart_data.py` with:

```python
"""Deterministic chart data builders for visual yearly reports."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.core.db import get_db
from backend.services.ai_insights_service import _load_yearly_report_plays_frame


def build_visual_chart_data(
    context: dict[str, Any],
    chart_specs: list[dict[str, Any]],
    *,
    plays_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    df = plays_df if plays_df is not None else _load_plays_for_context(context)
    builders = {
        "listening_calendar_heatmap": _calendar_data,
        "artist_monthly_trend": _artist_monthly_trend,
        "album_duality_compare": _album_duality_compare,
        "highlight_day_timeline": _highlight_day_timeline,
        "genre_language_mix": _genre_language_mix,
        "discovery_timeline": _discovery_timeline,
        "playback_billboard_matrix": _playback_billboard_matrix,
    }
    result: dict[str, Any] = {}
    for spec in chart_specs:
        chart_type = str(spec.get("chart_type") or "")
        builder = builders.get(chart_type)
        if builder is None:
            continue
        data = builder(context, spec, df)
        if data:
            result[str(spec["id"])] = data
    return result


def chart_coverage(context: dict[str, Any], *, plays_df: pd.DataFrame | None = None) -> dict[str, bool]:
    df = plays_df if plays_df is not None else _load_plays_for_context(context)
    billboard = _dict(context.get("personal_billboard_year_end"))
    discovery = _dict(context.get("discovery_and_returns"))
    genre = _dict(context.get("genre_distribution"))
    highlight = _dict(context.get("highlight_day_detail"))
    return {
        "listening_calendar": not df.empty and "ts_date" in df.columns,
        "artist_monthly_trend": not df.empty and {"ts_date", "artist_name"}.issubset(df.columns),
        "album_duality_compare": bool(context.get("top_albums")) and bool(billboard.get("albums")),
        "highlight_day_timeline": bool(highlight.get("date")) and not df.empty,
        "genre_language_mix": bool(genre.get("top_genres")),
        "discovery_timeline": bool(discovery.get("new_artists")),
        "playback_billboard_matrix": bool(billboard.get("tracks") or billboard.get("albums") or billboard.get("artists")),
    }


def _load_plays_for_context(context: dict[str, Any]) -> pd.DataFrame:
    period = _dict(context.get("reporting_period"))
    year = int(period.get("year") or str(period.get("start_date") or "0")[:4] or 0)
    conn = get_db(readonly=True)
    try:
        return _load_yearly_report_plays_frame(conn, year=year)
    finally:
        conn.close()
```

Continue the file with deterministic builder helpers:

```python
def _calendar_data(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del context, spec
    if df.empty or "ts_date" not in df.columns:
        return {}
    grouped = df.groupby("ts_date", dropna=False).agg(plays=("ts_date", "size"), minutes=("ms_played", lambda s: round(float(s.sum()) / 60000, 1))).reset_index()
    days = [{"date": str(row.ts_date), "plays": int(row.plays), "minutes": float(row.minutes)} for row in grouped.itertuples()]
    max_day = max(days, key=lambda row: row["plays"]) if days else None
    return {"days": days, "active_days": len(days), "max_day": max_day}


def _artist_monthly_trend(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del context
    entities = [str(name) for name in spec.get("entities") or [] if name]
    if df.empty or not entities or "artist_name" not in df.columns or "ts_date" not in df.columns:
        return {}
    work = df[df["artist_name"].isin(entities)].copy()
    if work.empty:
        return {}
    work["month"] = work["ts_date"].astype(str).str.slice(0, 7)
    rows = []
    for month, group in work.groupby("month"):
        row = {"month": str(month)}
        counts = group.groupby("artist_name").size()
        for entity in entities:
            row[entity] = int(counts.get(entity, 0))
        rows.append(row)
    return {"entities": entities, "months": rows}


def _album_duality_compare(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del spec, df
    top_albums = _list(context.get("top_albums"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    chart_albums = _list(billboard.get("albums"))
    if not top_albums or not chart_albums:
        return {}
    return {
        "playback_leader": top_albums[0],
        "chart_leader": chart_albums[0],
        "interpretation": "播放量和持续在榜衡量的是两种不同偏爱。",
    }


def _highlight_day_timeline(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del spec
    highlight = _dict(context.get("highlight_day_detail"))
    date = str(highlight.get("date") or "")
    if not date or df.empty or "ts_date" not in df.columns:
        return {}
    day = df[df["ts_date"].astype(str) == date]
    hourly = []
    if "hour" in day.columns:
        hourly = [{"hour": int(hour), "plays": int(count)} for hour, count in day.groupby("hour").size().items()]
    top_tracks = []
    if {"track_name", "artist_name"}.issubset(day.columns):
        for (track, artist), count in day.groupby(["track_name", "artist_name"]).size().sort_values(ascending=False).head(5).items():
            top_tracks.append({"name": str(track), "artist": str(artist), "plays": int(count)})
    max_repeats = max((row["plays"] for row in top_tracks), default=0)
    concentration = "high" if max_repeats >= max(8, len(day) * 0.2) else "low"
    return {"date": date, "total_plays": int(len(day) or highlight.get("plays") or 0), "hourly": hourly, "top_tracks": top_tracks, "repeat_concentration": concentration}


def _genre_language_mix(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del spec, df
    genre = _dict(context.get("genre_distribution"))
    return {"genres": _list(genre.get("top_genres")), "caveat": genre.get("caveat") or "Spotify 流派标签可能重叠，百分比不互斥。"}


def _discovery_timeline(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del spec, df
    discovery = _dict(context.get("discovery_and_returns"))
    return {"new_artists": _list(discovery.get("new_artists"))}


def _playback_billboard_matrix(context: dict[str, Any], spec: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    del spec, df
    billboard = _dict(context.get("personal_billboard_year_end"))
    rows = _list(billboard.get("tracks")) + _list(billboard.get("albums")) + _list(billboard.get("artists"))
    items = [
        {
            "name": row.get("name"),
            "type": row.get("type") or "unknown",
            "plays": row.get("plays") or row.get("chart_plays"),
            "weeks_on_chart": row.get("weeks_on_chart"),
            "peak": row.get("peak"),
            "rank": row.get("rank"),
        }
        for row in rows[:12]
        if row.get("name")
    ]
    return {"items": items}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]
```

- [ ] **Step 4: Run chart data tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_chart_data.py -q
```

Expected: pass.

- [ ] **Step 5: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports/visual_chart_data.py backend/tests/unit/test_visual_chart_data.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/domains/ai_reports/visual_chart_data.py backend/tests/unit/test_visual_chart_data.py
git commit -m "feat: add visual yearly chart data"
```

## Task 5: Add Visual Yearly Critic

**Files:**
- Create: `backend/domains/ai_reports/visual_yearly_critic.py`
- Create: `backend/tests/unit/test_visual_yearly_critic.py`

- [ ] **Step 1: Write critic tests**

Create `backend/tests/unit/test_visual_yearly_critic.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.visual_yearly_critic import critique_visual_yearly_artifact

pytestmark = pytest.mark.unit


def _artifact(prose: str, chart_count: int = 4) -> dict:
    chart_specs = [
        {"id": f"chart_{i}", "chart_type": "listening_calendar_heatmap", "data_key": f"chart_{i}"}
        for i in range(chart_count)
    ]
    return {
        "sections": [
            {
                "id": "opening",
                "heading": "几乎没有离开音乐的一年",
                "prose": prose,
                "chart_refs": ["chart_0"],
            },
            {"id": "companionship", "heading": "反复回到的声音", "prose": prose, "chart_refs": ["chart_1"]},
            {"id": "album_story", "heading": "两种不同的喜欢", "prose": prose, "chart_refs": ["chart_2"]},
            {"id": "discovery", "heading": "新声音留下痕迹", "prose": prose, "chart_refs": ["chart_3"]},
            {"id": "closing", "heading": "这一年留下什么", "prose": prose, "chart_refs": []},
            {"id": "rhythm", "heading": "生活里的节奏", "prose": prose, "chart_refs": []},
        ],
        "chart_specs": chart_specs,
        "chart_data": {f"chart_{i}": {"ok": True} for i in range(chart_count)},
        "insight_cards": [
            {"id": "activity", "caption": "音乐几乎每天都在场。"},
            {"id": "companion", "caption": "Taylor Swift 是反复回到的声音。"},
            {"id": "discovery", "caption": "JOLIN 是新出现的入口。"},
        ],
    }


def test_visual_critic_rejects_business_report_terms():
    artifact = _artifact("Taylor Swift 是稳定中心，形成三榜联动，提供第二层证据。" * 80)

    critique = critique_visual_yearly_artifact(artifact, {"is_partial_year": False})

    codes = {issue["code"] for issue in critique["issues"]}
    assert "business_report_tone" in codes
    assert critique["ok"] is False


def test_visual_critic_rejects_missing_charts():
    artifact = _artifact("Taylor Swift 更像你反复回到的声音。" * 100, chart_count=1)

    critique = critique_visual_yearly_artifact(artifact, {"is_partial_year": False})

    codes = {issue["code"] for issue in critique["issues"]}
    assert "not_enough_charts" in codes


def test_visual_critic_accepts_story_rich_artifact():
    prose = (
        "Taylor Swift 更像你这一年反复回到的声音。"
        "Michael Wong 则把华语记忆和现场感带进来。"
        "这些数字不是冷冰冰的排名，而是在说明音乐如何留在日常节奏里。"
        "JOLIN 的出现更像一个新入口，但还需要时间证明它会不会继续留下。"
        "播放量领先和个人榜单长留并不完全相同，这让两张专辑讲出了两种喜欢。"
    ) * 30
    artifact = _artifact(prose, chart_count=4)

    critique = critique_visual_yearly_artifact(artifact, {"is_partial_year": False})

    assert critique["ok"] is True
    assert critique["issues"] == []
```

- [ ] **Step 2: Run failing critic tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: missing module failure.

- [ ] **Step 3: Implement visual critic**

Create `backend/domains/ai_reports/visual_yearly_critic.py`:

```python
"""Narrative and visual quality critic for visual yearly artifacts."""

from __future__ import annotations

from typing import Any

BUSINESS_REPORT_TERMS = (
    "稳定中心",
    "三榜联动",
    "第二层证据",
    "evidence ledger",
    "dynamic outline",
    "综合来看",
    "后续观察",
)


def critique_visual_yearly_artifact(
    artifact: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    issues: list[dict[str, str]] = []
    prose = _all_prose(artifact)
    sections = _list(artifact.get("sections"))
    chart_specs = _list(artifact.get("chart_specs"))
    insight_cards = _list(artifact.get("insight_cards"))
    chart_data = artifact.get("chart_data") if isinstance(artifact.get("chart_data"), dict) else {}

    min_length = 1800 if context.get("is_partial_year") else 2800
    if len(prose) < min_length:
        issues.append(_issue("too_short", f"正文至少需要 {min_length} 个中文字符，当前为 {len(prose)}。"))
    if len(sections) < 6:
        issues.append(_issue("not_enough_sections", "图文年报至少需要 6 个章节。"))
    if len(chart_specs) < 4:
        issues.append(_issue("not_enough_charts", "图文年报至少需要 4 个图表。"))
    if len(insight_cards) < 3:
        issues.append(_issue("not_enough_insight_cards", "图文年报至少需要 3 个重点卡片。"))

    missing_refs = _missing_chart_refs(sections, chart_specs, chart_data)
    if missing_refs:
        issues.append(_issue("missing_chart_refs", "章节引用了不存在或无数据的图表：" + ", ".join(missing_refs)))

    forbidden = [term for term in BUSINESS_REPORT_TERMS if term in prose]
    if forbidden:
        issues.append(_issue("business_report_tone", "用户正文泄漏商业报告腔或内部术语：" + ", ".join(forbidden)))

    if not _has_story_obligations(prose):
        issues.append(_issue("missing_story_obligations", "正文缺少陪伴、生活节奏、新发现或播放/个人榜单关系分析。"))

    return {
        "ok": not issues,
        "issues": issues,
        "repair_instructions": [_repair_instruction(issue["code"]) for issue in issues],
    }


def _all_prose(artifact: dict[str, Any]) -> str:
    return "\n".join(str(section.get("prose") or "") for section in _list(artifact.get("sections")))


def _missing_chart_refs(
    sections: list[dict[str, Any]],
    chart_specs: list[dict[str, Any]],
    chart_data: dict[str, Any],
) -> list[str]:
    available = {str(spec.get("id")) for spec in chart_specs if spec.get("id")} & set(chart_data)
    refs = {
        str(ref)
        for section in sections
        for ref in section.get("chart_refs") or []
        if ref
    }
    return sorted(ref for ref in refs if ref not in available)


def _has_story_obligations(prose: str) -> bool:
    companionship = any(term in prose for term in ("陪伴", "反复回到", "留在日常", "日常节奏"))
    discovery = any(term in prose for term in ("新入口", "新声音", "新发现", "留下痕迹"))
    chart_relation = any(term in prose for term in ("播放量", "个人榜单", "长留", "持续在榜"))
    return companionship and discovery and chart_relation


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": "error"}


def _repair_instruction(code: str) -> str:
    return {
        "too_short": "扩写章节正文，增加故事解释而不是追加榜单。",
        "not_enough_sections": "补足 opening、year_rhythm、companionship、album_story、discovery、closing 等章节。",
        "not_enough_charts": "至少加入 4 个有真实 chart_data 的图表。",
        "not_enough_insight_cards": "至少加入 3 个重点卡片。",
        "missing_chart_refs": "移除无数据图表引用或补齐对应 chart_data。",
        "business_report_tone": "把商业报告词替换成用户可读的陪伴和音乐年记表达。",
        "missing_story_obligations": "补充陪伴感、生活节奏、新发现和播放/个人榜单关系分析。",
    }[code]


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]
```

- [ ] **Step 4: Run critic tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: pass.

- [ ] **Step 5: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports/visual_yearly_critic.py backend/tests/unit/test_visual_yearly_critic.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/domains/ai_reports/visual_yearly_critic.py backend/tests/unit/test_visual_yearly_critic.py
git commit -m "feat: add visual yearly critic"
```

## Task 6: Compose Visual Yearly Artifact

**Files:**
- Create: `backend/domains/ai_reports/visual_yearly_prompts.py`
- Create: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Create: `backend/tests/unit/test_visual_yearly_artifact_service.py`

- [ ] **Step 1: Write artifact service test with monkeypatched research**

Create `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_models import EvidenceLedgerEntry

pytestmark = pytest.mark.unit


def test_visual_yearly_artifact_service_generates_artifact(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2025,
        "reporting_period": {"year": 2025, "start_date": "2025-01-01", "end_date": "2025-12-31", "is_partial_year": False},
        "hero": {"active_days": 364, "total_minutes": 68100, "total_plays": 17567},
        "top_artists": [{"name": "Taylor Swift", "plays": 2629}, {"name": "Michael Wong", "plays": 2087}],
        "top_tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "plays": 190}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [{"name": "光良「回憶裡的瘋狂」巡迴演唱會", "artist": "Michael Wong", "weeks_on_chart": 32, "rank": 1}],
            "tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "weeks_on_chart": 13, "rank": 1}],
            "artists": [{"name": "Taylor Swift", "weeks_on_chart": 50, "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 16.7}], "caveat": "Spotify 流派标签可能重叠。"},
        "discovery_and_returns": {"new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}]},
        "highlight_day_detail": {"date": "2025-02-14", "plays": 154, "interpretation_guidance": "多曲目活跃日"},
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [EvidenceLedgerEntry(tool_name="yearly_overview", params={"year": 2025}, result_summary="summary")],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2025})

    assert result["success"] is True
    assert result["artifact"]["report_mode"] == "visual_yearly_artifact"
    assert result["metadata"]["contract_version"] == "visual_yearly_v1"
    assert result["metadata"]["section_count"] >= 6
    assert result["metadata"]["chart_count"] >= 4
    assert result["critic"]["ok"] is True
    assert result["fact_validation"]["ok"] is True
    assert "Taylor Swift" in result["report"]
    assert "光良「回憶裡的瘋狂」巡迴演唱會" in result["report"]
```

- [ ] **Step 2: Run failing artifact service test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_service.py -q
```

Expected: missing module failure.

- [ ] **Step 3: Add prompt constants**

Create `backend/domains/ai_reports/visual_yearly_prompts.py`:

```python
"""Prompts for visual yearly report artifact prose."""

VISUAL_YEARLY_ARTIFACT_SYSTEM_PROMPT = """你是个人音乐年记作者，不是商业分析师。

写作目标：
- 把数据翻译成有温度、有陪伴感、可阅读的音乐年记。
- 保留事实边界，不编造具体生活事件。
- 使用“像是”“更像”“也许”等克制推断。
- 不使用内部术语：稳定中心、三榜联动、第二层证据、evidence ledger、dynamic outline。

输出 JSON：
{
  "sections": [
    {
      "id": "opening",
      "role": "opening",
      "heading": "章节标题",
      "deck": "一句章节导语",
      "prose": "面向用户的正文",
      "chart_refs": ["listening_calendar"],
      "insight_refs": ["activity_density"],
      "evidence_refs": ["yearly_overview"],
      "pull_quote": "可选金句"
    }
  ]
}
"""
```

- [ ] **Step 4: Implement deterministic artifact composer first**

Create `backend/domains/ai_reports/visual_yearly_artifact_service.py` with public `generate_visual_yearly_artifact()`. The first implementation should not depend on LLM. Use deterministic sections so tests and probes are stable:

```python
"""Visual yearly report artifact orchestration."""

from __future__ import annotations

from typing import Any

from backend.domains.ai_reports.narrative_brief import build_narrative_brief
from backend.domains.ai_reports.visual_artifact_models import (
    VISUAL_YEARLY_CONTRACT_VERSION,
    VISUAL_YEARLY_REPORT_MODE,
    VisualYearlyArtifact,
    YearlyArtifactMetadata,
    YearlyArtifactSection,
    YearlyInsightCard,
    YearlyChartSpec,
)
from backend.domains.ai_reports.visual_brief import build_visual_brief
from backend.domains.ai_reports.visual_chart_data import build_visual_chart_data, chart_coverage
from backend.domains.ai_reports.visual_yearly_critic import critique_visual_yearly_artifact
from backend.domains.ai_reports.yearly_validator import validate_yearly_report


def generate_visual_yearly_artifact(
    request: dict[str, Any],
    *,
    emit_event=None,
) -> dict[str, Any]:
    evidence, context = _run_visual_research(request, emit_event=emit_event)
    _emit(emit_event, "building_narrative_brief", "正在提炼年度故事线", 0.48)
    narrative = build_narrative_brief(context)
    coverage = chart_coverage(context)
    _emit(emit_event, "planning_visuals", "正在选择年报图表", 0.58)
    visual = build_visual_brief(narrative, coverage)
    chart_specs = visual["chart_specs"]
    _emit(emit_event, "building_chart_data", "正在准备图表数据", 0.68)
    chart_data = build_visual_chart_data(context, chart_specs)
    _emit(emit_event, "composing_artifact", "正在生成图文年报", 0.78)
    sections = _compose_sections(context, narrative, visual)
    insight_cards = _compose_insight_cards(context, narrative)
    specs = tuple(_chart_spec(row) for row in chart_specs)
    prose = _report_text(sections)
    _emit(emit_event, "reviewing_visual_artifact", "正在检查文风与事实口径", 0.88)

    metadata = YearlyArtifactMetadata(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        fallback_level=visual.get("fallback_level"),
        section_count=len(sections),
        chart_count=len(chart_data),
        insight_card_count=len(insight_cards),
        article_length=len(prose),
        critic_passed=False,
        fact_validation_passed=False,
    )
    artifact = VisualYearlyArtifact(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        title=_title(context),
        subtitle=_subtitle(narrative),
        period=context.get("reporting_period") or {},
        narrative_brief=narrative,
        visual_brief=visual,
        sections=sections,
        insight_cards=insight_cards,
        chart_specs=specs,
        chart_data=chart_data,
        metadata=metadata,
    )
    artifact_payload = artifact.to_dict()
    critic = critique_visual_yearly_artifact(
        artifact_payload,
        {"is_partial_year": bool((context.get("reporting_period") or {}).get("is_partial_year"))},
    )
    fact_validation = _validate_visual_fact_safety(prose, artifact_payload, context)
    final_metadata = YearlyArtifactMetadata(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        fallback_level=metadata.fallback_level if critic["ok"] else "reduced_visuals",
        section_count=len(sections),
        chart_count=len(chart_data),
        insight_card_count=len(insight_cards),
        article_length=len(prose),
        critic_passed=bool(critic["ok"]),
        fact_validation_passed=bool(fact_validation["ok"]),
    )
    artifact_payload["metadata"] = final_metadata.to_dict()
    return {
        "success": True,
        "report": prose,
        "artifact": artifact_payload,
        "cached": False,
        "cached_at": None,
        "entities": _entities(context),
        "metadata": final_metadata.to_dict(),
        "critic": critic,
        "fact_validation": fact_validation,
        "evidence_ledger": [entry.to_dict() for entry in evidence],
        "error": None,
    }
```

Continue the file with deterministic helper functions:

```python
def _run_visual_research(request: dict[str, Any], emit_event=None):
    from backend.services.yearly_report_agent_service import _run_research_plan
    return _run_research_plan(request, emit_event=emit_event)


def _compose_sections(context: dict[str, Any], narrative: dict[str, Any], visual: dict[str, Any]) -> tuple[YearlyArtifactSection, ...]:
    lead = narrative["companionship_thread"]["entity"]
    second = narrative["second_thread"]["entity"]
    discovery = narrative["discovery_thread"]["entity"]
    tension = (narrative.get("tensions") or [{}])[0]
    sections = [
        YearlyArtifactSection("opening", "opening", "几乎没有离开音乐的一年", narrative["opening_scene"], _long_opening(context, narrative), ("listening_calendar",), ("activity_density",), ("yearly_overview",), "音乐不是偶尔打开的背景，而是全年生活的一部分。"),
        YearlyArtifactSection("companionship", "companionship", f"{lead}，你反复回到的声音", f"{lead} 不是只在某一首歌里出现。", _long_companionship(lead), ("artist_monthly_trend",), ("companion_artist",), ("yearly_top_entities",), None),
        YearlyArtifactSection("second_thread", "second_thread", f"{second} 带来的另一条情绪线", "这一年并不是单一语境的流行音乐。", _long_second_thread(second), ("artist_monthly_trend", "genre_language_mix"), ("second_thread",), ("genre_distribution",), None),
        YearlyArtifactSection("album_story", "album_story", "常听和长留，是两种不同的喜欢", "播放量第一和个人榜单第一不完全相同。", _long_album_story(tension), ("album_duality_compare", "playback_billboard_matrix"), ("album_duality",), ("personal_billboard_year_end",), None),
        YearlyArtifactSection("highlight_day", "highlight_day", "最密集的一天，不一定是单曲循环", "高光日更像一次密集漫游。", _long_highlight(context), ("highlight_day_timeline",), ("highlight_day",), ("highlight_day_detail",), None),
        YearlyArtifactSection("discovery", "discovery", f"{discovery}：新声音留下的痕迹", "新发现需要时间，但它已经出现。", _long_discovery(discovery, narrative), ("discovery_timeline",), ("discovery",), ("discovery_and_returns",), None),
        YearlyArtifactSection("closing", "closing", "这一年最终留下什么", "它留下的是陪伴、回望和新入口并存的画像。", _long_closing(narrative), (), (), (), None),
    ]
    return tuple(sections)
```

Add helper prose functions that each return at least 350 Chinese characters for full-year reports. Use no forbidden business-report terms. Keep exact entity names from context.

- [ ] **Step 5: Run artifact service test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_service.py -q
```

Expected: pass after helper prose reaches critic length.

- [ ] **Step 6: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports/visual_yearly_artifact_service.py backend/domains/ai_reports/visual_yearly_prompts.py backend/tests/unit/test_visual_yearly_artifact_service.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/domains/ai_reports/visual_yearly_artifact_service.py backend/domains/ai_reports/visual_yearly_prompts.py backend/tests/unit/test_visual_yearly_artifact_service.py
git commit -m "feat: compose visual yearly artifacts"
```

## Task 7: Route Visual Artifact Through API And AI Tasks

**Files:**
- Modify: `backend/models/ai_tasks.py`
- Modify: `backend/services/ai_task_service.py`
- Modify: `backend/api/ai_insights.py`
- Create: `backend/tests/contract/test_visual_yearly_report_contract.py`
- Modify: `backend/tests/unit/test_ai_report_tasks.py`

- [ ] **Step 1: Add contract tests for task and direct API routes**

Create `backend/tests/contract/test_visual_yearly_report_contract.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract


def _visual_result():
    return {
        "success": True,
        "report": "你的音乐年记" * 500,
        "artifact": {
            "report_mode": "visual_yearly_artifact",
            "contract_version": "visual_yearly_v1",
            "title": "你的 2025 音乐年记",
            "sections": [],
            "chart_specs": [],
            "chart_data": {},
            "metadata": {"report_mode": "visual_yearly_artifact", "contract_version": "visual_yearly_v1"},
        },
        "cached": False,
        "cached_at": None,
        "entities": {"artists": ["Taylor Swift"], "tracks": ["The Fate of Ophelia"]},
        "metadata": {"report_mode": "visual_yearly_artifact", "contract_version": "visual_yearly_v1"},
        "critic": {"ok": True, "issues": []},
        "fact_validation": {"ok": True, "issues": []},
        "evidence_ledger": [],
        "error": None,
    }


def test_yearly_story_force_visual_artifact_returns_artifact(monkeypatch):
    monkeypatch.setattr(
        "backend.domains.ai_reports.visual_yearly_artifact_service.generate_visual_yearly_artifact",
        lambda request, emit_event=None: _visual_result(),
    )
    client = TestClient(app)

    response = client.get("/api/ai-insights/yearly-story?year=2025&force=true&report_mode=visual_yearly_artifact")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["report_mode"] == "visual_yearly_artifact"
    assert payload["artifact"]["contract_version"] == "visual_yearly_v1"


def test_report_task_accepts_visual_yearly_mode(client):
    response = client.post(
        "/api/ai/tasks/report",
        json={"report_type": "yearly", "action": "generate", "year": 2025, "report_mode": "visual_yearly_artifact", "force": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"]
    assert payload["task_type"] == "ai_report_yearly"
```

- [ ] **Step 2: Run failing contract tests**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_visual_yearly_report_contract.py -q
```

Expected: fail because `report_mode` does not accept `visual_yearly_artifact`.

- [ ] **Step 3: Extend report mode models and response shape**

Modify `backend/models/ai_tasks.py`:

```python
report_mode: Literal["visual_yearly_artifact", "agentic_longform", "basic_summary"] = "visual_yearly_artifact"
```

Modify `backend/api/ai_insights.py` `DigestResponse`:

```python
artifact: Optional[dict[str, Any]] = None
```

Modify the `yearly_story()` query literal:

```python
report_mode: Literal["visual_yearly_artifact", "agentic_longform", "basic_summary"] = Query(
    "visual_yearly_artifact",
    description="Use visual artifact, agentic longform, or legacy basic summary yearly flow",
)
```

- [ ] **Step 4: Route visual report in API**

In `backend/api/ai_insights.py`, before the existing `agentic_longform` branch:

```python
if report_mode == "visual_yearly_artifact" and force:
    from backend.domains.ai_reports.visual_yearly_artifact_service import (
        generate_visual_yearly_artifact,
    )

    result = generate_visual_yearly_artifact(
        {
            "report_type": "yearly",
            "report_mode": report_mode,
            "year": year,
            "min_ms": filters.min_ms,
            "music_only": filters.music_only,
            "merge_enabled": filters.merge_enabled,
            "dynamic_threshold": filters.dynamic_threshold,
            "max_merge_gap_minutes": filters.max_merge_gap_minutes,
            "force": force,
        }
    )
    if not result["success"]:
        _raise_for_error(result)
    return result
```

- [ ] **Step 5: Route visual report in task service**

Modify `backend/services/ai_task_service.py`:

```python
_AGENTIC_STAGE_PROGRESS.update(
    {
        "building_narrative_brief": 0.48,
        "planning_visuals": 0.58,
        "building_chart_data": 0.68,
        "composing_artifact": 0.78,
        "reviewing_visual_artifact": 0.88,
    }
)
```

Add:

```python
def _should_use_visual_yearly_artifact(request: dict[str, Any]) -> bool:
    return request.get("report_type") == "yearly" and request.get(
        "report_mode", "visual_yearly_artifact"
    ) == "visual_yearly_artifact"
```

In `_run_report_generator()`, before `_should_use_agentic_yearly_report()`:

```python
if _should_use_visual_yearly_artifact(request):
    from backend.domains.ai_reports.visual_yearly_artifact_service import (
        generate_visual_yearly_artifact,
    )

    def emit_event(event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        del event_type
        event_payload = payload or {}
        stage = str(event_payload.get("stage") or "building_narrative_brief")
        progress = float(event_payload.get("progress_pct") or _AGENTIC_STAGE_PROGRESS.get(stage, 0.5))
        if progress_callback is not None:
            progress_callback(stage, progress, message)

    return generate_visual_yearly_artifact(request, emit_event=emit_event)
```

- [ ] **Step 6: Add unit test for visual task dispatch**

In `backend/tests/unit/test_ai_report_tasks.py`, add:

```python
def test_visual_yearly_report_mode_dispatches_visual_artifact(monkeypatch):
    from backend.services import ai_task_service

    called = {}

    def fake_generate(request, emit_event=None):
        called["request"] = request
        if emit_event:
            emit_event("stage_started", "正在提炼年度故事线", {"stage": "building_narrative_brief"})
        return {"success": True, "report": "visual", "artifact": {}, "cached": False, "metadata": {"report_mode": "visual_yearly_artifact"}, "evidence_ledger": []}

    monkeypatch.setattr(
        "backend.domains.ai_reports.visual_yearly_artifact_service.generate_visual_yearly_artifact",
        fake_generate,
    )

    result = ai_task_service._run_report_generator(
        None,
        {"report_type": "yearly", "report_mode": "visual_yearly_artifact", "year": 2025},
        progress_callback=lambda *args: None,
        should_continue=lambda: True,
    )

    assert result["metadata"]["report_mode"] == "visual_yearly_artifact"
    assert called["request"]["year"] == 2025
```

- [ ] **Step 7: Run backend routing tests**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_visual_yearly_report_contract.py backend/tests/unit/test_ai_report_tasks.py -q
```

Expected: pass.

- [ ] **Step 8: Checkpoint**

Run:

```bash
.venv/bin/ruff check backend/models/ai_tasks.py backend/api/ai_insights.py backend/services/ai_task_service.py backend/tests/contract/test_visual_yearly_report_contract.py backend/tests/unit/test_ai_report_tasks.py
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add backend/models/ai_tasks.py backend/api/ai_insights.py backend/services/ai_task_service.py backend/tests/contract/test_visual_yearly_report_contract.py backend/tests/unit/test_ai_report_tasks.py
git commit -m "feat: route visual yearly report tasks"
```

## Task 8: Add Frontend Artifact Types And Renderer Shell

**Files:**
- Create: `frontend/src/features/ai-insights/yearly-artifact/yearlyArtifactTypes.ts`
- Create: `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
- Create: `frontend/src/features/ai-insights/yearly-artifact/YearlyHero.tsx`
- Create: `frontend/src/features/ai-insights/yearly-artifact/YearlySection.tsx`
- Create: `frontend/src/features/ai-insights/yearly-artifact/YearlyInsightCards.tsx`
- Create: `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
- Create: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Write frontend renderer tests**

Create `frontend/src/tests/visual-yearly-report.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { VisualYearlyReport } from '@/features/ai-insights/yearly-artifact/VisualYearlyReport'
import type { VisualYearlyArtifact } from '@/features/ai-insights/yearly-artifact/yearlyArtifactTypes'

function artifact(): VisualYearlyArtifact {
  return {
    report_mode: 'visual_yearly_artifact',
    contract_version: 'visual_yearly_v1',
    title: '你的 2025 音乐年记',
    subtitle: '几乎没有离开音乐的一年',
    period: { year: 2025, start_date: '2025-01-01', end_date: '2025-12-31', is_partial_year: false },
    narrative_brief: {},
    visual_brief: {},
    sections: [
      {
        id: 'opening',
        role: 'opening',
        heading: '几乎没有离开音乐的一年',
        deck: '364 个活跃日说明音乐几乎每天都在场。',
        prose: '这一年，音乐几乎没有从你的日常里退场。',
        chart_refs: ['listening_calendar'],
        insight_refs: ['activity_density'],
        evidence_refs: ['yearly_overview'],
        pull_quote: '音乐不是偶尔打开的背景。',
      },
    ],
    insight_cards: [
      { id: 'activity_density', label: '全年陪伴密度', value: '364 天', caption: '这一年几乎每天都有音乐在场。', tone: 'warm', evidence_refs: [] },
    ],
    chart_specs: [
      { id: 'listening_calendar', chart_type: 'listening_calendar_heatmap', title: '音乐铺满这一年', narrative_question: '音乐是否每天都在场？', entities: [], data_key: 'listening_calendar', insight: '364 个活跃日。', fallback: '显示活跃日。' },
    ],
    chart_data: { listening_calendar: { days: [], active_days: 364 } },
    metadata: { report_mode: 'visual_yearly_artifact', contract_version: 'visual_yearly_v1', section_count: 1, chart_count: 1, insight_card_count: 1, article_length: 40, critic_passed: true, fact_validation_passed: true, fallback_level: null },
  }
}

describe('VisualYearlyReport', () => {
  it('renders hero, insight cards, sections, and chart blocks', () => {
    render(<VisualYearlyReport artifact={artifact()} />)

    expect(screen.getByText('你的 2025 音乐年记')).toBeInTheDocument()
    expect(screen.getByText('全年陪伴密度')).toBeInTheDocument()
    expect(screen.getByText('几乎没有离开音乐的一年')).toBeInTheDocument()
    expect(screen.getByText('音乐铺满这一年')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run failing frontend test**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: fail because renderer files do not exist.

- [ ] **Step 3: Add frontend artifact types**

Create `frontend/src/features/ai-insights/yearly-artifact/yearlyArtifactTypes.ts`:

```ts
export interface YearlyArtifactSection {
  id: string
  role: string
  heading: string
  deck: string
  prose: string
  chart_refs: string[]
  insight_refs: string[]
  evidence_refs: string[]
  pull_quote: string | null
}

export interface YearlyInsightCard {
  id: string
  label: string
  value: string
  caption: string
  tone: string
  evidence_refs: string[]
}

export interface YearlyChartSpec {
  id: string
  chart_type: string
  title: string
  narrative_question: string
  entities: string[]
  data_key: string
  insight: string
  fallback: string
}

export interface VisualYearlyArtifact {
  report_mode: 'visual_yearly_artifact'
  contract_version: string
  title: string
  subtitle: string
  period: Record<string, unknown>
  narrative_brief: Record<string, unknown>
  visual_brief: Record<string, unknown>
  sections: YearlyArtifactSection[]
  insight_cards: YearlyInsightCard[]
  chart_specs: YearlyChartSpec[]
  chart_data: Record<string, unknown>
  metadata: Record<string, unknown>
}

export function isVisualYearlyArtifact(value: unknown): value is VisualYearlyArtifact {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    record.report_mode === 'visual_yearly_artifact' &&
    Array.isArray(record.sections) &&
    Array.isArray(record.chart_specs) &&
    typeof record.chart_data === 'object' &&
    record.chart_data !== null
  )
}
```

- [ ] **Step 4: Add renderer shell components**

Create `VisualYearlyReport.tsx`, `YearlyHero.tsx`, `YearlyInsightCards.tsx`, `YearlySection.tsx`, and `YearlyChartBlock.tsx`. Keep the first pass simple and unframed:

```tsx
import type { VisualYearlyArtifact } from './yearlyArtifactTypes'
import { YearlyHero } from './YearlyHero'
import { YearlyInsightCards } from './YearlyInsightCards'
import { YearlySection } from './YearlySection'

export function VisualYearlyReport({ artifact }: { artifact: VisualYearlyArtifact }) {
  return (
    <article className="space-y-8 text-foreground">
      <YearlyHero artifact={artifact} />
      <YearlyInsightCards cards={artifact.insight_cards} />
      {artifact.sections.map((section) => (
        <YearlySection
          artifact={artifact}
          key={section.id}
          section={section}
        />
      ))}
    </article>
  )
}
```

```tsx
import type { VisualYearlyArtifact } from './yearlyArtifactTypes'

export function YearlyHero({ artifact }: { artifact: VisualYearlyArtifact }) {
  return (
    <header className="border-b border-border/60 pb-6">
      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        AI 音乐年报
      </p>
      <h2 className="mt-2 font-serif text-[34px] font-bold leading-tight text-foreground">
        {artifact.title}
      </h2>
      <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
        {artifact.subtitle}
      </p>
    </header>
  )
}
```

```tsx
import type { YearlyInsightCard } from './yearlyArtifactTypes'

export function YearlyInsightCards({ cards }: { cards: YearlyInsightCard[] }) {
  if (!cards.length) return null
  return (
    <section className="grid gap-3 sm:grid-cols-3">
      {cards.map((card) => (
        <div className="rounded-[8px] border border-border bg-card/50 p-4" key={card.id}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground">
            {card.label}
          </p>
          <p className="mt-2 font-serif text-[24px] font-semibold text-foreground">{card.value}</p>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{card.caption}</p>
        </div>
      ))}
    </section>
  )
}
```

```tsx
import type { VisualYearlyArtifact, YearlyArtifactSection } from './yearlyArtifactTypes'
import { YearlyChartBlock } from './YearlyChartBlock'

export function YearlySection({
  artifact,
  section,
}: {
  artifact: VisualYearlyArtifact
  section: YearlyArtifactSection
}) {
  return (
    <section className="space-y-4">
      <div className="max-w-3xl">
        <h3 className="font-serif text-[26px] font-semibold leading-tight text-foreground">
          {section.heading}
        </h3>
        {section.deck && (
          <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{section.deck}</p>
        )}
        <p className="mt-4 whitespace-pre-line text-[15px] leading-7 text-muted-foreground">
          {section.prose}
        </p>
        {section.pull_quote && (
          <blockquote className="mt-4 border-l-2 border-accent-foreground/50 pl-4 font-serif text-[18px] text-foreground">
            {section.pull_quote}
          </blockquote>
        )}
      </div>
      {section.chart_refs.map((chartId) => (
        <YearlyChartBlock
          chartData={artifact.chart_data[chartId]}
          key={chartId}
          spec={artifact.chart_specs.find((item) => item.id === chartId) ?? null}
        />
      ))}
    </section>
  )
}
```

```tsx
import type { YearlyChartSpec } from './yearlyArtifactTypes'

export function YearlyChartBlock({
  spec,
  chartData,
}: {
  spec: YearlyChartSpec | null
  chartData: unknown
}) {
  if (!spec) return null
  return (
    <figure className="rounded-[8px] border border-border bg-card/35 p-4">
      <figcaption>
        <p className="font-serif text-[18px] font-semibold text-foreground">{spec.title}</p>
        <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{spec.insight}</p>
      </figcaption>
      <div className="mt-4 min-h-[180px] rounded-[6px] bg-muted/20 p-4 text-[12px] text-muted-foreground">
        {chartData ? '图表数据已准备，后续任务渲染具体图表。' : spec.fallback}
      </div>
    </figure>
  )
}
```

- [ ] **Step 5: Run renderer test**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: pass.

- [ ] **Step 6: Checkpoint**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: pass. Commit when executing with commits enabled:

```bash
git add frontend/src/features/ai-insights/yearly-artifact frontend/src/tests/visual-yearly-report.test.tsx
git commit -m "feat: add visual yearly report renderer shell"
```

## Task 9: Add Concrete Chart Components

**Files:**
- Create files under `frontend/src/features/ai-insights/yearly-artifact/charts/`
- Modify: `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
- Modify: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Add chart dispatch test**

Extend `frontend/src/tests/visual-yearly-report.test.tsx`:

```tsx
it('renders concrete chart labels for supported chart types', () => {
  const value = artifact()
  value.chart_specs = [
    { ...value.chart_specs[0], chart_type: 'listening_calendar_heatmap', id: 'listening_calendar' },
    { ...value.chart_specs[0], chart_type: 'album_duality_compare', id: 'album_duality_compare', title: '两张专辑，两种喜欢' },
  ]
  value.chart_data = {
    listening_calendar: { days: [{ date: '2025-01-01', plays: 2, minutes: 6 }], active_days: 1 },
    album_duality_compare: {
      playback_leader: { name: 'The Life of a Showgirl', artist: 'Taylor Swift', plays: 1106 },
      chart_leader: { name: '光良「回憶裡的瘋狂」巡迴演唱會', artist: 'Michael Wong', weeks_on_chart: 32 },
    },
  }
  value.sections[0].chart_refs = ['listening_calendar', 'album_duality_compare']

  render(<VisualYearlyReport artifact={value} />)

  expect(screen.getByText('活跃 1 天')).toBeInTheDocument()
  expect(screen.getByText('The Life of a Showgirl')).toBeInTheDocument()
  expect(screen.getByText('光良「回憶裡的瘋狂」巡迴演唱會')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run failing chart component test**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: fail because concrete chart labels do not exist.

- [ ] **Step 3: Implement first chart components**

Create `ListeningCalendarChart.tsx`:

```tsx
interface CalendarDay {
  date: string
  plays: number
  minutes?: number
}

export function ListeningCalendarChart({ data }: { data: unknown }) {
  const record = data as { days?: CalendarDay[]; active_days?: number } | null
  const days = Array.isArray(record?.days) ? record.days.slice(0, 60) : []
  const activeDays = typeof record?.active_days === 'number' ? record.active_days : days.length
  if (!days.length) return <p className="text-[12px] text-muted-foreground">暂无日历数据</p>
  const max = Math.max(...days.map((day) => day.plays), 1)
  return (
    <div>
      <p className="mb-3 text-[12px] font-semibold text-muted-foreground">活跃 {activeDays} 天</p>
      <div className="grid grid-cols-15 gap-1">
        {days.map((day) => (
          <span
            aria-label={`${day.date} 播放 ${day.plays} 次`}
            className="aspect-square rounded-[3px] bg-accent-foreground/20"
            key={day.date}
            style={{ opacity: 0.25 + (day.plays / max) * 0.75 }}
            title={`${day.date}: ${day.plays} 次`}
          />
        ))}
      </div>
    </div>
  )
}
```

Create `AlbumDualityCompare.tsx`:

```tsx
function nameOf(value: unknown): string {
  return value && typeof value === 'object' && 'name' in value
    ? String((value as { name?: unknown }).name ?? '')
    : ''
}

export function AlbumDualityCompare({ data }: { data: unknown }) {
  const record = data as { playback_leader?: unknown; chart_leader?: unknown; interpretation?: string } | null
  const playback = nameOf(record?.playback_leader)
  const chart = nameOf(record?.chart_leader)
  if (!playback || !chart) return <p className="text-[12px] text-muted-foreground">专辑对照数据不足</p>
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-[8px] border border-border/70 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground">最常播放</p>
        <p className="mt-2 font-serif text-[18px] text-foreground">{playback}</p>
      </div>
      <div className="rounded-[8px] border border-border/70 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground">最稳定在榜</p>
        <p className="mt-2 font-serif text-[18px] text-foreground">{chart}</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Implement remaining chart components as readable first-pass views**

Create the remaining files with simple, data-driven, non-ECharts implementations:

- `ArtistMonthlyTrendChart.tsx`: table-like monthly rows for entities.
- `HighlightDayTimeline.tsx`: hourly bars and top tracks.
- `GenreLanguageMixChart.tsx`: horizontal percentage bars.
- `DiscoveryTimeline.tsx`: first-seen artist list.
- `PlaybackBillboardMatrix.tsx`: compact grid of items with plays/weeks.

Each component must:

- Accept `data: unknown`.
- Validate shape locally.
- Render a clear empty state.
- Avoid fixed widths wider than parent.

- [ ] **Step 5: Dispatch concrete chart components**

Modify `YearlyChartBlock.tsx`:

```tsx
import { AlbumDualityCompare } from './charts/AlbumDualityCompare'
import { ArtistMonthlyTrendChart } from './charts/ArtistMonthlyTrendChart'
import { DiscoveryTimeline } from './charts/DiscoveryTimeline'
import { GenreLanguageMixChart } from './charts/GenreLanguageMixChart'
import { HighlightDayTimeline } from './charts/HighlightDayTimeline'
import { ListeningCalendarChart } from './charts/ListeningCalendarChart'
import { PlaybackBillboardMatrix } from './charts/PlaybackBillboardMatrix'

function ChartBody({ spec, data }: { spec: YearlyChartSpec; data: unknown }) {
  switch (spec.chart_type) {
    case 'listening_calendar_heatmap':
      return <ListeningCalendarChart data={data} />
    case 'artist_monthly_trend':
      return <ArtistMonthlyTrendChart data={data} />
    case 'album_duality_compare':
      return <AlbumDualityCompare data={data} />
    case 'highlight_day_timeline':
      return <HighlightDayTimeline data={data} />
    case 'genre_language_mix':
      return <GenreLanguageMixChart data={data} />
    case 'discovery_timeline':
      return <DiscoveryTimeline data={data} />
    case 'playback_billboard_matrix':
      return <PlaybackBillboardMatrix data={data} />
    default:
      return <p className="text-[12px] text-muted-foreground">{spec.fallback}</p>
  }
}
```

- [ ] **Step 6: Run chart tests and build**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx
cd frontend && npm run build
```

Expected: tests pass and build succeeds.

- [ ] **Step 7: Checkpoint**

Commit when executing with commits enabled:

```bash
git add frontend/src/features/ai-insights/yearly-artifact frontend/src/tests/visual-yearly-report.test.tsx
git commit -m "feat: render visual yearly charts"
```

## Task 10: Integrate Artifact Into Existing AI Reports UI

**Files:**
- Modify: `frontend/src/features/ai-insights/AiReportsPanel.tsx`
- Modify: `frontend/src/features/ai-insights/ReportCard.tsx`
- Modify: `frontend/src/features/ai-tasks/AITaskProgress.tsx`
- Modify: `frontend/src/hooks/useAiTasks.ts`
- Modify: `frontend/src/tests/ai-task-components.test.tsx`
- Modify: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Extend ReportCard test for artifact branch**

In `frontend/src/tests/visual-yearly-report.test.tsx`, add:

```tsx
import { ReportCard } from '@/features/ai-insights/ReportCard'

it('ReportCard renders visual artifact instead of markdown when artifact exists', () => {
  render(
    <ReportCard
      artifact={artifact()}
      cached={false}
      cachedAt={null}
      entities={null}
      error={null}
      fetching={false}
      loading={false}
      onRetry={() => undefined}
      report="## Markdown fallback"
      reportType="yearly"
      title="年度叙事 · 2025"
    />,
  )

  expect(screen.getByText('你的 2025 音乐年记')).toBeInTheDocument()
  expect(screen.queryByText('Markdown fallback')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run failing ReportCard test**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: fail because `ReportCard` has no `artifact` prop.

- [ ] **Step 3: Extend frontend request/result types**

Modify `frontend/src/hooks/useAiTasks.ts`:

```ts
report_mode?: 'visual_yearly_artifact' | 'agentic_longform' | 'basic_summary'
```

Modify `AiReportsPanel.tsx` `ReportTaskResult`:

```ts
artifact: VisualYearlyArtifact | null
```

Use `isVisualYearlyArtifact(value.artifact)` in `reportResultFromPayload()`.

- [ ] **Step 4: Send visual mode for yearly reports**

Modify `AiReportsPanel.tsx` yearly payload:

```ts
return {
  report_type: 'yearly',
  action: 'cache_only',
  report_mode: 'visual_yearly_artifact',
  year,
  ...basePayload,
}
```

Do the same for generate payloads.

- [ ] **Step 5: Render visual artifact from ReportCard**

Modify `ReportCard.tsx`:

```tsx
import { VisualYearlyReport } from './yearly-artifact/VisualYearlyReport'
import type { VisualYearlyArtifact } from './yearly-artifact/yearlyArtifactTypes'

interface ReportCardProps {
  artifact?: VisualYearlyArtifact | null
}
```

Before Markdown content:

```tsx
{artifact ? (
  <VisualYearlyReport artifact={artifact} />
) : (
  <div className="prose prose-sm max-w-none max-h-[600px] overflow-y-auto text-[14px] leading-relaxed text-muted-foreground [&_h2]:font-serif [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-foreground [&_strong]:text-foreground">
    <AiMarkdown>{report}</AiMarkdown>
  </div>
)}
```

- [ ] **Step 6: Add stage labels**

Modify `AITaskProgress.tsx`:

```ts
building_narrative_brief: '提炼年度故事线',
planning_visuals: '选择年报图表',
building_chart_data: '准备图表数据',
composing_artifact: '生成图文年报',
reviewing_visual_artifact: '检查文风与事实口径',
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx src/tests/ai-task-components.test.tsx
cd frontend && npm run build
```

Expected: pass.

- [ ] **Step 8: Checkpoint**

Commit when executing with commits enabled:

```bash
git add frontend/src/features/ai-insights frontend/src/features/ai-tasks frontend/src/hooks/useAiTasks.ts frontend/src/tests/visual-yearly-report.test.tsx frontend/src/tests/ai-task-components.test.tsx
git commit -m "feat: show visual yearly artifacts in AI reports"
```

## Task 11: Add HTTP Probe And Golden Checks

**Files:**
- Create: `scripts/probe_visual_yearly_report_artifact.py`
- Create/Modify: `backend/tests/contract/test_visual_yearly_report_contract.py`

- [ ] **Step 1: Create probe script**

Create `scripts/probe_visual_yearly_report_artifact.py`:

```python
#!/usr/bin/env python3
"""Probe visual yearly report artifacts through the AI task API."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

FORBIDDEN_TERMS = (
    "稳定中心",
    "三榜联动",
    "第二层证据",
    "evidence ledger",
    "dynamic outline",
    "综合来看",
    "后续观察",
)


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--json-output", required=True)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    task = request_json(
        f"{base}/api/ai/tasks/report",
        method="POST",
        payload={
            "report_type": "yearly",
            "action": "generate",
            "report_mode": "visual_yearly_artifact",
            "year": args.year,
            "force": True,
        },
    )
    task_id = task["task_id"]
    deadline = time.time() + args.timeout
    detail = {}
    while time.time() < deadline:
        detail = request_json(f"{base}/api/ai/tasks/{task_id}")
        if detail.get("status") in {"done", "error", "cancelled"}:
            break
        time.sleep(2)

    result = detail.get("result") or {}
    artifact = result.get("artifact") or {}
    metadata = result.get("metadata") or {}
    sections = artifact.get("sections") or []
    chart_specs = artifact.get("chart_specs") or []
    chart_data = artifact.get("chart_data") or {}
    prose = "\n".join(str(section.get("prose") or "") for section in sections)
    issues: list[str] = []

    if detail.get("status") != "done":
        issues.append(f"task status is {detail.get('status')}")
    if metadata.get("report_mode") != "visual_yearly_artifact":
        issues.append("metadata report_mode is not visual_yearly_artifact")
    if metadata.get("contract_version") != "visual_yearly_v1":
        issues.append("contract_version is not visual_yearly_v1")
    if len(sections) < 6:
        issues.append("section_count < 6")
    if len(chart_specs) < 4:
        issues.append("chart_count < 4")
    if args.year < 2026 and len(prose) < 2800:
        issues.append("full-year prose length < 2800")
    missing_refs = sorted({
        ref
        for section in sections
        for ref in section.get("chart_refs", [])
        if ref not in chart_data
    })
    if missing_refs:
        issues.append("missing chart refs: " + ", ".join(missing_refs))
    forbidden = [term for term in FORBIDDEN_TERMS if term in prose]
    if forbidden:
        issues.append("forbidden terms: " + ", ".join(forbidden))
    if not (result.get("critic") or {}).get("ok"):
        issues.append("visual critic did not pass")
    if not (result.get("fact_validation") or {}).get("ok"):
        issues.append("fact validation did not pass")

    summary = {
        "ok": not issues,
        "issues": issues,
        "task_id": task_id,
        "metadata": metadata,
        "section_count": len(sections),
        "chart_count": len(chart_specs),
        "resolved_chart_data_count": len(chart_data),
        "article_length": len(prose),
        "preview": prose[:800],
    }
    Path(args.json_output).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run syntax check**

Run:

```bash
.venv/bin/ruff check scripts/probe_visual_yearly_report_artifact.py
.venv/bin/python -m py_compile scripts/probe_visual_yearly_report_artifact.py
```

Expected: pass.

- [ ] **Step 3: Run live probes**

Ensure backend is running on 8000, then run:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/probe_visual_yearly_report_artifact.py --base-url http://127.0.0.1:8000 --year 2025 --timeout 300 --json-output /tmp/spotify_visual_yearly_2025.json
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/probe_visual_yearly_report_artifact.py --base-url http://127.0.0.1:8000 --year 2026 --timeout 300 --json-output /tmp/spotify_visual_yearly_2026.json
```

Expected: both exit 0.

- [ ] **Step 4: Checkpoint**

Commit when executing with commits enabled:

```bash
git add scripts/probe_visual_yearly_report_artifact.py backend/tests/contract/test_visual_yearly_report_contract.py
git commit -m "test: add visual yearly artifact probe"
```

## Task 12: Browser Acceptance And Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `backend/CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md`

- [x] **Step 1: Run backend targeted matrix**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_models.py backend/tests/unit/test_narrative_brief.py backend/tests/unit/test_visual_brief.py backend/tests/unit/test_visual_chart_data.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_visual_yearly_report_contract.py -q
```

Expected: pass.

- [x] **Step 2: Run frontend targeted matrix**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx src/tests/ai-task-components.test.tsx
cd frontend && npm run build
```

Expected: pass.

- [x] **Step 3: Run API probes**

Run:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/probe_visual_yearly_report_artifact.py --base-url http://127.0.0.1:8000 --year 2025 --timeout 300 --json-output /tmp/spotify_visual_yearly_2025.json
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/probe_visual_yearly_report_artifact.py --base-url http://127.0.0.1:8000 --year 2026 --timeout 300 --json-output /tmp/spotify_visual_yearly_2026.json
```

Expected: pass.

- [x] **Step 4: Run browser acceptance**

Use the in-app browser or Playwright to verify:

1. Navigate to `/ai-insights`.
2. Click `年度叙事`.
3. Select `2025`.
4. Click `刷新报告`.
5. Confirm progress includes:
   - `提炼年度故事线`
   - `选择年报图表`
   - `准备图表数据`
   - `生成图文年报`
   - `检查文风与事实口径`
6. Confirm final page renders artifact, not only Markdown.
7. Confirm at least 4 chart blocks appear.
8. Set viewport width to 390px and confirm no horizontal overflow.
9. Confirm console error/warning count is 0.

Expected: all checks pass.

- [x] **Step 5: Update docs**

Update `README.md` AI Insights bullet to mention visual yearly artifacts:

```text
年度叙事默认生成图文音乐年报 artifact，包含故事章节、重点卡片、真实图表数据、个人榜单关系分析和文风/事实校验。
```

Update `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md` with:

```text
AI Visual Yearly Report Artifact（2026-07-04）：年度报告默认 `report_mode=visual_yearly_artifact`，保留只读 Report Agent 和 fact validator，新增 Narrative Brief、Visual Brief、Chart Data Builder、Visual Critic 与前端 artifact renderer。LLM 只写故事表达，不得生成图表数据；图表数据必须由 deterministic backend builder 生成。
```

Update `docs/README.md` with this plan link:

```markdown
| [`superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md`](superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md) | AI Visual Yearly Report Artifact 实施计划：Narrative Brief、Visual Brief、真实图表数据、图文年报渲染器、critic、probe 与浏览器验收 |
```

Update `docs/CHANGELOG.md` with implementation summary and actual verification commands.

- [x] **Step 6: Run final lint and staged checks**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports backend/services/ai_task_service.py backend/api/ai_insights.py backend/models/ai_tasks.py scripts/probe_visual_yearly_report_artifact.py
git diff --check
```

Expected: pass.

- [ ] **Step 7: Final checkpoint**

Not completed in this execution because no commit was requested.

Commit when executing with commits enabled:

```bash
git add README.md AGENTS.md CLAUDE.md backend/CLAUDE.md docs/README.md docs/CHANGELOG.md docs/superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md
git commit -m "docs: document visual yearly report artifact"
```

## Self-Review

- Spec coverage: every spec section is mapped to tasks:
  - Artifact schema: Task 1.
  - Narrative Brief: Task 2.
  - Visual Brief: Task 3.
  - Chart Data Builder: Task 4.
  - Visual/Narrative Critic: Task 5.
  - Artifact Composer and fact validation: Task 6.
  - API/task result integration: Task 7.
  - Frontend renderer and chart blocks: Tasks 8-10.
  - Probe/browser/docs: Tasks 11-12.
- 占位扫描：this plan contains no vague task, no open-ended “add tests” step, and no unassigned implementation area.
- Type consistency:
  - Report mode is consistently `visual_yearly_artifact`.
  - Contract version is consistently `visual_yearly_v1`.
  - Frontend `VisualYearlyArtifact` mirrors backend `VisualYearlyArtifact.to_dict()`.
  - Chart `id` and `data_key` use the same key in first implementation.
- Scope control:
  - Weekly/monthly reports stay on current renderer.
  - PDF export, sharing, custom themes, and generated images are not part of this plan.
  - `agentic_longform` and `basic_summary` remain available fallback modes.
