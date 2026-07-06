# AI Yearly Final Artifact Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI yearly visual report pass quality checks on the exact artifact text and chart blocks users see after refresh.

**Architecture:** Keep the existing `visual_yearly_artifact` and `editorial_agent_v1` pipeline. Add a backend final-visible-artifact quality gate, fix artifact section/chart assembly before caching, and add frontend renderer safeguards so repeated chart refs or internal chart copy cannot leak into the UI.

**Tech Stack:** FastAPI backend, Python dataclasses/unit tests, SQLite-backed AI task results, React + Vitest + Testing Library, Playwright/browser manual acceptance.

---

## Current Failure Evidence

The 2026 yearly report refreshed successfully in the browser, but the generated artifact exposed quality failures:

- Report task `0bffaba94e9f` was a real forced yearly generation with `report_mode=visual_yearly_artifact` and `writer_pipeline=editorial_agent_v1`.
- Page showed `Editorial Agent`, `事实核对通过`, `口味评分 35`, and `已通过编辑审稿`.
- User-visible text still contained repeated sections and chart blocks.
- Section decks leaked planner/internal copy such as `展示Olivia Rodrigo...` and `解释播放领先专辑...`.
- `YearlyChartBlock` rendered `chartSpec.insight`, which is currently written like an internal explanation in several specs.
- Existing critic and probe passed because they mostly validate `section.prose`, not the final visible artifact composed from title, subtitle, decks, prose, chart blocks, observations, and frontend chart dedup behavior.

This plan fixes the root cause: the final cacheable artifact must be judged and sanitized as a user-visible product, not as separate LLM draft fragments.

## File Structure

- Create `backend/domains/ai_reports/final_artifact_quality.py`
  - Owns final visible text extraction and deterministic quality checks.
  - Checks section deck/prose, repeated section fingerprints, repeated chart refs, internal planning language, placeholder tokens, and misleading accepted metadata.

- Modify `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Replace `section.purpose` as deck source.
  - Deduplicate editorial sections and globally assign each chart ref to one section.
  - Run final artifact quality before returning/caching metadata.
  - Merge final quality issues into critic metadata.

- Modify `backend/domains/ai_reports/visual_yearly_critic.py`
  - Include section `deck`, `pull_quote`, and user-visible chart observations in critic text.
  - Reject internal brief/purpose language in decks, not only in prose.

- Modify `scripts/probe_visual_yearly_report_artifact.py`
  - Validate final visible artifact text and duplicate chart rendering.
  - Fail when metadata says accepted but final visible text fails.

- Modify `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
  - Pre-filter duplicate chart refs across sections.

- Modify `frontend/src/features/ai-insights/yearly-artifact/YearlySection.tsx`
  - Accept already-filtered section refs without changing artifact data shape.

