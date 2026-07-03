# AI Yearly Report Editorial Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic editorial layer for AI visual yearly reports so generated reports assign each fact to one section, reduce template language, connect chart evidence to interpretation, and read like a personal music-year article instead of a data recap.

**Architecture:** Keep the existing `visual_yearly_artifact` contract, Report Agent research flow, chart data builder, and frontend renderer. Add `editorial_plan.py` between `story_insight_builder` and section composition; pass that plan into the composer and critic; replace exact chart-observation matching with interpreted chart evidence checks. The implementation is intentionally incremental: first build the plan, then consume it, then harden critic/probe/browser acceptance.

**Tech Stack:** FastAPI service layer, `backend/domains/ai_reports`, pytest unit/contract tests, `scripts/probe_visual_yearly_report_artifact.py`, React/Vitest smoke for renderer regressions, in-app browser QA on `/ai-insights`.

**Execution Status (2026-07-04):** Implemented via Subagent-Driven rollout. The backend now emits `yearly_editorial_v1` metadata, fact ownership, section roles, and language budgets; critic/probe checks now require interpreted chart evidence instead of raw observation echo; prose generation was tightened to reduce repeated facts and template words. Verified with focused backend tests, frontend renderer tests/build, changed/full real API probes for 2022-2026, and in-app browser refresh QA on `/ai-insights`.

---

## Source Spec

- `docs/superpowers/specs/2026-07-04-ai-yearly-report-editorial-layer-design.md`

## Current State

Already implemented and should be reused:

- `backend/domains/ai_reports/story_insight_builder.py`
  - Builds album relation, second-thread classification, highlight-day interpretation, discovery mode, and closing guidance.
- `backend/domains/ai_reports/dynamic_outline.py`
  - Selects section roles from chart signals.
- `backend/domains/ai_reports/narrative_quality.py`
  - Checks repeated core facts, missing chart observation usage, and generic phrase density.
- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Checks length, chart count, internal guidance leakage, repeated meta prose, same-album false contrast, unsupported Olivia claims, and calls narrative quality.
- `scripts/probe_visual_yearly_report_artifact.py`
  - Runs real task API probes and validates visual artifact shape.

Known gap to fix:

- Current quality gates still expect prose to contain chart observation strings exactly. The editorial-layer spec requires the opposite: chart observations should be interpreted, not repeated verbatim. This plan updates quality/probe logic to detect concrete chart usage without forcing exact sentence echo.

## File Map

### Backend Create

- `backend/domains/ai_reports/editorial_plan.py`
  - Defines `EditorialFact`, `SectionPlan`, and `EditorialPlan`.
  - Builds fact ownership from context, chart observations, story insights, and dynamic outline roles.
  - Stores language budgets, inference boundaries, and role contracts.

- `backend/tests/unit/test_editorial_plan.py`
  - Locks fact ownership, section roles, language budget, chart fact assignment, and metadata payload shape.

### Backend Modify

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Build editorial plan after story insights and before section composition.
  - Use editorial roles as the section order source.
  - Attach owned fact ids to section `evidence_refs`.
  - Add editorial metadata to `artifact.metadata`.
  - Reduce repeated/generic prose in `_long_opening`, `_long_companionship`, `_long_discovery`, and `_long_closing`.

- `backend/domains/ai_reports/narrative_quality.py`
  - Accept optional `editorial_plan`.
  - Replace exact chart observation matching with token/entity/month/number based chart-reading checks.
  - Add duplicate fact, chart-prose echo, language budget, data-listing, and unsupported life-claim checks.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Pass `editorial_plan` into narrative quality.
  - Convert new narrative quality issue codes into repair instructions.
  - Treat editorial hard blockers as cache-blocking errors.

- `scripts/probe_visual_yearly_report_artifact.py`
  - Validate editorial metadata.
  - Add `--mode changed|full` for broader quality sampling.
  - Replace exact chart-observation checks with interpreted chart-reading checks.
  - Check language budget and repeated fact ownership.

### Frontend Modify

- `frontend/src/features/ai-insights/yearly-artifact/YearlyReportArtifact.tsx` or the current artifact renderer entry file
  - Keep existing visual layout.
  - Ensure shortened chart captions still render accessibly.
  - Do not display full `editorial_plan`; only tolerate new metadata fields.

### Docs Modify

- `docs/CHANGELOG.md`
  - Add a short implementation and verification note after execution.

## Task 1: Add Editorial Plan Builder

**Files:**

- Create: `backend/domains/ai_reports/editorial_plan.py`
- Create: `backend/tests/unit/test_editorial_plan.py`

- [ ] **Step 1: Write failing tests for fact ownership and section plans**

