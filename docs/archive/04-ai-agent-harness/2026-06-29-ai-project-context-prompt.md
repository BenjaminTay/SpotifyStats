# AI Project Context Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable Project Context Layer to the read-only AI chat Agent so planner and final-answer LLM calls understand SpotifyStats as a personal music-data analysis product, not a generic data-query bot.

**Architecture:** Create a focused `project_context.py` module that owns prompt fragments, prompt builders, and a version string. Inject those fragments into planner and final-answer system prompts while preserving existing QuestionFrame, EvidenceRecipe, AnalyticalBrief, AnswerContract, answer_style, and read-only tool boundaries. Add unit, contract, golden-harness, and real-question checks so prompt context remains a testable harness contract.

**Tech Stack:** FastAPI, SQLite, Pydantic v2, pytest, Python 3.9-compatible typing, existing AI Agent service modules, ruff, golden-question harness.

---

## Source Spec

Use this spec as the source of truth:

- `docs/superpowers/specs/2026-06-29-ai-project-context-prompt-design.md`

Accepted decisions:

- First implementation only targets AI chat Agent, not weekly/monthly/yearly report prompts.
- Tone is “懂个人音乐数据的分析助手”: analytical first, with light music narrative, not a literary critic.
- Prompt may mention general user expectations, but not private user preferences beyond the current project/product context.
- `project_context_version` should be included in final payload and task result metadata, but does not need frontend display.

## File Structure

Create:

- `backend/domains/ai_agent/project_context.py`  
  Owns `PROJECT_CONTEXT_VERSION`, prompt fragments, prompt builders, and a compact `project_context_payload()`.
- `backend/tests/unit/test_ai_agent_project_context.py`  
  Tests prompt content, length budget, builder composition, and metadata payload.

Modify:

- `backend/services/ai_agent_service.py`  
  Uses prompt builders for planner/final/thinking final prompts, includes `project_context_version` in final payload and task result, and keeps retry instructions aligned with project context.
- `backend/tests/unit/test_ai_agent_evidence.py`  
  Adds assertions that final payload includes project context version while preserving answer_style behavior.
- `backend/tests/contract/test_ai_agent_task_contract.py`  
  Adds prompt-injection assertions through monkeypatched `_llm_chat`, verifying planner/final prompts include context and thinking prompt does not force report sections.
- `backend/tests/fixtures/ai_agent_golden_questions.json`  
  Adds or updates expected answer style metadata for representative Project Context questions if the existing fixture does not already cover it.
- `backend/tests/unit/test_ai_agent_golden_questions.py`  
  Validates any new `expected_answer_style` fixture field.
- `scripts/evaluate_ai_agent_harness.py`  
  Reads and checks `expected_answer_style` if added to fixtures.
- `docs/CHANGELOG.md`  
  Records the Project Context Layer addition and verification commands.
- `AGENTS.md`  
  Adds the Project Context Layer to the AI Agent summary.
- `backend/CLAUDE.md`  
  Documents prompt ownership, read-only boundary, and test expectations.

Do not modify in this plan:

- Frontend UI, unless implementation later chooses to display `project_context_version`.
- Report generation prompts in `ai_insights_service.py`.
- Any write-capable tools or arbitrary SQL/URL capabilities.

## Task 1: Add Project Context Prompt Module

**Files:**
- Create: `backend/domains/ai_agent/project_context.py`
- Create: `backend/tests/unit/test_ai_agent_project_context.py`

- [ ] **Step 1: Write the failing module tests**