- Modify `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
  - Stop rendering `spec.insight` as user copy.
  - Keep chart observations from deterministic `chart_data` visible.

- Modify `frontend/src/features/ai-insights/AiReportsPanel.tsx`
  - Clear stale report task state on report-type switch.
  - Add accessible selected state for report-type buttons.

- Tests:
  - Create `backend/tests/unit/test_final_artifact_quality.py`.
  - Extend `backend/tests/unit/test_visual_yearly_artifact_service.py`.
  - Extend `backend/tests/unit/test_visual_yearly_critic.py`.
  - Extend `frontend/src/tests/visual-yearly-report.test.tsx`.
  - Extend `frontend/src/tests/ai-insights-task-flow.test.tsx`.

---

### Task 1: Backend Final Visible Artifact Quality Gate

**Files:**
- Create: `backend/domains/ai_reports/final_artifact_quality.py`
- Test: `backend/tests/unit/test_final_artifact_quality.py`

- [ ] **Step 1: Write the failing backend tests**

Create `backend/tests/unit/test_final_artifact_quality.py`:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.final_artifact_quality import (
    evaluate_final_artifact_quality,
    final_visible_artifact_text,
)

pytestmark = pytest.mark.unit


def _artifact() -> dict:
    return {
        "title": "AI 音乐年报",
        "subtitle": "2026 · 截至 2026-06-23",
        "sections": [
            {
                "id": "stable_return",
                "heading": "最稳定的回访对象",
                "deck": "Taylor Swift 是年度重心。",
                "prose": (
                    "Taylor Swift 以 1115 次播放位列艺人榜第一。"
                    "这让年度第一不只是一个名次，而是一条你持续回到的声音。"
                ),
                "pull_quote": "Taylor Swift 以 1115 次播放位列艺人榜第一",
                "chart_refs": ["listening_calendar"],
            },
            {
                "id": "monthly_turning",
                "heading": "月度反超点",
                "deck": "Olivia Rodrigo 在 5 月短暂变亮。",
                "prose": (
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                    "这说明累计第一之外还存在阶段性变化。"
                ),
                "chart_refs": ["artist_monthly_trend"],
            },
            {
                "id": "album_longevity",
                "heading": "专辑的双重验证",
                "deck": "The Life of a Showgirl 同时具有播放热度和长留信号。",
                "prose": (
                    "The Life of a Showgirl 的播放量和个人 Billboard 专辑表现对齐，"
                    "个人榜在榜 24 周。"
                ),
                "chart_refs": ["album_duality_compare"],
            },
            {
                "id": "highlight_day",
                "heading": "高光日",
                "deck": "2026-04-03 是播放密度异常高的一天。",
                "prose": "2026-04-03 有 143 次播放，最高单曲只有 4 次，更像多曲目密集漫游。",
                "chart_refs": ["highlight_day_timeline"],
            },
            {
                "id": "new_voice",
                "heading": "新声音",
                "deck": "Zhang Zhen Yue 是今年清楚进入记录的新艺人。",
                "prose": "Zhang Zhen Yue 首次出现于 2026-03-09，累计 574 次播放。",
                "chart_refs": ["discovery_timeline"],
            },
            {
                "id": "closing",
                "heading": "这一年最终留下什么",
                "deck": "把前面的线索收束成一份可回看的音乐年记。",
                "prose": "这份年记记录的是你如何在熟悉和新鲜之间分配注意力。",
                "chart_refs": [],
            },
        ],
        "chart_specs": [
            {"id": "listening_calendar", "title": "音乐铺满当前统计期", "data_key": "listening_calendar"},
            {"id": "artist_monthly_trend", "title": "艺人月度趋势", "data_key": "artist_monthly_trend"},
            {"id": "album_duality_compare", "title": "专辑热度与长留关系", "data_key": "album_duality_compare"},
            {"id": "highlight_day_timeline", "title": "阶段高光日拆解", "data_key": "highlight_day_timeline"},
            {"id": "discovery_timeline", "title": "Zhang Zhen Yue 出现以后", "data_key": "discovery_timeline"},
        ],
        "chart_data": {
            "listening_calendar": {"observations": ["活跃 174 天。"]},
            "artist_monthly_trend": {
                "observations": ["Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"]
            },
            "album_duality_compare": {"observations": ["播放量和持续在榜指向同一张专辑。"]},
            "highlight_day_timeline": {"observations": ["最高单曲只有 4 次，更像多曲目密集漫游。"]},
            "discovery_timeline": {"observations": ["Zhang Zhen Yue 首次出现于 2026-03-09。"]},
        },
        "metadata": {
            "writer_pipeline_status": "accepted",
            "critic_passed": True,
            "taste_score": {"ok": True, "total": 35},
        },
    }


def test_final_visible_text_includes_user_visible_deck_and_chart_observations():
    text = final_visible_artifact_text(_artifact())

    assert "Taylor Swift 是年度重心。" in text
    assert "音乐铺满当前统计期" in text
    assert "活跃 174 天。" in text
    assert "Zhang Zhen Yue 首次出现于 2026-03-09。" in text


def test_final_quality_rejects_internal_deck_language():
    artifact = _artifact()
    artifact["sections"][1]["deck"] = "展示Olivia Rodrigo在5月超越Taylor Swift的播放量，说明偏好会在特定月份发生转向。"

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "internal_brief_leakage" for issue in result["issues"])


def test_final_quality_rejects_duplicate_section_prose():
    artifact = _artifact()
    artifact["sections"][5]["heading"] = "Taylor Swift 是最稳定的回访对象"
    artifact["sections"][5]["prose"] = artifact["sections"][0]["prose"]

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "duplicate_section_text" for issue in result["issues"])


def test_final_quality_rejects_duplicate_chart_refs():
    artifact = _artifact()
    artifact["sections"][1]["chart_refs"] = ["listening_calendar", "artist_monthly_trend"]

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "duplicate_chart_ref" for issue in result["issues"])


def test_final_quality_rejects_misleading_accepted_metadata_when_visible_text_fails():
    artifact = _artifact()
    artifact["sections"][0]["deck"] = "解释播放领先专辑和个人榜单领先专辑的关系。"
    artifact["metadata"]["writer_pipeline_status"] = "accepted"
    artifact["metadata"]["taste_score"] = {"ok": True, "total": 35}

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "misleading_quality_metadata" for issue in result["issues"])
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_final_artifact_quality.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'backend.domains.ai_reports.final_artifact_quality'`.

- [ ] **Step 3: Implement the final quality module**

Create `backend/domains/ai_reports/final_artifact_quality.py`:

```python
"""Final user-visible quality checks for visual yearly artifacts."""

from __future__ import annotations

import re
from typing import Any

INTERNAL_BRIEF_PATTERNS = (
    re.compile(r"^(展示|解释|说明|分析|揭示).{0,80}(播放量|个人榜单|偏好|关系|证据|趋势)"),
    re.compile(r"(chart_refs|evidence_refs|interpretation_guidance|safe_speculation_rules)"),
)

PLACEHOLDER_PATTERN = re.compile(r"\b(undefined|null|nan|unknown)\b", re.IGNORECASE)


def final_visible_artifact_text(artifact: dict[str, Any]) -> str:
    """Return the text a user can see in the visual yearly artifact."""
    chart_specs = _chart_specs_by_id(artifact)
    chart_data = _dict(artifact.get("chart_data"))
    parts: list[str] = [str(artifact.get("title") or ""), str(artifact.get("subtitle") or "")]
    rendered_charts: set[str] = set()
    for section in _list(artifact.get("sections")):
        parts.extend(
            [
                str(section.get("heading") or ""),
                str(section.get("deck") or ""),
                str(section.get("prose") or ""),
                str(section.get("pull_quote") or ""),
            ]
        )
        for chart_id in _chart_refs(section):
            if chart_id in rendered_charts:
                continue
            rendered_charts.add(chart_id)
            spec = chart_specs.get(chart_id)
            if spec:
                parts.append(str(spec.get("title") or ""))
            data_key = str(_dict(spec).get("data_key") or chart_id)
            parts.extend(_chart_observations(_dict(chart_data.get(chart_id) or chart_data.get(data_key))))
    return "\n".join(part for part in parts if part).strip()


def evaluate_final_artifact_quality(artifact: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    visible_text = final_visible_artifact_text(artifact)
    sections = _list(artifact.get("sections"))

    issues.extend(_internal_brief_issues(sections))
    issues.extend(_duplicate_section_issues(sections))
    issues.extend(_duplicate_chart_ref_issues(sections))

    placeholders = sorted(set(match.group(0) for match in PLACEHOLDER_PATTERN.finditer(visible_text)))
    if placeholders:
        issues.append(
            _issue(
                "placeholder_token",
                "最终可见文本包含占位符：" + ", ".join(placeholders),
            )
        )

    metadata = _dict(artifact.get("metadata"))
    if issues and (
        metadata.get("writer_pipeline_status") == "accepted"
        or _dict(metadata.get("taste_score")).get("ok") is True
        or metadata.get("critic_passed") is True
    ):
        issues.append(
            _issue(
                "misleading_quality_metadata",
                "最终可见文本未通过质量门禁，但 metadata 仍显示 accepted/critic/taste 通过。",
            )
        )

    return {
        "ok": not issues,
        "issues": issues,
        "visible_text_length": len(visible_text),
    }


def _internal_brief_issues(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for section in sections:
        text = "\n".join(str(section.get(key) or "") for key in ("heading", "deck", "prose"))
        for pattern in INTERNAL_BRIEF_PATTERNS:
            if pattern.search(text.strip()):
                issues.append(
                    _issue(
                        "internal_brief_leakage",
                        f"章节 {section.get('id') or section.get('heading') or 'unknown'} 泄漏内部 brief 语言。",
                    )
                )
                break
    return issues


def _duplicate_section_issues(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        prose = str(section.get("prose") or "")
        signature = _section_signature(prose)
        if not signature:
            continue
        previous = seen.get(signature)
        if previous:
            issues.append(
                _issue(
                    "duplicate_section_text",
                    f"章节 {previous} 与 {section_id} 的正文高度重复。",
                )
            )
        else:
            seen[signature] = section_id
    return issues


def _duplicate_chart_ref_issues(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    owner: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        for chart_id in _chart_refs(section):
            previous = owner.get(chart_id)
            if previous:
                issues.append(
                    _issue(
                        "duplicate_chart_ref",
                        f"图表 {chart_id} 同时被章节 {previous} 与 {section_id} 引用。",
                    )
                )
            else:
                owner[chart_id] = section_id
    return issues


def _section_signature(prose: str) -> str:
    text = re.sub(r"\s+", "", prose)
    if len(text) < 80:
        return ""
    return text[:180]


def _chart_refs(section: dict[str, Any]) -> list[str]:
    return [str(ref) for ref in section.get("chart_refs") or [] if str(ref).strip()]


def _chart_specs_by_id(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(spec.get("id")): spec
        for spec in _list(artifact.get("chart_specs"))
        if spec.get("id")
    }


def _chart_observations(data: dict[str, Any]) -> list[str]:
    observations = data.get("observations")
    if not isinstance(observations, list):
        return []
    return [str(item).strip() for item in observations if str(item).strip()]


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": "error"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]
```