Create `backend/tests/unit/test_editorial_plan.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.editorial_plan import build_editorial_plan

pytestmark = pytest.mark.unit


def _context() -> dict:
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
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            },
            "playback_billboard_matrix": {
                "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"]
            },
            "highlight_day_timeline": {
                "observations": ["2026-04-03 是播放最密集的一天，共 143 次。"]
            },
        },
    }


def _narrative() -> dict:
    return {
        "main_story": "Taylor Swift 是稳定回访对象，Olivia Rodrigo 形成阶段性上升。",
        "opening_scene": "这是一份截至 2026-06-23 的阶段性音乐年记。",
    }


def _insights() -> dict:
    return {
        "first_artist": "Taylor Swift",
        "second_thread": {"entity": "Olivia Rodrigo", "claim": "Olivia Rodrigo 形成第二条线索"},
        "album_relation": {
            "mode": "aligned",
            "playback_leader": "The Life of a Showgirl",
            "chart_leader": "The Life of a Showgirl",
            "claim": "The Life of a Showgirl 让播放量和个人 Billboard 指向同一个重心",
            "interpretation": "播放热度与榜单长留重合。",
        },
        "highlight_day": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation": "这一天更像许多歌曲密集经过。",
        },
        "discovery": {
            "entity": "Zhang Zhen Yue",
            "plays": 574,
            "first_date": "2026-03-09",
            "interpretation": "已经形成清晰的新支线。",
        },
    }


def _visual() -> dict:
    return {
        "outline_sections": [
            {"role": "opening", "reason": "建立时间范围"},
            {"role": "main_artist", "reason": "解释主线艺人"},
            {"role": "turning_point", "reason": "解释月度转折"},
            {"role": "album_story", "reason": "解释专辑关系"},
            {"role": "highlight_day", "reason": "解释高光日"},
            {"role": "discovery", "reason": "解释新发现"},
            {"role": "closing", "reason": "收束年度画像"},
        ]
    }


def test_editorial_plan_assigns_each_fact_to_one_home_section():
    plan = build_editorial_plan(_context(), _narrative(), _insights(), _visual())

    fact_ids = [fact.id for fact in plan.facts]
    assert len(fact_ids) == len(set(fact_ids))
    assert all(fact.home_section_role for fact in plan.facts)

    home_counts = {}
    for fact in plan.facts:
        home_counts.setdefault(fact.id, set()).add(fact.home_section_role)

    assert all(len(homes) == 1 for homes in home_counts.values())
    assert any(fact.home_section_role == "turning_point" for fact in plan.facts)
    assert any(fact.home_section_role == "album_story" for fact in plan.facts)


def test_editorial_plan_uses_visual_outline_roles_and_owns_chart_observations():
    plan = build_editorial_plan(_context(), _narrative(), _insights(), _visual())

    roles = [section.role for section in plan.sections]
    assert roles[:4] == ["opening", "main_artist", "turning_point", "album_story"]

    turning = next(section for section in plan.sections if section.role == "turning_point")
    owned = {fact.id for fact in plan.facts if fact.id in turning.owned_fact_ids}
    assert "artist_monthly_trend_primary_observation" in owned

    opening = next(section for section in plan.sections if section.role == "opening")
    assert "artist_monthly_trend_primary_observation" not in opening.owned_fact_ids


def test_editorial_plan_exposes_language_budget_and_metadata():
    plan = build_editorial_plan(_context(), _narrative(), _insights(), _visual())
    payload = plan.to_dict()

    assert payload["version"] == "yearly_editorial_v1"
    assert payload["language_budget"]["入口"] <= 2
    assert payload["language_budget"]["陪伴"] <= 4
    assert payload["metadata"]["fact_count"] == len(plan.facts)
    assert payload["metadata"]["section_roles"] == [section.role for section in plan.sections]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_editorial_plan.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'backend.domains.ai_reports.editorial_plan'`.

- [ ] **Step 3: Implement editorial plan models and builder**

Create `backend/domains/ai_reports/editorial_plan.py` with these public interfaces:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EDITORIAL_PLAN_VERSION = "yearly_editorial_v1"

LANGUAGE_BUDGET = {
    "入口": 2,
    "坐标": 1,
    "地图": 1,
    "声音线": 1,
    "情绪线": 1,
    "纹理": 1,
    "陪伴": 4,
    "主线": 3,
    "稳定中心": 0,
}

SECTION_CONTRACTS = {
    "opening": {
        "required_axes": ("thesis", "period"),
        "forbidden_moves": ("rank_dump", "top_entities_full_list"),
    },
    "year_rhythm": {
        "required_axes": ("life_rhythm",),
        "forbidden_moves": ("repeat_overview_numbers",),
    },
    "main_artist": {
        "required_axes": ("companionship",),
        "forbidden_moves": ("artist_top_five_dump",),
    },
    "second_thread": {
        "required_axes": ("secondary_preference",),
        "forbidden_moves": ("unsupported_language_claim",),
    },
    "turning_point": {
        "required_axes": ("phase_shift",),
        "forbidden_moves": ("vague_trend_without_month",),
    },
    "album_story": {
        "required_axes": ("playback_billboard_relation",),
        "forbidden_moves": ("same_entity_false_contrast",),
    },
    "billboard_divergence": {
        "required_axes": ("playback_billboard_relation",),
        "forbidden_moves": ("same_entity_false_contrast",),
    },
    "highlight_day": {
        "required_axes": ("day_density",),
        "forbidden_moves": ("invent_life_event",),
    },
    "discovery": {
        "required_axes": ("discovery_signal",),
        "forbidden_moves": ("overstate_small_signal",),
    },
    "closing": {
        "required_axes": ("synthesis",),
        "forbidden_moves": ("rank_dump", "empty_watchlist"),
    },
}


@dataclass(frozen=True)
class EditorialFact:
    id: str
    claim: str
    source: str
    home_section_role: str
    allowed_reuse: str
    interpretation_axis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "source": self.source,
            "home_section_role": self.home_section_role,
            "allowed_reuse": self.allowed_reuse,
            "interpretation_axis": self.interpretation_axis,
        }


@dataclass(frozen=True)
class SectionPlan:
    role: str
    heading_hint: str
    owned_fact_ids: tuple[str, ...]
    referenced_fact_ids: tuple[str, ...]
    required_interpretation_axes: tuple[str, ...]
    forbidden_moves: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "heading_hint": self.heading_hint,
            "owned_fact_ids": list(self.owned_fact_ids),
            "referenced_fact_ids": list(self.referenced_fact_ids),
            "required_interpretation_axes": list(self.required_interpretation_axes),
            "forbidden_moves": list(self.forbidden_moves),
        }


