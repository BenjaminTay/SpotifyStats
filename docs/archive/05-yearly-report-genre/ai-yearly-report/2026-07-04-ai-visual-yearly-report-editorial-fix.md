# AI Visual Yearly Report Editorial Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 2026 visual yearly report so it reads like a personal music-year article with specific, data-grounded insight instead of repeated template prose, internal instruction leakage, and incorrect data interpretations.

**Architecture:** Keep the existing `visual_yearly_artifact` pipeline, chart data builder, frontend renderer, and task/cache integration. Add a deterministic `Story Insight Builder` between evidence/narrative brief and section prose composition, then make the section writer consume structured insight modes such as aligned/divergent/missing. Upgrade the visual critic and probe so internal leakage, repeated meta prose, same-entity false contrast, and unsupported genre/artist claims are rejected before a report is accepted.

**Tech Stack:** FastAPI service layer, `backend/domains/ai_reports`, pytest unit/contract tests, `scripts/probe_visual_yearly_report_artifact.py`, React/Vitest smoke only for unchanged renderer regressions, Chrome CDP browser acceptance for `/ai-insights`.

---

## Source Evidence

Observed 2026 generated report problems:

- Repeated meta paragraph appears in almost every section: “图表负责回答……正文负责回答……”.
- Internal guidance leaks into user text: “证据强度可以先放在 high”, “不要写成重度单曲循环”.
- Album section writes false contrast when playback-leading album and personal-chart-leading album are the same: “The Life of a Showgirl 和 The Life of a Showgirl 说明了两种不同的喜欢”.
- Second-thread section hardcodes “华语、回望和现场感” for Olivia Rodrigo, which is unsupported by the artist and genre evidence.
- Visual critic passes the report despite those issues.

Root causes in current code:

- `backend/domains/ai_reports/visual_yearly_artifact_service.py` uses `_warm_extension()` for every section, causing repeated generic prose.
- `_long_discovery()` writes raw confidence labels into user prose.
- `_long_highlight()` writes raw `interpretation_guidance` into user prose.
- `_long_album_story()` assumes playback leader and chart leader are always different.
- `backend/domains/ai_reports/narrative_brief.py` hardcodes second-thread interpretation as “华语、记忆感或现场感”.
- `backend/domains/ai_reports/visual_yearly_critic.py` checks length and broad obligations but not internal leakage, repetition, or data-relationship contradictions.

## Scope

In scope:

- Add deterministic story insight classification for album relation, second-thread relation, highlight-day interpretation, discovery framing, and closing direction.
- Rewrite backend section prose generation to consume those insights.
- Upgrade critic and probe checks.
- Add tests that reproduce the exact 2026 failure modes.
- Re-run backend, probe, and browser acceptance.

Out of scope:

- New chart types.
- PDF/export/share features.
- Full LLM rewrite pipeline.
- Frontend visual redesign beyond verifying rendered text and existing chart blocks.

## File Map

### Backend Create

- `backend/domains/ai_reports/story_insight_builder.py`
  - Converts context + narrative brief into section-level insight objects.
  - Produces normalized modes:
    - `album_relation.mode`: `aligned`, `divergent`, `playback_only`, `chart_only`, `missing`
    - `second_thread.mode`: `same_language_family`, `genre_contrast`, `artist_contrast`, `fallback`
    - `highlight_day.mode`: `multi_track_dense_day`, `repeat_day`, `low_confidence`
    - `discovery.mode`: `strong_new_thread`, `emerging_signal`, `small_signal`
  - Sanitizes internal evidence labels into user-safe wording.

- `backend/tests/unit/test_story_insight_builder.py`
  - Locks the exact relationship classifications that the section writer depends on.

### Backend Modify

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Import and call `build_story_insights(context, narrative)`.
  - Replace `_warm_extension()` with section-specific prose.
  - Rewrite `_long_album_story()`, `_long_second_thread()`, `_long_highlight()`, `_long_discovery()`, and `_long_closing()` to consume insights.
  - Keep output schema unchanged: `artifact.sections[*].prose`, `chart_refs`, `insight_refs`.

- `backend/domains/ai_reports/narrative_brief.py`
  - Remove hardcoded “华语、记忆感或现场感” from second-thread interpretation.
  - Keep narrative brief factual and minimal; detailed interpretation moves to `story_insight_builder.py`.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Add hard blockers for internal instruction leakage.
  - Add repeated sentence / repeated meta-prose detection.
  - Add same-entity false contrast detection.
  - Add context-aware album relationship checks when `context` is provided.