- [ ] **Step 4: Run the new tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_final_artifact_quality.py -q
```

Expected: all tests pass.

---

### Task 2: Sanitize Backend Artifact Assembly Before Critic And Cache

**Files:**
- Modify: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Test: `backend/tests/unit/test_visual_yearly_artifact_service.py`

- [ ] **Step 1: Add failing service tests for purpose leaks and duplicate charts**

Append to `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
def test_editorial_article_purpose_is_not_rendered_as_user_deck(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc
    from backend.domains.ai_reports.editorial_agent.models import (
        ArticleDraft,
        ArticleSection,
        ClaimCheckResult,
        TasteScore,
    )

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [{"name": "Taylor Swift", "plays": 1115}, {"name": "Olivia Rodrigo", "plays": 769}],
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
    }
    article = ArticleDraft(
        title="2026 年中音乐年记",
        subtitle="截至 2026-06-23",
        thesis="Taylor Swift 的稳定回访、Olivia Rodrigo 的阶段变化和 Zhang Zhen Yue 的新声音共同构成年中主线。",
        sections=tuple(
            ArticleSection(
                id=section_id,
                heading=f"章节 {index}",
                purpose="展示Olivia Rodrigo在5月超越Taylor Swift的播放量，说明偏好会在特定月份发生转向。",
                prose=(
                    "Taylor Swift 以 1115 次播放位列艺人榜第一。"
                    "这让年度第一不只是一个名次，而是一条你持续回到的声音。"
                    if section_id == "stable_top_artist"
                    else "Zhang Zhen Yue 作为新发现信号表明年度记录持续引入新声音。"
                ),
                evidence_refs=("top_artist_taylor_swift",),
                chart_refs=("listening_calendar",),
            )
            for index, section_id in enumerate(
                (
                    "opening",
                    "stable_top_artist",
                    "monthly_turning_point",
                    "album_playback_billboard_alignment",
                    "highlight_day_density",
                    "discovery_signal",
                ),
                start=1,
            )
        ),
        closing="下半年继续看这些关系是否留下。",
    )
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: ([EvidenceLedgerEntry("yearly_overview", {"year": 2026}, "summary")], context),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True, "observations": ["活跃 174 天。"]} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "run_editorial_agent_pipeline",
        lambda context, *, chart_data, chat_fn=None, emit_stage=None: {
            "article": article,
            "claim_check": ClaimCheckResult((), (), (), (), ()),
            "taste_score": TasteScore(
                {
                    "文章感": 5,
                    "年度主题": 5,
                    "洞见密度": 5,
                    "个人化": 5,
                    "事实安全": 5,
                    "可读性": 5,
                    "图文融合": 5,
                },
                (),
            ),
            "metadata": {
                "writer_pipeline_version": "yearly_editorial_agent_v1",
                "claim_check_passed": True,
                "editorial_review_passed": True,
                "taste_score": {"ok": True, "total": 35, "dimensions": {}, "notes": []},
            },
        },
        raising=False,
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026, "writer_pipeline": "editorial_agent_v1"})
    decks = "\n".join(section["deck"] for section in result["artifact"]["sections"])
    chart_refs = [ref for section in result["artifact"]["sections"] for ref in section["chart_refs"]]

    assert "展示Olivia Rodrigo" not in decks
    assert "解释播放领先" not in decks
    assert len(chart_refs) == len(set(chart_refs))
    assert result["critic"]["ok"] is True
    assert result["metadata"]["final_artifact_quality_passed"] is True
```

- [ ] **Step 2: Run the targeted service test and confirm failure**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_service.py::test_editorial_article_purpose_is_not_rendered_as_user_deck -q
```

Expected: fail because decks include `section.purpose` and chart refs repeat.

- [ ] **Step 3: Import final quality gate**

In `backend/domains/ai_reports/visual_yearly_artifact_service.py`, add:

```python
from backend.domains.ai_reports.final_artifact_quality import evaluate_final_artifact_quality
```

- [ ] **Step 4: Replace purpose-as-deck with user-facing deck copy**

In `_sections_from_editorial_article`, replace:

```python
deck = _clean_user_text(article.thesis if index == 0 else section.purpose, context)
```

with:

```python
deck = _editorial_section_deck(article, section, index, context)
```

Add this helper near `_sections_from_editorial_article`:

```python
def _editorial_section_deck(
    article: ArticleDraft,
    section: ArticleSection,
    index: int,
    context: dict[str, Any],
) -> str:
    if index == 0:
        return _clean_user_text(article.thesis, context)
    prose_sentence = _first_sentence(section.prose)
    if prose_sentence:
        return _clean_user_text(prose_sentence, context)
    role = _role_for_editorial_section(section.id, index)
    return _clean_user_text(_deck_for_role(role, context), context)


def _deck_for_role(role: str, context: dict[str, Any]) -> str:
    if role == "turning_point":
        return "累计排名之外，也有某个月突然变亮的声音。"
    if role == "album_story":
        return "播放热度和个人 Billboard 长留需要放在一起读。"
    if role == "highlight_day":
        day = _dict(context.get("highlight_day_detail"))
        date = str(day.get("date") or "高光日")
        return f"{date} 更适合被看作播放密度升高的一天。"
    if role == "discovery":
        return "新出现的名字让年度画像不只停在旧偏好里。"
    if role == "closing":
        return "把前面的线索收束成一份可回看的音乐年记。"
    return "这一节继续解释播放记录里出现的年度关系。"
```

- [ ] **Step 5: Deduplicate section text and chart refs before building artifact**

Add helpers near `_sections_from_editorial_article`:

