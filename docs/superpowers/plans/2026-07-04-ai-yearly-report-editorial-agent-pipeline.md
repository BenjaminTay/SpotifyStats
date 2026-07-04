# AI Yearly Report Editorial Agent Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the yearly report prose path with a hybrid editorial agent pipeline that builds a research brief, lets the LLM plan/write/edit the article, validates claims deterministically, then renders the existing visual yearly artifact shape.

**Architecture:** Keep deterministic builders responsible for evidence, chart data, cache contracts, and safety checks. Add a focused `backend/domains/ai_reports/editorial_agent/` package for research brief models, storyline planning, LLM writing/editing, claim checking, orchestration, and taste scoring. Integrate behind `writer_pipeline=editorial_agent_v1`, prove quality with 2025/2026 probes and browser acceptance, then make the new pipeline the default only after the taste gate passes.

**Tech Stack:** FastAPI task orchestration, SQLite report cache, existing `LLMProvider` via `_llm_chat`, Python dataclasses + typed dicts, pytest unit/contract tests, existing visual yearly React artifact renderer, Vitest, Playwright/in-app browser smoke.

**Commit Policy:** Do not create per-task commits. The user explicitly requested keeping the spec and plan uncommitted until the repair is complete; stage and commit only after full implementation, verification, and documentation sync.

**Execution Status (2026-07-05):** Implemented. The final pipeline ships as `visual_yearly_artifact` + `writer_pipeline=editorial_agent_v1`; backend now has the `editorial_agent/` package, writer metadata, claim check, taste scoring, cache-key isolation, task progress stages, frontend badges, updated probe validation, artifact-level deterministic editorial fallback, browser refresh acceptance, and a fix for the partial-year post-processing bug that turned `表明年度` into `表之后度`.

---

## File Structure

Create:

- `backend/domains/ai_reports/editorial_agent/__init__.py` — package exports and version constants.
- `backend/domains/ai_reports/editorial_agent/models.py` — dataclasses for research brief, storyline plan, article draft, edited article, extracted claims, claim check result, and taste rubric.
- `backend/domains/ai_reports/editorial_agent/research_brief.py` — converts existing yearly context, chart data, and story insights into evidence-led story material.
- `backend/domains/ai_reports/editorial_agent/prompts.py` — planner/writer/editor/repair prompts.
- `backend/domains/ai_reports/editorial_agent/llm_steps.py` — JSON/text LLM helper functions with injectable chat function for tests.
- `backend/domains/ai_reports/editorial_agent/storyline_planner.py` — LLM planner plus deterministic fallback plan.
- `backend/domains/ai_reports/editorial_agent/writer.py` — LLM longform writer plus deterministic article fallback for explicit fallback levels.
- `backend/domains/ai_reports/editorial_agent/editor.py` — LLM editorial rewrite pass and deterministic cleanup helpers.
- `backend/domains/ai_reports/editorial_agent/claim_checker.py` — claim extraction and evidence matching.
- `backend/domains/ai_reports/editorial_agent/taste_rubric.py` — deterministic taste scoring used by probes and tests.
- `backend/domains/ai_reports/editorial_agent/pipeline.py` — orchestrates research, planning, writing, editing, claim checking, repair, and artifact section conversion.
- `backend/tests/unit/test_yearly_editorial_agent_models.py`
- `backend/tests/unit/test_yearly_research_brief.py`
- `backend/tests/unit/test_yearly_storyline_planner.py`
- `backend/tests/unit/test_yearly_writer_editor.py`
- `backend/tests/unit/test_yearly_claim_checker.py`
- `backend/tests/unit/test_yearly_taste_rubric.py`
- `backend/tests/unit/test_yearly_editorial_agent_pipeline.py`
- `backend/tests/contract/test_yearly_editorial_agent_contract.py`
- `scripts/evaluate_yearly_report_taste.py`

Modify:

- `backend/domains/ai_reports/visual_yearly_artifact_service.py` — route prose composition through the editorial agent when requested/defaulted.
- `backend/domains/ai_reports/visual_yearly_critic.py` — read editorial agent metadata and add new article-quality blockers.
- `backend/services/ai_task_service.py` — include `writer_pipeline` in report request/cache/payload, add progress stages, preserve fallback metadata.
- `backend/services/ai_insights_service.py` — include writer pipeline in visual yearly cache key or report mode cache part.
- `backend/models/ai_tasks.py` — allow `writer_pipeline` request field.
- `frontend/src/features/ai-tasks/AITaskProgress.tsx` — labels for new stages.
- `frontend/src/features/ai-insights/ReportCard.tsx` — optional badges for `writer_pipeline_version`, claim check, editorial review, and taste score.
- `frontend/src/tests/ai-task-components.test.tsx`
- `frontend/src/tests/visual-yearly-report.test.tsx`
- `scripts/probe_visual_yearly_report_artifact.py` — add `--writer-pipeline`, taste score checks, and metadata validation.
- `docs/README.md`
- `docs/CHANGELOG.md`
- `README.md`, `AGENTS.md`, `CLAUDE.md`, `backend/CLAUDE.md` only if the new pipeline becomes default.

Do not touch unrelated artist genre resolution files currently present in the worktree:

- `backend/core/db.py`
- `backend/core/migrations.py`
- `backend/tests/unit/test_migrations.py`
- `backend/tests/unit/test_artist_genre_resolution.py`
- `docs/superpowers/plans/2026-07-04-artist-genre-resolution.md`

---

## Task 1: Editorial Agent Models

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/__init__.py`
- Create: `backend/domains/ai_reports/editorial_agent/models.py`
- Test: `backend/tests/unit/test_yearly_editorial_agent_models.py`

- [ ] **Step 1: Write model tests first**

Create `backend/tests/unit/test_yearly_editorial_agent_models.py`:

```python
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    ClaimCheckResult,
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
    StorylinePlan,
)


