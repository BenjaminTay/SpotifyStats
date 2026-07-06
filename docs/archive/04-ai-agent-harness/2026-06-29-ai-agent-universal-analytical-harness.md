# AI Agent Universal Analytical Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the read-only AI chat Agent into a general analytical harness that frames the user's question, gathers the minimum evidence for that question family, builds a structured analytical brief, and prevents over-simplified or unsupported final answers.

**Architecture:** Keep the existing observable AI task runner, read-only tool registry, evidence cards, coverage review, answer critic, and golden-question harness. Add a deterministic `QuestionFrame`, `EvidenceRecipe`, axis-level `EvidenceSufficiency`, `AnalyticalBrief`, and contract-aware answer checks between the current intent parser and final LLM answer.

**Tech Stack:** FastAPI, SQLite, Pydantic v2, pytest, React 19, TypeScript, Vitest, Playwright smoke scripts.

---

## Source Spec

Use this design document as the authority for scope and terminology:

- `docs/superpowers/specs/2026-06-29-ai-agent-universal-analytical-harness-design.md`

The five design decisions at the end of the spec are accepted:

- First supported families: `simple_ranking`, `entity_detail`, `preference_comparison`, `trend_preference`, `period_comparison`, `change_explanation`, `time_of_day_ranking`, `identity_preference`, `habit_summary`.
- `preference_comparison` requires recent-window evidence, using `last_6_months` and `last_4_weeks`.
- `AnalyticalBrief` is deterministic in the first version.
- `AnswerContractCritic` uses deterministic checks in the first version.
- Frontend dimension-winner matrix is a final phase and does not block backend quality.

## Current Baseline

The codebase already has most of the building blocks:

- `backend/domains/ai_agent/question_intent.py` parses coarse `task_type`, `entity_type`, `entities`, `requested_metrics`, and `time_scope`.
- `backend/services/ai_agent_service.py` runs planner LLM, sanitizes tool plans, executes read-only tools, reviews coverage, builds final payload, calls final LLM, and retries once on validation failures.
- `backend/domains/ai_agent/coverage_review.py` checks found/missing entity coverage and can request bounded follow-up tool calls.
- `backend/domains/ai_agent/comparison.py` summarizes cumulative plays, total hours, personal Billboard score/rank, normalized intensity, and fairness notes for `compare_entities`.
- `backend/domains/ai_agent/evidence.py` and `evidence_builders.py` already produce compact evidence cards for final-answer context and UI.
- `backend/domains/ai_agent/answer_critic.py` rejects unsupported external Billboard / market claims and contradictions where found data is described as missing.
- `backend/tests/fixtures/ai_agent_golden_questions.json` and `scripts/evaluate_ai_agent_harness.py` provide an offline harness baseline.
- `frontend/src/features/ai-tasks/AIEvidenceCards.tsx` renders evidence cards in chat and task result shells.

The implementation should extend these modules, not replace them.

## File Structure

Create:

- `backend/domains/ai_agent/question_frame.py`  
  Converts `QuestionIntent` plus the raw question into a narrower analysis family, required axes, and answer contract.
- `backend/domains/ai_agent/evidence_recipes.py`  
  Maps `QuestionFrame.family` to required axes, recommended tool patterns, and follow-up limits.
- `backend/domains/ai_agent/analytical_brief.py`  
  Builds a deterministic final-answer brief from frame, recipe, tool results, coverage, and evidence cards.
- `backend/tests/unit/test_ai_agent_question_frame.py`
- `backend/tests/unit/test_ai_agent_evidence_recipes.py`
- `backend/tests/unit/test_ai_agent_analytical_brief.py`

Modify:

- `backend/domains/ai_agent/coverage_review.py`  
  Add axis-level sufficiency review while preserving `review_coverage()` compatibility.
- `backend/domains/ai_agent/answer_critic.py`  
  Add contract-level checks for overclaim, ignored conflicts, missing fairness, wrong axis, and missing required answer sections.
- `backend/services/ai_agent_service.py`  
  Compute frame and recipe once, include them in planner/final payload, use axis-level sufficiency, pass analytical brief to final prompt, and include new metadata in task result.
- `backend/tests/unit/test_ai_agent_coverage_review.py`
- `backend/tests/unit/test_ai_agent_answer_critic.py`
- `backend/tests/unit/test_ai_agent_golden_questions.py`
- `backend/tests/fixtures/ai_agent_golden_questions.json`
- `scripts/evaluate_ai_agent_harness.py`
- `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`
- `frontend/src/tests/ai-evidence-cards.test.tsx`
- `docs/README.md`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `backend/CLAUDE.md`
- `frontend/CLAUDE.md`

## Execution Rules

- Keep all new AI Agent tools and harness data read-only.
- Do not expose arbitrary SQL, arbitrary URL fetches, settings mutations, import jobs, cache clears, playlist operations, or write APIs.
- Preserve the existing `review_coverage(question_intent, coverage)` call shape until `ai_agent_service.py` is migrated.
- Keep `MAX_TOOL_CALLS = 5`; sufficiency follow-ups must deduplicate against already executed calls.
- Do not make ranking questions verbose by default. The layered response contract is for complex families such as preference comparison and identity preference.

---

### Task 1: Add QuestionFrame

**Files:**
- Create: `backend/domains/ai_agent/question_frame.py`
- Create: `backend/tests/unit/test_ai_agent_question_frame.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_ai_agent_question_frame.py`:

```python
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent


def _frame(question: str):
    return build_question_frame(question, parse_question_intent(question))


def test_album_preference_comparison_uses_layered_contract():
    frame = _frame(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert frame.family == "preference_comparison"
    assert frame.task_type == "comparison"
    assert frame.entity_type == "album"
    assert frame.entities == ["GUTS", "The Life of a Showgirl"]
    assert frame.answer_contract == "layered_preference_comparison"
    assert frame.requires_layered_conclusion is True
    assert set(frame.analysis_axes) >= {
        "cumulative",
        "recency",
        "intensity",
        "personal_billboard",
        "fairness",
    }


def test_late_night_song_question_uses_time_of_day_family():
    frame = _frame("我深夜最爱听什么歌？")

    assert frame.family == "time_of_day_ranking"
    assert frame.entity_type == "track"
    assert frame.answer_contract == "time_of_day_answer"
    assert frame.analysis_axes == ["time_of_day", "ranking"]


def test_2023_top_artist_stays_simple_ranking():
    frame = _frame("2023年我播放量最高的艺人是谁？")

    assert frame.family == "simple_ranking"
    assert frame.answer_contract == "simple_rank_answer"
    assert frame.time_scope == "year:2023"
    assert frame.requires_layered_conclusion is False


def test_identity_question_requires_layered_axes():
    frame = _frame("Taylor Swift 和 Olivia Rodrigo 谁更像我的本命？")

    assert frame.family == "identity_preference"
    assert frame.answer_contract == "identity_preference_answer"
    assert set(frame.analysis_axes) >= {"cumulative", "recency", "consistency", "peak"}
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_question_frame.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domains.ai_agent.question_frame'`.

- [ ] **Step 3: Implement QuestionFrame**

