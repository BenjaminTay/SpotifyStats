# AI Agent Harness Quality Roadmap Implementation Plan（历史实施规划）

> 状态：`SUPERSEDED`；核心 harness 已实现并完成定向、golden 和真实问答验证，本文的未勾选步骤仅保留历史实施顺序
> 当前边界：更广泛的语言/曲风证据与完整真实问题矩阵继续按当前 issue、测试和交付报告治理，不以本文件旧 checkbox 表示进度

> 历史执行说明：下文曾建议用 subagent-driven 流程逐项实施。该说明不再是当前仓库指令，所有 `- [ ]` 保留为历史文本，不应解读为功能尚未开发。

**Goal:** Upgrade the current read-only AI chat Agent from a single-pass tool runner into a evidence-driven analysis harness that can answer broad listening-data questions with stable, inspectable quality.

**Architecture:** Keep the existing V2 AI task/event/tool-call infrastructure. Add a typed evidence layer, deterministic question-intent parsing, read-only entity resolution and comparison tools, bounded coverage-review follow-up rounds, deterministic answer critique, frontend evidence cards, and a golden-question evaluation harness.

**Tech Stack:** FastAPI, SQLite, Pydantic v2, pytest, React 19, TypeScript, TanStack Query, Vitest, Playwright smoke scripts.

---

## Current Baseline

The current V2 implementation already has:

- AI task runs/events/tool calls persisted through `backend/domains/ai_tasks/repository.py`.
- Chat Agent orchestration in `backend/services/ai_agent_service.py`.
- Read-only tool registry in `backend/domains/ai_agent/tool_registry.py`.
- Tool handlers in `backend/domains/ai_agent/tools.py`.
- Frontend progress and tool trace UI in `frontend/src/features/ai-tasks/`.
- AI chat task flow in `frontend/src/features/ai-insights/ChatInterface.tsx`.

The quality gap is the harness, not the model. The model can reason well when it receives the right evidence. The harness must therefore make evidence complete, normalized, compact, validated, and visible.

## Final Implementation Status

截至当前代码，本文核心目标均已有实现和回归入口：

| 能力 | 当前证据 |
|---|---|
| Typed evidence cards / builders | `backend/domains/ai_agent/evidence.py`、`evidence_builders.py` 及对应单元测试 |
| Question intent / entity resolver / comparison | `question_intent.py`、`entity_resolver.py`、`compare_entities` 工具与回归测试 |
| Coverage follow-up / answer critic | `coverage_review.py`、`answer_critic.py`、Agent service 集成与 contract tests |
| 前端 evidence cards | `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`、`AIResultShell.tsx` 及 Vitest |
| Golden harness | `backend/tests/fixtures/ai_agent_golden_questions.json`、`scripts/evaluate_ai_agent_harness.py` |

核心实施提交从 `d4214cb0`、`a49f67e8`、`87eed387`、`6f72b497`、`c49eb93f`、`3453bee6`、`75c1a141`、`b706ca49`、`6bcbde1f` 到文档收口 `46800399`。2026-07-03 报告记录定向回归、golden 和真实浏览器问答通过；更广泛完整矩阵曾有 1 个语言证据问题为 Partial，因此不能把核心 harness 完成扩大为所有自然语言问题均已完全验证。

本文作为原始实施计划归档。后续质量扩展应建立短小、可复核的当前路线或 issue，而不是机械补勾已经演进的旧步骤。

## Success Criteria

- Comparison questions can distinguish cumulative preference, recent preference, same-window intensity, and personal Billboard performance.
- The Agent can resolve named albums/artists/tracks before calling analytic tools.
- The Agent can run one bounded follow-up round when coverage shows missing evidence.
- Final answers cannot contradict coverage or claim that found data is missing.
- The UI can show compact evidence cards in addition to raw tool traces.
- A golden-question suite catches regressions in tool choice, key metrics, forbidden claims, and answer completeness.
- All new tools remain backend-defined and read-only. No arbitrary SQL, arbitrary URL fetches, settings mutation, import jobs, cache clearing, playlists, or write operations are exposed.

## File Structure

Create:

- `backend/domains/ai_agent/evidence.py`  
  Typed evidence card models and compact JSON serialization helpers.
- `backend/domains/ai_agent/evidence_builders.py`  
  Convert existing tool results into evidence cards.
- `backend/domains/ai_agent/question_intent.py`  
  Deterministic question intent parser used before planner prompts.
- `backend/domains/ai_agent/entity_resolver.py`  
  Read-only local entity resolver for albums, artists, and tracks.
- `backend/domains/ai_agent/comparison.py`  
  Read-only comparison evidence builder for track, album, and artist questions.
- `backend/domains/ai_agent/coverage_review.py`  
  Coverage sufficiency review and follow-up plan generation.
- `backend/domains/ai_agent/answer_critic.py`  
  Deterministic answer-quality and contradiction checks.
- `backend/tests/unit/test_ai_agent_evidence_cards.py`
- `backend/tests/unit/test_ai_agent_question_intent.py`
- `backend/tests/unit/test_ai_agent_entity_resolver.py`
- `backend/tests/unit/test_ai_agent_comparison.py`
- `backend/tests/unit/test_ai_agent_coverage_review.py`
- `backend/tests/unit/test_ai_agent_answer_critic.py`
- `backend/tests/fixtures/ai_agent_golden_questions.json`
- `backend/tests/unit/test_ai_agent_golden_questions.py`
- `scripts/evaluate_ai_agent_harness.py`
- `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`
- `frontend/src/tests/ai-evidence-cards.test.tsx`

Modify:

- `backend/domains/ai_agent/tools.py`  
  Register `resolve_entity` and `compare_entities`; route comparison handler to new module.
- `backend/domains/ai_agent/tool_registry.py`  
  No schema change expected; ensure new tools are exposed in `get_default_registry()`.
- `backend/services/ai_agent_service.py`  
  Inject intent into planner prompt, include evidence cards in final payload, run coverage review follow-up, and use answer critic.
- `backend/models/ai_tasks.py`  
  Add optional evidence card fields to task result models if response models require strict schemas.
- `frontend/src/types/ai-tasks.ts`  
  Add `AiEvidenceCard` and nested metric/source types.
- `frontend/src/features/ai-tasks/AIResultShell.tsx`  
  Render evidence cards above tool trace when present.
- `frontend/src/features/ai-insights/ChatMessageList.tsx`  
  Pass evidence cards from message meta to `AIResultShell`.
- `frontend/src/types/ai-insights.ts`  
  Persist evidence cards in assistant message meta.
- `scripts/openapi_operation_audit.py`
- `scripts/api_smoke_probe.py`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `backend/CLAUDE.md`
- `frontend/CLAUDE.md`

---

### Task 1: Add Typed Evidence Cards

**Files:**
- Create: `backend/domains/ai_agent/evidence.py`
- Create: `backend/tests/unit/test_ai_agent_evidence_cards.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_ai_agent_evidence_cards.py`:

```python
from backend.domains.ai_agent.evidence import (
    EvidenceCard,
    EvidenceMetric,
    EvidenceSource,
    compact_evidence_cards,
)


def test_evidence_card_serializes_metric_and_source():
    card = EvidenceCard(
        card_id="album:GUTS:entity_stats",
        title="GUTS 播放统计",
        entity_name="GUTS",
        entity_type="album",
        source=EvidenceSource(tool_name="entity_stats", source_range="lifetime"),
        metrics=[
            EvidenceMetric(name="plays", label="播放次数", value=1749, unit="plays"),
            EvidenceMetric(name="hours", label="播放时长", value=95.6, unit="hours"),
        ],
        limitations=["全时期累计口径"],
    )

    payload = card.model_dump(exclude_none=True)

    assert payload["card_id"] == "album:GUTS:entity_stats"
    assert payload["metrics"][0]["value"] == 1749
    assert payload["source"]["tool_name"] == "entity_stats"


def test_compact_evidence_cards_limits_metric_count():
    card = EvidenceCard(
        card_id="album:GUTS:billboard",
        title="GUTS 个人榜单",
        entity_name="GUTS",
        entity_type="album",
        source=EvidenceSource(tool_name="billboard_entity_detail", source_range="all_years"),
        metrics=[
            EvidenceMetric(name=f"m{i}", label=f"Metric {i}", value=i)
            for i in range(20)
        ],
    )

    compact = compact_evidence_cards([card], max_metrics_per_card=5)

    assert len(compact) == 1
    assert len(compact[0]["metrics"]) == 5
    assert compact[0]["metrics"][4]["name"] == "m4"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_cards.py -q
```

Expected: FAIL because `backend.domains.ai_agent.evidence` does not exist.

- [ ] **Step 3: Implement the evidence models**

Create `backend/domains/ai_agent/evidence.py`:

```python
"""Typed compact evidence cards for AI Agent final-answer context."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceMetric(BaseModel):
    name: str
    label: str
    value: Any
    unit: str | None = None
    note: str | None = None


class EvidenceSource(BaseModel):
    tool_name: str
    source_range: str = ""
    params_summary: str = ""
    result_summary: str = ""


class EvidenceCard(BaseModel):
    card_id: str
    title: str
    entity_name: str | None = None
    entity_type: str | None = None
    question_axis: str | None = None
    source: EvidenceSource
    metrics: list[EvidenceMetric] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def compact_evidence_cards(
    cards: list[EvidenceCard],
    *,
    max_cards: int = 12,
    max_metrics_per_card: int = 10,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for card in cards[:max_cards]:
        payload = card.model_dump(exclude_none=True)
        payload["metrics"] = payload.get("metrics", [])[:max_metrics_per_card]
        compact.append(payload)
    return compact
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_cards.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/domains/ai_agent/evidence.py backend/tests/unit/test_ai_agent_evidence_cards.py
git commit -m "feat: add AI agent evidence card models"
```

---

### Task 2: Build Evidence Cards From Existing Tool Results

**Files:**
- Create: `backend/domains/ai_agent/evidence_builders.py`
- Create: `backend/tests/unit/test_ai_agent_evidence_cards.py`
- Modify: `backend/services/ai_agent_service.py`

- [ ] **Step 1: Add failing tests for tool-result conversion**

Append to `backend/tests/unit/test_ai_agent_evidence_cards.py`:

```python
from backend.domains.ai_agent.evidence_builders import build_evidence_cards


def test_builds_album_entity_stats_evidence_card():
    cards = build_evidence_cards(
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=album, album_name=GUTS",
                "result_summary": "found=true, plays=1749, hours=95.6",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "album_name": "GUTS",
                    "summary": {"total_plays": 1749, "total_hours": 95.6},
                },
            }
        ]
    )

    assert len(cards) == 1
    assert cards[0].entity_name == "GUTS"
    assert cards[0].question_axis == "personal_playback"
    assert cards[0].metrics[0].name == "total_plays"


def test_builds_album_billboard_evidence_card():
    cards = build_evidence_cards(
        [
            {
                "tool_name": "billboard_entity_detail",
                "status": "done",
                "params_summary": "entity=album, album_name=The Life of a Showgirl",
                "result_summary": "found=true",
                "source_range": "all_years",
                "data": {
                    "found": True,
                    "album_name": "The Life of a Showgirl",
                    "chart_summary": {
                        "power_score": 10629,
                        "power_rank": 9,
                        "peak_position": 1,
                        "weeks_on_chart": 37,
                        "no1_weeks": 14,
                    },
                },
            }
        ]
    )

    metric_names = {metric.name for metric in cards[0].metrics}
    assert cards[0].question_axis == "personal_billboard"
    assert "power_score" in metric_names
    assert "no1_weeks" in metric_names
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_cards.py -q
```

Expected: FAIL because `evidence_builders.py` does not exist.

- [ ] **Step 3: Implement evidence builders**

Create `backend/domains/ai_agent/evidence_builders.py`:

```python
"""Build compact evidence cards from read-only Agent tool results."""

from __future__ import annotations

from typing import Any

from backend.domains.ai_agent.evidence import EvidenceCard, EvidenceMetric, EvidenceSource


def _source(item: dict[str, Any]) -> EvidenceSource:
    return EvidenceSource(
        tool_name=str(item.get("tool_name") or ""),
        source_range=str(item.get("source_range") or ""),
        params_summary=str(item.get("params_summary") or ""),
        result_summary=str(item.get("result_summary") or ""),
    )


def _metric(
    name: str,
    label: str,
    value: Any,
    unit: str | None = None,
) -> EvidenceMetric | None:
    if value is None:
        return None
    return EvidenceMetric(name=name, label=label, value=value, unit=unit)


def _append_metric(metrics: list[EvidenceMetric], metric: EvidenceMetric | None) -> None:
    if metric is not None:
        metrics.append(metric)


def _entity_name(item: dict[str, Any], data: dict[str, Any]) -> str | None:
    for key in ("album_name", "artist_name", "track_name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    params_summary = str(item.get("params_summary") or "")
    for part in params_summary.split(", "):
        if part.startswith(("album_name=", "artist_name=", "track_name=")):
            return part.split("=", 1)[1]
    return None


def _entity_type(item: dict[str, Any], data: dict[str, Any]) -> str | None:
    entity = data.get("entity")
    if isinstance(entity, str):
        return entity
    params_summary = str(item.get("params_summary") or "")
    for part in params_summary.split(", "):
        if part.startswith("entity="):
            return part.split("=", 1)[1]
    return None


def _entity_stats_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return None
    name = _entity_name(item, data)
    entity_type = _entity_type(item, data)
    metrics: list[EvidenceMetric] = []
    _append_metric(metrics, _metric("total_plays", "播放次数", summary.get("total_plays"), "plays"))
    _append_metric(metrics, _metric("total_hours", "播放时长", summary.get("total_hours"), "hours"))
    _append_metric(metrics, _metric("unique_tracks", "不同歌曲数", summary.get("unique_tracks"), "tracks"))
    return EvidenceCard(
        card_id=f"{entity_type or 'entity'}:{name or 'unknown'}:entity_stats",
        title=f"{name or '实体'} 播放统计",
        entity_name=name,
        entity_type=entity_type,
        question_axis="personal_playback",
        source=_source(item),
        metrics=metrics,
        limitations=["本地 Spotify 播放记录口径"],
    )


def _billboard_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    summary = data.get("chart_summary")
    if not isinstance(summary, dict):
        return None
    name = _entity_name(item, data)
    entity_type = _entity_type(item, data)
    metrics: list[EvidenceMetric] = []
    _append_metric(metrics, _metric("power_score", "个人榜单 Power Score", summary.get("power_score")))
    _append_metric(metrics, _metric("power_rank", "个人榜单总排名", summary.get("power_rank")))
    _append_metric(metrics, _metric("peak_position", "最高排名", summary.get("peak_position")))
    _append_metric(metrics, _metric("weeks_on_chart", "在榜周数", summary.get("weeks_on_chart"), "weeks"))
    _append_metric(metrics, _metric("no1_weeks", "冠军周数", summary.get("no1_weeks"), "weeks"))
    return EvidenceCard(
        card_id=f"{entity_type or 'entity'}:{name or 'unknown'}:billboard",
        title=f"{name or '实体'} 个人榜单表现",
        entity_name=name,
        entity_type=entity_type,
        question_axis="personal_billboard",
        source=_source(item),
        metrics=metrics,
        limitations=["SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"],
    )


def build_evidence_cards(tool_results: list[dict[str, Any]]) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    for item in tool_results:
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        tool_name = item.get("tool_name")
        if tool_name == "entity_stats":
            card = _entity_stats_card(item, data)
        elif tool_name == "billboard_entity_detail":
            card = _billboard_card(item, data)
        else:
            card = None
        if card is not None:
            cards.append(card)
    return cards
```