def test_research_brief_serializes_story_candidates():
    evidence = EvidenceItem(
        id="top_artist_taylor_2026",
        claim="Taylor Swift 以 1115 次播放位列 2026 当前艺人第一。",
        source="yearly_top_entities.artists[0]",
        kind="playback_rank",
        confidence="high",
    )
    candidate = StoryCandidate(
        id="stable_center",
        title="Taylor Swift 是稳定回访对象",
        why_it_matters="它解释了年度重心，而不是只给出艺人榜第一。",
        evidence_refs=("top_artist_taylor_2026",),
        risk_notes=("不能写成外部官方 Billboard。",),
    )
    brief = ResearchBrief(
        period={"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        evidence_ledger=(evidence,),
        story_candidates=(candidate,),
        tensions=(),
        forbidden_inferences=("不能编造通勤、考试、天气或地点。",),
    )

    payload = brief.to_dict()

    assert payload["period"]["year"] == 2026
    assert payload["evidence_ledger"][0]["id"] == "top_artist_taylor_2026"
    assert payload["story_candidates"][0]["evidence_refs"] == ["top_artist_taylor_2026"]


def test_storyline_plan_and_article_sections_round_trip():
    plan = StorylinePlan(
        thesis="2026 上半年由稳定回访和阶段转折共同构成。",
        title="一份还在展开的音乐年记",
        subtitle="截至 2026-06-23，稳定和变化同时存在。",
        section_plan=(
            ArticleSection(
                id="opening",
                heading="今年还没有结束，但重心已经出现",
                purpose="建立阶段性年报边界和主论点",
                prose="",
                evidence_refs=("period_2026_ytd",),
                chart_refs=(),
            ),
        ),
        must_not_write=("不要按固定榜单模块展开。",),
    )
    draft = ArticleDraft(
        title=plan.title,
        subtitle=plan.subtitle,
        thesis=plan.thesis,
        sections=plan.section_plan,
        closing="继续观察下半年是否延续。",
    )

    assert draft.to_dict()["sections"][0]["heading"] == "今年还没有结束，但重心已经出现"
    assert StorylinePlan.from_dict(plan.to_dict()).thesis == plan.thesis


def test_claim_check_result_requires_all_supported_for_pass():
    passed = ClaimCheckResult(
        claims=(),
        unsupported_claims=(),
        contradicted_claims=(),
        ambiguous_claims=(),
        scope_leaks=(),
    )
    failed = ClaimCheckResult(
        claims=(),
        unsupported_claims=("没有证据的生活事件",),
        contradicted_claims=(),
        ambiguous_claims=(),
        scope_leaks=(),
    )

    assert passed.ok is True
    assert failed.ok is False
```

- [ ] **Step 2: Run model tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_editorial_agent_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domains.ai_reports.editorial_agent'`.

- [ ] **Step 3: Create package exports**

Create `backend/domains/ai_reports/editorial_agent/__init__.py`:

```python
"""Editorial-agent pipeline for AI yearly reports."""

WRITER_PIPELINE_VERSION = "yearly_editorial_agent_v1"
RESEARCH_BRIEF_VERSION = "yearly_research_brief_v1"
```

- [ ] **Step 4: Implement dataclasses**

Create `backend/domains/ai_reports/editorial_agent/models.py`:

```python
"""Structured models for the yearly editorial-agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    if value:
        return (str(value),)
    return ()


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    claim: str
    source: str
    kind: str
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "source": self.source,
            "kind": self.kind,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceItem":
        return cls(
            id=str(value.get("id") or ""),
            claim=str(value.get("claim") or ""),
            source=str(value.get("source") or ""),
            kind=str(value.get("kind") or ""),
            confidence=str(value.get("confidence") or "high"),
        )


@dataclass(frozen=True)
class StoryCandidate:
    id: str
    title: str
    why_it_matters: str
    evidence_refs: tuple[str, ...]
    risk_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "why_it_matters": self.why_it_matters,
            "evidence_refs": list(self.evidence_refs),
            "risk_notes": list(self.risk_notes),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StoryCandidate":
        return cls(
            id=str(value.get("id") or ""),
            title=str(value.get("title") or ""),
            why_it_matters=str(value.get("why_it_matters") or ""),
            evidence_refs=_tuple(value.get("evidence_refs")),
            risk_notes=_tuple(value.get("risk_notes")),
        )


@dataclass(frozen=True)
class ResearchBrief:
    period: dict[str, Any]
    evidence_ledger: tuple[EvidenceItem, ...]
    story_candidates: tuple[StoryCandidate, ...]
    tensions: tuple[dict[str, Any], ...]
    forbidden_inferences: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": dict(self.period),
            "evidence_ledger": [item.to_dict() for item in self.evidence_ledger],
            "story_candidates": [item.to_dict() for item in self.story_candidates],
            "tensions": [dict(item) for item in self.tensions],
            "forbidden_inferences": list(self.forbidden_inferences),
        }


@dataclass(frozen=True)
class ArticleSection:
    id: str
    heading: str
    purpose: str
    prose: str
    evidence_refs: tuple[str, ...]
    chart_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "heading": self.heading,
            "purpose": self.purpose,
            "prose": self.prose,
            "evidence_refs": list(self.evidence_refs),
            "chart_refs": list(self.chart_refs),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArticleSection":
        return cls(
            id=str(value.get("id") or ""),
            heading=str(value.get("heading") or ""),
            purpose=str(value.get("purpose") or ""),
            prose=str(value.get("prose") or ""),
            evidence_refs=_tuple(value.get("evidence_refs")),
            chart_refs=_tuple(value.get("chart_refs")),
        )


@dataclass(frozen=True)
class StorylinePlan:
    thesis: str
    title: str
    subtitle: str
    section_plan: tuple[ArticleSection, ...]
    must_not_write: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis": self.thesis,
            "title": self.title,
            "subtitle": self.subtitle,
            "section_plan": [section.to_dict() for section in self.section_plan],
            "must_not_write": list(self.must_not_write),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StorylinePlan":
        sections = tuple(
            ArticleSection.from_dict(item)
            for item in value.get("section_plan") or []
            if isinstance(item, dict)
        )
        return cls(
            thesis=str(value.get("thesis") or ""),
            title=str(value.get("title") or ""),
            subtitle=str(value.get("subtitle") or ""),
            section_plan=sections,
            must_not_write=_tuple(value.get("must_not_write")),
        )


@dataclass(frozen=True)
class ArticleDraft:
    title: str
    subtitle: str
    thesis: str
    sections: tuple[ArticleSection, ...]
    closing: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "thesis": self.thesis,
            "sections": [section.to_dict() for section in self.sections],
            "closing": self.closing,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArticleDraft":
        sections = tuple(
            ArticleSection.from_dict(item)
            for item in value.get("sections") or []
            if isinstance(item, dict)
        )
        return cls(
            title=str(value.get("title") or ""),
            subtitle=str(value.get("subtitle") or ""),
            thesis=str(value.get("thesis") or ""),
            sections=sections,
            closing=str(value.get("closing") or ""),
        )


@dataclass(frozen=True)
class ExtractedClaim:
    text: str
    claim_type: str
    matched_evidence_refs: tuple[str, ...] = ()
    status: str = "ambiguous"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "claim_type": self.claim_type,
            "matched_evidence_refs": list(self.matched_evidence_refs),
            "status": self.status,
        }


@dataclass(frozen=True)
class ClaimCheckResult:
    claims: tuple[ExtractedClaim, ...]
    unsupported_claims: tuple[str, ...]
    contradicted_claims: tuple[str, ...]
    ambiguous_claims: tuple[str, ...]
    scope_leaks: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (
            self.unsupported_claims
            or self.contradicted_claims
            or self.ambiguous_claims
            or self.scope_leaks
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "claims": [claim.to_dict() for claim in self.claims],
            "unsupported_claims": list(self.unsupported_claims),
            "contradicted_claims": list(self.contradicted_claims),
            "ambiguous_claims": list(self.ambiguous_claims),
            "scope_leaks": list(self.scope_leaks),
        }
```

- [ ] **Step 5: Run model tests and mypy subset**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_editorial_agent_models.py -q
.venv/bin/mypy backend/domains/ai_reports/editorial_agent/models.py
```

Expected: tests PASS; mypy exits 0.

---

## Task 2: Research Brief Builder

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/research_brief.py`
- Test: `backend/tests/unit/test_yearly_research_brief.py`

- [ ] **Step 1: Write research brief tests**

Create `backend/tests/unit/test_yearly_research_brief.py`:

```python
from backend.domains.ai_reports.editorial_agent.research_brief import build_research_brief


def _context():
    return {
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_plays": 7860, "total_minutes": 29882},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143, "top_track_plays": 4},
        "discovery_and_returns": {
            "new_artists": [
                {"name": "Zhang Zhen Yue", "first_seen": "2026-03-09", "plays": 574}
            ]
        },
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            },
            "playback_billboard_matrix": {
                "observations": [
                    "The Life of a Showgirl 是专辑里兼具高播放和长在榜的核心作品。"
                ]
            },
        },
    }


def test_research_brief_builds_story_candidates_from_context():
    brief = build_research_brief(_context())
    payload = brief.to_dict()
    candidate_ids = {item["id"] for item in payload["story_candidates"]}
    evidence_ids = {item["id"] for item in payload["evidence_ledger"]}

    assert payload["period"]["end_date"] == "2026-06-23"
    assert "stable_top_artist" in candidate_ids
    assert "monthly_turning_point" in candidate_ids
    assert "album_playback_billboard_alignment" in candidate_ids
    assert "highlight_day_density" in candidate_ids
    assert "discovery_signal" in candidate_ids
    assert "top_artist_taylor_swift" in evidence_ids
    assert "album_life_of_a_showgirl_alignment" in evidence_ids
    assert "不能编造通勤、考试、天气、地点、分手、旅行或加班。" in payload["forbidden_inferences"]


def test_research_brief_omits_empty_candidates():
    context = {"reporting_period": {"year": 2026}}
    brief = build_research_brief(context)

    assert brief.period["year"] == 2026
    assert brief.story_candidates == ()
    assert brief.evidence_ledger == ()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_research_brief.py -q
```

Expected: FAIL with missing `research_brief.py`.

- [ ] **Step 3: Implement research brief extraction**

Create `backend/domains/ai_reports/editorial_agent/research_brief.py`:

```python
"""Build research material for the yearly editorial agent."""

from __future__ import annotations

import re
from typing import Any

from backend.domains.ai_reports.editorial_agent.models import (
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
)


FORBIDDEN_INFERENCES = (
    "不能编造通勤、考试、天气、地点、分手、旅行或加班。",
    "不能把个人 Billboard 写成外部官方 Billboard。",
    "不能把 Spotify 流派标签写成互斥类别。",
)


def build_research_brief(context: dict[str, Any]) -> ResearchBrief:
    evidence: list[EvidenceItem] = []
    candidates: list[StoryCandidate] = []
    tensions: list[dict[str, Any]] = []

    period = _dict(context.get("reporting_period"))
    top_artists = _list(context.get("top_artists"))
    top_tracks = _list(context.get("top_tracks"))
    top_albums = _list(context.get("top_albums"))
    billboard = _dict(context.get("personal_billboard_year_end"))
    chart_data = _dict(context.get("chart_data"))

    top_artist = _first(top_artists)
    if top_artist:
        evidence_id = f"top_artist_{_slug(_name(top_artist))}"
        evidence.append(
            EvidenceItem(
                id=evidence_id,
                claim=f"{_name(top_artist)} 以 {_int(top_artist.get('plays'))} 次播放位列年度艺人第一。",
                source="top_artists[0]",
                kind="playback_rank",
            )
        )
        candidates.append(
            StoryCandidate(
                id="stable_top_artist",
                title=f"{_name(top_artist)} 是最稳定的回访对象",
                why_it_matters="它解释年度重心，而不是只复述艺人榜第一。",
                evidence_refs=(evidence_id,),
                risk_notes=("不能把第一名写成唯一偏好。",),
            )
        )

    monthly_observation = _first_observation(chart_data, "artist_monthly_trend")
    if monthly_observation:
        evidence.append(
            EvidenceItem(
                id="artist_monthly_turning_point",
                claim=monthly_observation,
                source="chart_data.artist_monthly_trend.observations[0]",
                kind="monthly_shift",
            )
        )
        candidates.append(
            StoryCandidate(
                id="monthly_turning_point",
                title="阶段性变化让年度主线不只看累计排名",
                why_it_matters="它能解释某个阶段的偏好变亮，而不是只看全年累计。",
                evidence_refs=("artist_monthly_turning_point",),
                risk_notes=("不能把阶段反超写成全年取代。",),
            )
        )

    top_album = _first(top_albums)
    chart_album = _first(_list(billboard.get("albums")))
    if top_album and chart_album:
        aligned = _name(top_album).casefold() == _name(chart_album).casefold()
        evidence_id = f"album_{_slug(_name(top_album))}_alignment"
        relation = "对齐" if aligned else "分歧"
        weeks = _int(chart_album.get("weeks_on_chart"))
        evidence.append(
            EvidenceItem(
                id=evidence_id,
                claim=f"{_name(top_album)} 的播放量和个人 Billboard 专辑表现{relation}，个人榜在榜 {weeks} 周。",
                source="top_albums[0]+personal_billboard_year_end.albums[0]",
                kind="playback_billboard_relation",
            )
        )
        candidates.append(
            StoryCandidate(
                id="album_playback_billboard_alignment" if aligned else "album_playback_billboard_tension",
                title="专辑热度和长留关系值得单独解释",
                why_it_matters="播放量回答当下反复选择，个人 Billboard 回答跨周留下。",
                evidence_refs=(evidence_id,),
                risk_notes=("如果对象相同，不能写成两种不同偏爱的冲突。",),
            )
        )
        tensions.append(
            {
                "id": "playback_billboard_album_relation",
                "summary": "播放量和个人 Billboard 专辑榜指向同一对象。"
                if aligned
                else "播放量和个人 Billboard 专辑榜指向不同对象。",
                "evidence_refs": [evidence_id],
            }
        )

    top_track = _first(top_tracks)
    if top_track:
        evidence.append(
            EvidenceItem(
                id=f"top_track_{_slug(_name(top_track))}",
                claim=f"{_name(top_track)} 以 {_int(top_track.get('plays'))} 次播放位列年度单曲第一。",
                source="top_tracks[0]",
                kind="playback_rank",
            )
        )

    highlight = _dict(context.get("highlight_day_detail"))
    if highlight.get("date"):
        evidence.append(
            EvidenceItem(
                id="highlight_day_density",
                claim=f"{highlight.get('date')} 有 {_int(highlight.get('plays'))} 次播放，最高单曲约 {_int(highlight.get('top_track_plays'))} 次。",
                source="highlight_day_detail",
                kind="day_density",
            )
        )
        candidates.append(
            StoryCandidate(
                id="highlight_day_density",
                title="最密集的一天更像播放密度变化",
                why_it_matters="它保留异常日的音乐存在感，但不编造当天发生了什么。",
                evidence_refs=("highlight_day_density",),
                risk_notes=("不能写现实事件，只能写播放密度。",),
            )
        )

    discovery = _first(_list(_dict(context.get("discovery_and_returns")).get("new_artists")))
    if discovery:
        evidence.append(
            EvidenceItem(
                id="new_artist_discovery",
                claim=f"{_name(discovery)} 首次出现于 {discovery.get('first_seen')}，累计 {_int(discovery.get('plays'))} 次播放。",
                source="discovery_and_returns.new_artists[0]",
                kind="discovery",
            )
        )
        candidates.append(
            StoryCandidate(
                id="discovery_signal",
                title=f"{_name(discovery)} 是新声音进入结构的证据",
                why_it_matters="它说明年度记录不只由熟悉对象构成。",
                evidence_refs=("new_artist_discovery",),
                risk_notes=("不能把新发现夸大成全年唯一主角。",),
            )
        )

    return ResearchBrief(
        period=period,
        evidence_ledger=tuple(evidence),
        story_candidates=tuple(candidates),
        tensions=tuple(tensions),
        forbidden_inferences=FORBIDDEN_INFERENCES,
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _slug(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return "_".join(tokens) or "unknown"


def _first_observation(chart_data: dict[str, Any], chart_id: str) -> str:
    observations = _dict(chart_data.get(chart_id)).get("observations")
    if isinstance(observations, list):
        for item in observations:
            text = str(item or "").strip()
            if text:
                return text
    return ""
```

- [ ] **Step 4: Run research brief tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_research_brief.py -q
```

Expected: PASS.

---

## Task 3: LLM Step Helpers and Prompts

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/prompts.py`
- Create: `backend/domains/ai_reports/editorial_agent/llm_steps.py`
- Test: `backend/tests/unit/test_yearly_storyline_planner.py`

- [ ] **Step 1: Write helper tests**

Create the first half of `backend/tests/unit/test_yearly_storyline_planner.py`:

```python
from backend.domains.ai_reports.editorial_agent.llm_steps import extract_json_object


def test_extract_json_object_reads_fenced_json():
    text = """模型说明
```json
{"title": "音乐年记", "sections": [1, 2]}
```
"""

    assert extract_json_object(text) == {"title": "音乐年记", "sections": [1, 2]}


def test_extract_json_object_returns_empty_dict_for_invalid_json():
    assert extract_json_object("不是 json") == {}
```

- [ ] **Step 2: Run helper tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_storyline_planner.py::test_extract_json_object_reads_fenced_json -q
```

Expected: FAIL with missing `llm_steps.py`.

- [ ] **Step 3: Add prompts**

Create `backend/domains/ai_reports/editorial_agent/prompts.py`:

```python
"""Prompts for the yearly editorial-agent pipeline."""

PLANNER_SYSTEM_PROMPT = """
你是 SpotifyStats 的年度音乐报告策划编辑。
你只基于 DATA 中的 Research Brief 规划文章主题和结构。
输出严格 JSON，不要 Markdown。
必须包含 thesis、title、subtitle、section_plan、must_not_write。
section_plan 每项包含 id、heading、purpose、evidence_refs、chart_refs。
不要按 TOP 艺人/TOP 单曲/TOP 专辑固定模块展开。
不要把个人 Billboard 写成外部官方 Billboard。
不要编造通勤、考试、天气、地点、分手、旅行或加班。
""".strip()

WRITER_SYSTEM_PROMPT = """
你是 SpotifyStats 的年度音乐年记作者。
你要把 Storyline Plan 写成自然中文文章，不是商业报告，不是榜单摘要。
输出严格 JSON，不要 Markdown。
每个 section 必须包含 id、heading、purpose、prose、evidence_refs、chart_refs。
少用“证据、画像、结构、尺度、重心、说明、意味着”。
可以写音乐如何在日常中反复出现，但不得编造具体生活事件。
每个事实出现后必须转化为用户音乐使用方式的解释。
个人 Billboard 必须保持本地个人榜单口径。
""".strip()

EDITOR_SYSTEM_PROMPT = """
你是 SpotifyStats 年度音乐报告的文字编辑。
你只能修改 DATA 中的 draft，不得新增 evidence 中没有的事实。
输出严格 JSON，不要 Markdown。
目标是删掉重复、降低术语密度、强化开头、缩短结尾、让文章更像写给用户的音乐年记。
不要新增通勤、考试、天气、地点、分手、旅行或加班等具体事件。
返回 revised_article、edit_notes、risk_flags。
""".strip()

REPAIR_SYSTEM_PROMPT = """
你是 SpotifyStats 年度音乐报告的事实修订编辑。
你只能根据 claim_check 中列出的问题定点改写正文。
输出严格 JSON，不要 Markdown。
必须删除或改写 unsupported、contradicted、ambiguous、scope_leak 声明。
不得改动已经支持的具体数字、日期、艺人、歌曲、专辑和个人 Billboard 口径。
""".strip()
```

- [ ] **Step 4: Add LLM helpers**

Create `backend/domains/ai_reports/editorial_agent/llm_steps.py`:

```python
"""LLM helpers for editorial-agent steps."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from backend.services.ai_insights_service import _llm_chat

ChatFn = Callable[[str, str, float], str | None]


def extract_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        raw = raw[start : end + 1] if start >= 0 and end > start else raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def call_json_step(
    system_prompt: str,
    payload: dict[str, Any],
    *,
    temperature: float,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    chat = chat_fn or _llm_chat
    text = chat(
        system_prompt,
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        temperature,
    )
    if not text:
        return {}
    return extract_json_object(text)
```

- [ ] **Step 5: Run helper tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_storyline_planner.py -q
```

Expected: helper tests PASS.

---

## Task 4: Storyline Planner

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/storyline_planner.py`
- Modify: `backend/tests/unit/test_yearly_storyline_planner.py`

- [ ] **Step 1: Add planner tests**

Append to `backend/tests/unit/test_yearly_storyline_planner.py`:

```python
from backend.domains.ai_reports.editorial_agent.models import (
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
)
from backend.domains.ai_reports.editorial_agent.storyline_planner import plan_storyline


def _brief():
    return ResearchBrief(
        period={"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        evidence_ledger=(
            EvidenceItem(
                id="top_artist_taylor",
                claim="Taylor Swift 以 1115 次播放位列年度艺人第一。",
                source="top_artists[0]",
                kind="playback_rank",
            ),
        ),
        story_candidates=(
            StoryCandidate(
                id="stable_top_artist",
                title="Taylor Swift 是稳定回访对象",
                why_it_matters="它解释年度重心。",
                evidence_refs=("top_artist_taylor",),
            ),
        ),
        tensions=(),
        forbidden_inferences=("不能编造生活事件。",),
    )


def test_plan_storyline_uses_llm_json_when_valid():
    def fake_chat(system_prompt: str, user_content: str, temperature: float) -> str:
        assert "年度音乐报告策划编辑" in system_prompt
        assert "stable_top_artist" in user_content
        assert temperature == 0.1
        return """
        {"thesis":"稳定回访构成上半年主线","title":"2026 音乐年记","subtitle":"稳定和变化同时存在","section_plan":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","evidence_refs":["top_artist_taylor"],"chart_refs":[]}],"must_not_write":["不要写成榜单摘要"]}
        """

    plan = plan_storyline(_brief(), chat_fn=fake_chat)

    assert plan.thesis == "稳定回访构成上半年主线"
    assert plan.section_plan[0].evidence_refs == ("top_artist_taylor",)


def test_plan_storyline_falls_back_when_llm_empty():
    plan = plan_storyline(_brief(), chat_fn=lambda *_args: "")

    assert plan.title
    assert plan.thesis
    assert plan.section_plan
    assert plan.section_plan[0].id == "opening"
```

- [ ] **Step 2: Run planner tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_storyline_planner.py -q
```

Expected: FAIL with missing `storyline_planner.py`.

- [ ] **Step 3: Implement planner**

Create `backend/domains/ai_reports/editorial_agent/storyline_planner.py`:

```python
"""Storyline planning for yearly editorial-agent reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn, call_json_step
from backend.domains.ai_reports.editorial_agent.models import ArticleSection, ResearchBrief, StorylinePlan
from backend.domains.ai_reports.editorial_agent.prompts import PLANNER_SYSTEM_PROMPT


def plan_storyline(brief: ResearchBrief, *, chat_fn: ChatFn | None = None) -> StorylinePlan:
    parsed = call_json_step(
        PLANNER_SYSTEM_PROMPT,
        {"research_brief": brief.to_dict()},
        temperature=0.1,
        chat_fn=chat_fn,
    )
    plan = _plan_from_payload(parsed)
    return plan if plan.section_plan and plan.thesis else _fallback_plan(brief)


def _plan_from_payload(payload: dict) -> StorylinePlan:
    return StorylinePlan.from_dict(
        {
            "thesis": payload.get("thesis"),
            "title": payload.get("title"),
            "subtitle": payload.get("subtitle"),
            "section_plan": payload.get("section_plan"),
            "must_not_write": payload.get("must_not_write"),
        }
    )


def _fallback_plan(brief: ResearchBrief) -> StorylinePlan:
    year = brief.period.get("year") or "这一年"
    end_date = brief.period.get("end_date")
    subtitle = f"截至 {end_date}，这是一份仍在展开的音乐年记。" if end_date else "一份个人音乐年记。"
    sections = [
        ArticleSection(
            id="opening",
            heading="今年还没有结束，但音乐重心已经出现",
            purpose="建立阶段性年报边界和主论点",
            prose="",
            evidence_refs=tuple(item.id for item in brief.evidence_ledger[:2]),
            chart_refs=(),
        )
    ]
    for candidate in brief.story_candidates[:5]:
        sections.append(
            ArticleSection(
                id=candidate.id,
                heading=candidate.title,
                purpose=candidate.why_it_matters,
                prose="",
                evidence_refs=candidate.evidence_refs,
                chart_refs=(),
            )
        )
    return StorylinePlan(
        thesis=f"{year} 的音乐记录需要同时看稳定回访、阶段变化和长期留下。",
        title=f"{year} 音乐年记",
        subtitle=subtitle,
        section_plan=tuple(sections),
        must_not_write=(
            "不要写成榜单摘要。",
            "不要编造具体生活事件。",
            "不要把个人 Billboard 写成外部官方 Billboard。",
        ),
    )
```

- [ ] **Step 4: Run planner tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_storyline_planner.py -q
```

Expected: PASS.

---

## Task 5: Writer and Editor

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/writer.py`
- Create: `backend/domains/ai_reports/editorial_agent/editor.py`
- Test: `backend/tests/unit/test_yearly_writer_editor.py`

- [ ] **Step 1: Write writer/editor tests**

Create `backend/tests/unit/test_yearly_writer_editor.py`:

```python
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
    StorylinePlan,
)
from backend.domains.ai_reports.editorial_agent.editor import edit_article
from backend.domains.ai_reports.editorial_agent.writer import write_article


def _brief():
    return ResearchBrief(
        period={"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        evidence_ledger=(
            EvidenceItem(
                id="top_artist_taylor",
                claim="Taylor Swift 以 1115 次播放位列年度艺人第一。",
                source="top_artists[0]",
                kind="playback_rank",
            ),
        ),
        story_candidates=(
            StoryCandidate(
                id="stable_top_artist",
                title="Taylor Swift 是稳定回访对象",
                why_it_matters="它解释年度重心。",
                evidence_refs=("top_artist_taylor",),
            ),
        ),
        tensions=(),
        forbidden_inferences=("不能编造生活事件。",),
    )


def _plan():
    return StorylinePlan(
        thesis="稳定回访构成上半年主线。",
        title="2026 音乐年记",
        subtitle="截至 2026-06-23，稳定和变化同时存在。",
        section_plan=(
            ArticleSection(
                id="opening",
                heading="重心已经出现",
                purpose="建立主论点",
                prose="",
                evidence_refs=("top_artist_taylor",),
                chart_refs=(),
            ),
        ),
        must_not_write=("不要写成榜单摘要。",),
    )


def test_write_article_uses_llm_sections():
    def fake_chat(_system_prompt: str, user_content: str, _temperature: float) -> str:
        assert "top_artist_taylor" in user_content
        return """
        {"title":"2026 音乐年记","subtitle":"截至 2026-06-23，稳定和变化同时存在。","thesis":"稳定回访构成上半年主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 不是偶然出现的名字，而是你上半年反复回到的声音。","evidence_refs":["top_artist_taylor"],"chart_refs":[]}],"closing":"这份记录还在展开。"}
        """

    draft = write_article(_brief(), _plan(), chart_data={}, chat_fn=fake_chat)

    assert draft.sections[0].prose.startswith("Taylor Swift")
    assert draft.closing == "这份记录还在展开。"


def test_edit_article_accepts_revised_article_and_notes():
    draft = ArticleDraft(
        title="2026 音乐年记",
        subtitle="截至 2026-06-23",
        thesis="稳定回访构成上半年主线。",
        sections=(
            ArticleSection(
                id="opening",
                heading="重心已经出现",
                purpose="建立主论点",
                prose="证据说明 Taylor Swift 是稳定中心。证据说明 Taylor Swift 是稳定中心。",
                evidence_refs=("top_artist_taylor",),
                chart_refs=(),
            ),
        ),
        closing="继续观察走势。",
    )

    def fake_chat(_system_prompt: str, _user_content: str, _temperature: float) -> str:
        return """
        {"revised_article":{"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"稳定回访构成上半年主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 更像你上半年反复回到的声音。","evidence_refs":["top_artist_taylor"],"chart_refs":[]}],"closing":"这份记录还在展开。"},"edit_notes":["删除重复句"],"risk_flags":[]}
        """

    edited = edit_article(_brief(), _plan(), draft, chat_fn=fake_chat)

    assert edited.article.sections[0].prose == "Taylor Swift 更像你上半年反复回到的声音。"
    assert edited.edit_notes == ("删除重复句",)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_writer_editor.py -q
```

Expected: FAIL with missing `writer.py` and `editor.py`.

- [ ] **Step 3: Extend models for edited article**

Append to `backend/domains/ai_reports/editorial_agent/models.py`:

```python
@dataclass(frozen=True)
class EditedArticle:
    article: ArticleDraft
    edit_notes: tuple[str, ...]
    risk_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "article": self.article.to_dict(),
            "edit_notes": list(self.edit_notes),
            "risk_flags": list(self.risk_flags),
        }