Create `backend/domains/ai_agent/question_frame.py`:

```python
"""Deterministic analytical framing for AI Agent questions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from backend.domains.ai_agent.question_intent import QuestionIntent

QuestionFamily = Literal[
    "simple_ranking",
    "entity_detail",
    "preference_comparison",
    "trend_preference",
    "period_comparison",
    "change_explanation",
    "time_of_day_ranking",
    "identity_preference",
    "habit_summary",
]

AnalysisAxis = Literal[
    "cumulative",
    "recency",
    "intensity",
    "personal_billboard",
    "fairness",
    "trend",
    "period",
    "time_of_day",
    "ranking",
    "detail",
    "consistency",
    "peak",
    "behavior",
]

AnswerContract = Literal[
    "simple_rank_answer",
    "entity_detail_answer",
    "layered_preference_comparison",
    "trend_answer",
    "period_comparison_answer",
    "change_explanation_answer",
    "time_of_day_answer",
    "identity_preference_answer",
    "habit_summary_answer",
]


class QuestionFrame(BaseModel):
    family: QuestionFamily
    task_type: str = "general"
    entity_type: str = "unknown"
    entities: list[str] = Field(default_factory=list)
    time_scope: str = "lifetime"
    requested_metrics: list[str] = Field(default_factory=list)
    analysis_axes: list[AnalysisAxis] = Field(default_factory=list)
    answer_contract: AnswerContract
    requires_layered_conclusion: bool = False


def _contains_any(question: str, tokens: Sequence[str]) -> bool:
    lower_question = question.casefold()
    return any(token.casefold() in lower_question for token in tokens)


def _dedupe_axes(axes: list[AnalysisAxis]) -> list[AnalysisAxis]:
    deduped: list[AnalysisAxis] = []
    for axis in axes:
        if axis not in deduped:
            deduped.append(axis)
    return deduped


def _family(question: str, intent: QuestionIntent) -> QuestionFamily:
    if _contains_any(question, ("本命", "真爱", "核心偏好")):
        return "identity_preference"
    if _contains_any(question, ("为什么", "原因")) and _contains_any(
        question,
        ("下降", "掉", "回落", "变少", "减少"),
    ):
        return "change_explanation"
    if _contains_any(question, ("今年和去年", "去年和今年", "相比去年", "对比去年")):
        return "period_comparison"
    if "time_of_day" in intent.requested_metrics:
        return "time_of_day_ranking"
    if intent.task_type == "comparison" and (
        _contains_any(question, ("更喜欢", "喜爱", "更甚", "最爱", "喜欢程度"))
        or "plays" in intent.requested_metrics
    ):
        return "preference_comparison"
    if intent.task_type == "trend":
        return "trend_preference"
    if intent.task_type == "ranking":
        return "simple_ranking"
    if intent.task_type == "entity_detail":
        return "entity_detail"
    return "habit_summary"


def _axes_for_family(family: QuestionFamily, intent: QuestionIntent) -> list[AnalysisAxis]:
    if family == "preference_comparison":
        axes: list[AnalysisAxis] = ["cumulative", "recency", "intensity"]
        if "personal_billboard" in intent.requested_metrics:
            axes.append("personal_billboard")
        if intent.needs_fairness_note or len(intent.entities) >= 2:
            axes.append("fairness")
        return _dedupe_axes(axes)
    if family == "identity_preference":
        return ["cumulative", "recency", "consistency", "peak", "personal_billboard", "fairness"]
    if family == "trend_preference":
        return ["recency", "trend"]
    if family == "period_comparison":
        return ["period", "ranking"]
    if family == "change_explanation":
        return ["trend", "recency", "ranking"]
    if family == "time_of_day_ranking":
        return ["time_of_day", "ranking"]
    if family == "simple_ranking":
        return ["ranking"]
    if family == "entity_detail":
        axes = ["detail", "cumulative"]
        if "personal_billboard" in intent.requested_metrics:
            axes.append("personal_billboard")
        return axes
    return ["behavior", "cumulative"]


def _contract_for_family(family: QuestionFamily) -> AnswerContract:
    return {
        "simple_ranking": "simple_rank_answer",
        "entity_detail": "entity_detail_answer",
        "preference_comparison": "layered_preference_comparison",
        "trend_preference": "trend_answer",
        "period_comparison": "period_comparison_answer",
        "change_explanation": "change_explanation_answer",
        "time_of_day_ranking": "time_of_day_answer",
        "identity_preference": "identity_preference_answer",
        "habit_summary": "habit_summary_answer",
    }[family]


def build_question_frame(question: str, intent: QuestionIntent | dict[str, object]) -> QuestionFrame:
    parsed_intent = (
        intent if isinstance(intent, QuestionIntent) else QuestionIntent.model_validate(intent)
    )
    family = _family(question, parsed_intent)
    return QuestionFrame(
        family=family,
        task_type=parsed_intent.task_type,
        entity_type=parsed_intent.entity_type,
        entities=parsed_intent.entities,
        time_scope=parsed_intent.time_scope,
        requested_metrics=parsed_intent.requested_metrics,
        analysis_axes=_axes_for_family(family, parsed_intent),
        answer_contract=_contract_for_family(family),
        requires_layered_conclusion=family
        in {"preference_comparison", "identity_preference"},
    )
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_question_frame.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/domains/ai_agent/question_frame.py backend/tests/unit/test_ai_agent_question_frame.py
git commit -m "feat: add AI agent question frame"
```

---

### Task 2: Add Evidence Recipes

**Files:**
- Create: `backend/domains/ai_agent/evidence_recipes.py`
- Create: `backend/tests/unit/test_ai_agent_evidence_recipes.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_ai_agent_evidence_recipes.py`:

```python
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent


def _recipe(question: str):
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    return recipe_for_frame(frame)


def test_preference_comparison_recipe_requires_recent_windows_and_compare_tool():
    recipe = _recipe(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert recipe.family == "preference_comparison"
    assert set(recipe.required_axes) >= {"cumulative", "recency", "intensity"}
    assert "personal_billboard" in recipe.required_axes
    assert "fairness" in recipe.conditional_axes
    assert {"tool_name": "compare_entities"} in recipe.required_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "period": "last_6_months",
    } in recipe.recommended_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "period": "last_4_weeks",
    } in recipe.recommended_tool_patterns


def test_simple_ranking_recipe_stays_small():
    recipe = _recipe("2023年我播放量最高的艺人是谁？")

    assert recipe.family == "simple_ranking"
    assert recipe.required_axes == ["ranking"]
    assert {"tool_name": "analysis_charts"} in recipe.required_tool_patterns
    assert recipe.max_followup_calls == 2


def test_time_of_day_recipe_uses_late_night_tracks():
    recipe = _recipe("我深夜最爱听什么歌？")

    assert recipe.family == "time_of_day_ranking"
    assert recipe.required_tool_patterns == [
        {"tool_name": "listening_hours", "view": "late_night_tracks"}
    ]
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_recipes.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domains.ai_agent.evidence_recipes'`.

- [ ] **Step 3: Implement EvidenceRecipe**

Create `backend/domains/ai_agent/evidence_recipes.py`:

```python
"""Evidence recipes for AI Agent analytical question families."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.domains.ai_agent.question_frame import QuestionFrame


class EvidenceRecipe(BaseModel):
    family: str
    required_axes: list[str] = Field(default_factory=list)
    conditional_axes: list[str] = Field(default_factory=list)
    required_tool_patterns: list[dict[str, object]] = Field(default_factory=list)
    recommended_tool_patterns: list[dict[str, object]] = Field(default_factory=list)
    max_followup_calls: int = 4


def recipe_for_frame(frame: QuestionFrame | dict[str, object]) -> EvidenceRecipe:
    parsed_frame = (
        frame if isinstance(frame, QuestionFrame) else QuestionFrame.model_validate(frame)
    )
    family = parsed_frame.family
    if family == "preference_comparison":
        required_axes = ["cumulative", "recency", "intensity"]
        if "personal_billboard" in parsed_frame.analysis_axes:
            required_axes.append("personal_billboard")
        return EvidenceRecipe(
            family=family,
            required_axes=required_axes,
            conditional_axes=["fairness"],
            required_tool_patterns=[{"tool_name": "compare_entities"}],
            recommended_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "entity_stats", "period": "last_4_weeks"},
            ],
            max_followup_calls=4,
        )
    if family == "identity_preference":
        return EvidenceRecipe(
            family=family,
            required_axes=["cumulative", "recency", "consistency", "peak"],
            conditional_axes=["personal_billboard", "fairness"],
            required_tool_patterns=[
                {"tool_name": "compare_entities"},
                {"tool_name": "entity_stats", "period": "last_6_months"},
            ],
            recommended_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_4_weeks"},
                {"tool_name": "billboard_entity_detail"},
            ],
            max_followup_calls=4,
        )
    if family == "trend_preference":
        return EvidenceRecipe(
            family=family,
            required_axes=["recency", "trend"],
            required_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "analysis_charts", "period": "last_6_months"},
            ],
            max_followup_calls=3,
        )
    if family == "period_comparison":
        return EvidenceRecipe(
            family=family,
            required_axes=["period", "ranking"],
            required_tool_patterns=[
                {"tool_name": "analysis_charts"},
                {"tool_name": "wrapped_yearly"},
            ],
            max_followup_calls=3,
        )
    if family == "change_explanation":
        return EvidenceRecipe(
            family=family,
            required_axes=["trend", "recency", "ranking"],
            required_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_6_months"},
                {"tool_name": "analysis_charts", "period": "last_6_months"},
            ],
            recommended_tool_patterns=[
                {"tool_name": "entity_stats", "period": "last_4_weeks"}
            ],
            max_followup_calls=4,
        )
    if family == "time_of_day_ranking":
        return EvidenceRecipe(
            family=family,
            required_axes=["time_of_day", "ranking"],
            required_tool_patterns=[
                {"tool_name": "listening_hours", "view": "late_night_tracks"}
            ],
            max_followup_calls=1,
        )
    if family == "simple_ranking":
        return EvidenceRecipe(
            family=family,
            required_axes=["ranking"],
            required_tool_patterns=[{"tool_name": "analysis_charts"}],
            recommended_tool_patterns=[{"tool_name": "wrapped_yearly"}],
            max_followup_calls=2,
        )
    if family == "entity_detail":
        required = [{"tool_name": "entity_stats"}]
        recommended = []
        if "personal_billboard" in parsed_frame.analysis_axes:
            recommended.append({"tool_name": "billboard_entity_detail"})
        return EvidenceRecipe(
            family=family,
            required_axes=["detail", "cumulative"],
            conditional_axes=["personal_billboard"],
            required_tool_patterns=required,
            recommended_tool_patterns=recommended,
            max_followup_calls=3,
        )
    return EvidenceRecipe(
        family=family,
        required_axes=["behavior", "cumulative"],
        required_tool_patterns=[{"tool_name": "analysis_stats"}],
        recommended_tool_patterns=[{"tool_name": "listening_hours"}],
        max_followup_calls=3,
    )
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_recipes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/domains/ai_agent/evidence_recipes.py backend/tests/unit/test_ai_agent_evidence_recipes.py
git commit -m "feat: add AI agent evidence recipes"
```

---

### Task 3: Upgrade Coverage Review to Axis Sufficiency

**Files:**
- Modify: `backend/domains/ai_agent/coverage_review.py`
- Modify: `backend/tests/unit/test_ai_agent_coverage_review.py`

- [ ] **Step 1: Add failing sufficiency tests**

Append to `backend/tests/unit/test_ai_agent_coverage_review.py`:

```python
from backend.domains.ai_agent.coverage_review import review_evidence_sufficiency
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent


def _frame_and_recipe(question: str):
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    return frame, recipe_for_frame(frame)


def test_preference_comparison_requests_recent_followups_when_lifetime_compare_exists():
    question = "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    frame, recipe = _frame_and_recipe(question)
    tool_results = [
        {
            "tool_name": "compare_entities",
            "status": "done",
            "source_range": "comparison",
            "params_summary": "entity_type=album, names=['GUTS', 'The Life of a Showgirl']",
            "data": {
                "entity_type": "album",
                "winner_by_cumulative_plays": "GUTS",
                "winner_by_power_score": "GUTS",
                "winner_by_intensity": "The Life of a Showgirl",
                "entities": [
                    {"name": "GUTS", "found": True, "plays": 1749, "power_score": 13566},
                    {
                        "name": "The Life of a Showgirl",
                        "found": True,
                        "plays": 1637,
                        "power_score": 10629,
                    },
                ],
                "fairness_notes": ["对象进入你的播放历史时间不同，累计值和强度值需要分开看。"],
            },
        }
    ]

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=tool_results,
        coverage={"comparison": {"compare_entities": "found"}},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["cumulative"] == "covered"
    assert review["axis_coverage"]["recency"] == "missing"
    assert review["axis_coverage"]["intensity"] == "covered"
    assert review["axis_coverage"]["personal_billboard"] == "covered"
    assert any(call["params"]["period"] == "last_6_months" for call in review["followup_tool_calls"])
    assert any(call["params"]["period"] == "last_4_weeks" for call in review["followup_tool_calls"])


def test_time_of_day_ranking_is_sufficient_with_late_night_tool():
    frame, recipe = _frame_and_recipe("我深夜最爱听什么歌？")
    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "listening_hours",
                "status": "done",
                "source_range": "late_night_tracks",
                "params_summary": "view=late_night_tracks",
                "data": {"view": "late_night_tracks", "items": {"tracks": []}},
            }
        ],
        coverage={},
    )

    assert review["sufficient"] is True
    assert review["axis_coverage"]["time_of_day"] == "covered"
    assert review["axis_coverage"]["ranking"] == "covered"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_coverage_review.py -q
```

Expected: FAIL because `review_evidence_sufficiency` is not defined.

- [ ] **Step 3: Implement axis-level review**

Modify `backend/domains/ai_agent/coverage_review.py` by adding these helpers and public function while keeping the existing `review_coverage()` intact:

```python
def _period_from_item(item: dict[str, Any]) -> str:
    data = item.get("data")
    if isinstance(data, dict):
        period = data.get("period")
        if isinstance(period, dict):
            value = period.get("period") or period.get("label")
            if isinstance(value, str):
                return value
    text = f"{item.get('source_range', '')} {item.get('params_summary', '')}"
    for period_name in ("last_6_months", "last_4_weeks", "this_year", "lifetime"):
        if period_name in text:
            return period_name
    return ""


def _has_tool(tool_results: list[dict[str, Any]], tool_name: str) -> bool:
    return any(item.get("tool_name") == tool_name and item.get("status") != "error" for item in tool_results)


def _has_recent_period(tool_results: list[dict[str, Any]]) -> bool:
    return any(
        item.get("tool_name") == "entity_stats"
        and _period_from_item(item) in {"last_6_months", "last_4_weeks"}
        for item in tool_results
    )


def _has_late_night_tool(tool_results: list[dict[str, Any]]) -> bool:
    return any(
        item.get("tool_name") == "listening_hours"
        and "late_night_tracks" in f"{item.get('source_range', '')} {item.get('params_summary', '')} {item.get('data', {})}"
        for item in tool_results
    )


def _compare_data(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in tool_results:
        if item.get("tool_name") != "compare_entities":
            continue
        data = item.get("data")
        if isinstance(data, dict):
            return data
    return {}


def _entity_followups(frame: dict[str, Any], period: str) -> list[dict[str, Any]]:
    entity_type = str(frame.get("entity_type") or "unknown")
    entities = frame.get("entities")
    if not isinstance(entities, list):
        return []
    calls: list[dict[str, Any]] = []
    for entity_name in entities:
        if not isinstance(entity_name, str) or not entity_name.strip():
            continue
        params: dict[str, Any] = {"entity": entity_type, "period": period}
        if entity_type == "album":
            params["album_name"] = entity_name
        elif entity_type == "artist":
            params["artist_name"] = entity_name
        elif entity_type == "track":
            params["track_name"] = entity_name
        else:
            continue
        calls.append({"tool_name": "entity_stats", "params": params})
    return calls


def _axis_coverage_for(
    axis: str,
    *,
    frame: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> str:
    comparison = _compare_data(tool_results)
    if axis == "cumulative":
        return "covered" if _has_tool(tool_results, "compare_entities") or _has_tool(tool_results, "entity_stats") else "missing"
    if axis == "recency":
        return "covered" if _has_recent_period(tool_results) else "missing"
    if axis == "intensity":
        return "covered" if comparison.get("winner_by_intensity") else "missing"
    if axis == "personal_billboard":
        if comparison.get("winner_by_power_score") or comparison.get("winner_by_power_rank"):
            return "covered"
        return "covered" if _has_tool(tool_results, "billboard_entity_detail") else "missing"
    if axis == "fairness":
        notes = comparison.get("fairness_notes")
        return "covered" if isinstance(notes, list) and notes else "partial"
    if axis == "time_of_day":
        return "covered" if _has_late_night_tool(tool_results) else "missing"
    if axis == "ranking":
        return "covered" if _has_tool(tool_results, "analysis_charts") or _has_late_night_tool(tool_results) else "missing"
    if axis == "trend":
        return "covered" if _has_recent_period(tool_results) or _has_tool(tool_results, "analysis_charts") else "missing"
    if axis == "period":
        return "covered" if _has_tool(tool_results, "wrapped_yearly") or _has_tool(tool_results, "analysis_charts") else "missing"
    if axis in {"detail", "behavior"}:
        return "covered" if tool_results else "missing"
    if axis in {"consistency", "peak"}:
        return "partial" if _has_tool(tool_results, "compare_entities") else "missing"
    return "missing"


def review_evidence_sufficiency(
    *,
    question_frame: dict[str, Any],
    evidence_recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    frame = question_frame if isinstance(question_frame, dict) else {}
    recipe = evidence_recipe if isinstance(evidence_recipe, dict) else {}
    required_axes = recipe.get("required_axes")
    if not isinstance(required_axes, list):
        required_axes = []
    conditional_axes = recipe.get("conditional_axes")
    if not isinstance(conditional_axes, list):
        conditional_axes = []
    requested_axes = list(dict.fromkeys([*required_axes, *conditional_axes]))

    axis_coverage = {
        str(axis): _axis_coverage_for(str(axis), frame=frame, tool_results=tool_results)
        for axis in requested_axes
    }
    missing_axes = [
        axis
        for axis, status in axis_coverage.items()
        if axis in required_axes and status == "missing"
    ]
    reasons = [f"{frame.get('family')} 缺少 {axis} 证据" for axis in missing_axes]
    followups: list[dict[str, Any]] = []
    max_followups = int(recipe.get("max_followup_calls") or 4)

    if "recency" in missing_axes:
        for period in ("last_6_months", "last_4_weeks"):
            for call in _entity_followups(frame, period):
                if len(followups) >= max_followups:
                    break
                followups.append(call)
    if "time_of_day" in missing_axes and len(followups) < max_followups:
        followups.append({"tool_name": "listening_hours", "params": {"view": "late_night_tracks"}})
    if "ranking" in missing_axes and len(followups) < max_followups:
        followups.append(
            {
                "tool_name": "analysis_charts",
                "params": {
                    "entity": frame.get("entity_type") if frame.get("entity_type") != "unknown" else "track",
                    "metric": "plays",
                    "period": "lifetime",
                    "limit": 10,
                },
            }
        )

    legacy_review = review_coverage(
        question_intent={
            "task_type": frame.get("task_type"),
            "entity_type": frame.get("entity_type"),
            "entities": frame.get("entities", []),
            "requested_metrics": frame.get("requested_metrics", []),
        },
        coverage=coverage,
    )
    for call in legacy_review.get("followup_tool_calls", []):
        if len(followups) >= max_followups:
            break
        if call not in followups:
            followups.append(call)
    reasons.extend(str(reason) for reason in legacy_review.get("reasons", []))

    return {
        "sufficient": not missing_axes and bool(legacy_review.get("sufficient", True)),
        "axis_coverage": axis_coverage,
        "missing_axes": missing_axes,
        "reasons": reasons,
        "followup_tool_calls": followups[:max_followups],
    }
```

- [ ] **Step 4: Run focused coverage tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_coverage_review.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/domains/ai_agent/coverage_review.py backend/tests/unit/test_ai_agent_coverage_review.py
git commit -m "feat: add AI agent evidence sufficiency review"
```

---

### Task 4: Add AnalyticalBrief

**Files:**
- Create: `backend/domains/ai_agent/analytical_brief.py`
- Create: `backend/tests/unit/test_ai_agent_analytical_brief.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_ai_agent_analytical_brief.py`:

```python
from backend.domains.ai_agent.analytical_brief import build_analytical_brief
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent


def test_preference_comparison_brief_keeps_conflicting_winners():
    question = "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    recipe = recipe_for_frame(frame)
    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "data": {
                    "entity_type": "album",
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_total_hours": "The Life of a Showgirl",
                    "winner_by_power_score": "GUTS",
                    "winner_by_intensity": "The Life of a Showgirl",
                    "entities": [
                        {
                            "name": "GUTS",
                            "found": True,
                            "plays": 1749,
                            "hours": 95.6,
                            "power_score": 13566,
                            "weeks_on_chart": 79,
                            "no1_weeks": 11,
                        },
                        {
                            "name": "The Life of a Showgirl",
                            "found": True,
                            "plays": 1637,
                            "hours": 96.0,
                            "power_score": 10629,
                            "weeks_on_chart": 37,
                            "no1_weeks": 14,
                        },
                    ],
                    "fairness_notes": ["对象进入你的播放历史时间不同，累计值和强度值需要分开看。"],
                },
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=album, album_name=The Life of a Showgirl, period=last_6_months",
                "data": {"summary": {"total_plays": 1200}},
            },
        ],
        coverage={"comparison": {"compare_entities": "found"}},
        evidence_cards=[],
    )

    assert brief["family"] == "preference_comparison"
    assert brief["conflict"] is True
    assert brief["dimension_winners"]["cumulative_plays"] == "GUTS"
    assert brief["dimension_winners"]["total_hours"] == "The Life of a Showgirl"
    assert brief["dimension_winners"]["intensity"] == "The Life of a Showgirl"
    assert "long_term" in brief["recommended_conclusion"]
    assert "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard" in brief["must_explain"]
    assert "市场影响力更大" in brief["forbidden_claims"]


def test_simple_ranking_brief_stays_concise():
    question = "2023年我播放量最高的艺人是谁？"
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    recipe = recipe_for_frame(frame)
    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "source_range": "2023-01-01..2023-12-31",
                "data": {
                    "entity": "artist",
                    "metric": "plays",
                    "rows": [{"rank": 1, "artist_name": "Taylor Swift", "plays": 800}],
                },
            }
        ],
        coverage={},
        evidence_cards=[],
    )

    assert brief["family"] == "simple_ranking"
    assert brief["conflict"] is False
    assert brief["recommended_conclusion"]["top_result"] == "Taylor Swift"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_analytical_brief.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domains.ai_agent.analytical_brief'`.

- [ ] **Step 3: Implement AnalyticalBrief builder**

Create `backend/domains/ai_agent/analytical_brief.py`:

```python
"""Deterministic analytical briefs for AI Agent final answers."""

from __future__ import annotations

from typing import Any


def _compare_data(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    for item in tool_results:
        if item.get("tool_name") != "compare_entities":
            continue
        data = item.get("data")
        if isinstance(data, dict):
            return data
    return {}


def _winner_values(compare_data: dict[str, Any]) -> dict[str, str]:
    mapping = {
        "cumulative_plays": compare_data.get("winner_by_cumulative_plays"),
        "total_hours": compare_data.get("winner_by_total_hours"),
        "power_score": compare_data.get("winner_by_power_score"),
        "power_rank": compare_data.get("winner_by_power_rank"),
        "intensity": compare_data.get("winner_by_intensity"),
    }
    return {key: str(value) for key, value in mapping.items() if value}


def _has_conflict(winners: dict[str, str]) -> bool:
    values = {winner for winner in winners.values() if winner}
    return len(values) > 1


def _ranking_top_result(tool_results: list[dict[str, Any]]) -> str | None:
    for item in tool_results:
        if item.get("tool_name") != "analysis_charts":
            continue
        data = item.get("data")
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            continue
        first = rows[0]
        if not isinstance(first, dict):
            continue
        for key in ("artist_name", "album_name", "track_name", "name"):
            value = first.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _preference_brief(
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    compare_data = _compare_data(tool_results)
    winners = _winner_values(compare_data)
    conflict = _has_conflict(winners)
    long_term = winners.get("cumulative_plays") or winners.get("power_score")
    recent_intensity = winners.get("intensity") or winners.get("total_hours")
    single = long_term or recent_intensity
    must_explain = [
        "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard",
        "累计值受进入播放历史时间影响",
    ]
    if conflict:
        must_explain.append("不同口径胜者不一致，不能说单方明显胜出")
    fairness_notes = compare_data.get("fairness_notes")
    if isinstance(fairness_notes, list):
        must_explain.extend(str(note) for note in fairness_notes if isinstance(note, str))
    return {
        "family": frame.get("family"),
        "answer_contract": frame.get("answer_contract"),
        "main_question": "比较对象哪一个更能代表用户偏好",
        "dimension_winners": winners,
        "conflict": conflict,
        "recommended_conclusion": {
            "long_term": long_term,
            "recent_intensity": recent_intensity,
            "single_answer_if_forced": single,
        },
        "must_explain": list(dict.fromkeys(must_explain)),
        "forbidden_claims": [
            "市场影响力更大",
            "外部官方 Billboard 成绩",
            "所有指标均指向同一对象",
            "明显单方胜出",
        ],
        "evidence_recipe": recipe,
    }


def build_analytical_brief(
    *,
    question_frame: dict[str, Any],
    evidence_recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
    coverage: dict[str, Any],
    evidence_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    frame = question_frame if isinstance(question_frame, dict) else {}
    recipe = evidence_recipe if isinstance(evidence_recipe, dict) else {}
    family = str(frame.get("family") or "")
    if family in {"preference_comparison", "identity_preference"}:
        return _preference_brief(frame=frame, recipe=recipe, tool_results=tool_results)
    if family == "simple_ranking":
        return {
            "family": family,
            "answer_contract": frame.get("answer_contract"),
            "main_question": "找出指定范围内的最高排名结果",
            "dimension_winners": {},
            "conflict": False,
            "recommended_conclusion": {"top_result": _ranking_top_result(tool_results)},
            "must_explain": ["说明时间范围和排序指标"],
            "forbidden_claims": ["混用不同时间范围"],
            "evidence_recipe": recipe,
        }
    if family == "time_of_day_ranking":
        return {
            "family": family,
            "answer_contract": frame.get("answer_contract"),
            "main_question": "找出指定时段内的偏好排行",
            "dimension_winners": {},
            "conflict": False,
            "recommended_conclusion": {"time_axis": "late_night_tracks"},
            "must_explain": ["说明时段窗口，不能用总体排行替代时段排行"],
            "forbidden_claims": ["用总体排行替代深夜排行"],
            "evidence_recipe": recipe,
        }
    return {
        "family": family or "habit_summary",
        "answer_contract": frame.get("answer_contract"),
        "main_question": "概括用户问题对应的本地听歌数据证据",
        "dimension_winners": {},
        "conflict": False,
        "recommended_conclusion": {},
        "must_explain": ["只基于本地工具证据回答"],
        "forbidden_claims": ["声称访问了 DATA 之外的数据"],
        "evidence_recipe": recipe,
        "coverage": coverage,
        "evidence_card_count": len(evidence_cards),
    }
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_analytical_brief.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/domains/ai_agent/analytical_brief.py backend/tests/unit/test_ai_agent_analytical_brief.py
git commit -m "feat: add AI agent analytical brief"
```

---

### Task 5: Wire Frame, Recipe, Sufficiency, and Brief Into Agent Service