- `scripts/probe_visual_yearly_report_artifact.py`
  - Add golden checks for the 2026 editorial failures.
  - Ensure probe fails if internal terms or repeated meta prose appear.

- `docs/CHANGELOG.md`
  - Add a short implementation summary and actual verification commands after execution.

## Implementation Tasks

### Task 1: Add Story Insight Builder

**Files:**
- Create: `backend/domains/ai_reports/story_insight_builder.py`
- Create: `backend/tests/unit/test_story_insight_builder.py`

- [ ] **Step 1: Write failing tests for album relation modes**

Create `backend/tests/unit/test_story_insight_builder.py` with:

```python
from __future__ import annotations

import pytest

from backend.domains.ai_reports.story_insight_builder import build_story_insights

pytestmark = pytest.mark.unit


def test_story_insights_marks_album_relation_aligned_when_leaders_match():
    context = {
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "The Life of a Showgirl",
                    "artist": "Taylor Swift",
                    "rank": 1,
                    "weeks_on_chart": 24,
                }
            ]
        },
    }

    insights = build_story_insights(context, {})

    album = insights["album_relation"]
    assert album["mode"] == "aligned"
    assert album["playback_leader"] == "The Life of a Showgirl"
    assert album["chart_leader"] == "The Life of a Showgirl"
    assert "重合" in album["claim"]
    assert "两种不同的喜欢" not in album["interpretation"]


def test_story_insights_marks_album_relation_divergent_when_leaders_differ():
    context = {
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "rank": 1,
                    "weeks_on_chart": 32,
                }
            ]
        },
    }

    insights = build_story_insights(context, {})

    album = insights["album_relation"]
    assert album["mode"] == "divergent"
    assert album["playback_leader"] == "The Life of a Showgirl"
    assert album["chart_leader"] == "光良「回憶裡的瘋狂」巡迴演唱會"
    assert "不完全相同" in album["claim"]
```

- [ ] **Step 2: Write failing tests for second-thread and sanitized guidance**

Append to `backend/tests/unit/test_story_insight_builder.py`:

```python
def test_story_insights_does_not_force_chinese_language_claim_for_english_artist():
    context = {
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "genre_distribution": {
            "top_genres": [
                {"name": "mandopop", "share": 14.4},
                {"name": "c-pop", "share": 14.4},
            ]
        },
    }

    insights = build_story_insights(context, {})

    second = insights["second_thread"]
    assert second["entity"] == "Olivia Rodrigo"
    assert "华语" not in second["interpretation"]
    assert "现场感" not in second["interpretation"]


def test_story_insights_sanitizes_highlight_guidance_and_discovery_confidence():
    context = {
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}]
        },
    }
    narrative = {"discovery_thread": {"entity": "Zhang Zhen Yue", "confidence": "high"}}

    insights = build_story_insights(context, narrative)

    assert insights["highlight_day"]["mode"] == "multi_track_dense_day"
    assert "不要写成" not in insights["highlight_day"]["interpretation"]
    assert "重度单曲循环" not in insights["highlight_day"]["interpretation"]
    assert insights["discovery"]["mode"] == "strong_new_thread"
    assert "high" not in insights["discovery"]["interpretation"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_story_insight_builder.py -q
```

Expected: fail because `backend.domains.ai_reports.story_insight_builder` does not exist.

- [ ] **Step 4: Implement story insight builder**

Create `backend/domains/ai_reports/story_insight_builder.py`:

```python
"""Section-level insight builder for visual yearly reports."""

from __future__ import annotations

from typing import Any


def build_story_insights(context: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    return {
        "album_relation": _album_relation(context),
        "second_thread": _second_thread(context),
        "highlight_day": _highlight_day(context),
        "discovery": _discovery(context, narrative),
        "closing": _closing(context),
    }


def _album_relation(context: dict[str, Any]) -> dict[str, Any]:
    playback_row = _first(_list(context.get("top_albums")))
    chart_row = _first(_list(_dict(context.get("personal_billboard_year_end")).get("albums")))
    playback = _name(playback_row)
    chart = _name(chart_row)
    if not playback and not chart:
        return {
            "mode": "missing",
            "playback_leader": "",
            "chart_leader": "",
            "claim": "专辑偏好证据还不够完整",
            "interpretation": "这一段不适合强行比较专辑。",
        }
    if playback and not chart:
        return {
            "mode": "playback_only",
            "playback_leader": playback,
            "chart_leader": "",
            "claim": f"{playback} 是播放侧最清晰的专辑",
            "interpretation": "目前只能从播放次数判断它的热度，不能补写个人榜单结论。",
        }
    if chart and not playback:
        return {
            "mode": "chart_only",
            "playback_leader": "",
            "chart_leader": chart,
            "claim": f"{chart} 是个人榜单里更稳定留下的专辑",
            "interpretation": "目前只能从个人榜单侧说明它的持续性。",
        }
    if _same_name(playback, chart):
        weeks = chart_row.get("weeks_on_chart")
        week_text = f"，并在个人榜单里停留 {int(weeks)} 周" if isinstance(weeks, (int, float)) else ""
        return {
            "mode": "aligned",
            "playback_leader": playback,
            "chart_leader": chart,
            "claim": f"{playback} 同时站在播放量和个人榜单前列",
            "interpretation": f"这不是两种偏爱的分裂，而是热度与长留在同一张专辑上重合{week_text}。",
        }
    return {
        "mode": "divergent",
        "playback_leader": playback,
        "chart_leader": chart,
        "claim": f"{playback} 和 {chart} 不完全相同",
        "interpretation": "播放量更像短期高频回到，个人榜单更强调跨周持续和排名稳定。",
    }


def _second_thread(context: dict[str, Any]) -> dict[str, Any]:
    top_artists = _list(context.get("top_artists"))
    second = _name(_at(top_artists, 1))
    lead = _name(_at(top_artists, 0))
    genres = [
        str(row.get("name") or "")
        for row in _list(_dict(context.get("genre_distribution")).get("top_genres"))[:5]
        if row.get("name")
    ]
    lower_genres = " ".join(genres).lower()
    if not second:
        return {
            "mode": "fallback",
            "entity": "",
            "claim": "第二条声音线还不明显",
            "interpretation": "这一年更适合围绕主线艺人展开。",
        }
    if _looks_chinese_context(second, lower_genres):
        return {
            "mode": "same_language_family",
            "entity": second,
            "claim": f"{second} 打开了另一条华语语境",
            "interpretation": "这条线索可以和流派/语种数据一起解释，但仍要避免把标签当作互斥分类。",
        }
    if lead:
        return {
            "mode": "artist_contrast",
            "entity": second,
            "claim": f"{second} 提供了不同于 {lead} 的另一种情绪重心",
            "interpretation": "这里可以写成年度画像里的第二条声音线，但不应强行绑定华语或现场感。",
        }
    return {
        "mode": "fallback",
        "entity": second,
        "claim": f"{second} 是另一条值得保留的声音线",
        "interpretation": "它扩展了年度画像，但现有证据不足以继续外推具体生活场景。",
    }


def _highlight_day(context: dict[str, Any]) -> dict[str, Any]:
    highlight = _dict(context.get("highlight_day_detail"))
    date = str(highlight.get("date") or "")
    plays = int(highlight.get("plays") or 0)
    raw_guidance = str(highlight.get("interpretation_guidance") or "")
    if "不高" in raw_guidance or "不要写成" in raw_guidance:
        mode = "multi_track_dense_day"
        interpretation = "这一天更像许多歌曲密集经过，而不是某一首歌支配整天。"
    elif "循环" in raw_guidance:
        mode = "repeat_day"
        interpretation = "这一天有更明显的重复播放特征，可以谨慎写成单曲回到。"
    else:
        mode = "low_confidence"
        interpretation = "这一天的播放密度值得记录，但不适合推断具体生活事件。"
    return {
        "mode": mode,
        "date": date,
        "plays": plays,
        "claim": f"{date} 是播放最密集的一天" if date else "这一年有一个播放密度很高的日子",
        "interpretation": interpretation,
    }


def _discovery(context: dict[str, Any], narrative: dict[str, Any]) -> dict[str, Any]:
    rows = _list(_dict(context.get("discovery_and_returns")).get("new_artists"))
    first = _first(rows)
    name = _name(first) or str(_dict(narrative.get("discovery_thread")).get("entity") or "")
    plays = int(first.get("plays") or 0) if first else 0
    first_date = str(first.get("first_date") or "")
    if plays >= 300:
        mode = "strong_new_thread"
        interpretation = f"{name} 已经不只是一次尝鲜，而是在这一年形成了清晰的新支线。"
    elif plays >= 80:
        mode = "emerging_signal"
        interpretation = f"{name} 是值得继续观察的新入口，已经留下可见播放痕迹。"
    else:
        mode = "small_signal"
        interpretation = f"{name} 更像一个刚出现的信号，还不适合写成年度主角。"
    return {
        "mode": mode,
        "entity": name,
        "plays": plays,
        "first_date": first_date,
        "claim": f"{name} 是这一年出现的新声音" if name else "这一年的新发现还不够清晰",
        "interpretation": interpretation if name else "新发现证据不足时，章节应降级为简短观察。",
    }


def _closing(context: dict[str, Any]) -> dict[str, Any]:
    period = _dict(context.get("reporting_period"))
    if period.get("is_partial_year"):
        return {
            "mode": "partial_year",
            "claim": "这还是一份阶段性年记",
            "interpretation": "更适合写成下半年观察，而不是完整年度定论。",
        }
    return {
        "mode": "full_year",
        "claim": "这一年已经形成完整轮廓",
        "interpretation": "可以收束为陪伴、回到和新入口并存的年度画像。",
    }


def _same_name(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def _looks_chinese_context(artist: str, lower_genres: str) -> bool:
    if any("\u4e00" <= char <= "\u9fff" for char in artist):
        return True
    return any(term in lower_genres for term in ("mandopop", "c-pop", "taiwanese", "cantopop"))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _at(rows: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return rows[index] if index < len(rows) else {}


def _name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "")
```