- [ ] **Step 4: Add evidence cards to final payload**

Modify `_final_payload()` in `backend/services/ai_agent_service.py`:

```python
from backend.domains.ai_agent.evidence import compact_evidence_cards
from backend.domains.ai_agent.evidence_builders import build_evidence_cards
```

Then update `_final_payload()`:

```python
def _final_payload(
    request: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    compact_results = [_compact_tool_result_for_llm(item) for item in tool_results]
    evidence_cards = build_evidence_cards(tool_results)
    return {
        "question": request.get("question", ""),
        "conversation_history": (request.get("conversation_history") or [])[-6:],
        "coverage": _build_coverage(tool_results),
        "evidence_cards": compact_evidence_cards(evidence_cards),
        "tool_results": compact_results,
    }
```

- [ ] **Step 5: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_cards.py backend/tests/unit/test_ai_agent_evidence.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/domains/ai_agent/evidence_builders.py backend/services/ai_agent_service.py backend/tests/unit/test_ai_agent_evidence_cards.py
git commit -m "feat: build evidence cards for AI agent answers"
```

---

### Task 3: Add Deterministic Question Intent Parsing

**Files:**
- Create: `backend/domains/ai_agent/question_intent.py`
- Create: `backend/tests/unit/test_ai_agent_question_intent.py`
- Modify: `backend/services/ai_agent_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_ai_agent_question_intent.py`:

```python
from backend.domains.ai_agent.question_intent import parse_question_intent


def test_detects_album_comparison_with_named_entities():
    intent = parse_question_intent(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert intent.task_type == "comparison"
    assert intent.entity_type == "album"
    assert intent.entities == ["GUTS", "The Life of a Showgirl"]
    assert "plays" in intent.requested_metrics
    assert "personal_billboard" in intent.requested_metrics
    assert intent.needs_fairness_note is True


def test_detects_trend_question():
    intent = parse_question_intent("我最近六个月是不是越来越喜欢 Olivia Rodrigo？")

    assert intent.task_type == "trend"
    assert intent.entity_type == "artist"
    assert intent.time_scope == "last_6_months"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_question_intent.py -q
```

Expected: FAIL because `question_intent.py` does not exist.

- [ ] **Step 3: Implement intent parsing**

Create `backend/domains/ai_agent/question_intent.py`:

```python
"""Deterministic question-intent hints for the read-only AI Agent planner."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["comparison", "trend", "ranking", "entity_detail", "general"]
EntityType = Literal["track", "album", "artist", "unknown"]


class QuestionIntent(BaseModel):
    task_type: TaskType = "general"
    entity_type: EntityType = "unknown"
    entities: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    time_scope: str = "lifetime"
    needs_fairness_note: bool = False


def _entity_type(question: str) -> EntityType:
    if any(token in question for token in ("专辑", "album", "Album")):
        return "album"
    if any(token in question for token in ("艺人", "歌手", "artist", "Artist")):
        return "artist"
    if any(token in question for token in ("歌曲", "单曲", "track", "Track", "song", "Song")):
        return "track"
    return "unknown"


def _task_type(question: str) -> TaskType:
    if any(token in question for token in ("哪张", "哪个", "哪首", "更", "比较", "vs", "VS", "对比")):
        return "comparison"
    if any(token in question for token in ("最近", "趋势", "越来越", "变化", "回升", "下降")):
        return "trend"
    if any(token in question for token in ("排名", "排行", "top", "Top", "最高")):
        return "ranking"
    return "general"


def _metrics(question: str) -> list[str]:
    metrics: list[str] = []
    if any(token in question for token in ("播放次数", "播放量", "听了多少", "plays")):
        metrics.append("plays")
    if any(token in question for token in ("时长", "小时", "hours")):
        metrics.append("hours")
    if any(token in question for token in ("billboard", "Billboard", "榜单", "排名", "冠军")):
        metrics.append("personal_billboard")
    if any(token in question for token in ("最近", "近期", "六个月", "6个月")):
        metrics.append("recent_window")
    return metrics or ["summary"]


def _time_scope(question: str) -> str:
    if any(token in question for token in ("六个月", "6个月", "半年")):
        return "last_6_months"
    if any(token in question for token in ("今年", "本年", "2026")):
        return "this_year"
    if any(token in question for token in ("最近", "近期")):
        return "last_4_weeks"
    return "lifetime"


def _named_entities(question: str) -> list[str]:
    matches = re.findall(r"[A-Z][A-Za-z0-9:'’!?.&\\- ]{1,80}", question)
    cleaned: list[str] = []
    for match in matches:
        value = match.strip(" ,，。？?：:")
        if not value:
            continue
        if value in {"Billboard", "SpotifyStats", "Top", "VS"}:
            continue
        if value not in cleaned:
            cleaned.append(value)
    return cleaned[:4]


def parse_question_intent(question: str) -> QuestionIntent:
    task_type = _task_type(question)
    metrics = _metrics(question)
    return QuestionIntent(
        task_type=task_type,
        entity_type=_entity_type(question),
        entities=_named_entities(question),
        requested_metrics=metrics,
        time_scope=_time_scope(question),
        needs_fairness_note=task_type == "comparison" and "personal_billboard" in metrics,
    )
```

- [ ] **Step 4: Send intent to planner prompt**

Modify `backend/services/ai_agent_service.py`:

```python
from backend.domains.ai_agent.question_intent import parse_question_intent
```

Update `_planner_user_content()`:

```python
def _planner_user_content(request: dict[str, Any]) -> str:
    question = str(request.get("question", ""))
    intent = parse_question_intent(question)
    payload = {
        "question": question,
        "question_intent": intent.model_dump(),
        "conversation_history": (request.get("conversation_history") or [])[-6:],
        "thinking_mode": _thinking_mode_enabled(request),
        "default_filters": {
            **_base_filter_params(request),
            "merge_level": request.get("merge_level", 1),
        },
        "available_tools": describe_for_model(),
    }
    return _compact_json(payload, limit=16000)
```

- [ ] **Step 5: Strengthen planner prompt for intent**

Modify `PLANNER_SYSTEM_PROMPT` in `backend/services/ai_agent_service.py` by adding:

```text
DATA.question_intent 是系统给出的结构化提示。
如果 task_type=comparison 且 entities 非空，必须为每个实体查询比较所需工具。
如果 requested_metrics 包含 personal_billboard，必须使用 billboard_entity_detail 或 compare_entities。
如果 time_scope 不是 lifetime，至少一个工具调用必须使用对应 period 或自定义窗口。
```

- [ ] **Step 6: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_question_intent.py backend/tests/unit/test_ai_agent_tools.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/domains/ai_agent/question_intent.py backend/services/ai_agent_service.py backend/tests/unit/test_ai_agent_question_intent.py
git commit -m "feat: add AI agent question intent hints"
```

---

### Task 4: Add Read-Only Entity Resolver Tool

**Files:**
- Create: `backend/domains/ai_agent/entity_resolver.py`
- Create: `backend/tests/unit/test_ai_agent_entity_resolver.py`
- Modify: `backend/domains/ai_agent/tools.py`

- [ ] **Step 1: Write failing resolver tests**

Create `backend/tests/unit/test_ai_agent_entity_resolver.py`:

```python
import sqlite3

from backend.domains.ai_agent.entity_resolver import resolve_entities


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE tracks (
            id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            ms_played INTEGER
        );
        INSERT INTO tracks VALUES
            (1, 'vampire', 'Olivia Rodrigo', 'GUTS', 200000),
            (2, 'bad idea right?', 'Olivia Rodrigo', 'GUTS', 180000),
            (3, 'The Fate of Ophelia', 'Taylor Swift', 'The Life of a Showgirl', 210000);
        """
    )
    return conn