**Files:**
- Modify: `backend/services/ai_agent_service.py`
- Modify: `backend/tests/unit/test_ai_agent_tools.py`
- Modify: `backend/tests/contract/test_ai_agent_task_contract.py`

- [ ] **Step 1: Add focused service-level tests**

Append to `backend/tests/unit/test_ai_agent_tools.py` or create a new unit test file if the existing file is already dense:

```python
from backend.services import ai_agent_service


def test_planner_user_content_contains_frame_and_recipe():
    content = ai_agent_service._planner_user_content(
        {
            "question": "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？",
            "thinking_mode": True,
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
            "merge_level": 2,
        }
    )

    assert '"question_frame"' in content
    assert '"family":"preference_comparison"' in content
    assert '"evidence_recipe"' in content
    assert '"layered_preference_comparison"' in content


def test_final_payload_contains_analytical_brief_and_sufficiency():
    request = {
        "question": "我深夜最爱听什么歌？",
        "thinking_mode": False,
    }
    payload = ai_agent_service._final_payload(
        request,
        [
            {
                "tool_name": "listening_hours",
                "status": "done",
                "source_range": "late_night_tracks",
                "params_summary": "view=late_night_tracks",
                "result_summary": "深夜歌曲排行",
                "data": {"view": "late_night_tracks", "items": {"tracks": []}},
            }
        ],
    )

    assert payload["question_frame"]["family"] == "time_of_day_ranking"
    assert payload["evidence_recipe"]["family"] == "time_of_day_ranking"
    assert payload["evidence_sufficiency"]["sufficient"] is True
    assert payload["analytical_brief"]["answer_contract"] == "time_of_day_answer"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_tools.py -q
```

Expected: FAIL because planner/final payloads do not include the new fields.

- [ ] **Step 3: Import and compute frame plus recipe**

Modify imports in `backend/services/ai_agent_service.py`:

```python
from backend.domains.ai_agent.analytical_brief import build_analytical_brief
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
```

Add this helper near `_thinking_mode_enabled()`:

```python
def _question_context(request: dict[str, Any]) -> dict[str, Any]:
    question = str(request.get("question", ""))
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    recipe = recipe_for_frame(frame)
    return {
        "question_intent": intent.model_dump(),
        "question_frame": frame.model_dump(),
        "evidence_recipe": recipe.model_dump(),
    }
```

- [ ] **Step 4: Update planner content and prompts**

Modify `_planner_user_content()` so it merges `_question_context(request)`:

```python
context = _question_context(request)
payload = {
    "question": question,
    **context,
    "conversation_history": (request.get("conversation_history") or [])[-6:],
    "thinking_mode": _thinking_mode_enabled(request),
    "default_filters": {
        **_base_filter_params(request),
        "merge_level": request.get("merge_level", 1),
    },
    "available_tools": describe_for_model(),
}
```

Extend `PLANNER_SYSTEM_PROMPT` with these sentences:

```text
DATA.question_frame 是硬约束，family 决定问题类型，analysis_axes 决定必须覆盖的证据维度。
DATA.evidence_recipe 是最低证据要求；规划工具时优先满足 required_axes 和 required_tool_patterns。
如果 family=preference_comparison，必须优先使用 compare_entities，并尽量补 last_6_months 或 last_4_weeks 的 entity_stats。
如果 family=trend_preference，不得只查询 lifetime。
如果 family=time_of_day_ranking，必须使用 listening_hours 且 view=late_night_tracks。
```

- [ ] **Step 5: Replace coverage review call with sufficiency review**

Import `review_evidence_sufficiency` and keep `review_coverage` only for compatibility tests:

```python
from backend.domains.ai_agent.coverage_review import review_evidence_sufficiency
```

Inside `run_chat_agent_task()`, replace the old `question_intent` assignment and `review_coverage` block with:

```python
context = _question_context(request)
coverage = _build_coverage(tool_results)
coverage_review = review_evidence_sufficiency(
    question_frame=context["question_frame"],
    evidence_recipe=context["evidence_recipe"],
    tool_results=tool_results,
    coverage=coverage,
)
```

Preserve the existing follow-up execution loop and deduplication.

- [ ] **Step 6: Add brief to final payload**

Modify `_final_payload()`:

```python
def _final_payload(
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    compact_results = [_compact_tool_result_for_llm(item) for item in tool_results]
    evidence_cards = build_evidence_cards(tool_results)
    compact_cards = compact_evidence_cards(evidence_cards)
    context = _question_context(request)
    coverage = _build_coverage(tool_results)
    evidence_sufficiency = review_evidence_sufficiency(
        question_frame=context["question_frame"],
        evidence_recipe=context["evidence_recipe"],
        tool_results=tool_results,
        coverage=coverage,
    )
    analytical_brief = build_analytical_brief(
        question_frame=context["question_frame"],
        evidence_recipe=context["evidence_recipe"],
        tool_results=tool_results,
        coverage=coverage,
        evidence_cards=compact_cards,
    )
    return {
        "question": request.get("question", ""),
        "conversation_history": (request.get("conversation_history") or [])[-6:],
        **context,
        "coverage": coverage,
        "evidence_sufficiency": evidence_sufficiency,
        "analytical_brief": analytical_brief,
        "evidence_cards": compact_cards,
        "tool_results": compact_results,
    }
```

- [ ] **Step 7: Update final-answer prompts and retry instruction**

Extend both final system prompts:

```text
DATA.question_frame.family 决定回答形状，DATA.answer_contract 或 DATA.analytical_brief.answer_contract 是硬约束。
DATA.analytical_brief 是回答底稿；必须覆盖 must_explain，不得出现 forbidden_claims。
如果 DATA.analytical_brief.conflict=true，必须分层回答，不要说所有指标都指向同一个对象。
```

Update `_retry_user_content()` instruction:

```python
"上一版回答与工具证据或回答契约矛盾。请只基于 coverage、evidence_sufficiency、analytical_brief 和 tool_results 重新回答；"
"不要声称 found 的实体或榜单数据缺失，不要忽略 analytical_brief.must_explain。"
```

- [ ] **Step 8: Include metadata in task result**

In the result dictionary passed to `_mark_done()`, add:

```python
"question_frame": final_payload["question_frame"],
"evidence_sufficiency": final_payload["evidence_sufficiency"],
"analytical_brief": final_payload["analytical_brief"],
```

- [ ] **Step 9: Run service tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_tools.py backend/tests/contract/test_ai_agent_task_contract.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

Run:

```bash
git add backend/services/ai_agent_service.py backend/tests/unit/test_ai_agent_tools.py backend/tests/contract/test_ai_agent_task_contract.py
git commit -m "feat: wire AI analytical harness into chat agent"
```

---

### Task 6: Extend Answer Critic and Golden Harness

**Files:**
- Modify: `backend/domains/ai_agent/answer_critic.py`
- Modify: `backend/tests/unit/test_ai_agent_answer_critic.py`
- Modify: `backend/tests/fixtures/ai_agent_golden_questions.json`
- Modify: `backend/tests/unit/test_ai_agent_golden_questions.py`
- Modify: `scripts/evaluate_ai_agent_harness.py`

- [ ] **Step 1: Add failing critic tests**