Create `backend/tests/unit/test_ai_agent_project_context.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_agent import project_context

pytestmark = pytest.mark.unit


def test_project_context_prompt_contains_product_semantics() -> None:
    prompt = project_context.PROJECT_CONTEXT_PROMPT

    assert "SpotifyStats" in prompt
    assert "个人" in prompt
    assert "本地 Spotify" in prompt
    assert "本地播放记录" in prompt
    assert "个人 Billboard" in prompt
    assert "不是通用音乐百科" in prompt
    assert "不是官方 Billboard" in prompt


def test_tool_playbook_mentions_required_agent_tools() -> None:
    prompt = project_context.TOOL_PLAYBOOK_PROMPT

    assert "analysis_stats" in prompt
    assert "analysis_charts" in prompt
    assert "entity_stats(entity=artist)" in prompt
    assert "top_albums/top_tracks" in prompt
    assert "compare_entities" in prompt
    assert "listening_hours" in prompt
    assert "不能只查 lifetime" in prompt


def test_answer_philosophy_keeps_simple_answers_concise() -> None:
    prompt = project_context.ANSWER_PHILOSOPHY_PROMPT

    assert "先回答" in prompt
    assert "answer_style=concise" in prompt
    assert "3-6 句" in prompt
    assert "不写流水账" in prompt
    assert "本地个人 Billboard" in prompt


def test_project_context_fragments_stay_within_budget() -> None:
    combined = "\n".join(
        [
            project_context.PROJECT_CONTEXT_PROMPT,
            project_context.TOOL_PLAYBOOK_PROMPT,
            project_context.ANSWER_PHILOSOPHY_PROMPT,
            project_context.SAFETY_BOUNDARY_PROMPT,
        ]
    )

    assert len(combined) < 3200


def test_prompt_builders_include_version_and_base_prompt() -> None:
    planner = project_context.build_planner_system_prompt("BASE PLANNER")
    final = project_context.build_final_answer_system_prompt("BASE FINAL")
    thinking = project_context.build_final_answer_system_prompt(
        "BASE THINKING",
        thinking_mode=True,
    )

    assert project_context.PROJECT_CONTEXT_VERSION in planner
    assert "BASE PLANNER" in planner
    assert project_context.TOOL_PLAYBOOK_PROMPT in planner
    assert "BASE FINAL" in final
    assert project_context.ANSWER_PHILOSOPHY_PROMPT in final
    assert "BASE THINKING" in thinking
    assert "思考模式" in thinking
    assert "我查了什么" not in thinking


def test_project_context_payload_is_compact_metadata() -> None:
    payload = project_context.project_context_payload()

    assert payload == {
        "project_context_version": project_context.PROJECT_CONTEXT_VERSION,
    }
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_project_context.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing attributes because `project_context.py` does not exist yet.

- [ ] **Step 3: Implement the prompt module**

Create `backend/domains/ai_agent/project_context.py`:

```python
"""Stable project context prompts for the read-only AI Agent."""

from __future__ import annotations

PROJECT_CONTEXT_VERSION = "spotify-stats-project-context-v1"

PROJECT_CONTEXT_PROMPT = """Project Context Version: spotify-stats-project-context-v1
你正在为 SpotifyStats 回答问题。SpotifyStats 是一个基于用户本地 Spotify Extended Streaming History 的个人音乐数据分析应用，不是通用音乐百科，也不是官方 Billboard 或市场数据查询工具。

本项目的核心数据来自用户自己的本地播放记录、账号收藏、Spotify 元数据、album project / track group 聚合，以及基于这些本地数据计算出的个人 Billboard。除非工具结果明确提供，否则不要声称知道用户在其他平台、离线环境或外部市场中的行为。

SpotifyStats Billboard 永远表示“用户个人播放行为生成的本地个人 Billboard”。它可以说明一首歌、专辑或艺人在用户个人数据中的榜单统治力、峰值、在榜周数、Power Score 和稳定性，但不能表述为外部官方 Billboard、商业成绩、市场影响力或大众流行度。

分析用户偏好时，不要把播放次数直接等同于“最喜欢”。应按问题需要区分累计播放次数、播放时长、近期窗口、单位时间强度、稳定性、峰值、个人 Billboard 表现、发行时间和进入用户播放历史的时间。不同指标冲突时要分层回答，而不是强行说所有指标都指向同一个对象。

回答应像一个懂个人音乐数据的分析助手：先直接回答用户真正问的问题，再给关键数字和必要边界。简单排行或事实问题默认短答；比较、趋势、原因、身份偏好等复杂问题才展开。不要把工具调用过程写成正文，不要输出模板化“我查了什么/自检与限制”，除非用户明确要求详细说明或证据不足。
"""

TOOL_PLAYBOOK_PROMPT = """Tool Playbook:
- 总体播放量、时间范围、Top 艺人/歌曲/专辑：优先 analysis_stats / analysis_charts / wrapped_yearly。
- 指定艺人、专辑、歌曲详情：优先 entity_stats；若用户提到榜单、Power Score、冠军周或个人 Billboard，再补 billboard_entity_detail。
- 2-4 个同类实体比较：优先 compare_entities；不要拆成大量单实体查询，除非需要补近期窗口。
- “更喜欢/喜爱程度/本命/偏好”不是单一播放次数问题；需要累计、近期、强度、稳定性或个人 Billboard 等多轴证据。
- 指定艺人范围内问最喜欢的专辑/歌曲：必须用 entity_stats(entity=artist) 的 top_albums/top_tracks，不能用全局 Top10 缺席判断。
- 趋势、最近、变化、下降、回升：不能只查 lifetime，必须查近期窗口或分期数据。
- 深夜/上午/时段类问题：必须使用 listening_hours 的对应 view。
"""