def test_resolve_album_by_name():
    conn = _conn()

    result = resolve_entities(conn, query="showgirl", entity_type="album", limit=5)

    assert result["found"] is True
    assert result["candidates"][0]["name"] == "The Life of a Showgirl"
    assert result["candidates"][0]["entity_type"] == "album"


def test_resolve_artist_by_name():
    conn = _conn()

    result = resolve_entities(conn, query="olivia", entity_type="artist", limit=5)

    assert result["found"] is True
    assert result["candidates"][0]["name"] == "Olivia Rodrigo"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_entity_resolver.py -q
```

Expected: FAIL because `entity_resolver.py` does not exist.

- [ ] **Step 3: Implement resolver**

Create `backend/domains/ai_agent/entity_resolver.py`:

```python
"""Read-only local entity resolver for AI Agent tools."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

EntityType = Literal["track", "album", "artist"]


def _table_query(entity_type: EntityType) -> tuple[str, str]:
    if entity_type == "album":
        return "album_name", "album"
    if entity_type == "artist":
        return "artist_name", "artist"
    return "track_name", "track"


def resolve_entities(
    conn: sqlite3.Connection,
    *,
    query: str,
    entity_type: EntityType,
    limit: int = 5,
) -> dict[str, Any]:
    column, rendered_type = _table_query(entity_type)
    normalized = f"%{query.strip().lower()}%"
    rows = conn.execute(
        f"""
        SELECT {column} AS name,
               COUNT(*) AS play_events,
               SUM(ms_played) AS total_ms
        FROM tracks
        WHERE lower({column}) LIKE ?
          AND {column} IS NOT NULL
          AND TRIM({column}) != ''
        GROUP BY {column}
        ORDER BY play_events DESC, total_ms DESC, name ASC
        LIMIT ?
        """,
        (normalized, limit),
    ).fetchall()
    candidates = [
        {
            "name": row["name"],
            "entity_type": rendered_type,
            "play_events": int(row["play_events"] or 0),
            "total_ms": int(row["total_ms"] or 0),
        }
        for row in rows
    ]
    return {"found": bool(candidates), "query": query, "entity_type": entity_type, "candidates": candidates}
```

- [ ] **Step 4: Register `resolve_entity` as an Agent tool**

Modify `backend/domains/ai_agent/tools.py`:

```python
from backend.domains.ai_agent.entity_resolver import resolve_entities
```

Add params model:

```python
class ResolveEntityParams(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    entity_type: Literal["track", "album", "artist"] = "album"
    limit: int = Field(default=5, ge=1, le=10)
```

Add handler:

```python
def resolve_entity_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, ResolveEntityParams)
        else ResolveEntityParams.model_validate(params)
    )
    conn = get_db(readonly=True)
    try:
        data = resolve_entities(
            conn,
            query=parsed.query,
            entity_type=parsed.entity_type,
            limit=parsed.limit,
        )
    finally:
        conn.close()
    return AgentToolResult(
        data=data,
        result_summary=f"found={str(data['found']).lower()}, candidates={len(data['candidates'])}",
        source_range="local_tracks",
    )
```

Add tool definition:

```python
RESOLVE_ENTITY_TOOL = AgentToolDefinition(
    name="resolve_entity",
    description="Resolve a user-provided album, artist, or track name against local listening data.",
    read_only=True,
    params_model=ResolveEntityParams,
    handler=resolve_entity_handler,
)
```

Modify `backend/domains/ai_agent/tool_registry.py` to import and register `RESOLVE_ENTITY_TOOL`.

- [ ] **Step 5: Add registry test**

Append to `backend/tests/unit/test_ai_agent_tools.py`:

```python
def test_registry_exposes_resolve_entity_tool() -> None:
    names = {tool["name"] for tool in tool_registry.list_tools()}
    assert "resolve_entity" in names
```

- [ ] **Step 6: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_entity_resolver.py backend/tests/unit/test_ai_agent_tools.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/domains/ai_agent/entity_resolver.py backend/domains/ai_agent/tools.py backend/domains/ai_agent/tool_registry.py backend/tests/unit/test_ai_agent_entity_resolver.py backend/tests/unit/test_ai_agent_tools.py
git commit -m "feat: add read-only AI entity resolver tool"
```

---

### Task 5: Add Generic Comparison Evidence Tool

**Files:**
- Create: `backend/domains/ai_agent/comparison.py`
- Create: `backend/tests/unit/test_ai_agent_comparison.py`
- Modify: `backend/domains/ai_agent/tools.py`
- Modify: `backend/domains/ai_agent/evidence_builders.py`

- [ ] **Step 1: Write failing comparison tests**

Create `backend/tests/unit/test_ai_agent_comparison.py`:

```python
from backend.domains.ai_agent.comparison import summarize_entity_comparison


def test_comparison_summarizes_cumulative_and_normalized_axes():
    result = summarize_entity_comparison(
        entity_type="album",
        entities=[
            {
                "name": "GUTS",
                "plays": 1749,
                "hours": 95.6,
                "first_play_date": "2023-09-08",
                "latest_play_date": "2026-06-23",
                "power_score": 13566,
                "power_rank": 4,
                "no1_weeks": 11,
                "weeks_on_chart": 79,
            },
            {
                "name": "The Life of a Showgirl",
                "plays": 1637,
                "hours": 96.0,
                "first_play_date": "2025-10-03",
                "latest_play_date": "2026-06-23",
                "power_score": 10629,
                "power_rank": 9,
                "no1_weeks": 14,
                "weeks_on_chart": 37,
            },
        ],
    )

    assert result["winner_by_cumulative_plays"] == "GUTS"
    assert result["winner_by_power_score"] == "GUTS"
    assert result["fairness_notes"]
    assert result["entities"][1]["plays_per_chart_week"] > result["entities"][0]["plays_per_chart_week"]
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_comparison.py -q
```

Expected: FAIL because `comparison.py` does not exist.

- [ ] **Step 3: Implement comparison summarizer**

Create `backend/domains/ai_agent/comparison.py`:

```python
"""Comparison evidence helpers for AI Agent answers."""

from __future__ import annotations

from typing import Any


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _winner(entities: list[dict[str, Any]], metric: str, *, lower_is_better: bool = False) -> str | None:
    if not entities:
        return None
    ranked = sorted(entities, key=lambda item: _num(item.get(metric)), reverse=not lower_is_better)
    return str(ranked[0].get("name")) if ranked[0].get("name") else None


def summarize_entity_comparison(
    *,
    entity_type: str,
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_entities: list[dict[str, Any]] = []
    for entity in entities:
        weeks = _num(entity.get("weeks_on_chart"))
        plays = _num(entity.get("plays"))
        enriched = dict(entity)
        enriched["plays_per_chart_week"] = round(plays / weeks, 2) if weeks > 0 else None
        normalized_entities.append(enriched)

    fairness_notes: list[str] = []
    first_dates = [item.get("first_play_date") for item in normalized_entities if item.get("first_play_date")]
    if len(set(first_dates)) > 1:
        fairness_notes.append("对象进入你的播放历史时间不同，累计值和强度值需要分开看。")
    if any(_num(item.get("weeks_on_chart")) > 0 for item in normalized_entities):
        fairness_notes.append("个人 Billboard 是本地播放榜单，不能解读为外部官方 Billboard 市场成绩。")

    return {
        "entity_type": entity_type,
        "entities": normalized_entities,
        "winner_by_cumulative_plays": _winner(normalized_entities, "plays"),
        "winner_by_total_hours": _winner(normalized_entities, "hours"),
        "winner_by_power_score": _winner(normalized_entities, "power_score"),
        "winner_by_power_rank": _winner(normalized_entities, "power_rank", lower_is_better=True),
        "winner_by_intensity": _winner(normalized_entities, "plays_per_chart_week"),
        "fairness_notes": fairness_notes,
    }
```

- [ ] **Step 4: Register `compare_entities` as a read-only Agent tool**

In `backend/domains/ai_agent/tools.py`, add params:

```python
class CompareEntitiesParams(BaseModel):
    entity_type: Literal["track", "album", "artist"] = "album"
    names: list[str] = Field(..., min_length=2, max_length=4)
    min_ms: int = Field(default=30000, ge=0, le=3_600_000)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=2, ge=1, le=3)
```

Add handler that composes existing handlers:

```python
def compare_entities_handler(params: BaseModel) -> AgentToolResult:
    parsed = (
        params
        if isinstance(params, CompareEntitiesParams)
        else CompareEntitiesParams.model_validate(params)
    )
    rows: list[dict[str, Any]] = []
    for name in parsed.names:
        entity_params = {
            "entity": parsed.entity_type,
            "min_ms": parsed.min_ms,
            "music_only": parsed.music_only,
            "merge_enabled": parsed.merge_enabled,
            "dynamic_threshold": parsed.dynamic_threshold,
            "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
            "merge_level": parsed.merge_level,
        }
        if parsed.entity_type == "album":
            entity_params["album_name"] = name
        elif parsed.entity_type == "artist":
            entity_params["artist_name"] = name
        else:
            continue
        playback = entity_stats_handler(EntityStatsParams.model_validate(entity_params)).data
        billboard = billboard_entity_detail_handler(
            BillboardEntityDetailParams.model_validate(
                {
                    "entity": parsed.entity_type,
                    "album_name": name if parsed.entity_type == "album" else None,
                    "artist_name": name if parsed.entity_type == "artist" else None,
                    "min_ms": parsed.min_ms,
                    "music_only": parsed.music_only,
                    "dynamic_threshold": parsed.dynamic_threshold,
                    "max_merge_gap_minutes": parsed.max_merge_gap_minutes,
                    "merge_level": parsed.merge_level,
                }
            )
        ).data
        summary = playback.get("summary") if isinstance(playback.get("summary"), dict) else {}
        chart_summary = billboard.get("chart_summary") if isinstance(billboard.get("chart_summary"), dict) else {}
        rows.append(
            {
                "name": name,
                "plays": summary.get("total_plays"),
                "hours": summary.get("total_hours"),
                "first_play_date": summary.get("first_play_date"),
                "latest_play_date": summary.get("latest_play_date"),
                "power_score": chart_summary.get("power_score"),
                "power_rank": chart_summary.get("power_rank"),
                "no1_weeks": chart_summary.get("no1_weeks"),
                "weeks_on_chart": chart_summary.get("weeks_on_chart"),
            }
        )
    data = summarize_entity_comparison(entity_type=parsed.entity_type, entities=rows)
    return AgentToolResult(
        data=data,
        result_summary=f"entities={len(rows)}, winner_by_plays={data.get('winner_by_cumulative_plays')}",
        source_range="comparison",
    )
```

Register `COMPARE_ENTITIES_TOOL` in `tools.py` and `tool_registry.py`.

- [ ] **Step 5: Add evidence builder support**

Modify `backend/domains/ai_agent/evidence_builders.py`:

```python
def _comparison_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    entities = data.get("entities")
    if not isinstance(entities, list):
        return None
    metrics = [
        EvidenceMetric(name="winner_by_cumulative_plays", label="累计播放胜出", value=data.get("winner_by_cumulative_plays")),
        EvidenceMetric(name="winner_by_power_score", label="个人榜单 Power Score 胜出", value=data.get("winner_by_power_score")),
        EvidenceMetric(name="winner_by_intensity", label="单位在榜周强度胜出", value=data.get("winner_by_intensity")),
    ]
    return EvidenceCard(
        card_id=f"{data.get('entity_type', 'entity')}:comparison",
        title="实体比较摘要",
        entity_type=str(data.get("entity_type") or "unknown"),
        question_axis="comparison",
        source=_source(item),
        metrics=[metric for metric in metrics if metric.value is not None],
        observations=[str(note) for note in data.get("fairness_notes", []) if isinstance(note, str)],
        limitations=["比较结果同时包含累计值与归一化强度，最终回答必须说明口径。"],
    )
```

Then add:

```python
elif tool_name == "compare_entities":
    card = _comparison_card(item, data)
```

- [ ] **Step 6: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_comparison.py backend/tests/unit/test_ai_agent_tools.py backend/tests/unit/test_ai_agent_evidence_cards.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/domains/ai_agent/comparison.py backend/domains/ai_agent/tools.py backend/domains/ai_agent/tool_registry.py backend/domains/ai_agent/evidence_builders.py backend/tests/unit/test_ai_agent_comparison.py backend/tests/unit/test_ai_agent_tools.py backend/tests/unit/test_ai_agent_evidence_cards.py
git commit -m "feat: add generic AI entity comparison tool"
```

---

### Task 6: Add Coverage Review And One Follow-Up Tool Round

**Files:**
- Create: `backend/domains/ai_agent/coverage_review.py`
- Create: `backend/tests/unit/test_ai_agent_coverage_review.py`
- Modify: `backend/services/ai_agent_service.py`

- [ ] **Step 1: Write failing coverage tests**

Create `backend/tests/unit/test_ai_agent_coverage_review.py`:

```python
from backend.domains.ai_agent.coverage_review import review_coverage


def test_review_requests_missing_billboard_for_album_comparison():
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "album",
            "entities": ["GUTS", "The Life of a Showgirl"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={
            "entities": {
                "GUTS": {"entity_stats": "found", "billboard_entity_detail": "found"},
                "The Life of a Showgirl": {"entity_stats": "found"},
            }
        },
    )

    assert review["sufficient"] is False
    assert review["followup_tool_calls"] == [
        {
            "tool_name": "billboard_entity_detail",
            "params": {"entity": "album", "album_name": "The Life of a Showgirl"},
        }
    ]


def test_review_accepts_complete_comparison_coverage():
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "album",
            "entities": ["GUTS", "The Life of a Showgirl"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={
            "entities": {
                "GUTS": {"entity_stats": "found", "billboard_entity_detail": "found"},
                "The Life of a Showgirl": {"entity_stats": "found", "billboard_entity_detail": "found"},
            }
        },
    )

    assert review["sufficient"] is True
    assert review["followup_tool_calls"] == []
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_coverage_review.py -q
```

Expected: FAIL because `coverage_review.py` does not exist.

- [ ] **Step 3: Implement coverage review**

Create `backend/domains/ai_agent/coverage_review.py`:

```python
"""Deterministic coverage review for bounded AI Agent follow-up tool calls."""

from __future__ import annotations

from typing import Any


def _entity_param(entity_type: str, entity_name: str) -> dict[str, Any]:
    if entity_type == "album":
        return {"entity": "album", "album_name": entity_name}
    if entity_type == "artist":
        return {"entity": "artist", "artist_name": entity_name}
    return {"entity": "track", "track_name": entity_name}


def review_coverage(
    *,
    question_intent: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    task_type = question_intent.get("task_type")
    entity_type = str(question_intent.get("entity_type") or "unknown")
    requested_metrics = set(question_intent.get("requested_metrics") or [])
    requested_entities = [
        entity for entity in question_intent.get("entities", []) if isinstance(entity, str)
    ]
    entities = coverage.get("entities") if isinstance(coverage, dict) else {}
    if not isinstance(entities, dict):
        entities = {}

    followup_tool_calls: list[dict[str, Any]] = []
    reasons: list[str] = []
    if task_type == "comparison":
        for entity_name in requested_entities:
            statuses = entities.get(entity_name, {})
            if not isinstance(statuses, dict):
                statuses = {}
            if statuses.get("entity_stats") != "found":
                followup_tool_calls.append(
                    {"tool_name": "entity_stats", "params": _entity_param(entity_type, entity_name)}
                )
                reasons.append(f"{entity_name} 缺少播放统计")
            if "personal_billboard" in requested_metrics and statuses.get("billboard_entity_detail") != "found":
                followup_tool_calls.append(
                    {"tool_name": "billboard_entity_detail", "params": _entity_param(entity_type, entity_name)}
                )
                reasons.append(f"{entity_name} 缺少个人榜单证据")

    return {
        "sufficient": len(followup_tool_calls) == 0,
        "reasons": reasons,
        "followup_tool_calls": followup_tool_calls[:4],
    }
```

- [ ] **Step 4: Add follow-up round in Agent service**

Modify `backend/services/ai_agent_service.py`:

```python
from backend.domains.ai_agent.coverage_review import review_coverage
from backend.domains.ai_agent.question_intent import parse_question_intent
```

Add helper:

```python
def _execute_tool_call(
    repo: AiTaskRepository,
    *,
    task_id: str,
    tool_call: dict[str, Any],
    index: int,
    progress_pct: float,
) -> dict[str, Any] | None:
    tool_name = str(tool_call["tool_name"])
    params = tool_call.get("params") if isinstance(tool_call.get("params"), dict) else {}
    if not _set_stage(
        repo,
        task_id=task_id,
        stage="calling_tool",
        progress_pct=progress_pct,
        message=f"正在调用只读工具：{tool_name}",
        payload={"tool_name": tool_name, "index": index},
    ):
        return None
    try:
        result = dispatch_tool(tool_name, params)
    except Exception as exc:
        error_message = str(exc) or exc.__class__.__name__
        repo.add_tool_call(
            task_id=task_id,
            tool_name=tool_name,
            status="error",
            params_summary=_raw_params_summary(params),
            result_summary="",
            source_range="",
            error=error_message,
        )
        return {
            "tool_name": tool_name,
            "status": "error",
            "params_summary": _raw_params_summary(params),
            "error": error_message,
        }
    repo.add_tool_call(
        task_id=task_id,
        tool_name=result["tool_name"],
        status="done",
        params_summary=result.get("params_summary", ""),
        result_summary=result.get("result_summary", ""),
        source_range=result.get("source_range", ""),
        error=None,
    )
    return {
        "tool_name": result["tool_name"],
        "status": "done",
        "params_summary": result.get("params_summary", ""),
        "result_summary": result.get("result_summary", ""),
        "source_range": result.get("source_range", ""),
        "data": result.get("data"),
    }
```

Refactor the existing tool execution loop to call `_execute_tool_call()`. After the first loop, add:

```python
question_intent = parse_question_intent(str(request.get("question", ""))).model_dump()
coverage_review = review_coverage(
    question_intent=question_intent,
    coverage=_build_coverage(tool_results),
)
if not coverage_review["sufficient"]:
    _set_stage(
        repo,
        task_id=task_id,
        stage="reviewing_coverage",
        progress_pct=0.78,
        message="正在补查缺失证据",
        payload={"reasons": coverage_review["reasons"]},
    )
    existing = {(item["tool_name"], item.get("params_summary", "")) for item in tool_results}
    for offset, followup in enumerate(coverage_review["followup_tool_calls"], start=1):
        result = _execute_tool_call(
            repo,
            task_id=task_id,
            tool_call=followup,
            index=len(tool_results) + offset,
            progress_pct=min(0.86, 0.78 + offset * 0.03),
        )
        if result is not None:
            identity = (result["tool_name"], result.get("params_summary", ""))
            if identity not in existing:
                tool_results.append(result)
                existing.add(identity)
```

- [ ] **Step 5: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/contract/test_ai_agent_task_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/domains/ai_agent/coverage_review.py backend/services/ai_agent_service.py backend/tests/unit/test_ai_agent_coverage_review.py
git commit -m "feat: add AI agent coverage follow-up round"
```

---

### Task 7: Add Deterministic Answer Critic

**Files:**
- Create: `backend/domains/ai_agent/answer_critic.py`
- Create: `backend/tests/unit/test_ai_agent_answer_critic.py`
- Modify: `backend/services/ai_agent_service.py`

- [ ] **Step 1: Write failing critic tests**

Create `backend/tests/unit/test_ai_agent_answer_critic.py`:

```python
from backend.domains.ai_agent.answer_critic import critique_answer


def test_critic_rejects_external_billboard_claim():
    critique = critique_answer(
        answer="GUTS 的 Billboard 市场影响力更大，所以你更喜欢它。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [
                {
                    "title": "GUTS 个人榜单表现",
                    "limitations": ["SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"],
                }
            ],
        },
    )

    assert critique["ok"] is False
    assert "外部官方 Billboard" in critique["issues"][0]


def test_critic_accepts_personal_billboard_language():
    critique = critique_answer(
        answer="在你的个人 Billboard 口径里，GUTS 的 Power Score 更高。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is True
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_answer_critic.py -q
```

Expected: FAIL because `answer_critic.py` does not exist.

- [ ] **Step 3: Implement answer critic**

Create `backend/domains/ai_agent/answer_critic.py`:

```python
"""Deterministic final-answer critique for AI Agent responses."""

from __future__ import annotations

from typing import Any

EXTERNAL_BILLBOARD_TOKENS = (
    "Billboard 市场",
    "市场影响力",
    "商业成绩",
    "权威榜单",
    "外部官方 Billboard",
)


def critique_answer(answer: str, final_payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if any(token in answer for token in EXTERNAL_BILLBOARD_TOKENS):
        if "个人 Billboard" not in answer and "本地个人榜单" not in answer:
            issues.append("回答把 SpotifyStats 个人 Billboard 表述成外部官方 Billboard 或市场成绩。")
    if "数据不足" in answer and "found" in str(final_payload):
        issues.append("回答出现数据不足表述；请确认是否与 coverage 中的 found 证据矛盾。")
    return {"ok": len(issues) == 0, "issues": issues}
```

- [ ] **Step 4: Use critic in Agent retry**

Modify `backend/services/ai_agent_service.py`:

```python
from backend.domains.ai_agent.answer_critic import critique_answer
```

After `_answer_validation_issues()` is called:

```python
critic_result = critique_answer(answer, final_payload)
if not critic_result["ok"]:
    validation_issues.extend(str(issue) for issue in critic_result["issues"])
```

Keep the existing single retry behavior.

- [ ] **Step 5: Verify tests pass**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_evidence.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/domains/ai_agent/answer_critic.py backend/services/ai_agent_service.py backend/tests/unit/test_ai_agent_answer_critic.py
git commit -m "feat: add deterministic AI answer critic"
```

---

### Task 8: Render Evidence Cards In Chat UI

**Files:**
- Create: `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`
- Create: `frontend/src/tests/ai-evidence-cards.test.tsx`
- Modify: `frontend/src/types/ai-tasks.ts`
- Modify: `frontend/src/types/ai-insights.ts`
- Modify: `frontend/src/features/ai-tasks/AIResultShell.tsx`
- Modify: `frontend/src/features/ai-insights/ChatMessageList.tsx`

- [ ] **Step 1: Write failing frontend test**

Create `frontend/src/tests/ai-evidence-cards.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AIEvidenceCards } from '@/features/ai-tasks/AIEvidenceCards'

describe('AIEvidenceCards', () => {
  it('renders compact evidence metrics and limitations', () => {
    render(
      <AIEvidenceCards
        cards={[
          {
            card_id: 'album:GUTS:entity_stats',
            title: 'GUTS 播放统计',
            entity_name: 'GUTS',
            entity_type: 'album',
            question_axis: 'personal_playback',
            source: { tool_name: 'entity_stats', source_range: 'lifetime' },
            metrics: [
              { name: 'total_plays', label: '播放次数', value: 1749, unit: 'plays' },
            ],
            observations: [],
            limitations: ['全时期累计口径'],
          },
        ]}
      />,
    )

    expect(screen.getByText('GUTS 播放统计')).toBeInTheDocument()
    expect(screen.getByText('播放次数')).toBeInTheDocument()
    expect(screen.getByText('1749 plays')).toBeInTheDocument()
    expect(screen.getByText('全时期累计口径')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd frontend && npm test -- ai-evidence-cards.test.tsx --run
```

Expected: FAIL because `AIEvidenceCards` does not exist.

- [ ] **Step 3: Add TypeScript types**

Modify `frontend/src/types/ai-tasks.ts`:

```ts
export interface AiEvidenceMetric {
  name: string
  label: string
  value: string | number | boolean | null
  unit?: string | null
  note?: string | null
}

export interface AiEvidenceSource {
  tool_name: string
  source_range?: string
  params_summary?: string
  result_summary?: string
}

export interface AiEvidenceCard {
  card_id: string
  title: string
  entity_name?: string | null
  entity_type?: string | null
  question_axis?: string | null
  source: AiEvidenceSource
  metrics: AiEvidenceMetric[]
  observations?: string[]
  limitations?: string[]
}
```

- [ ] **Step 4: Implement evidence card component**

Create `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`:

```tsx
import type { AiEvidenceCard, AiEvidenceMetric } from '@/types/ai-tasks'

interface AIEvidenceCardsProps {
  cards: AiEvidenceCard[]
}

function metricValue(metric: AiEvidenceMetric): string {
  const rendered = metric.value == null ? '无数据' : String(metric.value)
  return metric.unit ? `${rendered} ${metric.unit}` : rendered
}

export function AIEvidenceCards({ cards }: AIEvidenceCardsProps) {
  if (cards.length === 0) return null

  return (
    <section className="rounded-[8px] border border-border bg-card/30 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        证据卡片
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {cards.map((card) => (
          <article className="rounded-[8px] border border-border/50 bg-muted/20 p-3" key={card.card_id}>
            <div className="min-w-0">
              <h4 className="text-[13px] font-semibold text-foreground">{card.title}</h4>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                {card.source.tool_name}
                {card.source.source_range ? ` · ${card.source.source_range}` : ''}
              </p>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2">
              {card.metrics.map((metric) => (
                <div className="min-w-0" key={metric.name}>
                  <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
                  <dd className="text-[13px] font-medium text-foreground">{metricValue(metric)}</dd>
                </div>
              ))}
            </dl>
            {(card.observations?.length || card.limitations?.length) && (
              <ul className="mt-3 space-y-1 text-[11px] leading-relaxed text-muted-foreground">
                {[...(card.observations ?? []), ...(card.limitations ?? [])].map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 5: Render evidence cards in result shell**

Modify `frontend/src/features/ai-tasks/AIResultShell.tsx`:

```tsx
import { AIEvidenceCards } from './AIEvidenceCards'
import type { AiEvidenceCard, AiToolCall } from '@/types/ai-tasks'

interface AIResultShellProps {
  evidenceCards?: AiEvidenceCard[]
  toolCalls: AiToolCall[]
}

export function AIResultShell({ evidenceCards = [], toolCalls }: AIResultShellProps) {
  return (
    <div className="space-y-3">
      <AIEvidenceCards cards={evidenceCards} />
      <AIToolTrace toolCalls={toolCalls} />
    </div>
  )
}
```

Preserve the existing `AIToolTrace` import and props that are already present.

- [ ] **Step 6: Pass evidence cards from chat metadata**

Modify `frontend/src/types/ai-insights.ts` to include:

```ts
import type { AiEvidenceCard } from './ai-tasks'

export interface ChatAgentMeta {
  evidence_cards?: AiEvidenceCard[]
}
```

Update `chatAgentMeta()` so it reads:

```ts
evidence_cards: Array.isArray(task.result?.evidence_cards)
  ? task.result.evidence_cards as AiEvidenceCard[]
  : [],
```

Modify `frontend/src/features/ai-insights/ChatMessageList.tsx` so `AIResultShell` receives:

```tsx
<AIResultShell
  evidenceCards={message.meta?.evidence_cards ?? []}
  toolCalls={message.meta?.tool_calls ?? []}
/>
```

- [ ] **Step 7: Verify frontend tests pass**

Run:

```bash
cd frontend && npm test -- ai-evidence-cards.test.tsx ai-insights-chat-task-flow.test.tsx --run
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add frontend/src/features/ai-tasks/AIEvidenceCards.tsx frontend/src/features/ai-tasks/AIResultShell.tsx frontend/src/features/ai-insights/ChatMessageList.tsx frontend/src/types/ai-tasks.ts frontend/src/types/ai-insights.ts frontend/src/tests/ai-evidence-cards.test.tsx
git commit -m "feat: show AI evidence cards in chat results"
```

---

### Task 9: Add Golden-Question Evaluation Harness

**Files:**
- Create: `backend/tests/fixtures/ai_agent_golden_questions.json`
- Create: `backend/tests/unit/test_ai_agent_golden_questions.py`
- Create: `scripts/evaluate_ai_agent_harness.py`

- [ ] **Step 1: Create golden question fixture**

Create `backend/tests/fixtures/ai_agent_golden_questions.json`:

```json
[
  {
    "id": "album-guts-showgirl-comparison",
    "question": "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？",
    "expected_intent": {
      "task_type": "comparison",
      "entity_type": "album",
      "entities": ["GUTS", "The Life of a Showgirl"],
      "requested_metrics": ["plays", "personal_billboard"]
    },
    "expected_tools": ["entity_stats", "billboard_entity_detail"],
    "required_answer_terms": ["GUTS", "The Life of a Showgirl", "播放", "个人 Billboard"],
    "forbidden_answer_terms": ["市场影响力", "外部官方 Billboard", "数据不足", "缺少 The Life of a Showgirl"]
  },
  {
    "id": "recent-artist-trend",
    "question": "我最近六个月是不是越来越喜欢 Olivia Rodrigo？",
    "expected_intent": {
      "task_type": "trend",
      "entity_type": "artist",
      "entities": ["Olivia Rodrigo"],
      "requested_metrics": ["recent_window"]
    },
    "expected_tools": ["entity_stats", "analysis_charts"],
    "required_answer_terms": ["最近六个月", "Olivia Rodrigo"],
    "forbidden_answer_terms": ["无法判断", "没有数据"]
  }
]
```

- [ ] **Step 2: Write deterministic fixture test**

Create `backend/tests/unit/test_ai_agent_golden_questions.py`:

```python
import json
from pathlib import Path

from backend.domains.ai_agent.question_intent import parse_question_intent

FIXTURE = Path("backend/tests/fixtures/ai_agent_golden_questions.json")


def test_golden_question_intents_are_detected():
    cases = json.loads(FIXTURE.read_text())

    for case in cases:
        intent = parse_question_intent(case["question"])
        expected = case["expected_intent"]
        assert intent.task_type == expected["task_type"], case["id"]
        assert intent.entity_type == expected["entity_type"], case["id"]
        for entity in expected["entities"]:
            assert entity in intent.entities, case["id"]
        for metric in expected["requested_metrics"]:
            assert metric in intent.requested_metrics, case["id"]
```

- [ ] **Step 3: Add evaluation script**

Create `scripts/evaluate_ai_agent_harness.py`:

```python
#!/usr/bin/env python3
"""Offline deterministic checks for AI Agent harness quality fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from backend.domains.ai_agent.answer_critic import critique_answer
from backend.domains.ai_agent.question_intent import parse_question_intent