Append to `backend/tests/unit/test_ai_agent_answer_critic.py`:

```python
from backend.domains.ai_agent.answer_critic import critique_answer


def test_critic_rejects_single_winner_overclaim_when_brief_has_conflict():
    payload = {
        "analytical_brief": {
            "family": "preference_comparison",
            "answer_contract": "layered_preference_comparison",
            "conflict": True,
            "dimension_winners": {
                "cumulative_plays": "GUTS",
                "total_hours": "The Life of a Showgirl",
                "intensity": "The Life of a Showgirl",
            },
            "must_explain": ["不同口径胜者不一致，不能说单方明显胜出"],
            "forbidden_claims": ["明显单方胜出", "所有指标均指向同一对象"],
        },
        "coverage": {},
    }

    result = critique_answer("结论：所有指标均指向 GUTS 明显胜出。", payload)

    assert result["ok"] is False
    assert any("冲突证据" in issue or "过度单一结论" in issue for issue in result["issues"])


def test_critic_requires_personal_billboard_boundary_from_brief():
    payload = {
        "analytical_brief": {
            "family": "preference_comparison",
            "answer_contract": "layered_preference_comparison",
            "conflict": False,
            "dimension_winners": {"power_score": "GUTS"},
            "must_explain": ["SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"],
            "forbidden_claims": ["外部官方 Billboard 成绩"],
        },
        "coverage": {},
    }

    result = critique_answer("GUTS 的 Billboard 成绩更强。", payload)

    assert result["ok"] is False
    assert any("本地个人榜单" in issue for issue in result["issues"])
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_answer_critic.py -q
```

Expected: FAIL because the critic does not inspect `analytical_brief` contracts yet.

- [ ] **Step 3: Add contract-level critic helpers**

Modify `backend/domains/ai_agent/answer_critic.py`:

```python
from collections.abc import Sequence

CONFLICT_OVERCLAIM_TOKENS = (
    "明显胜出",
    "均指向",
    "都指向",
    "毫无疑问",
    "完全",
)


def _brief(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("analytical_brief")
    return value if isinstance(value, dict) else {}


def _answer_contains_any(answer: str, tokens: Sequence[str]) -> bool:
    return any(token in answer for token in tokens)


def _brief_contract_issues(answer: str, payload: dict[str, Any]) -> list[str]:
    brief = _brief(payload)
    if not brief:
        return []
    issues: list[str] = []
    forbidden_claims = brief.get("forbidden_claims")
    if isinstance(forbidden_claims, list):
        for claim in forbidden_claims:
            if isinstance(claim, str) and claim and claim in answer:
                issues.append(f"回答出现 analytical_brief 禁止的 claim：{claim}")
                break
    if brief.get("conflict") is True and _answer_contains_any(answer, CONFLICT_OVERCLAIM_TOKENS):
        issues.append("analytical_brief 标记存在冲突证据，但回答给出过度单一结论。")
    must_explain = brief.get("must_explain")
    if isinstance(must_explain, list):
        for required in must_explain:
            if not isinstance(required, str):
                continue
            if "本地个人榜单" in required and not any(
                qualifier in answer for qualifier in PERSONAL_BILLBOARD_QUALIFIERS
            ):
                issues.append("回答缺少 SpotifyStats Billboard 是本地个人榜单的边界说明。")
                break
            if "不同口径胜者不一致" in required and not any(
                token in answer for token in ("不同口径", "分口径", "长期", "近期", "强度")
            ):
                issues.append("回答忽略了 analytical_brief 要求解释的冲突口径。")
                break
    return issues
```

At the end of `critique_answer()`, before returning, extend issues:

```python
if isinstance(final_payload, dict):
    issues.extend(_brief_contract_issues(answer, final_payload))
```

- [ ] **Step 4: Extend golden fixture fields**

For each item in `backend/tests/fixtures/ai_agent_golden_questions.json`, add:

```json
"expected_frame": {
  "family": "preference_comparison",
  "answer_contract": "layered_preference_comparison",
  "analysis_axes_contains": ["cumulative", "recency", "intensity"]
},
"expected_recipe": {
  "required_axes_contains": ["cumulative", "recency", "intensity"],
  "required_tool_patterns_contains": [{"tool_name": "compare_entities"}]
}
```

Use these values for the existing cases:

- `album_guts_vs_showgirl`: family `preference_comparison`, contract `layered_preference_comparison`, axes `cumulative`, `recency`, `intensity`, `personal_billboard`, `fairness`.
- `artist_olivia_last_6_months_trend`: family `trend_preference`, contract `trend_answer`, axes `recency`, `trend`.
- `ranking_top_artist_2023`: family `simple_ranking`, contract `simple_rank_answer`, axes `ranking`.
- `deep_night_tracks_and_hours`: family `time_of_day_ranking`, contract `time_of_day_answer`, axes `time_of_day`, `ranking`.

Add four new cases:

- `artist_identity_taylor_vs_olivia`
- `period_this_year_vs_last_year`
- `album_recent_drop_explanation`
- `habit_plays_vs_preference_explanation`

Each new case must include `question`, `expected_intent`, `expected_frame`, `expected_recipe`, `required_tool_calls`, `recommended_tools`, `required_answer_terms`, and `forbidden_answer_terms`.

- [ ] **Step 5: Update evaluator**

Modify `scripts/evaluate_ai_agent_harness.py` imports:

```python
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
```

Add validators:

```python
def _validate_contains(case_id: str, label: str, actual: list[Any], expected: Any) -> list[str]:
    if not isinstance(expected, list):
        return [f"{case_id}: {label} must be a list"]
    missing = [item for item in expected if item not in actual]
    return [f"{case_id}: {label} missing {missing}"] if missing else []


def _validate_frame_and_recipe(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = str(case.get("id") or "<missing-id>")
    question = str(case.get("question") or "")
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    recipe = recipe_for_frame(frame)

    expected_frame = case.get("expected_frame")
    if isinstance(expected_frame, dict):
        for key in ("family", "answer_contract"):
            if key in expected_frame and getattr(frame, key) != expected_frame[key]:
                failures.append(
                    f"{case_id}: frame.{key} expected {expected_frame[key]!r}, got {getattr(frame, key)!r}"
                )
        if "analysis_axes_contains" in expected_frame:
            failures.extend(
                _validate_contains(
                    case_id,
                    "frame.analysis_axes",
                    frame.analysis_axes,
                    expected_frame["analysis_axes_contains"],
                )
            )
    else:
        failures.append(f"{case_id}: expected_frame must be an object")

    expected_recipe = case.get("expected_recipe")
    if isinstance(expected_recipe, dict):
        if "required_axes_contains" in expected_recipe:
            failures.extend(
                _validate_contains(
                    case_id,
                    "recipe.required_axes",
                    recipe.required_axes,
                    expected_recipe["required_axes_contains"],
                )
            )
    else:
        failures.append(f"{case_id}: expected_recipe must be an object")
    return failures
```

Call it inside `evaluate_case()`:

```python
failures.extend(_validate_frame_and_recipe(case))
```

