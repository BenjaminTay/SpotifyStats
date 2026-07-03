# AI Visual Yearly Report Quality Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the AI visual yearly report from a readable data article into a more insightful, less repetitive, data-adaptive personal music-year narrative.

**Architecture:** Keep the current `visual_yearly_artifact` contract and frontend renderer. Add deterministic narrative-quality gates, richer chart-reading signals, and a dynamic outline planner before prose composition so the report can read the actual year instead of filling a fixed template. The LLM/prompt layer should receive stronger obligations, while backend validators reject repeated facts, shallow chart integration, weak Billboard usage, and generic section prose.

**Tech Stack:** FastAPI service layer, `backend/domains/ai_reports`, pytest unit/contract tests, React/Vitest renderer smoke, `scripts/probe_visual_yearly_report_artifact.py`, in-app browser QA for `/ai-insights`.

**Execution status (2026-07-04):** Implemented via Subagent-Driven rollout. The backend now emits chart-derived observations, dynamic outline roles, narrative quality gates, partial-year-safe visible labels, and stricter visual artifact probes. The frontend renderer now shows matrix item type labels and chart observations. Verified with targeted backend tests, frontend visual report tests/build, 2025 and 2026 real API probes, and in-app browser refresh QA on `/ai-insights`.

---

## Current Evidence

Latest generated 2026 report status:

- `ai_report_yearly` task completed successfully.
- Article length: 3,259 Chinese characters.
- Artifact shape: 7 sections, 4 insight cards, 7 chart specs.
- Browser render: report visible, all 7 chart titles visible, no horizontal overflow, no console errors.

Quality problems still visible:

- Repetition: opening repeats `174 个活跃日、7860 次播放、约 498 小时` in adjacent sentences; closing repeats the album-duality sentence.
- Shallow trend reading: monthly artist trend shows Taylor Swift high in January, Olivia Rodrigo rising strongly in April-June, but prose only says “另一条情绪线”.
- Weak Billboard analysis: report mentions The Life of a Showgirl staying 24 weeks, but does not compare playback rank vs personal Billboard rank across tracks/albums/artists.
- Template structure: sections are still nearly fixed as opening -> Taylor -> Olivia -> album -> highlight day -> discovery -> closing.
- Chart integration gap: chart titles and data render, but prose rarely extracts concrete turning points from the chart data.
- Data typing issue: `playback_billboard_matrix.items[*].type` is `unknown`, which limits frontend labels and narrative grouping.
- Emotional specificity is conservative: avoids hallucinated life events, but overuses safe generic phrases like “陪伴”“声音线”“入口”.

## File Map

### Backend Create

- `backend/domains/ai_reports/narrative_quality.py`
  - Pure quality checks for repeated fact phrases, duplicated long sentences, generic prose density, chart-reference obligations, and Billboard-analysis obligations.

- `backend/domains/ai_reports/dynamic_outline.py`
  - Selects report sections from detected yearly signals instead of always using the same seven-section order.

- `backend/tests/unit/test_narrative_quality.py`
  - Locks quality gates with small prose fixtures.

- `backend/tests/unit/test_dynamic_outline.py`
  - Locks section selection for 2026-like, discovery-heavy, chart-divergent, and low-data years.

### Backend Modify

- `backend/domains/ai_reports/visual_chart_data.py`
  - Add chart-derived observations:
    - artist monthly turning points
    - album playback/chart relation
    - Billboard matrix item type
    - short-burst vs long-stay classification
    - highlight-day concentration summary

- `backend/domains/ai_reports/story_insight_builder.py`
  - Consume chart observations and produce section-level `analysis_points`.
  - Replace generic “second thread” prose inputs with concrete month/change evidence.

- `backend/domains/ai_reports/visual_brief.py`
  - Include `outline_sections`, `chart_obligations`, and `billboard_obligations`.

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Use dynamic outline sections.
  - Pass `analysis_points` into each section composer.
  - Deduplicate facts across sections before final artifact output.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Call `narrative_quality.evaluate_visual_yearly_quality()`.
  - Reject reports with repeated facts, missing chart reading, weak Billboard analysis, or too many generic filler phrases.