FIXTURE = Path("backend/tests/fixtures/ai_agent_golden_questions.json")


def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    failures: list[str] = []
    for case in cases:
        intent = parse_question_intent(case["question"]).model_dump()
        for key, expected_value in case["expected_intent"].items():
            actual_value = intent.get(key)
            if isinstance(expected_value, list):
                missing = [item for item in expected_value if item not in actual_value]
                if missing:
                    failures.append(f"{case['id']}: missing intent {key} values {missing}")
            elif actual_value != expected_value:
                failures.append(f"{case['id']}: expected {key}={expected_value}, got {actual_value}")

        synthetic_answer = " ".join(case["required_answer_terms"])
        critique = critique_answer(synthetic_answer, {"coverage": {}, "evidence_cards": []})
        if not critique["ok"]:
            failures.append(f"{case['id']}: critic rejected required terms {critique['issues']}")

    if failures:
        print("AI Agent harness eval failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"AI Agent harness eval passed: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run evaluation**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_golden_questions.py -q
.venv/bin/python scripts/evaluate_ai_agent_harness.py
```

Expected:

```text
1 passed
AI Agent harness eval passed: 2 cases
```

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/tests/fixtures/ai_agent_golden_questions.json backend/tests/unit/test_ai_agent_golden_questions.py scripts/evaluate_ai_agent_harness.py
git commit -m "test: add AI agent golden question harness"
```

---

### Task 10: Update API Audits, Smoke, Docs, And Final Verification

**Files:**
- Modify: `scripts/openapi_operation_audit.py`
- Modify: `scripts/api_smoke_probe.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `AGENTS.md`
- Modify: `backend/CLAUDE.md`
- Modify: `frontend/CLAUDE.md`

- [ ] **Step 1: Update audit evidence if new endpoints are added**

If Tasks 4 and 5 only add Agent registry tools behind existing `/api/ai/tasks/chat`, no OpenAPI operation entry changes. Run audit first:

```bash
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit.json
```

Expected:

```text
Unaccounted operations | 0
Unaccounted obligations | 0
```

If either command reports unaccounted AI task operations, add the exact new operation path to `TARGETED_CONTRACT_EVIDENCE` with the test file introduced in the task that owns the endpoint.

- [ ] **Step 2: Add smoke coverage for evidence card payload shape**

Modify `scripts/api_smoke_probe.py` only if `/api/ai/tasks/chat` receives a non-live test seam. Add a safe missing-task case if it is not already present:

```python
ApiSmokeCase("ai_task_missing", "GET", "/api/ai/tasks/nonexistent-smoke-task", expected_status=200)
```

Expected existing result remains:

```text
PASS ai_task_missing 200 /api/ai/tasks/nonexistent-smoke-task
```

- [ ] **Step 3: Update docs**

Add a section to `docs/CHANGELOG.md`:

```markdown
## 2026-06-29 — AI Agent Harness Quality Roadmap

### 新增

- 增加 AI Agent evidence cards、问题意图解析、实体解析、通用比较工具、coverage follow-up、answer critic 和 golden-question eval harness
- 前端问答结果展示证据卡片，帮助用户理解回答依据

### 验证

- `.venv/bin/pytest backend/tests/unit/test_ai_agent_* -q`
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`
- `cd frontend && npm test -- ai-evidence-cards.test.tsx ai-insights-chat-task-flow.test.tsx --run`
```

Update `AGENTS.md`, `backend/CLAUDE.md`, and `frontend/CLAUDE.md` with one bullet each:

```markdown
- AI Agent harness quality layer: evidence cards, deterministic intent parsing, read-only entity resolver/comparison tools, coverage follow-up, answer critic, and golden-question eval.
```

- [ ] **Step 4: Run backend verification**

Run:

```bash
.venv/bin/ruff check backend/
.venv/bin/pre-commit run --all-files
.venv/bin/pytest backend/tests/unit/test_ai_agent_evidence_cards.py backend/tests/unit/test_ai_agent_question_intent.py backend/tests/unit/test_ai_agent_entity_resolver.py backend/tests/unit/test_ai_agent_comparison.py backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_golden_questions.py -q
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
```

Expected:

```text
All checks passed
AI Agent targeted tests PASS
unit PASS
contract PASS
```

- [ ] **Step 5: Run frontend verification**

Run:

```bash
cd frontend && npm test -- ai-evidence-cards.test.tsx ai-insights-chat-task-flow.test.tsx ai-task-components.test.tsx --run
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected:

```text
targeted Vitest PASS
full Vitest PASS
build PASS
```

- [ ] **Step 6: Run smoke and real browser verification**

Run:

```bash
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173
node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport desktop --routes /ai-insights
```

Manual browser verification at `http://localhost:5173/ai-insights`:

1. Open the Q&A tab.
2. Enable `思考模式`.
3. Ask: `从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？`
4. Confirm the progress includes planning, tool calls, evidence review or answer writing, and done.
5. Confirm the final answer mentions both albums, personal playback, personal Billboard, and fairness limits.
6. Confirm it does not use `市场影响力`, `外部官方 Billboard`, or `The Life of a Showgirl 数据不足`.
7. Confirm evidence cards render above or near the tool trace.

- [ ] **Step 7: Commit final integration**

Run:

```bash
git add scripts/openapi_operation_audit.py scripts/api_smoke_probe.py docs/CHANGELOG.md AGENTS.md backend/CLAUDE.md frontend/CLAUDE.md
git commit -m "docs: document AI agent harness quality layer"
```

---

## Final Review Checklist

- Spec coverage: covered. Evidence cards, intent parsing, entity resolution, comparison tool, coverage follow-up, answer critic, frontend evidence display, golden eval, audits, smoke, docs, and manual browser verification each have an implementation task.
- Placeholder scan: this plan contains no unresolved placeholder markers or unbounded "add tests" instruction. Every test task includes exact test file content or exact assertions.
- Type consistency: backend evidence card fields are `card_id`, `title`, `entity_name`, `entity_type`, `question_axis`, `source`, `metrics`, `observations`, and `limitations`; frontend `AiEvidenceCard` uses the same names.
- Safety boundary: every new model-facing capability is a backend-defined read-only tool. No arbitrary SQL, URL fetch, mutation, import, cache clear, playlist, settings write, or unreviewed route is exposed.
- Verification boundary: final answer quality is checked through deterministic unit tests, golden fixtures, frontend tests, smoke, and one real browser Q&A path.

## Execution Notes

Recommended execution mode is Subagent-Driven:

1. Dispatch one subagent per task.
2. Review each task before starting the next task.
3. Commit after each task when tests pass.
4. Keep the existing V2 Agent behavior working at every checkpoint.