@dataclass(frozen=True)
class EditorialPlan:
    version: str
    thesis: str
    facts: tuple[EditorialFact, ...]
    sections: tuple[SectionPlan, ...]
    language_budget: dict[str, int]
    inference_rules: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        section_roles = [section.role for section in self.sections]
        return {
            "version": self.version,
            "thesis": self.thesis,
            "facts": [fact.to_dict() for fact in self.facts],
            "sections": [section.to_dict() for section in self.sections],
            "language_budget": dict(self.language_budget),
            "inference_rules": {key: list(value) for key, value in self.inference_rules.items()},
            "metadata": {
                "editorial_plan_version": self.version,
                "fact_count": len(self.facts),
                "section_roles": section_roles,
            },
        }
```

Then add `build_editorial_plan(context, narrative, insights, visual)` and helpers:

```python
def build_editorial_plan(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
    visual: dict[str, Any] | None = None,
) -> EditorialPlan:
    roles = _outline_roles(visual)
    facts = tuple(_build_facts(context, insights, roles))
    sections = tuple(_build_sections(roles, facts))
    thesis = str(narrative.get("main_story") or insights.get("opening_thesis") or "这一年的音乐偏好正在形成。")
    return EditorialPlan(
        version=EDITORIAL_PLAN_VERSION,
        thesis=thesis,
        facts=facts,
        sections=sections,
        language_budget=dict(LANGUAGE_BUDGET),
        inference_rules={
            "allowed": (
                "听歌密度可以解释为日常在场。",
                "月度上升可以解释为阶段性关注增强。",
                "长期在榜可以解释为持续留下。",
            ),
            "forbidden": (
                "不得编造天气、地点、考试、分手、旅行、加班等具体事件。",
                "不得把个人 Billboard 写成外部官方 Billboard。",
                "不得把 Spotify 流派标签写成互斥类别。",
            ),
        },
    )
```

Implementation requirements for private helpers:

- `_outline_roles(visual)` returns `visual["outline_sections"][*]["role"]` when present; otherwise returns `("opening", "main_artist", "turning_point", "album_story", "highlight_day", "discovery", "closing")`.
- `_build_facts(context, insights, roles)` creates at least these ids when data exists:
  - `yearly_overview_density` -> `opening`
  - `top_artist_primary` -> `main_artist`
  - `artist_monthly_trend_primary_observation` -> `turning_point` if that role exists, otherwise `second_thread`
  - `album_relation_primary` -> `album_story` or `billboard_divergence`
  - `playback_billboard_matrix_primary_observation` -> `album_story` or `billboard_divergence`
  - `highlight_day_density` -> `highlight_day`
  - `discovery_primary` -> `discovery`
- `_build_sections(roles, facts)` fills each section with owned facts whose `home_section_role` matches the role and referenced facts whose `allowed_reuse` is not `"none"`.
- `_build_sections` keeps only roles listed in `SECTION_CONTRACTS`, and appends missing `opening` and `closing` if absent.

- [ ] **Step 4: Run editorial plan tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_editorial_plan.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Checkpoint**

Review these files:

```bash
git diff -- backend/domains/ai_reports/editorial_plan.py backend/tests/unit/test_editorial_plan.py
```

Suggested checkpoint message if the user later asks for commits:

```text
feat: add AI yearly editorial plan builder
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 2: Route Editorial Plan Through Visual Yearly Artifact Service

**Files:**

- Modify: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Modify: `backend/tests/unit/test_visual_yearly_artifact_service.py`

- [ ] **Step 1: Add service tests for editorial metadata and evidence refs**

Append to `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
def test_visual_yearly_artifact_exposes_editorial_metadata(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }

    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: ([], context),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            "artist_monthly_trend": {
                "ok": True,
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ],
            },
            "album_duality_compare": {"ok": True, "relation": "aligned"},
            "playback_billboard_matrix": {
                "ok": True,
                "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"],
            },
            "highlight_day_timeline": {
                "ok": True,
                "observations": ["2026-04-03 是播放最密集的一天，共 143 次。"],
            },
            "genre_language_mix": {"ok": True},
            "discovery_timeline": {"ok": True, "new_artists": [{"name": "Zhang Zhen Yue"}]},
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    metadata = result["artifact"]["metadata"]
    assert metadata["editorial_plan_version"] == "yearly_editorial_v1"
    assert metadata["fact_count"] >= 5
    assert "turning_point" in metadata["section_roles"]
    assert any("artist_monthly_trend_primary_observation" in section["evidence_refs"] for section in result["artifact"]["sections"])
```

- [ ] **Step 2: Run the new service test and verify it fails**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_exposes_editorial_metadata -q
```

Expected: fail because artifact metadata has no `editorial_plan_version`.

- [ ] **Step 3: Add wrapper imports and build the plan**

In `backend/domains/ai_reports/visual_yearly_artifact_service.py`, add this wrapper near existing wrappers:

```python
def build_editorial_plan(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
    visual: dict[str, Any] | None = None,
) -> Any:
    from backend.domains.ai_reports.editorial_plan import build_editorial_plan as build

    return build(context, narrative, insights, visual)
```

Then in `generate_visual_yearly_artifact`, after `story_insights = build_story_insights(context, narrative)`, add:

```python
    editorial_plan = build_editorial_plan(context, narrative, story_insights, visual)
```

Change section composition call to:

```python
    sections = _compose_sections(context, narrative, story_insights, visual, editorial_plan=editorial_plan)
```

Before critic, create:

```python
    editorial_payload = editorial_plan.to_dict()
    editorial_metadata = editorial_payload["metadata"]
```

Initialize artifact metadata with editorial fields:

```python
        "metadata": dict(editorial_metadata),