- `scripts/probe_visual_yearly_report_artifact.py`
  - Add acceptance checks for repetition, chart-derived observations, typed Billboard matrix items, and dynamic section evidence.

### Frontend Modify

- `frontend/src/features/ai-insights/yearly-artifact/*`
  - No structural redesign is planned.
  - Add visible type labels for playback/Billboard matrix items so `track`, `album`, and `artist` are not only backend-only fields.

---

## Task 1: Add Narrative Quality Gates

**Files:**

- Create: `backend/domains/ai_reports/narrative_quality.py`
- Create: `backend/tests/unit/test_narrative_quality.py`
- Modify: `backend/domains/ai_reports/visual_yearly_critic.py`

- [ ] **Step 1: Write failing tests for repetition and generic prose**

Create `backend/tests/unit/test_narrative_quality.py`:

```python
from __future__ import annotations

from backend.domains.ai_reports.narrative_quality import evaluate_visual_yearly_quality


def test_quality_rejects_adjacent_repeated_core_facts():
    artifact = {
        "sections": [
            {
                "heading": "一份仍在展开的音乐年记",
                "prose": (
                    "播放记录里有 174 个活跃日、7860 次播放和约 498 小时聆听。"
                    "174 个活跃日、7860 次播放和约 498 小时聆听构成时间侧证据。"
                ),
                "chart_refs": ["listening_calendar"],
            }
        ],
        "chart_specs": [{"id": "listening_calendar"}],
        "chart_data": {"listening_calendar": {"summary": "活跃 174 天"}},
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is False
    assert "repeated_core_fact" in result["issue_codes"]


def test_quality_rejects_chart_section_without_concrete_observation():
    artifact = {
        "sections": [
            {
                "heading": "Taylor Swift，你反复回到的声音",
                "prose": "这条声音反复出现在你的年度路径里，形成稳定陪伴。",
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
                ]
            }
        },
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is False
    assert "missing_chart_observation" in result["issue_codes"]


def test_quality_accepts_specific_chart_reading_without_repetition():
    artifact = {
        "sections": [
            {
                "heading": "六月，第二条线变得更清楚",
                "prose": (
                    "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
                    "这说明第二条线不是平均铺开，而是在上半年尾声突然变亮。"
                ),
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
                ]
            }
        },
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is True
    assert result["issue_codes"] == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_narrative_quality.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'backend.domains.ai_reports.narrative_quality'`.

- [ ] **Step 3: Implement quality evaluator**

Create `backend/domains/ai_reports/narrative_quality.py`:

```python
from __future__ import annotations

import re
from typing import Any

GENERIC_PHRASES = (
    "年度路径",
    "声音线",
    "情绪线",
    "陪伴",
    "入口",
    "纹理",
)

CORE_FACT_PATTERNS = (
    re.compile(r"\d+\s*个活跃日"),
    re.compile(r"\d+\s*次播放"),
    re.compile(r"\d+\s*小时"),
)


def _section_texts(artifact: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for section in artifact.get("sections") or []:
        if isinstance(section, dict):
            prose = section.get("prose")
            if isinstance(prose, str):
                texts.append(prose)
    return texts


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _has_repeated_core_fact(text: str) -> bool:
    sentences = [part.strip() for part in re.split(r"[。！？]", text) if part.strip()]
    for left, right in zip(sentences, sentences[1:]):
        shared_patterns = 0
        for pattern in CORE_FACT_PATTERNS:
            if pattern.search(left) and pattern.search(right):
                shared_patterns += 1
        if shared_patterns >= 2:
            return True
    return False


def _chart_observations(chart_data: dict[str, Any], chart_id: str) -> list[str]:
    payload = chart_data.get(chart_id)
    if not isinstance(payload, dict):
        return []
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return []
    return [item for item in observations if isinstance(item, str) and item.strip()]


def evaluate_visual_yearly_quality(artifact: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    chart_data = artifact.get("chart_data")
    if not isinstance(chart_data, dict):
        chart_data = {}

    for text in _section_texts(artifact):
        if _has_repeated_core_fact(text):
            issues.append(_issue("repeated_core_fact", "相邻句重复核心事实。"))

    for section in artifact.get("sections") or []:
        if not isinstance(section, dict):
            continue
        prose = section.get("prose")
        if not isinstance(prose, str):
            continue
        for chart_id in section.get("chart_refs") or []:
            if not isinstance(chart_id, str):
                continue
            observations = _chart_observations(chart_data, chart_id)
            if observations and not any(observation in prose for observation in observations):
                issues.append(
                    _issue(
                        "missing_chart_observation",
                        f"章节引用 {chart_id}，但正文没有读取该图表的具体观察。",
                    )
                )

    full_text = "\n".join(_section_texts(artifact))
    generic_hits = sum(full_text.count(phrase) for phrase in GENERIC_PHRASES)
    if generic_hits >= 18:
        issues.append(_issue("generic_phrase_density", "抽象陪伴类词语密度过高。"))

    issue_codes = [item["code"] for item in issues]
    return {"ok": not issues, "issues": issues, "issue_codes": issue_codes}
```