- [ ] **Step 6: Run golden and critic tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_golden_questions.py -q
.venv/bin/python scripts/evaluate_ai_agent_harness.py
```

Expected: PASS and evaluator prints `PASS`.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/domains/ai_agent/answer_critic.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/fixtures/ai_agent_golden_questions.json backend/tests/unit/test_ai_agent_golden_questions.py scripts/evaluate_ai_agent_harness.py
git commit -m "feat: enforce AI answer contracts"
```

---

### Task 7: Frontend Evidence Matrix and Documentation

**Files:**
- Modify: `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`
- Modify: `frontend/src/tests/ai-evidence-cards.test.tsx`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `AGENTS.md`
- Modify: `backend/CLAUDE.md`
- Modify: `frontend/CLAUDE.md`

- [ ] **Step 1: Add frontend test for comparison winner matrix**

Append to `frontend/src/tests/ai-evidence-cards.test.tsx`:

```tsx
it('renders comparison winner metrics as a readable matrix', () => {
  render(
    <AIEvidenceCards
      cards={[
        {
          card_id: 'album:comparison',
          title: '实体比较摘要',
          entity_type: 'album',
          question_axis: 'comparison',
          source: { tool_name: 'compare_entities', source_range: 'comparison' },
          metrics: [
            { name: 'winner_by_cumulative_plays', label: '累计播放胜出', value: 'GUTS' },
            { name: 'winner_by_total_hours', label: '播放时长胜出', value: 'The Life of a Showgirl' },
            { name: 'winner_by_power_score', label: '个人榜单 Power Score 胜出', value: 'GUTS' },
            { name: 'winner_by_intensity', label: '单位在榜周强度胜出', value: 'The Life of a Showgirl' },
          ],
          observations: ['对象进入你的播放历史时间不同，累计值和强度值需要分开看。'],
          limitations: ['比较结果必须说明口径。'],
        },
      ]}
    />,
  )

  expect(screen.getByText('累计播放胜出')).toBeInTheDocument()
  expect(screen.getAllByText('GUTS').length).toBeGreaterThanOrEqual(2)
  expect(screen.getByText('单位在榜周强度胜出')).toBeInTheDocument()
  expect(screen.getAllByText('The Life of a Showgirl').length).toBeGreaterThanOrEqual(2)
})
```

- [ ] **Step 2: Run the frontend test**

Run:

```bash
cd frontend && npm test -- ai-evidence-cards.test.tsx
```

Expected: PASS. The existing evidence card layout already supports this; if text wraps poorly in manual browser verification, continue to Step 3.

- [ ] **Step 3: Tighten comparison card layout**

If the test passes but the comparison matrix is cramped, modify the metrics grid in `AIEvidenceCards.tsx`:

```tsx
const isComparison = card.question_axis === 'comparison'
```

Replace the `<dl>` class:

```tsx
<dl className={`mt-3 grid gap-x-3 gap-y-2 ${isComparison ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-2'}`}>
```

This keeps long album names readable on 390px mobile while preserving the compact two-column layout on wider screens.

- [ ] **Step 4: Update documentation**

Update:

- `docs/README.md`: add this implementation plan under "当前功能设计" next to the spec.
- `docs/CHANGELOG.md`: add an Unreleased bullet describing the Universal Analytical Harness plan and the accepted scope.
- `AGENTS.md`: update the AI observable task paragraph once the implementation lands, naming `QuestionFrame`, `EvidenceRecipe`, `EvidenceSufficiency`, `AnalyticalBrief`, and answer contracts.
- `backend/CLAUDE.md`: add the new backend modules in the AI Agent/domain module list.
- `frontend/CLAUDE.md`: mention comparison evidence cards and the no-horizontal-overflow expectation.

The `docs/README.md` row should be:

```markdown
| [`superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md`](superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md) | AI Agent 通用分析中间层实施计划：问题家族、证据配方、分析底稿、回答契约与验收步骤 |
```

- [ ] **Step 5: Run backend and frontend verification**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_question_frame.py backend/tests/unit/test_ai_agent_evidence_recipes.py backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/unit/test_ai_agent_analytical_brief.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_golden_questions.py -q
.venv/bin/python scripts/evaluate_ai_agent_harness.py
cd frontend && npm test -- ai-evidence-cards.test.tsx
cd frontend && npm run build
```

Expected: all commands PASS.

- [ ] **Step 6: Run user-behavior verification in browser**

Start services if needed:

```bash
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend
cd frontend && npm run dev
```

Open `http://localhost:5173/ai-insights` and ask:

```text
从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？
```

Acceptance:

- Progress stages show planning, tool calls, coverage/evidence review, LLM generation.
- Tool trace includes `compare_entities` and recent-window follow-up evidence when available.
- Final answer states that cumulative/long-term evidence favors GUTS.
- Final answer states that intensity or some conflicting dimensions favor The Life of a Showgirl when evidence supports it.
- Final answer explicitly says SpotifyStats Billboard is the user's local personal chart, not external official Billboard.
- Final answer does not say every metric points to the same album.
- Evidence cards remain readable at desktop and 390px mobile widths.

- [ ] **Step 7: Commit**

Run:

```bash
git add frontend/src/features/ai-tasks/AIEvidenceCards.tsx frontend/src/tests/ai-evidence-cards.test.tsx docs/README.md docs/CHANGELOG.md AGENTS.md backend/CLAUDE.md frontend/CLAUDE.md
git commit -m "docs: document AI analytical harness rollout"
```

---

## Final Verification Matrix

Run these commands after all tasks are complete:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_question_intent.py backend/tests/unit/test_ai_agent_question_frame.py backend/tests/unit/test_ai_agent_evidence_recipes.py backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/unit/test_ai_agent_analytical_brief.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_golden_questions.py -q
.venv/bin/pytest backend/tests/contract/test_ai_agent_task_contract.py backend/tests/contract/test_ai_task_api.py -q
.venv/bin/python scripts/evaluate_ai_agent_harness.py
cd frontend && npm test -- ai-evidence-cards.test.tsx ai-insights-chat-task-flow.test.tsx
cd frontend && npm run build
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173
node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport both --include-detail-routes
```

Expected:

- All backend unit and contract tests pass.
- Golden harness prints `PASS`.
- Frontend tests and production build pass.
- `/ai-insights` interaction smoke passes.
- Control inventory smoke reports no visible interaction violations and no horizontal overflow.

## Self-Review Checklist

- Spec coverage: all accepted families have frame and recipe coverage; the first implementation deeply supports `preference_comparison`, `simple_ranking`, and `time_of_day_ranking`, while the other families receive deterministic frame/recipe/brief scaffolding and golden coverage.
- No write operations: the plan only touches read-only tool planning, local analysis evidence, deterministic validation, UI rendering, and docs.
- GUTS vs Showgirl generalization: the plan fixes the underlying axis/contract gap, not a single answer string.
- Backward compatibility: `review_coverage()` remains available; existing evidence cards and chat task result JSON remain additive.
- Verification: implementation must include unit tests, contract tests, golden harness, frontend tests, build, and browser-like AI Insights smoke.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session with checkpoints.

Because this touches the backend harness, answer quality gates, frontend evidence rendering, and docs, Subagent-Driven is the safer default.