- [ ] **Step 5: Run story insight tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_story_insight_builder.py -q
```

Expected: all tests pass.

### Task 2: Rewrite Section Prose To Consume Insights

**Files:**
- Modify: `backend/domains/ai_reports/visual_yearly_artifact_service.py`
- Modify: `backend/domains/ai_reports/narrative_brief.py`
- Modify: `backend/tests/unit/test_visual_yearly_artifact_service.py`

- [ ] **Step 1: Add failing service tests for the 2026 editorial failures**

Append to `backend/tests/unit/test_visual_yearly_artifact_service.py`:

```python
def test_visual_yearly_artifact_does_not_leak_internal_guidance_for_2026(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as module

    context = _visual_context_2026_same_album()
    monkeypatch.setattr(module, "run_visual_report_research", lambda request, emit_event=None: context)

    result = module.generate_visual_yearly_artifact({"report_type": "yearly", "year": 2026})

    report = result["report"]
    assert result["success"] is True
    assert "证据强度" not in report
    assert "high" not in report
    assert "不要写成" not in report
    assert "重度单曲循环" not in report
    assert "图表负责回答" not in report
    assert "The Life of a Showgirl 和 The Life of a Showgirl" not in report
    assert "热度与长留" in report or "同一张专辑" in report


def test_visual_yearly_artifact_second_thread_does_not_force_wrong_genre_claim(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as module

    context = _visual_context_2026_same_album()
    monkeypatch.setattr(module, "run_visual_report_research", lambda request, emit_event=None: context)

    result = module.generate_visual_yearly_artifact({"report_type": "yearly", "year": 2026})

    second = next(section for section in result["artifact"]["sections"] if section["id"] == "second_thread")
    assert "Olivia Rodrigo" in second["prose"]
    assert "华语" not in second["prose"]
    assert "现场感" not in second["prose"]


def _visual_context_2026_same_album():
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
            {"name": "Zhang Zhen Yue", "plays": 574},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "artist": "Taylor Swift", "rank": 1, "weeks_on_chart": 19, "peak_position": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {
            "top_genres": [
                {"name": "mandopop", "share": 14.4},
                {"name": "c-pop", "share": 14.4},
                {"name": "taiwanese pop", "share": 13.1},
            ],
            "caveat": "Spotify 流派标签可能重叠，百分比不互斥。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
        "request_filters": {
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 10,
        },
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_does_not_leak_internal_guidance_for_2026 backend/tests/unit/test_visual_yearly_artifact_service.py::test_visual_yearly_artifact_second_thread_does_not_force_wrong_genre_claim -q
```

Expected: fail with current repeated template/internal leakage.

- [ ] **Step 3: Wire story insights into service**

Modify `backend/domains/ai_reports/visual_yearly_artifact_service.py` imports:

```python
from backend.domains.ai_reports.story_insight_builder import build_story_insights
```

Modify artifact generation after narrative is built:

```python
narrative = build_narrative_brief(context)
story_insights = build_story_insights(context, narrative)
visual = build_visual_brief(narrative, chart_coverage(context))
sections = _compose_sections(context, narrative, story_insights)
insight_cards = _compose_insight_cards(context, narrative)
```

Modify `_compose_sections` signature:

```python
def _compose_sections(
    context: dict[str, Any],
    narrative: dict[str, Any],
    story_insights: dict[str, Any],
) -> tuple[_Section, ...]:
```

Inside `_compose_sections`, set:

```python
album_relation = _dict(story_insights.get("album_relation"))
second_thread = _dict(story_insights.get("second_thread"))
highlight_day = _dict(story_insights.get("highlight_day"))
discovery_insight = _dict(story_insights.get("discovery"))
closing = _dict(story_insights.get("closing"))
```

Then call:

```python
_long_second_thread(second_thread)
_album_heading(album_relation)
_album_deck(album_relation)
_long_album_story(album_relation)
_long_highlight(highlight_day)
_long_discovery(discovery_insight)
_long_closing(context, closing)
```

- [ ] **Step 4: Replace repeated prose helpers**

In `backend/domains/ai_reports/visual_yearly_artifact_service.py`, remove `_warm_extension()` usage from `_long_opening`, `_long_companionship`, `_long_second_thread`, `_long_album_story`, `_long_highlight`, `_long_discovery`, and `_long_closing`.

Replace `_long_opening()` with:

```python
def _long_opening(context: dict[str, Any], narrative: dict[str, Any]) -> str:
    hero = _dict(context.get("hero"))
    period = _period(context)
    active_days = hero.get("active_days") or 0
    total_plays = hero.get("total_plays") or 0
    total_minutes = hero.get("total_minutes") or 0
    prefix = ""
    if period.get("is_partial_year") and period.get("end_date"):
        prefix = f"截至 {period['end_date']}，"
    main_story = str(narrative.get("main_story") or "")
    if prefix and main_story.startswith(prefix.rstrip("，")):
        prefix = ""
    return (
        f"{prefix}{main_story} 播放记录里有 {active_days} 个活跃日、"
        f"{total_plays} 次播放和约 {round(float(total_minutes) / 60):,} 小时聆听。"
        "这份年记先从密度开始，因为它比单个冠军更能说明音乐如何在场："
        "有些日子音乐靠前，有些日子只是安静陪在旁边，但它持续给这一阶段留下清楚的纹理。"
    )
```

Replace `_long_companionship()` with:

```python
def _long_companionship(context: dict[str, Any], lead: str) -> str:
    plays = _plays_at(context, "top_artists", 0)
    top_track = _top_name(context, "top_tracks", 0, "年度最高播放单曲")
    top_track_plays = _plays_at(context, "top_tracks", 0)
    return (
        f"{lead} 在这一年里不是偶然出现的名字。{plays} 次播放让它成为一条稳定声音线，"
        "更像你在不同普通时刻里反复回到的坐标。"
        f"单曲层面，{top_track} 以 {top_track_plays} 次播放站在前面，"
        "说明这条主线不只是艺人排名靠前，也有具体歌曲承担了最密集的回到。"
    )
```

Add helper functions:

```python
def _album_heading(album_relation: dict[str, Any]) -> str:
    if album_relation.get("mode") == "aligned":
        return "热度和长留，落在同一张专辑上"
    if album_relation.get("mode") == "divergent":
        return "常听和长留，是两种不同的喜欢"
    return "专辑偏好留下的线索"


def _album_deck(album_relation: dict[str, Any]) -> str:
    if album_relation.get("mode") == "aligned":
        return "播放量第一和个人榜单第一在这里重合。"
    if album_relation.get("mode") == "divergent":
        return "播放量第一和个人榜单第一不完全相同。"
    return "这一段只写数据能支持的专辑判断。"
```

Replace section prose functions:

```python
def _long_second_thread(second_thread: dict[str, Any]) -> str:
    entity = str(second_thread.get("entity") or "另一条声音")
    claim = str(second_thread.get("claim") or f"{entity} 是年度里的另一条声音线。")
    interpretation = str(second_thread.get("interpretation") or "它扩展了年度画像，但不适合外推具体生活场景。")
    return f"{claim} {interpretation}"


def _long_album_story(album_relation: dict[str, Any]) -> str:
    claim = str(album_relation.get("claim") or "专辑偏好留下了清楚线索。")
    interpretation = str(album_relation.get("interpretation") or "这里不强行把播放次数等同于全部偏好。")
    playback = str(album_relation.get("playback_leader") or "")
    chart = str(album_relation.get("chart_leader") or "")
    if album_relation.get("mode") == "aligned" and playback:
        return (
            f"{claim}。{interpretation} "
            f"这让 {playback} 不只是一个播放次数高的名字，也成为这段时间里持续留在视野里的专辑。"
        )
    if album_relation.get("mode") == "divergent" and playback and chart:
        return (
            f"{claim}。{interpretation} "
            f"所以 {playback} 更像高频点开的热度，{chart} 更像跨周留下来的耐听。"
        )
    return f"{claim}。{interpretation}"


def _long_highlight(highlight_day: dict[str, Any]) -> str:
    claim = str(highlight_day.get("claim") or "这一年有一个播放密度很高的日子")
    interpretation = str(highlight_day.get("interpretation") or "它适合被写成音乐密度，而不是具体生活事件。")
    plays = highlight_day.get("plays")
    play_text = f"，共有 {int(plays)} 次播放" if isinstance(plays, (int, float)) and plays else ""
    return f"{claim}{play_text}。{interpretation} 这一天的价值在于把音乐流动摊开，而不是制造没有证据的戏剧。"


def _long_discovery(discovery: dict[str, Any]) -> str:
    entity = str(discovery.get("entity") or "新声音")
    claim = str(discovery.get("claim") or f"{entity} 是这一年出现的新声音。")
    interpretation = str(discovery.get("interpretation") or "它是值得保留的观察点。")
    first_date = str(discovery.get("first_date") or "")
    date_text = f"它第一次出现在 {first_date}，" if first_date else ""
    return f"{claim}。{date_text}{interpretation}"


def _long_closing(context: dict[str, Any], closing: dict[str, Any]) -> str:
    year = _period(context).get("year") or context.get("year") or "这一年"
    claim = str(closing.get("claim") or f"{year} 没有留下单一答案。")
    interpretation = str(closing.get("interpretation") or "它更像一份由播放记录写成的阶段性画像。")
    return (
        f"{year} 最终留下的不是单一答案。{claim}。{interpretation} "
        "如果把这些章节合在一起看，稳定回到的声音、新出现的入口和高密度的一天，"
        "共同组成了这份音乐年记。"
    )
```

- [ ] **Step 5: Remove hardcoded second-thread interpretation from narrative brief**

In `backend/domains/ai_reports/narrative_brief.py`, replace:

```python
"interpretation": f"{second_artist} 提供了另一条更偏华语、记忆感或现场感的情绪线。",
```

with:

```python
"interpretation": f"{second_artist} 提供了另一条不同于主线艺人的声音线。" if second_artist else "",
```

- [ ] **Step 6: Run service tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_story_insight_builder.py backend/tests/unit/test_visual_yearly_artifact_service.py -q
```

Expected: all tests pass.

### Task 3: Harden Visual Critic

**Files:**
- Modify: `backend/domains/ai_reports/visual_yearly_critic.py`
- Modify: `backend/tests/unit/test_visual_yearly_critic.py`

- [ ] **Step 1: Add failing critic tests**

Append to `backend/tests/unit/test_visual_yearly_critic.py`:

```python
def test_visual_critic_rejects_internal_guidance_leakage():
    artifact = _artifact_with_prose(
        "Zhang Zhen Yue 是新声音。证据强度可以先放在 high。不要写成重度单曲循环。"
        "播放量和个人榜单留下了关系，音乐也有陪伴感。"
    )

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any(issue["code"] == "internal_guidance_leakage" for issue in result["issues"])


def test_visual_critic_rejects_repeated_meta_prose():
    repeated = (
        "图表负责回答发生了什么，正文负责回答为什么值得被记住。"
        "陪伴和新发现都在这里，播放量和个人榜单也有关系。"
    )
    artifact = _artifact_with_prose("\n".join([repeated, repeated, repeated]))

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any(issue["code"] == "repeated_template_prose" for issue in result["issues"])


def test_visual_critic_rejects_same_album_false_contrast():
    artifact = _artifact_with_prose(
        "The Life of a Showgirl 和 The Life of a Showgirl 说明了两种不同的喜欢。"
        "陪伴、新发现、播放量和个人榜单都被提到。"
    )
    context = {
        "is_partial_year": True,
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "personal_billboard_year_end": {"albums": [{"name": "The Life of a Showgirl"}]},
    }

    result = critique_visual_yearly_artifact(artifact, context)

    assert result["ok"] is False
    assert any(issue["code"] == "same_entity_false_contrast" for issue in result["issues"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: new tests fail because critic does not detect those issues.

- [ ] **Step 3: Add critic checks**

In `backend/domains/ai_reports/visual_yearly_critic.py`, add constants:

```python
INTERNAL_GUIDANCE_TERMS = (
    "证据强度",
    "不要写成",
    "guidance",
    "interpretation_guidance",
    "safe_speculation_rules",
    "high",
    "medium",
    "low",
)

REPEATED_META_TERMS = (
    "图表负责回答",
    "正文负责回答",
    "为什么值得被记住",
)
```

Inside `critique_visual_yearly_artifact()`, after business term check:

```python
internal = [term for term in INTERNAL_GUIDANCE_TERMS if term in prose]
if internal:
    issues.append(_issue("internal_guidance_leakage", "用户正文泄漏内部写作指令或证据标签：" + ", ".join(internal)))

if _has_repeated_template_prose(prose):
    issues.append(_issue("repeated_template_prose", "多个章节重复同一段模板解释，读起来不像文章。"))

if _has_same_entity_false_contrast(prose, context):
    issues.append(_issue("same_entity_false_contrast", "同一实体被写成了两种不同偏好的对比。"))
```

Add helper functions:

```python
def _has_repeated_template_prose(prose: str) -> bool:
    return sum(1 for term in REPEATED_META_TERMS if prose.count(term) >= 2) >= 2


def _has_same_entity_false_contrast(prose: str, context: dict[str, Any]) -> bool:
    playback = _name(_first(_list(context.get("top_albums"))))
    chart = _name(_first(_list(_dict(context.get("personal_billboard_year_end")).get("albums"))))
    if not playback or not chart or playback.casefold() != chart.casefold():
        return False
    return (
        f"{playback} 和 {chart}" in prose
        and any(term in prose for term in ("两种不同", "不完全相同", "分歧"))
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "")
```

Extend `_repair_instruction()` mapping:

```python
"internal_guidance_leakage": "删除内部写作指令、confidence 标签和 prompt 约束，只保留用户可读解释。",
"repeated_template_prose": "删除跨章节复用的元叙述，每个章节只写该章节自己的判断、证据和解释。",
"same_entity_false_contrast": "当播放榜和个人榜实体相同时，写成热度与长留重合，不要写成两种不同偏爱。",
```

- [ ] **Step 4: Run critic tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_visual_yearly_critic.py -q
```

Expected: all critic tests pass.

### Task 4: Update Probe Golden Checks

**Files:**
- Modify: `scripts/probe_visual_yearly_report_artifact.py`

- [ ] **Step 1: Extend forbidden terms**

In `scripts/probe_visual_yearly_report_artifact.py`, extend `FORBIDDEN_TERMS`:

```python
FORBIDDEN_TERMS = (
    "稳定中心",
    "三榜联动",
    "第二层证据",
    "evidence ledger",
    "dynamic outline",
    "综合来看",
    "后续观察",
    "证据强度",
    "不要写成",
    "interpretation_guidance",
    "safe_speculation_rules",
    "图表负责回答",
    "正文负责回答",
)
```

- [ ] **Step 2: Add 2026 same-album guard**

In `_validate()`, add:

```python
if year == 2026 and "The Life of a Showgirl 和 The Life of a Showgirl" in prose:
    issues.append("2026 same album was written as false contrast")
if year == 2026 and "Olivia Rodrigo" in prose and "Olivia Rodrigo 让年度画像多了一条不同的情绪线。它把华语" in prose:
    issues.append("2026 second thread forces unsupported Chinese genre claim")
```

- [ ] **Step 3: Add repeated-template guard**

In `_validate()`, add:

```python
if prose.count("为什么值得被记住") >= 2 or prose.count("图表负责回答") >= 2:
    issues.append("repeated visual-report template prose")
```

- [ ] **Step 4: Run probe syntax checks**

Run:

```bash
.venv/bin/ruff check scripts/probe_visual_yearly_report_artifact.py
.venv/bin/python -m py_compile scripts/probe_visual_yearly_report_artifact.py
```

Expected: both pass.

### Task 5: Full Targeted Verification

**Files:**
- No code changes in this task.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_story_insight_builder.py backend/tests/unit/test_visual_yearly_artifact_models.py backend/tests/unit/test_narrative_brief.py backend/tests/unit/test_visual_brief.py backend/tests/unit/test_visual_chart_data.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_visual_yearly_report_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend targeted tests and build**

Run:

```bash
cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx src/tests/ai-task-components.test.tsx
cd frontend && npm run build
```

Expected: tests pass and build exits 0.

- [ ] **Step 3: Run ruff and diff check**

Run:

```bash
.venv/bin/ruff check backend/domains/ai_reports backend/services/ai_task_service.py backend/services/ai_insights_service.py backend/api/ai_insights.py backend/models/ai_tasks.py scripts/probe_visual_yearly_report_artifact.py backend/tests/unit/test_story_insight_builder.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/contract/test_visual_yearly_report_contract.py
git diff --check
```

Expected: both pass.

- [ ] **Step 4: Run live artifact probes**

Run:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/probe_visual_yearly_report_artifact.py --base-url http://127.0.0.1:8000 --year 2025 --timeout 300 --json-output /tmp/spotify_visual_yearly_2025_editorial_fix.json
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/probe_visual_yearly_report_artifact.py --base-url http://127.0.0.1:8000 --year 2026 --timeout 300 --json-output /tmp/spotify_visual_yearly_2026_editorial_fix.json
```

Expected:

- Both probes exit 0.
- 2026 report does not contain `证据强度`, `不要写成`, `图表负责回答`, `The Life of a Showgirl 和 The Life of a Showgirl`.
- 2026 report contains either `热度与长留` or `同一张专辑`.

- [ ] **Step 5: Run browser acceptance**

Use Chrome CDP, Playwright, or the in-app browser:

1. Navigate to `/ai-insights`.
2. Click `年度叙事`.
3. Generate or load 2026 report.
4. Confirm final page renders artifact, not Markdown-only fallback.
5. Confirm text does not contain `证据强度`, `不要写成`, `图表负责回答`, or `The Life of a Showgirl 和 The Life of a Showgirl`.
6. Confirm at least 6 sections and 6 chart blocks render.
7. Set viewport width to 390px and confirm horizontal overflow is 0.
8. Confirm console error/warning count is 0.

Expected: all checks pass.

### Task 6: Documentation And Final Review

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-07-04-ai-visual-yearly-report-editorial-fix.md`

- [ ] **Step 1: Update changelog after implementation**

Add a new entry to `docs/CHANGELOG.md`:

```markdown
## 2026-07-04 — AI Visual Yearly Report Editorial Fix

### 修复

- 年度图文报告新增 Story Insight Builder，在写作前先判断播放榜/个人榜单关系、新发现强度、高光日类型和第二声音线，避免模板硬套数据。
- 修复 2026 年报中的内部指令泄漏、重复元叙述、同专辑误写成对比、Olivia Rodrigo 被错误绑定华语语境等问题。
- Visual critic 和 HTTP probe 增加内部词泄漏、重复模板、同实体 false contrast 和 2026 golden checks。

### 验证

- 填入实际运行过的 pytest、Vitest、build、ruff、probe 和 browser acceptance 结果。
```

- [ ] **Step 2: Mark this plan status**

At the top of this plan, after the header block, add:

```markdown
## Implementation Status

Status: implemented and verified on 2026-07-04.

Acceptance evidence:

- Backend targeted pytest: command from Task 5 Step 1 and its final passed count.
- Frontend targeted Vitest/build: commands from Task 5 Step 2 and their pass/build status.
- Live 2025/2026 probes: commands from Task 5 Step 4 and their output JSON paths.
- Browser acceptance: viewport sizes, console issue count, horizontal overflow result, and screenshot paths.
```

- [ ] **Step 3: Final code review**

Review these diffs manually:

```bash
git diff -- backend/domains/ai_reports/story_insight_builder.py backend/domains/ai_reports/visual_yearly_artifact_service.py backend/domains/ai_reports/visual_yearly_critic.py scripts/probe_visual_yearly_report_artifact.py
git diff -- backend/tests/unit/test_story_insight_builder.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_critic.py
```

Expected:

- No user-facing prose contains internal guidance labels.
- Album aligned/divergent modes are both tested.
- Critic detects all failure modes observed in the 2026 report.
- Existing artifact schema remains unchanged.

## Acceptance Criteria

- 2026 generated visual yearly report has no internal instruction leakage.
- 2026 generated report does not repeat the same meta paragraph across sections.
- If playback-leading album and personal-chart-leading album are identical, the report writes aligned heat/long-tail interpretation, not contrast.
- Olivia Rodrigo is not described as bringing a Chinese-language or live-show thread unless the evidence explicitly supports that.
- Visual critic fails the original bad 2026 report pattern.
- HTTP probe fails on those same bad patterns.
- Browser acceptance passes on desktop and 390px mobile with 0 console warning/error and 0 horizontal overflow.

## Self-Review

- Spec coverage: all observed failures map to tasks:
  - Internal leakage: Tasks 1, 2, 3, 4.
  - Repeated template prose: Tasks 2, 3, 4.
  - Same-album false contrast: Tasks 1, 2, 3, 4.
  - Unsupported Olivia Rodrigo genre claim: Tasks 1, 2, 4.
  - Verification and browser acceptance: Task 5.
- 占位扫描：this plan contains no unresolved markers, no unassigned implementation step, and no open-ended “add tests” instruction without concrete tests.
- Type consistency:
  - `build_story_insights(context, narrative)` returns a `dict[str, Any]`.
  - Section writer consumes `album_relation`, `second_thread`, `highlight_day`, `discovery`, and `closing`.
  - Existing artifact schema remains `visual_yearly_v1`.
- Scope control:
  - This plan does not add new chart types or frontend redesign.
  - This plan does not replace the task/cache/report-mode integration already implemented.
  - This plan is a focused editorial-quality repair on top of the visual yearly artifact.