```

- [ ] **Step 4: Implement writer**

Create `backend/domains/ai_reports/editorial_agent/writer.py`:

```python
"""Longform article writer for yearly editorial-agent reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn, call_json_step
from backend.domains.ai_reports.editorial_agent.models import ArticleDraft, ResearchBrief, StorylinePlan
from backend.domains.ai_reports.editorial_agent.prompts import WRITER_SYSTEM_PROMPT


def write_article(
    brief: ResearchBrief,
    plan: StorylinePlan,
    *,
    chart_data: dict,
    chat_fn: ChatFn | None = None,
) -> ArticleDraft:
    parsed = call_json_step(
        WRITER_SYSTEM_PROMPT,
        {
            "research_brief": brief.to_dict(),
            "storyline_plan": plan.to_dict(),
            "chart_data_keys": sorted(chart_data),
        },
        temperature=0.35,
        chat_fn=chat_fn,
    )
    draft = ArticleDraft.from_dict(parsed)
    return draft if draft.sections and draft.title else _fallback_draft(plan)


def _fallback_draft(plan: StorylinePlan) -> ArticleDraft:
    sections = tuple(
        section.__class__(
            id=section.id,
            heading=section.heading,
            purpose=section.purpose,
            prose=f"{section.heading}。这一节需要围绕 {section.purpose} 展开。",
            evidence_refs=section.evidence_refs,
            chart_refs=section.chart_refs,
        )
        for section in plan.section_plan
    )
    return ArticleDraft(
        title=plan.title,
        subtitle=plan.subtitle,
        thesis=plan.thesis,
        sections=sections,
        closing="这份记录保留了当前数据能支持的音乐变化。",
    )
```

- [ ] **Step 5: Implement editor**

Create `backend/domains/ai_reports/editorial_agent/editor.py`:

```python
"""Editorial rewrite pass for yearly reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn, call_json_step
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    EditedArticle,
    ResearchBrief,
    StorylinePlan,
)
from backend.domains.ai_reports.editorial_agent.prompts import EDITOR_SYSTEM_PROMPT