ANSWER_PHILOSOPHY_PROMPT = """Answer Philosophy:
- 第一段先回答用户真正问的问题，不要先解释工具过程。
- 默认 answer_style=concise 时，使用 3-6 句或最多 3 个 bullet。
- answer_style=structured 时，可以使用短小标题、表格或列表，但不写流水账。
- answer_style=detailed 时，才展开完整依据、限制和自检。
- 有冲突证据时，用“长期/近期/强度/榜单”分层，而不是压成假确定性。
- 所有数字都要能从 DATA 找到；没有来源的数字不要写。
- 必须保留本地个人 Billboard 与外部官方 Billboard 的边界。
"""

SAFETY_BOUNDARY_PROMPT = """Safety Boundary:
你只能基于系统提供的 DATA、工具结果、证据卡片、coverage、EvidenceSufficiency 和 AnalyticalBrief 回答。若证据不足，应说明缺口，并优先使用可用只读工具补查；不要编造工具、SQL、URL、外部搜索或写操作。
"""


def _join_prompt_parts(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def build_planner_system_prompt(base_prompt: str) -> str:
    return _join_prompt_parts(
        PROJECT_CONTEXT_PROMPT,
        TOOL_PLAYBOOK_PROMPT,
        SAFETY_BOUNDARY_PROMPT,
        base_prompt,
    )


def build_final_answer_system_prompt(base_prompt: str, *, thinking_mode: bool = False) -> str:
    thinking_note = (
        "Thinking Mode Note: 思考模式只表示工具核对更充分和可见分析摘要，不表示回答必须变长。"
        if thinking_mode
        else ""
    )
    return _join_prompt_parts(
        PROJECT_CONTEXT_PROMPT,
        ANSWER_PHILOSOPHY_PROMPT,
        SAFETY_BOUNDARY_PROMPT,
        thinking_note,
        base_prompt,
    )


def project_context_payload() -> dict[str, str]:
    return {"project_context_version": PROJECT_CONTEXT_VERSION}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_project_context.py -q
```

Expected: PASS.

## Task 2: Inject Project Context Into Agent Prompts

**Files:**
- Modify: `backend/services/ai_agent_service.py`
- Modify: `backend/tests/unit/test_ai_agent_evidence.py`
- Modify: `backend/tests/contract/test_ai_agent_task_contract.py`

- [ ] **Step 1: Add failing payload test**

Append this assertion to `test_scoped_ranking_defaults_to_concise_answer_style` in `backend/tests/unit/test_ai_agent_evidence.py`:

```python
    assert payload["project_context_version"] == "spotify-stats-project-context-v1"
```

Add a new test in the same file:

```python
def test_final_user_content_includes_project_context_version() -> None:
    content = ai_agent_service._final_user_content(
        {
            "question": "2023年我播放量最高的艺人是谁？",
            "conversation_history": [],
        },
        [
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "params_summary": "period=custom, start_date=2023-01-01, end_date=2023-12-31, entity=artist, metric=plays",
                "result_summary": "rows=10, top_artist=Taylor Swift",
                "source_range": "2023-01-01..2023-12-31",
                "data": {
                    "entity": "artist",
                    "metric": "plays",
                    "period": {"period": "custom", "start_date": "2023-01-01", "end_date": "2023-12-31"},
                    "rows": [{"rank": 1, "artist_name": "Taylor Swift", "plays": 1000}],
                },
            }
        ],
    )

    payload = json.loads(content)
    assert payload["project_context_version"] == "spotify-stats-project-context-v1"