```

Pass the editorial payload into critic context:

```python
        {**context, "is_partial_year": bool(_period(context).get("is_partial_year")), "editorial_plan": editorial_payload},
```

Merge final metadata:

```python
    metadata = {
        "report_mode": VISUAL_YEARLY_REPORT_MODE,
        "contract_version": VISUAL_YEARLY_CONTRACT_VERSION,
        "fallback_level": None if critic["ok"] else "reduced_visuals",
        "section_count": len(sections),
        "chart_count": len(chart_data),
        "insight_card_count": len(insight_cards),
        "article_length": len(prose),
        "critic_passed": bool(critic["ok"]),
        "fact_validation_passed": bool(fact_validation["ok"]),
        **editorial_metadata,
    }
```

- [ ] **Step 4: Let section composition use editorial roles and fact refs**

Change `_compose_sections` signature:

```python
def _compose_sections(
    context: dict[str, Any],
    narrative: dict[str, Any],
    insights: dict[str, Any],
    visual: dict[str, Any] | None = None,
    *,
    editorial_plan: Any | None = None,
) -> tuple[_Section, ...]:
```

Replace:

```python
    roles = _outline_roles(visual)
```

with:

```python
    roles = _editorial_roles(editorial_plan) or _outline_roles(visual)
```

After the fallback section fill, return:

```python
    return _attach_editorial_fact_refs(tuple(sections), editorial_plan)
```

Add helpers near `_outline_roles`:

```python
def _editorial_roles(editorial_plan: Any | None) -> list[str]:
    sections = getattr(editorial_plan, "sections", None)
    if not sections:
        return []
    return [str(getattr(section, "role", "") or "") for section in sections if getattr(section, "role", "")]


def _attach_editorial_fact_refs(
    sections: tuple[_Section, ...],
    editorial_plan: Any | None,
) -> tuple[_Section, ...]:
    plan_sections = getattr(editorial_plan, "sections", None)
    if not plan_sections:
        return sections
    by_role = {str(getattr(section, "role", "")): section for section in plan_sections}
    updated: list[_Section] = []
    for section in sections:
        plan_section = by_role.get(section.role)
        owned = tuple(getattr(plan_section, "owned_fact_ids", ()) or ()) if plan_section else ()
        refs = tuple(dict.fromkeys((*section.evidence_refs, *owned)))
        updated.append(
            _Section(
                section.id,
                section.role,
                section.heading,
                section.deck,
                section.prose,
                section.chart_refs,
                section.insight_refs,
                refs,
                section.pull_quote,
            )
        )
    return tuple(updated)
```

- [ ] **Step 5: Run targeted service tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_exposes_editorial_metadata backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_service_generates_artifact -q
```

Expected: both pass.

- [ ] **Step 6: Checkpoint**

Review:

```bash
git diff -- backend/domains/ai_reports/visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_artifact_service.py
```

Suggested checkpoint message if the user later asks for commits:

```text
feat: route AI yearly reports through editorial plans
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 3: Replace Exact Chart Echo With Interpreted Chart Reading

**Files:**

- Modify: `backend/domains/ai_reports/narrative_quality.py`
- Modify: `backend/domains/ai_reports/visual_yearly_critic.py`
- Modify: `backend/tests/unit/test_narrative_quality.py`
- Modify: `backend/tests/unit/test_visual_yearly_critic.py`

- [ ] **Step 1: Update narrative quality tests for interpreted chart usage**

In `backend/tests/unit/test_narrative_quality.py`, replace `test_quality_accepts_specific_chart_reading_without_repetition` with:

```python
def test_quality_accepts_interpreted_chart_reading_without_exact_echo():
    observation = "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    artifact = {
        "sections": [
            {
                "heading": "六月，第二条线变得更清楚",
                "prose": (
                    "到了 2026-06，Olivia Rodrigo 的月度播放已经越过 Taylor Swift。"
                    "这说明第二条线不是平均铺开，而是在上半年尾声突然变亮。"
                ),
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {"artist_monthly_trend": {"observations": [observation]}},
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is True
    assert result["issue_codes"] == []
```

Add:

```python
def test_quality_rejects_exact_chart_echo_without_interpretation():
    observation = "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    artifact = {
        "sections": [
            {
                "heading": "六月，第二条线变得更清楚",
                "prose": observation,
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {"artist_monthly_trend": {"observations": [observation]}},
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is False
    assert "chart_prose_echo" in result["issue_codes"]
```

- [ ] **Step 2: Run narrative quality tests and verify failure**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_narrative_quality.py -q
```

Expected: fail because current implementation requires exact observation inclusion and does not report `chart_prose_echo`.

- [ ] **Step 3: Implement interpreted chart reading helpers**

In `backend/domains/ai_reports/narrative_quality.py`, update public function signature:

```python
def evaluate_visual_yearly_quality(
    artifact: dict[str, Any],
    editorial_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Add helpers:

```python
INTERPRETATION_MARKERS = (
    "说明",
    "意味着",
    "更像",
    "不是",
    "而是",
    "因此",
    "这让",
    "这使",
    "可以看见",
)


def _uses_chart_observation(section_text: str, observation: str) -> bool:
    if observation in section_text:
        return _has_interpretation_marker(section_text.replace(observation, "", 1))
    tokens = _observation_tokens(observation)
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in section_text)
    return matched >= min(3, len(tokens)) and _has_interpretation_marker(section_text)


def _is_chart_echo(section_text: str, observation: str) -> bool:
    if observation not in section_text:
        return False
    return not _has_interpretation_marker(section_text.replace(observation, "", 1))


def _has_interpretation_marker(text: str) -> bool:
    return any(marker in text for marker in INTERPRETATION_MARKERS)


def _observation_tokens(observation: str) -> list[str]:
    import re

    tokens: list[str] = []
    tokens.extend(re.findall(r"\d{4}-\d{2}", observation))
    tokens.extend(re.findall(r"\d+\s*次", observation))
    for name in ("Taylor Swift", "Olivia Rodrigo", "Zhang Zhen Yue", "The Life of a Showgirl", "Opalite"):
        if name in observation:
            tokens.append(name)
    return list(dict.fromkeys(tokens))
```

In chart-ref loop, replace exact `any(observation in prose for observation in observations)` with:

```python
            if observations and not any(_uses_chart_observation(prose, observation) for observation in observations):
                issues.append(
                    _issue(
                        "missing_chart_observation",
                        f"章节引用 {chart_id}，但正文没有解释该图表的具体观察。",
                    )
                )
            if any(_is_chart_echo(prose, observation) for observation in observations):
                issues.append(
                    _issue(
                        "chart_prose_echo",
                        f"章节引用 {chart_id}，但正文只复述图表观察，没有解释增量。",
                    )
                )
```

- [ ] **Step 4: Add editorial plan aware checks**

Still in `narrative_quality.py`, add after generic phrase check:

```python
    if editorial_plan:
        issues.extend(_editorial_plan_issues(artifact, editorial_plan))
```

Add:

```python
def _editorial_plan_issues(
    artifact: dict[str, Any],
    editorial_plan: dict[str, Any],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    prose_by_role = {
        str(section.get("role") or ""): str(section.get("prose") or "")
        for section in artifact.get("sections") or []
        if isinstance(section, dict)
    }
    facts = [fact for fact in editorial_plan.get("facts") or [] if isinstance(fact, dict)]
    for fact in facts:
        claim = str(fact.get("claim") or "").strip()
        home = str(fact.get("home_section_role") or "").strip()
        if len(claim) < 8 or not home:
            continue
        full_hits = [
            role for role, prose in prose_by_role.items()
            if claim in prose
        ]
        if len(full_hits) > 1:
            issues.append(
                _issue(
                    "duplicate_fact_home",
                    f"事实 {fact.get('id')} 在多个章节完整复述：{', '.join(full_hits)}。",
                )
            )
        if full_hits and home not in full_hits:
            issues.append(
                _issue(
                    "section_role_violation",
                    f"事实 {fact.get('id')} 出现在 {full_hits[0]}，但主场是 {home}。",
                )
            )
    budget = editorial_plan.get("language_budget") if isinstance(editorial_plan.get("language_budget"), dict) else {}
    full_text = "\n".join(prose_by_role.values())
    for phrase, limit in budget.items():
        try:
            max_count = int(limit)
        except (TypeError, ValueError):
            continue
        if full_text.count(str(phrase)) > max_count:
            issues.append(_issue("generic_language_overuse", f"“{phrase}”超过语言预算 {max_count} 次。"))
    if _has_unsupported_life_claim(full_text):
        issues.append(_issue("unsupported_life_claim", "正文出现无证据生活事件推测。"))
    if _has_data_listing_without_interpretation(full_text):
        issues.append(_issue("data_listing_without_interpretation", "连续数字罗列缺少解释句。"))
    return issues
```

Add simple guards:

```python
UNSUPPORTED_LIFE_EVENT_TERMS = (
    "考试",
    "分手",
    "旅行",
    "加班",
    "通勤路上",
    "下雨",
    "失眠",
)


def _has_unsupported_life_claim(text: str) -> bool:
    return any(term in text for term in UNSUPPORTED_LIFE_EVENT_TERMS)


def _has_data_listing_without_interpretation(text: str) -> bool:
    sentences = [part for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]
    numeric_run = 0
    for sentence in sentences:
        numberish = len(re.findall(r"\d+", sentence)) >= 2
        interpretive = _has_interpretation_marker(sentence)
        if numberish and not interpretive:
            numeric_run += 1
        else:
            numeric_run = 0
        if numeric_run >= 3:
            return True
    return False
```

- [ ] **Step 5: Pass editorial plan from visual critic**

In `backend/domains/ai_reports/visual_yearly_critic.py`, change:

```python
    quality = evaluate_visual_yearly_quality(artifact)
```

to:

```python
    quality = evaluate_visual_yearly_quality(artifact, _dict(context.get("editorial_plan")))
```

Add repair instruction mappings for:

```python
"duplicate_fact_home": "同一事实只能在主场章节完整展开，其他章节必须改成短引用或解释。",
"chart_prose_echo": "正文不要只复述图表观察；保留关键实体/月份/数字，并补充解释增量。",
"section_role_violation": "把事实移回对应章节，或调整 editorial plan 的 fact ownership。",
"generic_language_overuse": "减少入口、坐标、地图、声音线、陪伴等抽象词，改成具体实体和证据。",
"data_listing_without_interpretation": "连续数字后必须补解释句，说明它代表稳定、转折、集中或长留。",
"unsupported_life_claim": "删除无证据生活事件，只保留从播放密度、时段和持续性可推导的生活节奏分析。",
```

- [ ] **Step 6: Run quality and critic tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_narrative_quality.py backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Checkpoint**

Review:

```bash
git diff -- backend/domains/ai_reports/narrative_quality.py backend/domains/ai_reports/visual_yearly_critic.py backend/tests/unit/test_narrative_quality.py backend/tests/unit/test_visual_yearly_critic.py
```

Suggested checkpoint message if the user later asks for commits:

```text
test: enforce editorial quality gates for yearly reports
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 4: Make Section Prose Consume Editorial Intent

**Files:**

- Modify: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Modify: `backend/tests/unit/test_visual_yearly_artifact_service.py`

- [ ] **Step 1: Add tests for reduced generic language and no repeated overview**

Append to `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
def test_visual_yearly_artifact_respects_language_budget_and_avoids_overview_repetition(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }

    monkeypatch.setattr(svc, "_run_visual_research", lambda request, emit_event=None: ([], context))
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            spec["id"]: {"ok": True, "observations": []} for spec in chart_specs
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})
    prose = result["report"]

    assert prose.count("174 个活跃日") <= 1
    assert prose.count("7860 次播放") <= 1
    assert prose.count("入口") <= result["artifact"]["metadata"]["language_budget"]["入口"]
    assert prose.count("坐标") <= result["artifact"]["metadata"]["language_budget"]["坐标"]
    assert prose.count("地图") <= result["artifact"]["metadata"]["language_budget"]["地图"]
    assert "通勤" not in prose
    assert "下雨" not in prose
```

- [ ] **Step 2: Run the new test and verify it fails if prose still overuses generic phrases**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_respects_language_budget_and_avoids_overview_repetition -q
```

Expected: fail until metadata includes language budget and prose is tightened.

- [ ] **Step 3: Expose language budget in metadata**

When merging final metadata in `generate_visual_yearly_artifact`, include:

```python
        "language_budget": editorial_payload["language_budget"],
```

Keep this in artifact metadata only. It is acceptable for frontend to ignore it.

- [ ] **Step 4: Tighten opening prose**

In `_long_opening`, keep the first sentence with active days, plays, and hours. Replace the rest of the paragraph with a shorter interpretation that does not reuse `坐标`, `纹理`, or `私人路径`.

Use this replacement return body:

```python
    return (
        f"{prefix}{main_story} 播放记录里有 {active_days} 个活跃日、"
        f"{total_plays} 次播放和约 {round(float(total_minutes) / 60):,} 小时聆听。"
        f"{time_axis} 这些数字最有价值的地方，不是证明你听得多，而是说明音乐在{year_phrase}持续在场："
        "它有时靠前，有时只是安静地铺在日常后面。"
        "所以这份报告不会把榜单重新念一遍，而会先看音乐出现的节奏，"
        "再看哪些艺人、专辑和单曲在不同时间尺度里留下来。"
        "播放量回答的是当下反复选择，个人 Billboard 则保留跨周持续性；"
        "把两者放在一起，才更接近这一年真实的音乐使用方式。"
    )
```

- [ ] **Step 5: Tighten companionship and discovery prose**

In `_long_companionship`, replace “声音线里最亮的一处坐标” with:

```python
        f"单曲层面，{top_track} 以 {top_track_plays} 次播放站在最前面，"
        f"是这条年度声音里最清楚的单曲证据。{track_axis} "
```

Replace the sentence containing “多个入口” with:

```python
        "一个艺人能反复出现，往往说明它在不同场景里都能成立："
```

In `_long_discovery`, replace the paragraph fragment:

```python
        f"{interpretation} 新发现不一定马上变成长期主线，它更像一个入口：先出现，"
        "再用后续播放证明自己是否会留下。把它写成“入口”而不是直接写成“主角”，"
```

with:

```python
        f"{interpretation} 新发现不一定马上变成长期主线，它通常先作为一个新名字出现，"
        "再用后续播放证明自己是否会留下。把它写成“刚进入结构的声音”而不是直接写成“主角”，"
```

Replace “听歌地图” with “听歌结构” and “开了一扇门” with “增加了一个新方向” in the same function.

- [ ] **Step 6: Tighten closing prose**

In `_long_closing`, replace the first half with a shorter synthesis. Keep later paragraph about playback vs personal Billboard if it does not duplicate the album section claim.

Use this opening segment:

```python
    return (
        f"{year} 最终留下的不是单一答案。{direction} "
        "如果把这些章节合在一起看，你的音乐年记更像一组关系："
        f"稳定回到的艺人、专辑层面的长留、新声音的出现，以及某一天突然变高的播放密度。"
        f"{album_axis} {style_axis} "
        "它不替你编造具体生活事件，只把音乐如何在场记录下来：哪些声音陪得久，哪些专辑留得稳，"
        "哪一天音乐忽然变得很密，哪个新名字开始进入你的时间线。"
```

Then remove these phrases from closing:

- `私人地图`
- `坐标`
- `入口`
- `叙事地图`
- `缝隙`

Keep one explanation of:

```text
播放量告诉我们你在哪些名字上花了最多时间，个人 Billboard 则把周与周之间的延续性保留下来。
```

- [ ] **Step 7: Run service test group**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_editorial_plan.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Checkpoint**

Review:

```bash
git diff -- backend/domains/ai_reports/visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_artifact_service.py
```

Suggested checkpoint message if the user later asks for commits:

```text
fix: tighten AI yearly report editorial prose
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 5: Extend Probe For Editorial Acceptance

**Files:**

- Modify: `scripts/probe_visual_yearly_report_artifact.py`

- [ ] **Step 1: Add CLI mode argument**

In `main()`, add:

```python
    parser.add_argument(
        "--mode",
        choices=("single", "changed", "full"),
        default="single",
        help="single probes --year; changed probes 2025 and 2026; full probes all locally meaningful yearly samples.",
    )
```

If `args.mode != "single"`, run multiple years:

```python
    years = [args.year]
    if args.mode == "changed":
        years = [2025, 2026]
    elif args.mode == "full":
        years = [2022, 2023, 2024, 2025, 2026]
    summaries = [_probe_year(base, year, args.timeout, args.poll_interval) for year in years]
    aggregate = {
        "ok": all(summary["ok"] for summary in summaries),
        "mode": args.mode,
        "summaries": summaries,
        "issues": [f"{summary['year']}: {issue}" for summary in summaries for issue in summary["issues"]],
    }
    Path(args.json_output).write_text(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0 if aggregate["ok"] else 1
```

Extract the existing single-year body into:

```python
def _probe_year(base: str, year: int, timeout: int, poll_interval: float) -> dict[str, Any]:
    task = request_json(
        f"{base}/api/ai/tasks/report",
        method="POST",
        payload={
            "report_type": "yearly",
            "action": "generate",
            "report_mode": "visual_yearly_artifact",
            "year": year,
            "force": True,
        },
    )
    task_id = str(task["task_id"])
    deadline = time.time() + timeout
    detail: dict[str, Any] = {}
    while time.time() < deadline:
        detail = request_json(f"{base}/api/ai/tasks/{task_id}")
        if detail.get("status") in {"done", "error", "cancelled"}:
            break
        time.sleep(poll_interval)
    return _build_summary(year=year, task_id=task_id, detail=detail, result=_dict(detail.get("result")))
```

Then the `single` branch writes that one summary.

- [ ] **Step 2: Replace exact chart observation probe with interpreted check**

In `_chart_observation_checks`, replace exact `matched = [observation for observation in observations if observation in section_text]` with:

```python
            matched = [observation for observation in observations if _uses_chart_observation(section_text, observation)]
            echoed = [observation for observation in observations if _is_chart_echo(section_text, observation)]
```

Include `echoed_observations` and `echo_failed` in the row:

```python
                    "echoed_observations": echoed[:3],
                    "echo_failed": bool(echoed),
```

Add helper functions mirroring `narrative_quality.py`:

```python
INTERPRETATION_MARKERS = ("说明", "意味着", "更像", "不是", "而是", "因此", "这让", "这使", "可以看见")


def _uses_chart_observation(section_text: str, observation: str) -> bool:
    if observation in section_text:
        return _has_interpretation_marker(section_text.replace(observation, "", 1))
    tokens = _observation_tokens(observation)
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in section_text)
    return matched >= min(3, len(tokens)) and _has_interpretation_marker(section_text)


def _is_chart_echo(section_text: str, observation: str) -> bool:
    return observation in section_text and not _has_interpretation_marker(section_text.replace(observation, "", 1))


def _has_interpretation_marker(text: str) -> bool:
    return any(marker in text for marker in INTERPRETATION_MARKERS)


def _observation_tokens(observation: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(re.findall(r"\d{4}-\d{2}", observation))
    tokens.extend(re.findall(r"\d+\s*次", observation))
    for name in ("Taylor Swift", "Olivia Rodrigo", "Zhang Zhen Yue", "The Life of a Showgirl", "Opalite"):
        if name in observation:
            tokens.append(name)
    return list(dict.fromkeys(tokens))
```

- [ ] **Step 3: Add editorial metadata validation**

In `_validate`, after metadata checks, add:

```python
    if artifact_metadata.get("editorial_plan_version") != "yearly_editorial_v1":
        issues.append("artifact metadata editorial_plan_version is not yearly_editorial_v1")
    if not artifact_metadata.get("section_roles"):
        issues.append("artifact metadata section_roles is empty")
    if int(artifact_metadata.get("fact_count") or 0) < 5:
        issues.append("artifact metadata fact_count < 5")
```

In `_quality_checks`, include:

```python
            "editorial_plan_version": artifact_metadata.get("editorial_plan_version"),
            "section_roles": artifact_metadata.get("section_roles"),
            "fact_count": artifact_metadata.get("fact_count"),
```

When collecting chart observation issues, also add:

```python
    echo_failures = [
        f"{row['section_id']} -> {row['chart_id']}"
        for row in quality_checks["chart_observation_checks"]
        if row.get("echo_failed")
    ]
    if echo_failures:
        issues.append("chart prose echo without interpretation: " + ", ".join(echo_failures))
```

- [ ] **Step 4: Syntax check the probe**

Run:

```bash
source .venv/bin/activate
python -m py_compile scripts/probe_visual_yearly_report_artifact.py
```

Expected: no output and exit code 0.

- [ ] **Step 5: Checkpoint**

Review:

```bash
git diff -- scripts/probe_visual_yearly_report_artifact.py
```

Suggested checkpoint message if the user later asks for commits:

```text
test: extend yearly report editorial probe
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 6: Frontend Metadata Tolerance And Caption Regression

**Files:**

- Modify: current yearly artifact renderer under `frontend/src/features/ai-insights/yearly-artifact/`
- Modify: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Inspect renderer entry file**

Run:

```bash
rg -n "metadata|chart|caption|observations|YearlyReportArtifact" frontend/src/features/ai-insights/yearly-artifact frontend/src/tests/visual-yearly-report.test.tsx
```

Expected: identify the renderer component that renders chart observations/captions.

- [ ] **Step 2: Add renderer test for extra metadata tolerance**

In `frontend/src/tests/visual-yearly-report.test.tsx`, add a fixture field under artifact metadata:

```ts
metadata: {
  report_mode: 'visual_yearly_artifact',
  contract_version: 'visual_yearly_v1',
  fallback_level: null,
  section_count: 6,
  chart_count: 4,
  insight_card_count: 3,
  article_length: 2800,
  critic_passed: true,
  fact_validation_passed: true,
  editorial_plan_version: 'yearly_editorial_v1',
  fact_count: 8,
  section_roles: ['opening', 'main_artist', 'turning_point', 'album_story', 'highlight_day', 'closing'],
  language_budget: { '入口': 2, '陪伴': 4 },
}
```

Add assertion:

```ts
expect(screen.getByText(/音乐年记/)).toBeInTheDocument()
expect(screen.queryByText(/yearly_editorial_v1/)).not.toBeInTheDocument()
```

- [ ] **Step 3: Run frontend visual report test**

Run:

```bash
cd frontend
npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: pass. If it fails because metadata is rendered raw, hide debug metadata from user-facing UI.

- [ ] **Step 4: Checkpoint**

Review:

```bash
git diff -- frontend/src/features/ai-insights/yearly-artifact frontend/src/tests/visual-yearly-report.test.tsx
```

Suggested checkpoint message if the user later asks for commits:

```text
test: tolerate yearly editorial metadata in renderer
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 7: Full Verification And Browser Acceptance

**Files:**

- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
source .venv/bin/activate
pytest \
  backend/tests/unit/test_editorial_plan.py \
  backend/tests/unit/test_narrative_quality.py \
  backend/tests/unit/test_visual_yearly_critic.py \
  backend/tests/unit/test_visual_yearly_artifact_service.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend visual test**

Run:

```bash
cd frontend
npm test -- --run src/tests/visual-yearly-report.test.tsx
```

Expected: pass.

- [ ] **Step 3: Run build or narrow type check**

Run:

```bash
cd frontend
npm run build
```

Expected: production build succeeds.

- [ ] **Step 4: Run changed-year probe**

Ensure backend is running on `127.0.0.1:8000`, then run:

```bash
source .venv/bin/activate
python scripts/probe_visual_yearly_report_artifact.py \
  --mode changed \
  --year 2026 \
  --timeout 300 \
  --json-output /tmp/spotify_visual_yearly_editorial_changed.json
```

Expected:

- Exit code 0.
- JSON `ok: true`.
- Summaries for 2025 and 2026.
- Each summary includes `artifact_metadata.editorial_plan_version == "yearly_editorial_v1"`.

- [ ] **Step 5: Run full-year probe if changed mode passes**

Run:

```bash
source .venv/bin/activate
python scripts/probe_visual_yearly_report_artifact.py \
  --mode full \
  --year 2026 \
  --timeout 300 \
  --json-output /tmp/spotify_visual_yearly_editorial_full.json
```

Expected:

- Exit code 0, or only years with genuinely insufficient historical data fail with explicit sparse-data issue.
- If any year fails, inspect JSON and classify whether it is a product bug or a sparse-data acceptance update.

- [ ] **Step 6: Browser acceptance on `/ai-insights`**

Use the in-app browser or Playwright browser control:

1. Open `http://localhost:5173/ai-insights`.
2. Go to the yearly report tab.
3. Select 2026.
4. Click refresh/generate.
5. Wait for task status done.
6. Confirm timestamp updates.
7. Confirm report body changed when force refresh is used.
8. Confirm visible report includes:
   - `截至 2026-06-23`
   - `Taylor Swift`
   - `Olivia Rodrigo`
   - `The Life of a Showgirl`
   - At least one explanation of playback vs personal Billboard.
9. Confirm report does not overuse:
   - `入口`
   - `坐标`
   - `地图`
   - `声音线`
10. Confirm no console errors and no horizontal overflow.

- [ ] **Step 7: Update changelog**

Add to `docs/CHANGELOG.md` under the latest AI section:

```markdown
- AI Visual Yearly Report Editorial Layer：年度图文报告新增确定性 Editorial Plan，给核心事实分配唯一章节主场，记录 section roles/fact count/language budget，并将 critic/probe 从“原样复述图表 observation”升级为“解释性使用图表证据”。这减少了报告中的模板词、重复事实和播放分析页面复述感，同时继续保留个人 Billboard 与本地播放数据的事实边界。
```

- [ ] **Step 8: Final checkpoint**

Run:

```bash
git status --short
git diff --check
```

Expected:

- No whitespace errors.
- Changed files match this plan scope.

Suggested final checkpoint message if the user later asks for commits:

```text
feat: add editorial layer for AI yearly reports
```

Do not run `git commit` unless the user explicitly asks for commits.

## Implementation Order

Run tasks in order:

1. Task 1 builds a standalone editorial plan and tests it in isolation.
2. Task 2 wires the plan into the yearly artifact service without changing frontend behavior.
3. Task 3 updates quality gates so the new editorial contract is enforceable.
4. Task 4 tightens prose generation to satisfy the new gates.
5. Task 5 upgrades the real API probe.
6. Task 6 confirms the frontend tolerates new metadata.
7. Task 7 performs real data and browser acceptance.

## Acceptance Criteria

The implementation is complete when:

- `generate_visual_yearly_artifact()` returns metadata with:
  - `editorial_plan_version = "yearly_editorial_v1"`
  - `fact_count >= 5`
  - non-empty `section_roles`
  - `language_budget`
- 2025 and 2026 changed-mode probes pass.
- The report no longer requires exact chart observation echo in prose.
- Repeated core facts, repeated generic language, unsupported life-event claims, and same-album false contrast are rejected before cache.
- Browser refresh on `/ai-insights` shows an updated, readable report with no console errors or horizontal overflow.

## Self-Review

- Spec coverage: covered Fact Ledger, Section Role Contract, Language Budget, Chart-Prose Bridge, Narrative Inference Calibrator, Editorial Critic, metadata, probes, and browser acceptance.
- Scope check: this is one subsystem, AI visual yearly reports. It does not rewrite Report Agent tools, frontend layout, PDF/export, or general chat.
- Type consistency: public names are `EditorialFact`, `SectionPlan`, `EditorialPlan`, `build_editorial_plan`, `yearly_editorial_v1`, and are referenced consistently across service, critic, and probe tasks.