def edit_article(
    brief: ResearchBrief,
    plan: StorylinePlan,
    draft: ArticleDraft,
    *,
    chat_fn: ChatFn | None = None,
) -> EditedArticle:
    parsed = call_json_step(
        EDITOR_SYSTEM_PROMPT,
        {
            "research_brief": brief.to_dict(),
            "storyline_plan": plan.to_dict(),
            "draft": draft.to_dict(),
        },
        temperature=0.2,
        chat_fn=chat_fn,
    )
    revised = parsed.get("revised_article") if isinstance(parsed.get("revised_article"), dict) else {}
    article = ArticleDraft.from_dict(revised)
    if not article.sections:
        article = _deterministic_cleanup(draft)
    return EditedArticle(
        article=article,
        edit_notes=tuple(str(item) for item in parsed.get("edit_notes") or [] if str(item).strip()),
        risk_flags=tuple(str(item) for item in parsed.get("risk_flags") or [] if str(item).strip()),
    )


def _deterministic_cleanup(draft: ArticleDraft) -> ArticleDraft:
    return ArticleDraft(
        title=draft.title,
        subtitle=draft.subtitle,
        thesis=draft.thesis,
        sections=tuple(
            section.__class__(
                id=section.id,
                heading=section.heading,
                purpose=section.purpose,
                prose=_dedupe_sentences(section.prose),
                evidence_refs=section.evidence_refs,
                chart_refs=section.chart_refs,
            )
            for section in draft.sections
        ),
        closing=_dedupe_sentences(draft.closing),
    )


def _dedupe_sentences(text: str) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for sentence in [part.strip() for part in text.split("。") if part.strip()]:
        if sentence in seen:
            continue
        seen.add(sentence)
        output.append(sentence)
    return "。".join(output) + ("。" if output else "")
```

- [ ] **Step 6: Run writer/editor tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_writer_editor.py -q
```

Expected: PASS.

---

## Task 6: Claim Checker

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/claim_checker.py`
- Test: `backend/tests/unit/test_yearly_claim_checker.py`

- [ ] **Step 1: Write claim checker tests**

Create `backend/tests/unit/test_yearly_claim_checker.py`:

```python
from backend.domains.ai_reports.editorial_agent.claim_checker import check_article_claims
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    EvidenceItem,
    ResearchBrief,
)


def _article(text: str):
    return ArticleDraft(
        title="2026 音乐年记",
        subtitle="截至 2026-06-23",
        thesis="稳定和变化同时存在。",
        sections=(
            ArticleSection(
                id="opening",
                heading="重心出现",
                purpose="建立主论点",
                prose=text,
                evidence_refs=("top_artist_taylor",),
                chart_refs=(),
            ),
        ),
        closing="",
    )