```python
def _dedupe_editorial_sections(sections: tuple[_Section, ...]) -> tuple[_Section, ...]:
    seen_signatures: set[str] = set()
    result: list[_Section] = []
    for section in sections:
        signature = _section_text_signature(section.prose)
        if signature and signature in seen_signatures:
            continue
        if signature:
            seen_signatures.add(signature)
        result.append(section)
    return tuple(result)


def _section_text_signature(text: str) -> str:
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < 80:
        return ""
    return compact[:180]


def _dedupe_chart_refs_across_sections(sections: tuple[_Section, ...]) -> tuple[_Section, ...]:
    rendered: set[str] = set()
    result: list[_Section] = []
    for section in sections:
        chart_refs: list[str] = []
        for chart_ref in section.chart_refs:
            if chart_ref in rendered:
                continue
            rendered.add(chart_ref)
            chart_refs.append(chart_ref)
        result.append(
            _Section(
                id=section.id,
                role=section.role,
                heading=section.heading,
                deck=section.deck,
                prose=section.prose,
                chart_refs=tuple(chart_refs),
                insight_refs=section.insight_refs,
                evidence_refs=section.evidence_refs,
                pull_quote=section.pull_quote,
            )
        )
    return tuple(result)
```

After:

```python
sections = _ensure_minimum_editorial_prose(sections, context)
```

add:

```python
sections = _dedupe_editorial_sections(sections)
sections = _dedupe_chart_refs_across_sections(sections)
```

- [ ] **Step 6: Merge final quality into critic metadata**

After `fact_validation = _validate_visual_fact_safety(prose, artifact, context)`, add:

```python
    final_quality = evaluate_final_artifact_quality(artifact)
    if not final_quality["ok"]:
        critic = {
            **critic,
            "ok": False,
            "issues": [*_list(critic.get("issues")), *final_quality["issues"]],
            "repair_instructions": [
                *_list(critic.get("repair_instructions")),
                "修复最终可见 artifact 文本后再缓存报告。",
            ],
        }
```

In metadata, add:

```python
"final_artifact_quality_passed": bool(final_quality["ok"]),
"final_artifact_quality": final_quality,
```

Set fallback level with final gate:

```python
"fallback_level": None if critic["ok"] and final_quality["ok"] else "final_quality_gate_failed",
```

Use `_list` only for lists of dicts in this file. If `_list(critic.get("repair_instructions"))` is not appropriate because `_list` filters dicts, add:

```python
def _str_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if str(item).strip()]
```

and use `_str_list(critic.get("repair_instructions"))`.

- [ ] **Step 7: Run targeted tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_final_artifact_quality.py backend/tests/unit/test_visual_yearly_artifact_service.py::test_editorial_article_purpose_is_not_rendered_as_user_deck -q
```

Expected: all tests pass.

---

### Task 3: Expand Visual Critic To Judge Decks And Final Text

**Files:**
- Modify: `backend/domains/ai_reports/visual_yearly_critic.py`
- Test: `backend/tests/unit/test_visual_yearly_critic.py`

- [ ] **Step 1: Add failing critic test for deck leakage**

Append to `backend/tests/unit/test_visual_yearly_critic.py`:

```python
def test_visual_critic_rejects_internal_guidance_in_deck():
    prose = (
        "Taylor Swift 是你反复回到的陪伴声音。"
        "JOLIN 是新发现，播放量和个人榜单关系也留在日常节奏里。"
    ) * 30
    artifact = _artifact(prose)
    artifact["sections"][1]["deck"] = "展示Olivia Rodrigo在5月超越Taylor Swift的播放量，说明偏好会在特定月份发生转向。"

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any(issue["code"] == "internal_guidance_leakage" for issue in result["issues"])
```

- [ ] **Step 2: Run the test and confirm failure**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py::test_visual_critic_rejects_internal_guidance_in_deck -q
```

Expected: fail because `_all_prose()` only reads `section.prose`.

- [ ] **Step 3: Include visible section text in critic**

In `backend/domains/ai_reports/visual_yearly_critic.py`, replace:

```python
def _all_prose(artifact: dict[str, Any]) -> str:
    return "\n".join(str(section.get("prose") or "") for section in _list(artifact.get("sections")))
```

with:

```python
def _all_prose(artifact: dict[str, Any]) -> str:
    parts: list[str] = []
    for section in _list(artifact.get("sections")):
        parts.extend(
            [
                str(section.get("heading") or ""),
                str(section.get("deck") or ""),
                str(section.get("prose") or ""),
                str(section.get("pull_quote") or ""),
            ]
        )
    chart_data = _dict(artifact.get("chart_data"))
    for payload in chart_data.values():
        observations = _dict(payload).get("observations")
        if isinstance(observations, list):
            parts.extend(str(item) for item in observations if str(item).strip())
    return "\n".join(part for part in parts if part)
```

- [ ] **Step 4: Strengthen internal guidance terms**

Extend `INTERNAL_GUIDANCE_TERMS` with the visible leak patterns:

```python
INTERNAL_GUIDANCE_TERMS = (
    "证据强度",
    "不要写成",
    "interpretation_guidance",
    "safe_speculation_rules",
    "展示Olivia",
    "展示播放",
    "解释播放领先",
    "揭示偏好深度",
    "说明偏好会在特定月份",
)
```

- [ ] **Step 5: Run critic tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: all tests pass.

---

### Task 4: Frontend Renderer Dedup And Chart Copy Cleanup

**Files:**
- Modify: `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
- Modify: `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
- Test: `frontend/src/tests/visual-yearly-report.test.tsx`

- [ ] **Step 1: Add failing frontend tests**

Append to `frontend/src/tests/visual-yearly-report.test.tsx` inside `describe('VisualYearlyReport', () => { ... })`:

```tsx
  it('renders each chart only once even when multiple sections reference it', () => {
    const value = artifact()
    value.sections = [
      {
        ...value.sections[0],
        id: 'opening',
        heading: '开篇',
        chart_refs: ['listening_calendar'],
      },
      {
        ...value.sections[0],
        id: 'stable_return',
        heading: '稳定回访',
        chart_refs: ['listening_calendar'],
      },
    ]

    render(<VisualYearlyReport artifact={value} />)

    expect(screen.getAllByText('音乐铺满这一年')).toHaveLength(1)
  })

  it('does not render chart spec insight as user-facing copy', () => {
    const value = artifact()
    value.chart_specs[0].insight = '展示播放密度并解释当前统计期的陪伴关系。'
    value.chart_data.listening_calendar = {
      days: [],
      active_days: 364,
      observations: ['活跃 364 天，说明音乐几乎每天都在场。'],
    }

    render(<VisualYearlyReport artifact={value} />)

    expect(screen.queryByText('展示播放密度并解释当前统计期的陪伴关系。')).not.toBeInTheDocument()
    expect(screen.getByText('活跃 364 天，说明音乐几乎每天都在场。')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Run frontend targeted tests and confirm failure**

Run:

```bash
cd frontend && npm test -- visual-yearly-report.test.tsx
```

Expected: the duplicate chart or chart insight test fails.

- [ ] **Step 3: Deduplicate chart refs in VisualYearlyReport**

Replace `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx` with:

```tsx
import { useMemo } from 'react'

import { YearlyHero } from './YearlyHero'
import { YearlyInsightCards } from './YearlyInsightCards'
import { YearlySection } from './YearlySection'
import type { VisualYearlyArtifact } from './yearlyArtifactTypes'

function sectionsWithUniqueChartRefs(artifact: VisualYearlyArtifact) {
  const rendered = new Set<string>()
  const available = new Set(artifact.chart_specs.map((spec) => spec.id))

  return artifact.sections.map((section) => ({
    ...section,
    chart_refs: section.chart_refs.filter((chartId) => {
      if (!available.has(chartId)) return false
      if (rendered.has(chartId)) return false
      rendered.add(chartId)
      return true
    }),
  }))
}

export function VisualYearlyReport({ artifact }: { artifact: VisualYearlyArtifact }) {
  const sections = useMemo(() => sectionsWithUniqueChartRefs(artifact), [artifact])

  return (
    <article className="min-w-0 space-y-8 text-foreground">
      <YearlyHero artifact={artifact} />
      <YearlyInsightCards cards={artifact.insight_cards} />
      {sections.map((section) => (
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

- [ ] **Step 4: Stop rendering internal chart spec insight**

In `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`, remove:

```tsx
  const insight = cleanText(spec.insight)
```

and remove:

```tsx
        {insight && <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{insight}</p>}
```

Keep `fallback` for missing chart data and keep deterministic observations from `chart_data`.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm test -- visual-yearly-report.test.tsx
```

Expected: all tests pass.

---

### Task 5: Report Type Switch State Guard

**Files:**
- Modify: `frontend/src/features/ai-insights/AiReportsPanel.tsx`
- Test: `frontend/src/tests/ai-insights-task-flow.test.tsx`

- [ ] **Step 1: Add failing UI flow test for yearly switch payload and stale content**

Append to `frontend/src/tests/ai-insights-task-flow.test.tsx` inside `describe('AiInsightsExperience report task flow', () => { ... })`:

```tsx
  it('switches to yearly reports without keeping weekly copy or payload', async () => {
    const client = createClient()
    mockCommonGet()
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path !== '/ai/tasks/report') {
        return Promise.reject(new Error(`unexpected POST ${path}`))
      }
      const payload = body as { action?: string; report_type?: string; year?: number }
      if (payload.action === 'cache_only' && payload.report_type === 'weekly') {
        return Promise.resolve({
          task_id: 'task-weekly-cache',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '缓存检查完成',
          result: {
            cached: true,
            report: '缓存命中的周报',
            cached_at: '2026-06-28T00:00:00',
            entities: { artists: [], tracks: [] },
            needs_generation: false,
          },
        })
      }
      if (payload.action === 'cache_only' && payload.report_type === 'yearly') {
        return Promise.resolve({
          task_id: 'task-yearly-cache',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '缓存检查完成',
          result: {
            cached: false,
            report: null,
            cached_at: null,
            entities: null,
            needs_generation: true,
          },
        })
      }
      if (payload.action === 'generate' && payload.report_type === 'yearly') {
        return Promise.resolve({
          task_id: 'task-generate',
          status: 'queued',
          stage: 'checking_cache',
          progress_pct: 0,
          message: '准备生成 AI 报告',
          result: null,
        })
      }
      return Promise.reject(new Error(`unexpected payload ${JSON.stringify(payload)}`))
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    expect(await screen.findByText('缓存命中的周报')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '年度叙事' }))

    expect(await screen.findByText('将年度听歌总结转化为音乐故事')).toBeInTheDocument()
    await waitFor(() => {
      expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', expect.objectContaining({
        report_type: 'yearly',
        action: 'cache_only',
        report_mode: 'visual_yearly_artifact',
        writer_pipeline: 'editorial_agent_v1',
        year: 2026,
      }))
    })
    expect(screen.queryByText('缓存命中的周报')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '生成报告' }))

    await waitFor(() => {
      expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', expect.objectContaining({
        report_type: 'yearly',
        action: 'generate',
        force: true,
        report_mode: 'visual_yearly_artifact',
        writer_pipeline: 'editorial_agent_v1',
        year: 2026,
      }))
    })
  })