```

- [ ] **Step 2: Add failing prompt-injection contract test**

Add this test to `backend/tests/contract/test_ai_agent_task_contract.py`:

```python
def test_chat_agent_prompts_include_project_context(monkeypatch) -> None:
    class FakeConn:
        def close(self) -> None:
            pass

    class FakeRepo:
        def __init__(self) -> None:
            self.result: dict[str, object] | None = None

        def update_run_if_not_terminal(self, **kwargs):
            if "result" in kwargs:
                self.result = kwargs["result"]
            return True

        def add_event(self, **kwargs):
            pass

        def get_run(self, task_id):
            return {"status": "running"}

        def add_tool_call(self, **kwargs):
            pass

    fake_repo = FakeRepo()
    llm_calls: list[tuple[str, str, float]] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return '[{"tool_name":"analysis_stats","params":{"period":"this_year"}}]'
        return "今年你听歌很多。"

    def fake_dispatch_tool(tool_name, params=None):
        return {
            "tool_name": tool_name,
            "params_summary": "period=this_year",
            "result_summary": "plays=100",
            "source_range": "2026-01-01..2026-06-29",
            "data": {
                "period": {"period": "this_year"},
                "summary": {"total_plays": 100},
            },
        }

    monkeypatch.setattr(ai_agent_service, "get_db", lambda readonly=False: FakeConn())
    monkeypatch.setattr(ai_agent_service, "AiTaskRepository", lambda conn: fake_repo)
    monkeypatch.setattr(ai_agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(ai_agent_service, "dispatch_tool", fake_dispatch_tool)

    ai_agent_service.run_chat_agent_task("task-project-context", {"question": "我今年听歌怎么样？"})

    assert len(llm_calls) >= 2
    planner_prompt = llm_calls[0][0]
    final_prompt = llm_calls[1][0]
    assert "spotify-stats-project-context-v1" in planner_prompt
    assert "Tool Playbook" in planner_prompt
    assert "不要编造工具、SQL、URL" in planner_prompt
    assert "spotify-stats-project-context-v1" in final_prompt
    assert "Answer Philosophy" in final_prompt
    assert "本地个人 Billboard" in final_prompt
    assert fake_repo.result is not None
    assert fake_repo.result["project_context_version"] == "spotify-stats-project-context-v1"
```

Ensure the test module already imports `ai_agent_service`; if not, add:

```python
from backend.services import ai_agent_service
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider \
  backend/tests/unit/test_ai_agent_evidence.py \
  backend/tests/contract/test_ai_agent_task_contract.py::test_chat_agent_prompts_include_project_context -q
```

Expected: FAIL because payload and prompts do not yet include project context.

- [ ] **Step 4: Modify AI Agent service imports and prompt constants**

In `backend/services/ai_agent_service.py`, add:

```python
from backend.domains.ai_agent.project_context import (
    PROJECT_CONTEXT_VERSION,
    build_final_answer_system_prompt,
    build_planner_system_prompt,
    project_context_payload,
)
```

Rename current prompt strings to base strings:

```python
BASE_PLANNER_SYSTEM_PROMPT = """...existing planner prompt..."""
BASE_FINAL_ANSWER_SYSTEM_PROMPT = """...existing final prompt..."""
BASE_THINKING_FINAL_ANSWER_SYSTEM_PROMPT = """...existing thinking prompt..."""
```

Then define:

```python
PLANNER_SYSTEM_PROMPT = build_planner_system_prompt(BASE_PLANNER_SYSTEM_PROMPT)
FINAL_ANSWER_SYSTEM_PROMPT = build_final_answer_system_prompt(BASE_FINAL_ANSWER_SYSTEM_PROMPT)
THINKING_FINAL_ANSWER_SYSTEM_PROMPT = build_final_answer_system_prompt(
    BASE_THINKING_FINAL_ANSWER_SYSTEM_PROMPT,
    thinking_mode=True,
)
```

- [ ] **Step 5: Add project context metadata to final payload**

In `_final_payload()`, add `**project_context_payload()` to the returned dictionary:

```python
    return {
        "question": request.get("question", ""),
        "conversation_history": (request.get("conversation_history") or [])[-6:],
        **context,
        **project_context_payload(),
        "answer_style": answer_style,
        "coverage": coverage,
        "evidence_sufficiency": evidence_sufficiency,
        "analytical_brief": analytical_brief,
        "evidence_cards": compact_cards,
        "tool_results": compact_results,
    }
```

- [ ] **Step 6: Add metadata to persisted task result**

In `_mark_done(... result={...})`, add:

```python
                "project_context_version": PROJECT_CONTEXT_VERSION,
```

Place it next to `thinking_mode` and `answer_retried`.

- [ ] **Step 7: Strengthen retry instruction**

In `_retry_user_content()`, ensure the instruction includes project context:

```python
            "不要声称 found 的实体或榜单数据缺失，不要忽略 analytical_brief.must_explain，"
            "并严格遵守 project_context_version、answer_style 和 Project Context 的项目语境要求。"
```

- [ ] **Step 8: Run targeted tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider \
  backend/tests/unit/test_ai_agent_project_context.py \
  backend/tests/unit/test_ai_agent_evidence.py \
  backend/tests/contract/test_ai_agent_task_contract.py::test_chat_agent_prompts_include_project_context -q
```

Expected: PASS.

## Task 3: Extend Golden Harness For Answer Style Metadata

**Files:**
- Modify: `backend/tests/fixtures/ai_agent_golden_questions.json`
- Modify: `backend/tests/unit/test_ai_agent_golden_questions.py`
- Modify: `scripts/evaluate_ai_agent_harness.py`

- [ ] **Step 1: Add failing fixture-shape test**

In `backend/tests/unit/test_ai_agent_golden_questions.py`, add:

```python
def test_golden_questions_may_assert_answer_style() -> None:
    cases = _load_cases()
    style_cases = [case for case in cases if case.get("expected_answer_style")]

    assert style_cases
    for case in style_cases:
        assert case["expected_answer_style"] in {"concise", "structured", "detailed"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_golden_questions.py::test_golden_questions_may_assert_answer_style -q
```

Expected: FAIL because no fixture case has `expected_answer_style`.

- [ ] **Step 3: Add expected answer style to representative fixtures**

Edit `backend/tests/fixtures/ai_agent_golden_questions.json`.

For the Ariana scoped ranking case, add:

```json
"expected_answer_style": "concise"
```

For the GUTS vs The Life of a Showgirl comparison case, add:

```json
"expected_answer_style": "structured"
```

For any explicitly detailed/table case, add:

```json
"expected_answer_style": "detailed"
```

If the fixture has no explicit detailed/table case, do not add a fake case only for this; keep first implementation focused on existing representative questions.

- [ ] **Step 4: Update golden harness unit test to compare actual answer style**

In `backend/tests/unit/test_ai_agent_golden_questions.py`, locate the parametrized current-intent/frame test and add:

```python
    expected_answer_style = case.get("expected_answer_style")
    if expected_answer_style:
        payload = ai_agent_service._final_payload(
            {"question": question, "conversation_history": []},
            [],
        )
        assert payload["answer_style"]["style"] == expected_answer_style
```

If the test module does not import `ai_agent_service`, add:

```python
from backend.services import ai_agent_service
```

- [ ] **Step 5: Update CLI harness**

In `scripts/evaluate_ai_agent_harness.py`, after it builds or validates expected frame/recipe, add logic equivalent to:

```python
expected_answer_style = case.get("expected_answer_style")
if expected_answer_style:
    payload = ai_agent_service._final_payload(
        {"question": question, "conversation_history": []},
        [],
    )
    actual_style = payload["answer_style"]["style"]
    if actual_style != expected_answer_style:
        failures.append(
            f"{case_id}: expected answer_style={expected_answer_style}, got {actual_style}"
        )
```

Use the script's existing failure collection variable names and output style.

- [ ] **Step 6: Run golden tests and CLI harness**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_golden_questions.py -q
.venv/bin/python scripts/evaluate_ai_agent_harness.py
```

Expected: PASS.

## Task 4: Documentation Sync

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `AGENTS.md`
- Modify: `backend/CLAUDE.md`

- [ ] **Step 1: Update changelog**

Add a new top entry to `docs/CHANGELOG.md`:

```markdown
## 2026-06-29 — AI Agent Project Context Layer

### 新增

- **Project Context Prompt**：AI 问答新增稳定项目语境层，集中描述 SpotifyStats 的个人音乐数据定位、本地个人 Billboard 边界、偏好分析口径和默认回答哲学。
- **Prompt 组合与版本化**：Planner 与最终回答 prompt 通过 `project_context.py` 组合 Project Context、Tool Playbook、Answer Philosophy 和 Safety Boundary，并在最终 payload / task result 中记录 `project_context_version`。
- **Golden answer style 护栏**：Golden harness 可检查代表问题的 `expected_answer_style`，防止简单问题再次退化为长报告或复杂比较被压成单一结论。

### 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_project_context.py backend/tests/unit/test_ai_agent_evidence.py backend/tests/unit/test_ai_agent_golden_questions.py backend/tests/contract/test_ai_agent_task_contract.py -q`
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`
- `.venv/bin/ruff check backend/domains/ai_agent backend/services/ai_agent_service.py`
```

- [ ] **Step 2: Update AGENTS.md AI Agent summary**

In `AGENTS.md`, update the AI Agent paragraph to include:

```markdown
Project Context Prompt 作为 AI Agent 的项目语境层，集中描述 SpotifyStats 的个人音乐数据定位、本地个人 Billboard 边界、偏好分析口径和默认回答哲学；Planner 与最终回答 prompt 通过版本化 context 组合工具 playbook 与 answer philosophy，最终 payload / task result 记录 `project_context_version` 便于排查。
```

Keep the existing read-only boundary text.

- [ ] **Step 3: Update backend/CLAUDE.md prompt ownership notes**

In `backend/CLAUDE.md`, add a bullet near the AI Agent constraints:

```markdown
- AI Agent 项目语境由 `backend/domains/ai_agent/project_context.py` 统一维护；新增 prompt 规则时优先更新 Project Context / Tool Playbook / Answer Philosophy，并同步 `test_ai_agent_project_context.py`、golden fixture 和 changelog，避免在 `ai_agent_service.py` 中复制散落语境。
```

- [ ] **Step 4: Run markdown diff check**

Run:

```bash
git diff --check
```

Expected: no output.

## Task 5: Full Target Verification And Real Question Acceptance

**Files:**
- No new files expected.
- Verify existing backend and local `/ai-insights` app if services are running.

- [ ] **Step 1: Run backend target tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider \
  backend/tests/unit/test_ai_agent_project_context.py \
  backend/tests/unit/test_ai_agent_question_frame.py \
  backend/tests/unit/test_ai_agent_evidence_recipes.py \
  backend/tests/unit/test_ai_agent_coverage_review.py \
  backend/tests/unit/test_ai_agent_analytical_brief.py \
  backend/tests/unit/test_ai_agent_answer_critic.py \
  backend/tests/unit/test_ai_agent_golden_questions.py \
  backend/tests/unit/test_ai_agent_tools.py \
  backend/tests/unit/test_ai_agent_question_intent.py \
  backend/tests/unit/test_ai_agent_evidence.py \
  backend/tests/unit/test_ai_agent_evidence_cards.py \
  backend/tests/contract/test_ai_agent_task_contract.py -q
```

Expected: all pass.

- [ ] **Step 2: Run golden harness**

Run:

```bash
.venv/bin/python scripts/evaluate_ai_agent_harness.py
```

Expected: all cases pass.

- [ ] **Step 3: Run ruff**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_agent backend/services/ai_agent_service.py backend/tests/unit/test_ai_agent_project_context.py
```

Expected: all checks pass.

- [ ] **Step 4: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Verify real chat behavior through API or browser**

If backend `http://127.0.0.1:8000` and frontend `http://localhost:5173` are running, ask these through `/ai-insights` or `POST /api/ai/tasks/chat`:

```text
我最喜欢的 Ariana Grande 的专辑和歌曲是什么？
```

Expected:

- Uses scoped artist `entity_stats`.
- Answer is concise.
- Mentions `eternal sunshine` and `Santa Tell Me` if current data matches the existing local DB.
- Does not include “我查了什么 / 自检与限制” unless evidence is insufficient.

```text
从播放次数和 billboard 榜单成绩来看，我对 GUTS 和 The Life of a Showgirl 哪张更喜欢？
```

Expected:

- Treats Billboard as local personal Billboard.
- Does not say external official Billboard, market influence, or commercial performance.
- Gives layered long-term / recent / intensity / fairness answer.

```text
我深夜最爱听什么歌？
```

Expected:

- Uses `listening_hours` late-night tool path.
- Does not use global ranking as a substitute.

- [ ] **Step 6: Summarize verification evidence**

In the final implementation response, include:

```text
验证：
- pytest target suite: ...
- golden harness: ...
- ruff: ...
- git diff --check: ...
- real /ai-insights check: ...
```

Do not claim real browser verification if only API verification was performed.

## Commit Policy

Do not create a git commit unless the user explicitly asks. The repository currently has multiple in-progress AI/Markdown/time-display edits; keep this implementation scoped and avoid reverting unrelated changes.

If the user later asks for a commit, stage all intentional changes from this plan plus already approved related changes as requested, then follow the repository commit format in `AGENTS.md`.