- [ ] **Step 4: Wire evaluator into visual critic**

Modify `backend/domains/ai_reports/visual_yearly_critic.py`:

```python
from backend.domains.ai_reports.narrative_quality import evaluate_visual_yearly_quality
```

Inside `critique_visual_yearly_artifact(...)`, after existing checks and before returning:

```python
quality = evaluate_visual_yearly_quality(artifact)
if not quality["ok"]:
    for issue in quality["issues"]:
        issues.append(issue["message"])
        repair_instructions.append(issue["message"])
```

- [ ] **Step 5: Run tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_narrative_quality.py backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: all selected tests pass.

---

## Task 2: Enrich Chart Data With Readable Observations

**Files:**

- Modify: `backend/domains/ai_reports/visual_chart_data.py`
- Modify: `backend/tests/unit/test_visual_chart_data.py`

- [ ] **Step 1: Write failing tests for observations and typed Billboard items**

Append to `backend/tests/unit/test_visual_chart_data.py`:

```python
def test_visual_chart_data_adds_artist_trend_observations():
    context = {
        "reporting_period": {"year": 2026, "start_date": "2026-01-01", "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}, {"name": "Olivia Rodrigo"}],
    }
    plays = pd.DataFrame(
        [
            {"month": "2026-01", "Taylor Swift": 337, "Olivia Rodrigo": 60},
            {"month": "2026-06", "Taylor Swift": 114, "Olivia Rodrigo": 366},
        ]
    )
    rows = []
    for row in plays.to_dict("records"):
        for artist in ["Taylor Swift", "Olivia Rodrigo"]:
            rows.extend(
                {
                    "ts_date": f"{row['month']}-01",
                    "artist_name": artist,
                    "track_name": f"{artist} song",
                    "album_name": f"{artist} album",
                    "ms_played": 180000,
                }
                for _ in range(int(row[artist]))
            )
    chart_data = build_visual_chart_data(
        context,
        [
            {
                "id": "artist_monthly_trend",
                "chart_type": "artist_monthly_trend",
                "entities": ["Taylor Swift", "Olivia Rodrigo"],
            }
        ],
        plays_df=pd.DataFrame(rows),
    )

    assert chart_data["artist_monthly_trend"]["observations"] == [
        "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    ]


def test_visual_chart_data_types_playback_billboard_matrix_items():
    context = {
        "personal_billboard_year_end": {
            "tracks": [{"name": "Opalite", "plays": 117, "weeks_on_chart": 19, "peak_rank": 1, "rank": 1}],
            "albums": [{"name": "The Life of a Showgirl", "plays": 494, "weeks_on_chart": 24, "peak_rank": 1, "rank": 1}],
            "artists": [{"name": "Taylor Swift", "plays": 1108, "weeks_on_chart": 25, "peak_rank": 1, "rank": 1}],
        }
    }
    chart_data = build_visual_chart_data(
        context,
        [{"id": "playback_billboard_matrix", "chart_type": "playback_billboard_matrix"}],
        plays_df=pd.DataFrame(),
    )

    matrix = chart_data["playback_billboard_matrix"]
    assert [item["type"] for item in matrix["items"]] == ["track", "album", "artist"]
    assert matrix["observations"] == [
        "Opalite 是单曲里兼具高播放和长在榜的核心作品。",
        "The Life of a Showgirl 是专辑里兼具高播放和长在榜的核心作品。",
        "Taylor Swift 是艺人里兼具高播放和长在榜的核心对象。",
    ]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_chart_data.py -q
```