```

- [ ] **Step 2: Run the targeted UI test**

Run:

```bash
cd frontend && npm test -- ai-insights-task-flow.test.tsx
```

Expected: the new test fails if weekly content remains visible or yearly payload is not sent.

- [ ] **Step 3: Clear stale task state on report type switch**

In `frontend/src/features/ai-insights/AiReportsPanel.tsx`, add:

```tsx
  const handleReportTypeChange = (type: ReportType) => {
    if (type === reportType) return
    reportPayloadKeyRef.current = null
    setActiveReportTaskId(null)
    setCurrentReportTask(null)
    setReportType(type)
  }
```

Replace:

```tsx
onClick={() => setReportType(type)}
```

with:

```tsx
onClick={() => handleReportTypeChange(type)}
aria-pressed={reportType === type}
```

- [ ] **Step 4: Run UI flow tests**

Run:

```bash
cd frontend && npm test -- ai-insights-task-flow.test.tsx
```

Expected: all tests pass.

---

### Task 6: Probe The Same Final Visible Text The User Sees

**Files:**
- Modify: `scripts/probe_visual_yearly_report_artifact.py`
- Test: `backend/tests/unit/test_visual_yearly_critic.py`

- [ ] **Step 1: Add failing probe test for deck leak and duplicate chart refs**

Append to `backend/tests/unit/test_visual_yearly_critic.py`:

```python
def test_visual_probe_rejects_final_visible_deck_leak_and_duplicate_chart_refs():
    prose = (
        "Taylor Swift 是你反复回到的陪伴声音。"
        "Zhang Zhen Yue 是新发现，播放量和个人榜单关系也留在日常节奏里。"
    ) * 30
    artifact = _probe_artifact(prose)
    artifact["sections"][0]["deck"] = "展示Olivia Rodrigo在5月超越Taylor Swift的播放量。"
    artifact["sections"][1]["chart_refs"] = ["artist_monthly_trend"]
    result = _probe_result(artifact)
    probe_text = visual_probe._artifact_text(result, artifact, artifact["sections"])

    issues = visual_probe._validate(
        year=2026,
        detail={"status": "done"},
        result=result,
        artifact=artifact,
        metadata=result["metadata"],
        sections=artifact["sections"],
        chart_specs=artifact["chart_specs"],
        chart_data=artifact["chart_data"],
        prose=probe_text,
        writer_pipeline="editorial_agent_v1",
    )

    assert any("internal brief leakage" in issue for issue in issues)
    assert any("duplicate chart refs" in issue for issue in issues)
```

- [ ] **Step 2: Run the failing probe test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py::test_visual_probe_rejects_final_visible_deck_leak_and_duplicate_chart_refs -q
```

Expected: fail because the probe does not yet check these final visible defects.

- [ ] **Step 3: Add final-visible checks to probe script**

In `scripts/probe_visual_yearly_report_artifact.py`, add constants near `INTERPRETATION_MARKERS`:

```python
INTERNAL_BRIEF_LEAK_PATTERNS = (
    re.compile(r"^(展示|解释|说明|分析|揭示).{0,80}(播放量|个人榜单|偏好|关系|证据|趋势)"),
    re.compile(r"(interpretation_guidance|safe_speculation_rules|evidence_refs|chart_refs)"),
)
```

Add helper functions before `_dict`:

```python
def _internal_brief_leaks(sections: list[dict[str, Any]]) -> list[str]:
    leaks: list[str] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        visible = _section_body_text(section)
        if any(pattern.search(visible.strip()) for pattern in INTERNAL_BRIEF_LEAK_PATTERNS):
            leaks.append(section_id)
    return leaks


def _duplicate_chart_refs(sections: list[dict[str, Any]]) -> list[str]:
    owner: dict[str, str] = {}
    duplicates: list[str] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        for ref in section.get("chart_refs") or []:
            chart_id = str(ref)
            previous = owner.get(chart_id)
            if previous:
                duplicates.append(f"{chart_id}: {previous}, {section_id}")
            else:
                owner[chart_id] = section_id
    return duplicates
```

In `_validate`, after placeholder checks, add:

```python
    internal_brief_leaks = _internal_brief_leaks(sections)
    if internal_brief_leaks:
        issues.append("internal brief leakage in sections: " + ", ".join(internal_brief_leaks))
    duplicate_chart_refs = _duplicate_chart_refs(sections)
    if duplicate_chart_refs:
        issues.append("duplicate chart refs: " + ", ".join(duplicate_chart_refs))
    final_quality = _dict(metadata.get("final_artifact_quality"))
    if metadata.get("final_artifact_quality_passed") is not True:
        issues.append("metadata final_artifact_quality_passed is not true")
    if final_quality and final_quality.get("ok") is not True:
        issues.append("metadata final_artifact_quality.ok is not true")
```

In `_quality_checks`, include:

```python
        "internal_brief_leaks": _internal_brief_leaks(sections),
        "duplicate_chart_refs": _duplicate_chart_refs(sections),
```

- [ ] **Step 4: Run probe tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: all tests pass.

---

### Task 7: Verification Matrix And Browser Acceptance

**Files:**
- No code changes unless failures point to a previous task.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
.venv/bin/pytest \
  backend/tests/unit/test_final_artifact_quality.py \
  backend/tests/unit/test_visual_yearly_artifact_service.py \
  backend/tests/unit/test_visual_yearly_critic.py \
  backend/tests/contract/test_visual_yearly_report_contract.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend targeted tests**

Run:

```bash
cd frontend && npm test -- visual-yearly-report.test.tsx ai-insights-task-flow.test.tsx
```

Expected: all tests pass.

- [ ] **Step 3: Run lint/build checks**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports scripts/probe_visual_yearly_report_artifact.py backend/tests/unit/test_final_artifact_quality.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_critic.py
.venv/bin/ruff format --check backend/domains/ai_reports scripts/probe_visual_yearly_report_artifact.py backend/tests/unit/test_final_artifact_quality.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_critic.py
cd frontend && npm run build
```

Expected: all commands pass.

- [ ] **Step 4: Run changed yearly artifact probe**

With backend running on port 8000:

```bash
.venv/bin/python scripts/probe_visual_yearly_report_artifact.py \
  --mode changed \
  --writer-pipeline editorial_agent_v1 \
  --json-output /tmp/visual_yearly_artifact_quality_gate.json
```

Expected:

- Exit code `0`.
- JSON `ok` is `true`.
- 2025 and 2026 summaries contain `metadata.final_artifact_quality_passed: true`.
- No issue contains `internal brief leakage`.
- No issue contains `duplicate chart refs`.

- [ ] **Step 5: Browser acceptance for actual user flow**

Use the in-app browser or Playwright to execute:

1. Open `http://localhost:5173/ai-insights`.
2. Click `报告`.
3. Click `年度叙事`.
4. Click `2026`.
5. Click `刷新报告`.
6. Wait until the task progress disappears and the report card shows `刷新报告`.
7. Confirm the card title is `年度叙事 · 2026`.
8. Confirm badges do not show `口味评分 35` unless `final_artifact_quality_passed` is true.
9. Confirm visible text does not contain:
   - `展示Olivia`
   - `解释播放领先`
   - `揭示偏好深度`
   - `interpretation_guidance`
   - `safe_speculation_rules`
10. Confirm each visible chart title appears at most once.
11. Confirm `Taylor Swift 以 1115 次播放位列艺人榜第一` or equivalent stable-return paragraph appears at most once as a full paragraph.

Expected: pass all checks, no console errors, no fallback composer badge, and no weekly report content after switching to yearly.

---

## Self-Review

**Spec coverage:**

- Final visible text gate: Task 1 and Task 2.
- Internal brief leakage: Task 1, Task 2, Task 3, Task 6.
- Duplicate sections and duplicate chart refs: Task 1, Task 2, Task 4, Task 6.
- Frontend chart insight leakage: Task 4.
- Report type switch stale state: Task 5.
- Probe catches what browser catches: Task 6 and Task 7.

**Placeholder scan:** This plan contains no unresolved placeholder markers, no open-ended validation instructions, and no cross-task shorthand implementation steps.

**Type consistency:** The backend quality helper returns a dict with `ok`, `issues`, and `visible_text_length`; service metadata stores `final_artifact_quality_passed` and `final_artifact_quality`; probe reads the same keys.

**Commit guidance:** Do not commit automatically while executing this plan unless the user explicitly asks. After all verification passes, summarize modified files and test evidence first.