def _brief():
    return ResearchBrief(
        period={"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        evidence_ledger=(
            EvidenceItem(
                id="top_artist_taylor",
                claim="Taylor Swift 以 1115 次播放位列年度艺人第一。",
                source="top_artists[0]",
                kind="playback_rank",
            ),
            EvidenceItem(
                id="artist_monthly_turning_point",
                claim="Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。",
                source="chart_data.artist_monthly_trend.observations[0]",
                kind="monthly_shift",
            ),
        ),
        story_candidates=(),
        tensions=(),
        forbidden_inferences=("不能编造通勤、考试、天气、地点、分手、旅行或加班。",),
    )


def test_claim_checker_passes_supported_entities_and_numbers():
    result = check_article_claims(
        _article("Taylor Swift 以 1115 次播放成为你当前年度艺人第一。"),
        _brief(),
    )

    assert result.ok is True
    assert result.claims
    assert result.claims[0].matched_evidence_refs == ("top_artist_taylor",)


def test_claim_checker_flags_unsupported_life_event():
    result = check_article_claims(_article("这像一次通勤路上的陪伴。"), _brief())

    assert result.ok is False
    assert result.unsupported_claims == ("这像一次通勤路上的陪伴。",)


def test_claim_checker_flags_external_billboard_scope_leak():
    result = check_article_claims(_article("这张专辑登上了官方 Billboard。"), _brief())

    assert result.ok is False
    assert result.scope_leaks == ("这张专辑登上了官方 Billboard。",)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_claim_checker.py -q
```

Expected: FAIL with missing `claim_checker.py`.

- [ ] **Step 3: Implement claim checker**

Create `backend/domains/ai_reports/editorial_agent/claim_checker.py`:

```python
"""Deterministic claim checks for editorial-agent yearly reports."""

from __future__ import annotations

import re

from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ClaimCheckResult,
    ExtractedClaim,
    ResearchBrief,
)

UNSUPPORTED_LIFE_TERMS = ("通勤", "考试", "天气", "下雨", "分手", "旅行", "加班")
EXTERNAL_BILLBOARD_TERMS = ("官方 Billboard", "外部 Billboard", "美国 Billboard")


def check_article_claims(article: ArticleDraft, brief: ResearchBrief) -> ClaimCheckResult:
    evidence = {item.id: item.claim for item in brief.evidence_ledger}
    unsupported: list[str] = []
    ambiguous: list[str] = []
    scope_leaks: list[str] = []
    claims: list[ExtractedClaim] = []

    for sentence in _sentences(_article_text(article)):
        if any(term in sentence for term in UNSUPPORTED_LIFE_TERMS):
            unsupported.append(sentence)
            continue
        if any(term in sentence for term in EXTERNAL_BILLBOARD_TERMS):
            scope_leaks.append(sentence)
            continue
        if _contains_fact_signal(sentence):
            refs = _matched_refs(sentence, evidence)
            if refs:
                claims.append(
                    ExtractedClaim(
                        text=sentence,
                        claim_type="fact",
                        matched_evidence_refs=refs,
                        status="supported",
                    )
                )
            else:
                ambiguous.append(sentence)

    return ClaimCheckResult(
        claims=tuple(claims),
        unsupported_claims=tuple(unsupported),
        contradicted_claims=(),
        ambiguous_claims=tuple(ambiguous),
        scope_leaks=tuple(scope_leaks),
    )


def _article_text(article: ArticleDraft) -> str:
    return "\n".join([article.title, article.subtitle, article.thesis, *(s.prose for s in article.sections), article.closing])


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]


def _contains_fact_signal(sentence: str) -> bool:
    return bool(re.search(r"\d", sentence)) or any(
        token in sentence for token in ("第一", "超过", "高过", "个人 Billboard", "播放")
    )


def _matched_refs(sentence: str, evidence: dict[str, str]) -> tuple[str, ...]:
    sentence_tokens = set(_tokens(sentence))
    refs: list[str] = []
    for evidence_id, claim in evidence.items():
        evidence_tokens = set(_tokens(claim))
        if len(sentence_tokens & evidence_tokens) >= min(3, len(evidence_tokens)):
            refs.append(evidence_id)
    return tuple(refs)


def _tokens(text: str) -> list[str]:
    tokens = re.findall(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d+\s*次|\d+\s*周|\d+", text)
    tokens.extend(re.findall(r"[A-Za-z][A-Za-z'&. -]{2,}", text))
    tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,}", text))
    return [token.strip().casefold() for token in tokens if token.strip()]
```

- [ ] **Step 4: Run claim checker tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_claim_checker.py -q
```

Expected: PASS.

---

## Task 7: Taste Rubric

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/taste_rubric.py`
- Create: `scripts/evaluate_yearly_report_taste.py`
- Test: `backend/tests/unit/test_yearly_taste_rubric.py`

- [ ] **Step 1: Write taste rubric tests**

Create `backend/tests/unit/test_yearly_taste_rubric.py`:

```python
from backend.domains.ai_reports.editorial_agent.models import ArticleDraft, ArticleSection
from backend.domains.ai_reports.editorial_agent.taste_rubric import score_article_taste


def _article(prose: str, closing: str = "这份记录还在展开。"):
    return ArticleDraft(
        title="2026 音乐年记",
        subtitle="截至 2026-06-23",
        thesis="Taylor Swift 的稳定回访、Olivia Rodrigo 的阶段升温和 The Life of a Showgirl 的长留共同构成主线。",
        sections=(
            ArticleSection(
                id="opening",
                heading="重心出现",
                purpose="建立主论点",
                prose=prose,
                evidence_refs=("top_artist_taylor",),
                chart_refs=("artist_monthly_trend",),
            ),
        ),
        closing=closing,
    )


def test_taste_rubric_rewards_article_with_thesis_and_specific_entities():
    score = score_article_taste(
        _article(
            "Taylor Swift 反复出现，Olivia Rodrigo 在 2026-05 变亮，The Life of a Showgirl 同时留在播放量和个人 Billboard 里。"
        )
    )

    assert score.total >= 26
    assert score.dimensions["年度主题"] >= 4
    assert score.dimensions["事实安全"] == 5


def test_taste_rubric_penalizes_jargon_and_weak_closing():
    score = score_article_taste(
        _article(
            "证据说明年度画像的结构和尺度形成稳定重心。综合来看，第二层证据构成三榜联动。",
            closing="后续观察走势。",
        )
    )

    assert score.total < 26
    assert score.dimensions["可读性"] < 4
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_taste_rubric.py -q
```

Expected: FAIL with missing `taste_rubric.py`.

- [ ] **Step 3: Extend models for taste score**

Append to `backend/domains/ai_reports/editorial_agent/models.py`:

```python
@dataclass(frozen=True)
class TasteScore:
    dimensions: dict[str, int]
    notes: tuple[str, ...]

    @property
    def total(self) -> int:
        return sum(self.dimensions.values())

    @property
    def ok(self) -> bool:
        return (
            self.total >= 26
            and self.dimensions.get("事实安全", 0) == 5
            and self.dimensions.get("文章感", 0) >= 4
            and self.dimensions.get("年度主题", 0) >= 4
            and self.dimensions.get("可读性", 0) >= 4
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "total": self.total,
            "dimensions": dict(self.dimensions),
            "notes": list(self.notes),
        }
```

- [ ] **Step 4: Implement rubric**

Create `backend/domains/ai_reports/editorial_agent/taste_rubric.py`:

```python
"""Taste rubric for yearly editorial-agent reports."""

from __future__ import annotations

from backend.domains.ai_reports.editorial_agent.models import ArticleDraft, TasteScore

JARGON = ("证据", "画像", "结构", "尺度", "重心", "综合来看", "三榜联动", "第二层证据")
SPECIFIC_MARKERS = ("Taylor Swift", "Olivia Rodrigo", "The Life of a Showgirl", "个人 Billboard", "2026-05")


def score_article_taste(article: ArticleDraft) -> TasteScore:
    text = _text(article)
    notes: list[str] = []
    dimensions = {
        "文章感": _article_feel(text),
        "年度主题": _theme_score(article),
        "洞见密度": _insight_score(text),
        "个人化": _specificity_score(text),
        "事实安全": _fact_safety_score(text),
        "可读性": _readability_score(text),
        "图文融合": _visual_score(article),
    }
    if dimensions["可读性"] < 4:
        notes.append("抽象术语或模板词偏多。")
    if dimensions["年度主题"] < 4:
        notes.append("缺少清楚年度主题。")
    if "后续观察走势" in text:
        notes.append("结尾仍像模板展望。")
    return TasteScore(dimensions=dimensions, notes=tuple(notes))


def _text(article: ArticleDraft) -> str:
    return "\n".join([article.title, article.subtitle, article.thesis, *(s.prose for s in article.sections), article.closing])


def _article_feel(text: str) -> int:
    if any(term in text for term in ("我查了什么", "依据", "自检与限制")):
        return 2
    return 5 if len(text) >= 500 else 4


def _theme_score(article: ArticleDraft) -> int:
    thesis = article.thesis.strip()
    if len(thesis) >= 24 and any(marker in thesis for marker in ("共同", "构成", "不是", "而是", "同时")):
        return 5
    return 3 if thesis else 1


def _insight_score(text: str) -> int:
    markers = sum(text.count(marker) for marker in ("不是", "而是", "同时", "反复", "留下", "变亮", "长留"))
    return 5 if markers >= 5 else 4 if markers >= 3 else 2


def _specificity_score(text: str) -> int:
    hits = sum(1 for marker in SPECIFIC_MARKERS if marker in text)
    return 5 if hits >= 4 else 4 if hits >= 3 else 2


def _fact_safety_score(text: str) -> int:
    unsafe = ("通勤", "考试", "下雨", "分手", "旅行", "加班", "官方 Billboard")
    return 3 if any(term in text for term in unsafe) else 5