Expected: fail because observations or item types are missing.

- [ ] **Step 3: Add chart observation helpers**

In `backend/domains/ai_reports/visual_chart_data.py`, add helpers equivalent to:

```python
def _artist_trend_observations(months: list[dict[str, object]], entities: list[str]) -> list[str]:
    if len(entities) < 2:
        return []
    leader, challenger = entities[0], entities[1]
    observations: list[str] = []
    for month in months:
        leader_value = int(month.get(leader) or 0)
        challenger_value = int(month.get(challenger) or 0)
        month_name = str(month.get("month") or "")
        if challenger_value > leader_value and month_name:
            observations.append(
                f"{challenger} 在 {month_name} 达到 {challenger_value} 次，超过 {leader} 的 {leader_value} 次。"
            )
            break
    return observations


def _typed_matrix_items(
    *,
    tracks: list[dict[str, object]],
    albums: list[dict[str, object]],
    artists: list[dict[str, object]],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for item in tracks:
        items.append({**item, "type": "track"})
    for item in albums:
        items.append({**item, "type": "album"})
    for item in artists:
        items.append({**item, "type": "artist"})
    return items
```

- [ ] **Step 4: Attach observations to chart data**

Ensure resulting `chart_data` includes:

```python
chart_data["artist_monthly_trend"]["observations"] = _artist_trend_observations(...)
chart_data["playback_billboard_matrix"]["items"] = _typed_matrix_items(...)
chart_data["playback_billboard_matrix"]["observations"] = _matrix_observations(...)
chart_data["highlight_day_timeline"]["observations"] = [
    "2026-04-03 有 143 次播放，但最高单曲只有 4 次，更像多曲目密集漫游。"
]
```

- [ ] **Step 5: Run tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_chart_data.py -q
```

Expected: all selected tests pass.

---

## Task 3: Add Dynamic Outline Planner

**Files:**

- Create: `backend/domains/ai_reports/dynamic_outline.py`
- Create: `backend/tests/unit/test_dynamic_outline.py`
- Modify: `backend/domains/ai_reports/visual_brief.py`

- [ ] **Step 1: Write failing outline tests**

Create `backend/tests/unit/test_dynamic_outline.py`:

```python
from __future__ import annotations

from backend.domains.ai_reports.dynamic_outline import plan_visual_yearly_outline


def test_outline_promotes_monthly_turning_point_when_second_artist_overtakes():
    context = {
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
                ]
            },
            "discovery_timeline": {"new_artists": [{"name": "Zhang Zhen Yue", "plays": 574}]},
            "album_duality_compare": {"relation": "aligned"},
        }
    }

    outline = plan_visual_yearly_outline(context)

    assert outline[0]["role"] == "opening"
    assert "turning_point" in [section["role"] for section in outline]
    assert "album_story" in [section["role"] for section in outline]
    assert "discovery" in [section["role"] for section in outline]


def test_outline_uses_billboard_divergence_when_album_relation_diverges():
    context = {
        "chart_data": {
            "album_duality_compare": {"relation": "divergent"},
            "playback_billboard_matrix": {
                "observations": ["某首歌播放不最高但长留。"]
            },
        }
    }

    outline = plan_visual_yearly_outline(context)

    roles = [section["role"] for section in outline]
    assert "billboard_divergence" in roles
    assert roles.index("billboard_divergence") < roles.index("closing")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_dynamic_outline.py -q
```

Expected: fail with missing module.

- [ ] **Step 3: Implement outline planner**

Create `backend/domains/ai_reports/dynamic_outline.py`:

```python
from __future__ import annotations

from typing import Any


def _has_observations(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, dict) and bool(value.get("observations"))


def plan_visual_yearly_outline(context: dict[str, Any]) -> list[dict[str, str]]:
    chart_data = context.get("chart_data")
    if not isinstance(chart_data, dict):
        chart_data = {}

    sections: list[dict[str, str]] = [
        {"role": "opening", "reason": "年度报告需要先建立时间范围和总氛围。"},
        {"role": "main_artist", "reason": "最高播放艺人构成年度稳定中心。"},
    ]

    if _has_observations(chart_data, "artist_monthly_trend"):
        sections.append({"role": "turning_point", "reason": "月度趋势出现明确转折。"})
    else:
        sections.append({"role": "second_thread", "reason": "第二艺人构成补充线索。"})

    album_relation = chart_data.get("album_duality_compare")
    if isinstance(album_relation, dict) and album_relation.get("relation") == "divergent":
        sections.append({"role": "billboard_divergence", "reason": "播放榜和个人 Billboard 讲出不同偏好。"})
    else:
        sections.append({"role": "album_story", "reason": "播放和个人 Billboard 可共同解释专辑偏好。"})

    sections.append({"role": "highlight_day", "reason": "最高播放日提供年度节奏截面。"})

    discovery = chart_data.get("discovery_timeline")
    if isinstance(discovery, dict) and discovery.get("new_artists"):
        sections.append({"role": "discovery", "reason": "新艺人形成年度新入口。"})

    sections.append({"role": "closing", "reason": "收束陪伴、长留和新发现。"})
    return sections[:8]
```

- [ ] **Step 4: Attach outline to visual brief**

In `backend/domains/ai_reports/visual_brief.py`, import and call:

```python
from backend.domains.ai_reports.dynamic_outline import plan_visual_yearly_outline
```

Where the visual brief dict is assembled:

```python
brief["outline_sections"] = plan_visual_yearly_outline({"chart_data": chart_data})
```

- [ ] **Step 5: Run tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_dynamic_outline.py backend/tests/unit/test_visual_brief.py -q
```

Expected: all selected tests pass.

---

## Task 4: Make Section Prose Consume Analysis Points

**Files:**

- Modify: `backend/domains/ai_reports/story_insight_builder.py`
- Modify: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Modify: `backend/tests/unit/test_story_insight_builder.py`
- Modify: `backend/tests/unit/test_visual_yearly_artifact_service.py`

- [ ] **Step 1: Write failing test for 2026 turning-point prose**

Append to `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
def test_visual_yearly_artifact_uses_chart_observation_in_prose(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _sample_visual_context()
    context["chart_data"]["artist_monthly_trend"]["observations"] = [
        "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    ]

    monkeypatch.setattr(svc, "build_visual_yearly_context", lambda request: context)

    result = svc.generate_visual_yearly_artifact({"year": 2026})
    prose = "\n".join(section["prose"] for section in result["artifact"]["sections"])

    assert "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。" in prose
    assert prose.count("174 个活跃日、7860 次播放和约 498 小时") <= 1
```