def _readability_score(text: str) -> int:
    jargon_hits = sum(text.count(term) for term in JARGON)
    if jargon_hits >= 6:
        return 2
    if jargon_hits >= 3:
        return 3
    return 5


def _visual_score(article: ArticleDraft) -> int:
    refs = {ref for section in article.sections for ref in section.chart_refs}
    return 5 if refs else 3
```

- [ ] **Step 5: Add CLI evaluator**

Create `scripts/evaluate_yearly_report_taste.py`:

```python
#!/usr/bin/env python3
"""Evaluate yearly report taste from a saved task/probe JSON payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-input", required=True)
    parser.add_argument("--min-total", type=int, default=26)
    args = parser.parse_args()
    payload = json.loads(Path(args.json_input).read_text())
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    taste = summary.get("taste_score") or summary.get("metadata", {}).get("taste_score") or {}
    total = int(taste.get("total") or 0)
    ok = bool(taste.get("ok")) and total >= args.min_total
    print(json.dumps({"ok": ok, "total": total, "taste_score": taste}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run rubric tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_taste_rubric.py -q
python -m py_compile scripts/evaluate_yearly_report_taste.py
```

Expected: PASS.

---

## Task 8: Editorial Agent Pipeline Orchestrator

**Files:**
- Create: `backend/domains/ai_reports/editorial_agent/pipeline.py`
- Test: `backend/tests/unit/test_yearly_editorial_agent_pipeline.py`

- [ ] **Step 1: Write pipeline tests**

Create `backend/tests/unit/test_yearly_editorial_agent_pipeline.py`:

```python
from backend.domains.ai_reports.editorial_agent.pipeline import run_editorial_agent_pipeline


def test_pipeline_returns_article_sections_and_metadata():
    context = {
        "reporting_period": {"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
        "top_tracks": [{"name": "Opalite", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "weeks_on_chart": 24}]
        },
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            }
        },
    }

    def fake_chat(system_prompt: str, user_content: str, temperature: float) -> str:
        if "策划编辑" in system_prompt:
            return '{"thesis":"Taylor Swift 的稳定回访和 Olivia Rodrigo 的阶段升温共同构成主线。","title":"2026 音乐年记","subtitle":"截至 2026-06-23","section_plan":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","evidence_refs":["top_artist_taylor_swift","artist_monthly_turning_point"],"chart_refs":["artist_monthly_trend"]}],"must_not_write":["不要写成榜单摘要"]}'
        if "年度音乐年记作者" in system_prompt:
            return '{"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"Taylor Swift 的稳定回访和 Olivia Rodrigo 的阶段升温共同构成主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 以 1115 次播放反复出现，Olivia Rodrigo 在 2026-05 变亮，The Life of a Showgirl 也留在个人 Billboard 里。","evidence_refs":["top_artist_taylor_swift","artist_monthly_turning_point"],"chart_refs":["artist_monthly_trend"]}],"closing":"这份记录还在展开。"}'
        return '{"revised_article":{"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"Taylor Swift 的稳定回访和 Olivia Rodrigo 的阶段升温共同构成主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 以 1115 次播放反复出现，Olivia Rodrigo 在 2026-05 变亮，The Life of a Showgirl 也留在个人 Billboard 里。","evidence_refs":["top_artist_taylor_swift","artist_monthly_turning_point"],"chart_refs":["artist_monthly_trend"]}],"closing":"这份记录还在展开。"},"edit_notes":["保留具体实体"],"risk_flags":[]}'

    result = run_editorial_agent_pipeline(context, chart_data=context["chart_data"], chat_fn=fake_chat)

    assert result["metadata"]["writer_pipeline_version"] == "yearly_editorial_agent_v1"
    assert result["metadata"]["claim_check_passed"] is True
    assert result["metadata"]["taste_score"]["total"] >= 26
    assert result["article"].sections[0].heading == "重心已经出现"
```

- [ ] **Step 2: Run pipeline tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_editorial_agent_pipeline.py -q
```

Expected: FAIL with missing `pipeline.py`.

- [ ] **Step 3: Implement pipeline**

Create `backend/domains/ai_reports/editorial_agent/pipeline.py`:

```python
"""Orchestration for the yearly editorial-agent writing pipeline."""

from __future__ import annotations

from typing import Any

from backend.domains.ai_reports.editorial_agent import (
    RESEARCH_BRIEF_VERSION,
    WRITER_PIPELINE_VERSION,
)
from backend.domains.ai_reports.editorial_agent.claim_checker import check_article_claims
from backend.domains.ai_reports.editorial_agent.editor import edit_article
from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn
from backend.domains.ai_reports.editorial_agent.models import ArticleDraft
from backend.domains.ai_reports.editorial_agent.research_brief import build_research_brief
from backend.domains.ai_reports.editorial_agent.storyline_planner import plan_storyline
from backend.domains.ai_reports.editorial_agent.taste_rubric import score_article_taste
from backend.domains.ai_reports.editorial_agent.writer import write_article


def run_editorial_agent_pipeline(
    context: dict[str, Any],
    *,
    chart_data: dict[str, Any],
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    brief = build_research_brief({**context, "chart_data": chart_data})
    plan = plan_storyline(brief, chat_fn=chat_fn)
    draft = write_article(brief, plan, chart_data=chart_data, chat_fn=chat_fn)
    edited = edit_article(brief, plan, draft, chat_fn=chat_fn)
    claim_check = check_article_claims(edited.article, brief)
    article = edited.article
    if not claim_check.ok:
        article = _remove_failed_sentences(article, claim_check.unsupported_claims + claim_check.scope_leaks)
        claim_check = check_article_claims(article, brief)
    taste = score_article_taste(article)
    return {
        "article": article,
        "research_brief": brief,
        "storyline_plan": plan,
        "edit_notes": edited.edit_notes,
        "risk_flags": edited.risk_flags,
        "claim_check": claim_check,
        "taste_score": taste,
        "metadata": {
            "writer_pipeline_version": WRITER_PIPELINE_VERSION,
            "research_brief_version": RESEARCH_BRIEF_VERSION,
            "claim_check_passed": claim_check.ok,
            "editorial_review_passed": len(edited.risk_flags) == 0,
            "taste_score": taste.to_dict(),
        },
    }


def _remove_failed_sentences(article: ArticleDraft, failed_sentences: tuple[str, ...]) -> ArticleDraft:
    if not failed_sentences:
        return article
    failed = set(failed_sentences)
    return ArticleDraft(
        title=article.title,
        subtitle=article.subtitle,
        thesis=article.thesis,
        sections=tuple(
            section.__class__(
                id=section.id,
                heading=section.heading,
                purpose=section.purpose,
                prose=_strip_sentences(section.prose, failed),
                evidence_refs=section.evidence_refs,
                chart_refs=section.chart_refs,
            )
            for section in article.sections
        ),
        closing=_strip_sentences(article.closing, failed),
    )


def _strip_sentences(text: str, failed: set[str]) -> str:
    parts = [part.strip() for part in text.split("。") if part.strip()]
    kept = [part for part in parts if part not in failed]
    return "。".join(kept) + ("。" if kept else "")
```

- [ ] **Step 4: Run pipeline tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_editorial_agent_pipeline.py -q
```

Expected: PASS.

---

## Task 9: Integrate Pipeline Into Visual Yearly Artifact Service

**Files:**
- Modify: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Modify: `backend/services/ai_task_service.py`
- Modify: `backend/models/ai_tasks.py`
- Modify: `backend/services/ai_insights_service.py`
- Test: `backend/tests/unit/test_visual_yearly_artifact_service.py`
- Test: `backend/tests/unit/test_ai_report_tasks.py`
- Test: `backend/tests/contract/test_yearly_editorial_agent_contract.py`

- [ ] **Step 1: Add request and metadata contract tests**

Create `backend/tests/contract/test_yearly_editorial_agent_contract.py`:

```python
from backend.domains.ai_reports.editorial_agent import WRITER_PIPELINE_VERSION


def test_writer_pipeline_version_constant_is_cache_safe():
    assert WRITER_PIPELINE_VERSION == "yearly_editorial_agent_v1"
```

Add to `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
def test_visual_yearly_artifact_can_use_editorial_agent_pipeline(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    def fake_research(_request, emit_event=None):
        return [], {
            "reporting_period": {"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
            "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
            "top_tracks": [{"name": "Opalite", "plays": 123}],
            "top_albums": [{"name": "The Life of a Showgirl", "plays": 445}],
            "personal_billboard_year_end": {"albums": [{"name": "The Life of a Showgirl", "weeks_on_chart": 24}]},
        }

    class FakeArticle:
        title = "2026 音乐年记"
        subtitle = "截至 2026-06-23"
        thesis = "Taylor Swift 的稳定回访和 The Life of a Showgirl 的长留共同构成主线。"
        sections = ()
        closing = "这份记录还在展开。"

    def fake_pipeline(context, *, chart_data, chat_fn=None):
        del context, chart_data, chat_fn
        return {
            "article": FakeArticle(),
            "metadata": {
                "writer_pipeline_version": "yearly_editorial_agent_v1",
                "claim_check_passed": True,
                "editorial_review_passed": True,
                "taste_score": {"ok": True, "total": 30},
            },
            "research_brief": None,
            "storyline_plan": None,
            "claim_check": None,
            "taste_score": None,
            "edit_notes": (),
            "risk_flags": (),
        }

    monkeypatch.setattr(svc, "_run_visual_research", fake_research)
    monkeypatch.setattr(svc, "build_narrative_brief", lambda context: {"main_story": "x"})
    monkeypatch.setattr(svc, "chart_coverage", lambda context: {})
    monkeypatch.setattr(svc, "build_visual_brief", lambda *args, **kwargs: {"chart_specs": []})
    monkeypatch.setattr(svc, "build_visual_chart_data", lambda context, chart_specs: {})
    monkeypatch.setattr(svc, "build_story_insights", lambda context, narrative: {})
    monkeypatch.setattr(svc, "run_editorial_agent_pipeline", fake_pipeline)

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "editorial_agent_v1"}
    )

    assert result["metadata"]["writer_pipeline_version"] == "yearly_editorial_agent_v1"
    assert result["metadata"]["claim_check_passed"] is True
```

- [ ] **Step 2: Run integration tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_yearly_editorial_agent_contract.py backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_can_use_editorial_agent_pipeline -q
```

Expected: FAIL because `visual_yearly_artifact_service` does not expose the new pipeline call.

- [ ] **Step 3: Add request flag model**

Modify `backend/models/ai_tasks.py` to add an optional request field:

```python
writer_pipeline: str | None = Field(
    default=None,
    description="Optional yearly report writer pipeline, e.g. editorial_agent_v1.",
)
```

Ensure `backend/services/ai_task_service.py` keeps the field when normalizing report requests. If there is a whitelist or request dict builder, add:

```python
"writer_pipeline": request.get("writer_pipeline"),
```

- [ ] **Step 4: Add pipeline hook to visual artifact service**

Modify imports and helpers in `backend/domains/ai_reports/visual_yearly_artifact_service.py`:

```python
from backend.domains.ai_reports.editorial_agent.pipeline import run_editorial_agent_pipeline
```

Add helper:

```python
def _should_use_editorial_agent(request: dict[str, Any]) -> bool:
    return str(request.get("writer_pipeline") or "").strip() == "editorial_agent_v1"
```

Inside `generate_visual_yearly_artifact`, after `chart_data` is built and before deterministic `_compose_sections`, branch:

```python
editorial_agent_result = None
if _should_use_editorial_agent(request):
    _emit(
        emit_event,
        "stage_started",
        "正在选择年度主题",
        "planning_storyline",
        0.72,
    )
    editorial_agent_result = run_editorial_agent_pipeline(context, chart_data=chart_data)
```

When composing sections, use a converter:

```python
sections = (
    _sections_from_editorial_agent(editorial_agent_result["article"])
    if editorial_agent_result
    else _compose_sections(
        context,
        narrative,
        story_insights,
        visual,
        editorial_plan=editorial_plan,
    )
)
```

Add converter:

```python
def _sections_from_editorial_agent(article: Any) -> list[_Section]:
    sections = []
    for item in getattr(article, "sections", ()):
        sections.append(
            _Section(
                id=str(getattr(item, "id", "")),
                role=str(getattr(item, "id", "")),
                heading=str(getattr(item, "heading", "")),
                deck=str(getattr(item, "purpose", "")),
                prose=str(getattr(item, "prose", "")),
                chart_refs=tuple(getattr(item, "chart_refs", ())),
                evidence_refs=tuple(getattr(item, "evidence_refs", ())),
            )
        )
    return sections
```

Merge metadata:

```python
agent_metadata = editorial_agent_result.get("metadata") if editorial_agent_result else {}
metadata = {
    ...,
    **agent_metadata,
}
```

- [ ] **Step 5: Include writer pipeline in visual cache key**

In `backend/services/ai_insights_service.py`, wherever visual yearly cache mode/contract is composed, add `writer_pipeline` to the cache discriminator. If cache helper only accepts `report_mode`, encode:

```python
report_mode = (
    f"{VISUAL_YEARLY_REPORT_MODE}:{request.get('writer_pipeline')}"
    if request.get("writer_pipeline")
    else VISUAL_YEARLY_REPORT_MODE
)
```

In `backend/services/ai_task_service.py`, keep result metadata unchanged for UI, but use the same discriminator for cache read/write. Add a unit test asserting a cache-only request without `writer_pipeline` does not return a cached `writer_pipeline=editorial_agent_v1` artifact.

- [ ] **Step 6: Run integration tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_yearly_editorial_agent_contract.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_ai_report_tasks.py -q
```

Expected: PASS.

---

## Task 10: Task Progress and Frontend Metadata

**Files:**
- Modify: `backend/services/ai_task_service.py`
- Modify: `frontend/src/features/ai-tasks/AITaskProgress.tsx`
- Modify: `frontend/src/features/ai-insights/ReportCard.tsx`
- Modify: `frontend/src/tests/ai-task-components.test.tsx`
- Modify: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Add frontend tests for progress labels**

Add to `frontend/src/tests/ai-task-components.test.tsx`:

```tsx
it('renders yearly editorial agent progress stages', () => {
  render(
    <AITaskProgress
      task={{
        task_id: 'task-1',
        task_type: 'ai_report_yearly',
        status: 'running',
        stage: 'editing_article',
        progress_pct: 0.82,
        message: '正在编辑成稿',
        created_at: '2026-07-04 00:00:00',
        updated_at: '2026-07-04 00:00:01',
        result: null,
        error: null,
      }}
      events={[]}
    />
  )

  expect(screen.getByText(/正在编辑成稿/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Add metadata badge test**

Add to `frontend/src/tests/visual-yearly-report.test.tsx`:

```tsx
it('shows editorial agent metadata badges', () => {
  render(
    <ReportCard
      title="年度叙事"
      reportType="yearly"
      report="正文"
      artifact={null}
      cached={false}
      cachedAt="2026-07-04 00:00:00"
      entities={null}
      metadata={{
        writer_pipeline_version: 'yearly_editorial_agent_v1',
        claim_check_passed: true,
        editorial_review_passed: true,
        taste_score: { ok: true, total: 30 },
      }}
      loading={false}
      fetching={false}
      error={null}
      onRetry={() => undefined}
    />
  )

  expect(screen.getByText('Editorial Agent')).toBeInTheDocument()
  expect(screen.getByText('事实已核对')).toBeInTheDocument()
  expect(screen.getByText('口味评分 30')).toBeInTheDocument()
})
```

- [ ] **Step 3: Run frontend tests and confirm failure**

Run:

```bash
cd frontend && npm test -- --run src/tests/ai-task-components.test.tsx src/tests/visual-yearly-report.test.tsx
```

Expected: FAIL until labels/badges are added.

- [ ] **Step 4: Add stage labels**

Modify `frontend/src/features/ai-tasks/AITaskProgress.tsx` stage label map:

```ts
const STAGE_LABELS: Record<string, string> = {
  researching_year: '正在整理年度证据',
  planning_storyline: '正在选择年度主题',
  drafting_article: '正在撰写年报正文',
  editing_article: '正在编辑成稿',
  checking_claims: '正在核对事实口径',
  assembling_artifact: '正在生成图文年报',
}
```

Merge with existing labels instead of replacing unrelated stages.

- [ ] **Step 5: Add ReportCard badges**

In `frontend/src/features/ai-insights/ReportCard.tsx`, derive:

```tsx
const writerPipeline = typeof metadata?.writer_pipeline_version === 'string'
  ? metadata.writer_pipeline_version
  : null
const claimCheckPassed = typeof metadata?.claim_check_passed === 'boolean'
  ? metadata.claim_check_passed
  : null
const editorialReviewPassed = typeof metadata?.editorial_review_passed === 'boolean'
  ? metadata.editorial_review_passed
  : null
const tasteScore = isRecord(metadata?.taste_score) && typeof metadata.taste_score.total === 'number'
  ? metadata.taste_score.total
  : null
```

Render badges inside the existing metadata badge row:

```tsx
{writerPipeline === 'yearly_editorial_agent_v1' && (
  <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
    Editorial Agent
  </span>
)}
{claimCheckPassed === true && (
  <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
    事实已核对
  </span>
)}
{editorialReviewPassed === true && (
  <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
    编辑已通过
  </span>
)}
{tasteScore !== null && (
  <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
    口味评分 {tasteScore}
  </span>
)}
```

- [ ] **Step 6: Run frontend tests**

Run:

```bash
cd frontend && npm test -- --run src/tests/ai-task-components.test.tsx src/tests/visual-yearly-report.test.tsx
```

Expected: PASS.

---

## Task 11: Probe and Taste Acceptance

**Files:**
- Modify: `scripts/probe_visual_yearly_report_artifact.py`
- Test: script smoke via local backend.

- [ ] **Step 1: Add probe arguments**

Modify parser in `scripts/probe_visual_yearly_report_artifact.py`:

```python
parser.add_argument(
    "--writer-pipeline",
    default=None,
    help="Optional writer pipeline, e.g. editorial_agent_v1.",
)
parser.add_argument("--min-taste-score", type=int, default=26)
```

When building the task payload:

```python
if args.writer_pipeline:
    payload["writer_pipeline"] = args.writer_pipeline
```

- [ ] **Step 2: Validate metadata and taste score**

Extend artifact validation:

```python
if args.writer_pipeline == "editorial_agent_v1":
    metadata = result.get("metadata") or {}
    if metadata.get("writer_pipeline_version") != "yearly_editorial_agent_v1":
        issues.append("writer pipeline metadata missing yearly_editorial_agent_v1")
    if metadata.get("claim_check_passed") is not True:
        issues.append("claim check did not pass")
    taste = metadata.get("taste_score") if isinstance(metadata.get("taste_score"), dict) else {}
    if int(taste.get("total") or 0) < args.min_taste_score:
        issues.append("taste score below threshold")
```

- [ ] **Step 3: Run single-year editorial agent probe**

Run with backend already running on `127.0.0.1:8000`:

```bash
source .venv/bin/activate && python scripts/probe_visual_yearly_report_artifact.py --mode single --year 2026 --writer-pipeline editorial_agent_v1 --timeout 300 --json-output /tmp/spotify_visual_yearly_editorial_agent_2026.json
```

Expected: exit 0 and JSON includes:

```json
{
  "ok": true,
  "summary": {
    "metadata": {
      "writer_pipeline_version": "yearly_editorial_agent_v1",
      "claim_check_passed": true
    }
  }
}
```

- [ ] **Step 4: Run changed-years probe**

Run:

```bash
source .venv/bin/activate && python scripts/probe_visual_yearly_report_artifact.py --mode changed --year 2026 --writer-pipeline editorial_agent_v1 --timeout 300 --json-output /tmp/spotify_visual_yearly_editorial_agent_changed.json
```

Expected: 2025 and 2026 both pass. 2026 includes `截至 2026-06-23`; 2025 does not use year-midpoint phrasing as a full-year report.

- [ ] **Step 5: Run taste evaluator**

Run:

```bash
python scripts/evaluate_yearly_report_taste.py --json-input /tmp/spotify_visual_yearly_editorial_agent_2026.json --min-total 26
```

Expected: exit 0, `ok=true`, `total >= 26`.

---

## Task 12: Make Editorial Agent Default After Taste Gate

**Files:**
- Modify: `frontend/src/features/ai-insights/AiReportsPanel.tsx`
- Modify: `backend/services/ai_task_service.py`
- Test: `frontend/src/tests/ai-insights-task-flow.test.tsx`
- Test: `backend/tests/unit/test_ai_report_tasks.py`

- [ ] **Step 1: Add default request tests**

In `frontend/src/tests/ai-insights-task-flow.test.tsx`, assert yearly generation sends:

```ts
expect(startReportTask).toHaveBeenCalledWith(
  expect.objectContaining({
    report_type: 'yearly',
    report_mode: 'visual_yearly_artifact',
    writer_pipeline: 'editorial_agent_v1',
  }),
)
```

In `backend/tests/unit/test_ai_report_tasks.py`, add an assertion that yearly visual artifact generation preserves `writer_pipeline`.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_ai_report_tasks.py -q
cd frontend && npm test -- --run src/tests/ai-insights-task-flow.test.tsx
```

Expected: FAIL until request defaults include `writer_pipeline`.

- [ ] **Step 3: Default yearly visual requests to editorial agent**

Modify `frontend/src/features/ai-insights/AiReportsPanel.tsx` yearly payload:

```ts
return {
  report_type: 'yearly',
  action: 'cache_only',
  report_mode: 'visual_yearly_artifact',
  writer_pipeline: 'editorial_agent_v1',
  year,
  ...basePayload,
}
```

Ensure generation inherits the same payload because `startGenerateReport` spreads `reportPayload`.

- [ ] **Step 4: Backend fallback default**

In `backend/services/ai_task_service.py`, when normalizing a yearly `visual_yearly_artifact` request with no writer pipeline, set:

```python
if request.get("report_type") == "yearly" and _should_use_visual_yearly_artifact(request):
    request.setdefault("writer_pipeline", "editorial_agent_v1")
```

This keeps API clients aligned with the frontend default.

- [ ] **Step 5: Run default request tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_ai_report_tasks.py -q
cd frontend && npm test -- --run src/tests/ai-insights-task-flow.test.tsx
```

Expected: PASS.

---

## Task 13: Browser Acceptance

**Files:**
- No code files unless the browser check reveals a defect.

- [ ] **Step 1: Start or reuse backend and frontend**

Run if servers are not already active:

```bash
source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend
cd frontend && npm run dev
```

Expected:

- Backend reachable at `http://127.0.0.1:8000/health`.
- Frontend reachable at `http://localhost:5173/ai-insights`.

- [ ] **Step 2: Browser flow**

In the in-app browser:

1. Open `http://localhost:5173/ai-insights`.
2. Click `报告`.
3. Click `年度叙事`.
4. Click `今年`.
5. Click `刷新报告`.
6. Wait until the report finishes.

Expected UI:

- Progress shows yearly writing stages such as `正在选择年度主题`, `正在撰写年报正文`, `正在编辑成稿`, `正在核对事实口径`.
- Final report badge includes `Editorial Agent`, `事实已核对`, and `口味评分`.
- Report renders hero, cards, sections, and charts.
- No console error/warn.
- Horizontal overflow is 0.
- Task result metadata includes `writer_pipeline_version=yearly_editorial_agent_v1`.

- [ ] **Step 3: Compare report quality manually**

Read the generated 2026 report and score it using:

- Article feel: at least 4/5.
- Clear yearly thesis: at least 4/5.
- Insight density: at least 4/5.
- Personalization: at least 4/5.
- Fact safety: exactly 5/5.
- Readability: at least 4/5.
- Visual integration: at least 4/5.

Expected: total at least 26/35 and no obvious return to deterministic template voice.

---

## Task 14: Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `backend/CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Update durable docs**

Add a concise durable note to AI report sections:

```markdown
AI 年度叙事默认走 `visual_yearly_artifact` + `writer_pipeline=editorial_agent_v1`：后端先构建 Research Brief 和确定性图表数据，再由 LLM 规划主题、撰写正文、编辑改稿，最后用 Claim Checker 和 taste rubric 校验事实与可读性；缓存 key 包含 writer pipeline version，避免旧 deterministic 年报挡住新结果。
```

Use this in `README.md`, `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md` where current AI yearly report notes live.

- [ ] **Step 2: Update docs index and changelog**

In `docs/README.md`, ensure both spec and plan are indexed:

```markdown
| [`superpowers/specs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md`](superpowers/specs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md) | AI Yearly Report Editorial Agent Pipeline 设计：Research Brief、Storyline Planner、LLM 主笔、LLM 编辑、Claim Checker、Taste Rubric 与 artifact 兼容迁移 |
| [`superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md`](superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md) | AI Yearly Report Editorial Agent Pipeline 实施计划：模型、研究简报、LLM 写作/编辑、claim checker、taste rubric、缓存隔离、默认切换和验收步骤 |
```

In `docs/CHANGELOG.md`, add a top entry with:

- backend pipeline changes.
- frontend metadata/progress changes.
- probe/taste acceptance.
- validation commands actually run.

- [ ] **Step 3: Run targeted backend tests**

Run:

```bash
source .venv/bin/activate && pytest \
  backend/tests/unit/test_yearly_editorial_agent_models.py \
  backend/tests/unit/test_yearly_research_brief.py \
  backend/tests/unit/test_yearly_storyline_planner.py \
  backend/tests/unit/test_yearly_writer_editor.py \
  backend/tests/unit/test_yearly_claim_checker.py \
  backend/tests/unit/test_yearly_taste_rubric.py \
  backend/tests/unit/test_yearly_editorial_agent_pipeline.py \
  backend/tests/unit/test_visual_yearly_artifact_service.py \
  backend/tests/unit/test_ai_report_tasks.py \
  backend/tests/contract/test_yearly_editorial_agent_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run frontend tests and build**

Run:

```bash
cd frontend && npm test -- --run \
  src/tests/ai-task-components.test.tsx \
  src/tests/ai-insights-task-flow.test.tsx \
  src/tests/visual-yearly-report.test.tsx
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Run quality probes**

Run:

```bash
source .venv/bin/activate && python scripts/probe_visual_yearly_report_artifact.py --mode changed --year 2026 --writer-pipeline editorial_agent_v1 --timeout 300 --json-output /tmp/spotify_visual_yearly_editorial_agent_changed.json
python scripts/evaluate_yearly_report_taste.py --json-input /tmp/spotify_visual_yearly_editorial_agent_changed.json --min-total 26
```

Expected: PASS.

- [ ] **Step 6: Run pre-commit**

Run:

```bash
.venv/bin/pre-commit run --all-files
```

Expected: ruff, ruff format, mypy, detect-secrets PASS.

- [ ] **Step 7: Final git commit after all repairs**

Only after all implementation tasks and validation pass, commit all relevant AI yearly report files together. Exclude unrelated artist genre resolution changes unless the user explicitly says they belong in this batch.

Commit shape:

```bash
git status --short
git add README.md AGENTS.md CLAUDE.md backend/CLAUDE.md docs/README.md docs/CHANGELOG.md \
  docs/superpowers/specs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md \
  docs/superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md \
  backend/domains/ai_reports/editorial_agent \
  backend/domains/ai_reports/visual_yearly_artifact_service.py \
  backend/domains/ai_reports/visual_yearly_critic.py \
  backend/models/ai_tasks.py \
  backend/services/ai_task_service.py \
  backend/services/ai_insights_service.py \
  backend/tests/unit/test_yearly_editorial_agent_models.py \
  backend/tests/unit/test_yearly_research_brief.py \
  backend/tests/unit/test_yearly_storyline_planner.py \
  backend/tests/unit/test_yearly_writer_editor.py \
  backend/tests/unit/test_yearly_claim_checker.py \
  backend/tests/unit/test_yearly_taste_rubric.py \
  backend/tests/unit/test_yearly_editorial_agent_pipeline.py \
  backend/tests/contract/test_yearly_editorial_agent_contract.py \
  frontend/src/features/ai-tasks/AITaskProgress.tsx \
  frontend/src/features/ai-insights/ReportCard.tsx \
  frontend/src/features/ai-insights/AiReportsPanel.tsx \
  frontend/src/tests/ai-task-components.test.tsx \
  frontend/src/tests/ai-insights-task-flow.test.tsx \
  frontend/src/tests/visual-yearly-report.test.tsx \
  scripts/probe_visual_yearly_report_artifact.py \
  scripts/evaluate_yearly_report_taste.py
git commit -m "feat: add yearly report editorial agent pipeline"
```

Expected: one final repair commit containing spec, plan, implementation, tests, probes, and docs.

---

## Self-Review

Spec coverage:

- Research Brief: Task 2.
- Storyline Planner: Task 4.
- LLM writer: Task 5.
- LLM editor: Task 5.
- Claim Checker: Task 6 and Task 8.
- Taste Rubric: Task 7 and Task 11.
- Artifact compatibility: Task 9.
- Cache and writer pipeline version: Task 9.
- Task progress and UX: Task 10 and Task 13.
- Browser acceptance: Task 13.
- Documentation and final commit boundary: Task 14.

Scope check:

- The plan does not implement artist genre resolution.
- The plan does not redesign frontend visuals.
- The plan keeps chart data deterministic.
- The plan uses explicit `writer_pipeline=editorial_agent_v1` first and switches default only after taste probe/browser acceptance.

Placeholder scan:

- No unresolved placeholder markers, no vague “handle edge cases”, and no empty test steps.
- Each implementation task has exact files, test commands, and concrete code snippets.

Execution handoff:

Plan complete and saved to `docs/superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md`. Two execution options:

1. Subagent-Driven (recommended) — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution — execute tasks in this session with checkpoints.