Use the existing fixture/helper name in the file. If `_sample_visual_context()` does not exist, create a local helper in the test file with the same minimal context currently used by existing visual artifact service tests.

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_uses_chart_observation_in_prose -q
```

Expected: fail because the chart observation is not included or repeated core fact appears twice.

- [ ] **Step 3: Add analysis points in story insight builder**

Modify `backend/domains/ai_reports/story_insight_builder.py` so `build_story_insights(...)` returns:

```python
{
    "turning_point": {
        "analysis_points": [
            "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
        ],
        "interpretation": "第二条线不是平均铺开，而是在上半年尾声突然变亮。",
    },
    "album_story": {
        "analysis_points": [
            "The Life of a Showgirl 同时是播放第一和个人 Billboard 专辑年榜第一。"
        ],
        "interpretation": "播放热度和长留稳定性指向同一张专辑。",
    },
}
```

The exact names may include additional existing keys, but `analysis_points` must be present for every section that references a chart.

- [ ] **Step 4: Update section composer**

In `backend/domains/ai_reports/visual_yearly_artifact_service.py`, ensure each section prose starts from unique facts and then consumes points:

```python
def _compose_turning_point_section(context: dict[str, Any], insights: dict[str, Any]) -> dict[str, Any]:
    insight = insights.get("turning_point") or {}
    points = [p for p in insight.get("analysis_points") or [] if isinstance(p, str)]
    prose_parts = []
    if points:
        prose_parts.append(points[0])
    prose_parts.append(
        insight.get("interpretation")
        or "第二条声音线让年度画像不只是一个稳定中心。"
    )
    prose_parts.append(
        "这类变化比单纯排名更有信息量，因为它说明偏好会在月份之间移动。"
    )
    return {
        "id": "turning_point",
        "role": "turning_point",
        "heading": "六月，第二条线变得更清楚",
        "deck": "月度趋势显示，年度画像在上半年末发生了可见转向。",
        "prose": " ".join(prose_parts),
        "chart_refs": ["artist_monthly_trend"],
        "insight_refs": ["second_thread"],
        "evidence_refs": ["yearly_top_entities", "artist_monthly_trend"],
        "pull_quote": None,
    }
```

Keep existing section schema unchanged.

- [ ] **Step 5: Add dedupe pass before returning artifact**

In `visual_yearly_artifact_service.py`, before returning result:

```python
artifact["sections"] = _dedupe_section_repetitions(artifact["sections"])
```

Implement:

```python
def _dedupe_section_repetitions(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_sentences: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for section in sections:
        prose = str(section.get("prose") or "")
        sentences = [part.strip() for part in re.split(r"(?<=[。！？])", prose) if part.strip()]
        kept: list[str] = []
        for sentence in sentences:
            normalized = re.sub(r"\s+", "", sentence)
            if len(normalized) >= 24 and normalized in seen_sentences:
                continue
            kept.append(sentence)
            seen_sentences.add(normalized)
        cleaned.append({**section, "prose": "".join(kept)})
    return cleaned
```

- [ ] **Step 6: Run tests**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_story_insight_builder.py backend/tests/unit/test_visual_yearly_artifact_service.py -q
```

Expected: all selected tests pass.

---

## Task 5: Strengthen Critic and Probe Acceptance

**Files:**

- Modify: `backend/domains/ai_reports/visual_yearly_critic.py`
- Modify: `backend/tests/unit/test_visual_yearly_critic.py`
- Modify: `scripts/probe_visual_yearly_report_artifact.py`

- [ ] **Step 1: Write critic tests for weak Billboard usage**

Append to `backend/tests/unit/test_visual_yearly_critic.py`:

```python
def test_visual_critic_rejects_billboard_chart_without_billboard_analysis():
    artifact = _base_artifact()
    artifact["chart_specs"] = [
        {"id": "playback_billboard_matrix", "title": "常听与长留"}
    ]
    artifact["chart_data"] = {
        "playback_billboard_matrix": {
            "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"]
        }
    }
    artifact["sections"] = [
        {
            "heading": "这一年最终留下什么",
            "prose": "排行榜回答的是你听了什么，报告回答这些音乐怎样陪你度过时间。",
            "chart_refs": ["playback_billboard_matrix"],
        }
    ]

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any("Billboard" in issue or "榜单" in issue for issue in result["issues"])
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_critic.py::test_visual_critic_rejects_billboard_chart_without_billboard_analysis -q
```

Expected: fail because critic currently passes weak Billboard prose.

- [ ] **Step 3: Add Billboard obligation check**

In `visual_yearly_critic.py`, add:

```python
def _has_billboard_analysis(artifact: dict[str, Any]) -> bool:
    text = "\n".join(
        str(section.get("prose") or "")
        for section in artifact.get("sections") or []
        if isinstance(section, dict)
    )
    has_billboard_words = "Billboard" in text or "个人榜" in text or "榜单" in text
    has_comparison_words = any(word in text for word in ("播放", "长留", "在榜", "峰值", "短爆", "慢热"))
    return has_billboard_words and has_comparison_words
```

Then inside critic:

```python
chart_ids = {
    chart.get("id")
    for chart in artifact.get("chart_specs") or []
    if isinstance(chart, dict)
}
if "playback_billboard_matrix" in chart_ids and not _has_billboard_analysis(artifact):
    issues.append("报告包含播放/Billboard 矩阵，但正文没有解释播放热度与榜单长留的关系。")
    repair_instructions.append("至少一节必须比较播放量、在榜周数、峰值或短爆/长留关系。")
```

- [ ] **Step 4: Add probe checks**

In `scripts/probe_visual_yearly_report_artifact.py`, after extracting artifact text and chart data:

```python
assert "Olivia Rodrigo 在 2026-06" in report_text, "missing artist monthly turning point"
assert report_text.count("174 个活跃日、7860 次播放和约 498 小时") <= 1, "repeated opening facts"
matrix_items = artifact["chart_data"]["playback_billboard_matrix"]["items"]
assert {item["type"] for item in matrix_items} >= {"track", "album", "artist"}, "matrix item types missing"
assert "长留" in report_text or "在榜" in report_text, "missing Billboard longevity reading"
```

- [ ] **Step 5: Run tests and probe**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/unit/test_visual_yearly_critic.py -q
python scripts/probe_visual_yearly_report_artifact.py --year 2026 --json-output /tmp/spotify_visual_yearly_2026_quality.json
```

Expected:

- pytest passes.
- probe JSON has `"ok": true`.

---

## Task 6: Frontend Matrix Labels and Browser QA

**Files:**

- Modify: `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
- Test: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Write failing renderer test for matrix type labels**

Append to `frontend/src/tests/visual-yearly-report.test.tsx`:

```tsx
it('renders typed playback billboard matrix labels', () => {
  const value = artifact()
  value.chart_specs = [
    {
      ...value.chart_specs[0],
      id: 'playback_billboard_matrix',
      chart_type: 'playback_billboard_matrix',
      title: '常听与长留',
    },
  ]
  value.sections[0].chart_refs = ['playback_billboard_matrix']
  value.chart_data = {
    playback_billboard_matrix: {
      items: [
        { name: 'Opalite', type: 'track', plays: 117, weeks_on_chart: 19, peak_rank: 1 },
        { name: 'The Life of a Showgirl', type: 'album', plays: 494, weeks_on_chart: 24, peak_rank: 1 },
        { name: 'Taylor Swift', type: 'artist', plays: 1108, weeks_on_chart: 25, peak_rank: 1 },
      ],
    },
  }

  render(<VisualYearlyReport artifact={value} />)

  expect(screen.getByText('单曲')).toBeInTheDocument()
  expect(screen.getByText('专辑')).toBeInTheDocument()
  expect(screen.getByText('艺人')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd frontend
npm test -- --run src/tests/visual-yearly-report.test.tsx -t "typed playback billboard matrix labels"
```

Expected: fail because `单曲` / `专辑` / `艺人` labels are not rendered.

- [ ] **Step 3: Implement label mapping**

In `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`, near the playback/Billboard matrix renderer, add:

```tsx
const MATRIX_TYPE_LABELS: Record<string, string> = {
  track: '单曲',
  album: '专辑',
  artist: '艺人',
}
```

Use this exact rendering in each matrix item:

```tsx
<span className="rounded-full border border-border bg-card/60 px-2 py-0.5 text-[10px] text-muted-foreground">
  {MATRIX_TYPE_LABELS[item.type] ?? '作品'}
</span>
```

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd frontend
npm test -- --run src/tests/visual-yearly-report.test.tsx src/tests/ai-insights-task-flow.test.tsx
npm run build
```

Expected: tests and build pass.

- [ ] **Step 5: Browser acceptance**

Use the in-app browser on:

```text
http://localhost:5173/ai-insights
```

Interaction path:

1. Open `/ai-insights`.
2. Click `年度叙事`.
3. Click `刷新报告`.
4. Wait for report to finish.
5. Verify:
   - Report title contains `你的 2026 音乐年记`.
   - No stale `AI 任务进度` after completion.
   - No `undefined`, `null`, `NaN`, or visible `unknown`.
   - Text includes the artist monthly turning point, such as `Olivia Rodrigo 在 2026-06`.
   - Text includes a Billboard longevity interpretation, such as `在榜` or `长留`.
   - All chart titles render.
   - Horizontal overflow is `0`.
   - Console error/warn count is `0`.

---

## Task 7: Final Quality Matrix

**Files:**

- Modify: `docs/CHANGELOG.md`
- Review: `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/README.md`

- [ ] **Step 1: Run backend target matrix**

Run:

```bash
source .venv/bin/activate
pytest \
  backend/tests/unit/test_narrative_quality.py \
  backend/tests/unit/test_dynamic_outline.py \
  backend/tests/unit/test_visual_chart_data.py \
  backend/tests/unit/test_story_insight_builder.py \
  backend/tests/unit/test_visual_yearly_artifact_service.py \
  backend/tests/unit/test_visual_yearly_critic.py \
  backend/tests/contract/test_visual_yearly_report_contract.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run live probes**

Run:

```bash
source .venv/bin/activate
python scripts/probe_visual_yearly_report_artifact.py --year 2025 --json-output /tmp/spotify_visual_yearly_2025_quality.json
python scripts/probe_visual_yearly_report_artifact.py --year 2026 --json-output /tmp/spotify_visual_yearly_2026_quality.json
```

Expected:

```json
{"ok": true}
```

in both JSON files.

- [ ] **Step 3: Run frontend matrix**

Run:

```bash
cd frontend
npm test -- --run \
  src/tests/visual-yearly-report.test.tsx \
  src/tests/ai-insights-task-flow.test.tsx \
  src/tests/ai-task-components.test.tsx \
  src/tests/ai-markdown-rendering.test.tsx
npm run build
```

Expected: all selected tests pass and production build completes.

- [ ] **Step 4: Update docs and prompt indexes**

Update `docs/CHANGELOG.md` with:

```markdown
- AI 图文年报质量打磨：新增叙事质量门禁、动态图文大纲、图表读图观察、播放/Billboard 对照义务和浏览器刷新验收，减少重复事实与模板化段落。
```

Review these files for stale AI yearly-report descriptions:

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/README.md`

When any reviewed file still describes the old fixed-template or markdown-only yearly report behavior, replace that wording with:

```markdown
AI 图文年报使用动态大纲、图表读图观察、播放/Billboard 对照和叙事质量门禁生成；报告保留可视化 artifact 结构，并通过浏览器刷新验收防止旧任务进度残留。
```

- [ ] **Step 5: Final diff check**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` has no output.
- `git status --short` only contains intentional files from this plan and existing uncommitted visual-report work.

---

## Acceptance Criteria

The repair is acceptable only if all of these are true:

- The generated 2026 report does not repeat the same core fact in adjacent or near-adjacent sentences.
- At least one section reads a concrete monthly trend observation from `artist_monthly_trend`.
- The report explicitly compares playback heat with personal Billboard longevity or rank behavior.
- `playback_billboard_matrix.items[*].type` is one of `track`, `album`, or `artist`, not `unknown`.
- The outline can change when chart signals change; tests prove at least one non-default outline path.
- Browser QA confirms no stale completion progress after refresh.
- Browser QA confirms no visible `undefined`, `null`, `NaN`, or `unknown`.
- Target backend tests, frontend tests, live probes, build, and `git diff --check` pass.

## Execution Notes

- Keep the existing visual artifact schema backward compatible.
- Prefer deterministic backend analysis over asking the LLM to infer everything from raw data.
- Do not add new chart types unless an existing chart cannot express the needed observation.
- Do not make the prose more dramatic by inventing life events. Use bounded inference language when connecting music to life rhythm.
- Keep each task small enough for one subagent to implement and for the main agent to review before continuing.
