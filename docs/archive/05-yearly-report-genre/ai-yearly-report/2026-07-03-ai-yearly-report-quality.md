# AI Yearly Report Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make AI yearly reports trustworthy for partial-year data, entity-heavy summaries, personality interpretation, genre interpretation, year-over-year comparison, and evidence-grounded narrative writing.

**Architecture:** Keep the existing AI Insights report API and task progress flow. Add a deterministic yearly-report contract layer before the LLM, rewrite only the yearly story prompt, and add a lightweight yearly report validator with one retry before caching. Do not change the general chat Agent or frontend report UI unless a test reveals a regression.

**Tech Stack:** FastAPI service layer, SQLite, pandas-backed playback loaders, pytest unit/contract tests, existing AI task report orchestration, Markdown report output.

---

## Scope

Fix these issues from the 2026 yearly report review:

- Partial 2026 data was written as a complete year.
- Full-year 2025 vs partial-year 2026 comparison was treated as fair.
- Top artist, top track, and new artist names were dropped by the yearly AI data package.
- Personality score labels were mismatched.
- Genre shares were interpreted without the "其他流派" bucket or overlap caveat.
- Low-confidence highlights were over-dramatized.
- The report invented unsupported life scenes.
- Output lacked enough concrete names and evidence density.
- The yearly prompt over-encouraged generic emotional storytelling.

Out of scope:

- Do not implement the copyright/lyrics fix from review issue 8 in this plan.
- Do not redesign the AI Insights UI.
- Do not change weekly or monthly report semantics except where shared helpers require safe reuse.
- Do not expose new write tools or arbitrary SQL.

## Current Root Causes

- `backend/services/ai_insights_service.py::_gather_yearly_data()` reads `artist_name` and `track_name` from Wrapped top-list objects that actually expose `name`, so entity names are erased before the LLM sees them.
- `YEARLY_STORY_SYSTEM` requires "来年寄语" and emotional meaning for each data point, but it does not mention partial-year reports, same-period comparisons, unsupported scenes, genre overlap, or empty-entity handling.
- The yearly data payload exposes raw `personality.dimensions` but does not provide a normalized top-dimension summary, so the LLM can attach scores to the wrong labels.
- Wrapped `comparison.last_year` compares the selected year against the previous full year. For the latest partial year, that comparison is misleading unless replaced by same-period YTD or explicitly suppressed.

## File Map

- Create: `backend/domains/ai_reports/__init__.py`
  Package marker for deterministic AI report data-contract helpers.
- Create: `backend/domains/ai_reports/yearly_contract.py`
  Build reporting period metadata, normalized top lists, personality summary, genre caveat, same-period comparison, and writing constraints.
- Create: `backend/domains/ai_reports/yearly_validator.py`
  Validate generated yearly reports against the data contract and produce retry instructions.
- Create: `backend/tests/unit/test_ai_insights_yearly_quality.py`
  Regression tests for yearly report data shaping, partial-year context, same-period comparison, prompt guardrails, and validator retry.
- Modify: `backend/services/ai_insights_service.py`
  Use the yearly contract helpers, rewrite `YEARLY_STORY_SYSTEM`, run validation and one retry before caching.
- Modify: `backend/tests/unit/test_ai_insights_service.py`
  Add focused compatibility assertions if existing tests are easier to extend than the new yearly test file.
- Modify: `backend/tests/unit/test_ai_report_tasks.py`
  Ensure AI task yearly generation still returns entities and does not cache invalid yearly reports.
- Modify: `backend/tests/contract/test_ai_insights_contract.py`
  Keep `/api/ai-insights/yearly-story` contract stable while allowing richer result internals.
- Modify if needed: `docs/README.md`, `docs/CHANGELOG.md`, `AGENTS.md`, `CLAUDE.md`, `backend/CLAUDE.md`
  Only update if implementation changes prompt/data-contract behavior enough that repo guidance or changelog would become stale.

## Acceptance Criteria

- 2026 yearly report data includes `reporting_period.end_date == "2026-06-23"` on the current production DB and marks the report as partial-year.
- 2026 report text says "截至 2026-06-23" or equivalent, and does not frame the report as a completed full year.
- Top artist names, top track names, and new artist names are present in the LLM input and in generated text when available.
- Partial-year comparison uses same-period YTD metrics or explicitly says full-year comparison is not fair.
- Personality labels and scores match the normalized data contract.
- Genre text includes or accounts for "其他流派" when it is in the top genres, and includes an overlap/metadata caveat.
- Unsupported narrative scenes such as weather, insomnia, farewell, or major life turning points are not introduced unless present in the data.
- Low-confidence highlights are described proportionally. A top track played 4 times on the most active day cannot be called heavy looping.
- Invalid yearly reports are retried once and are not cached if severe validation issues remain.
- Existing AI report task progress, cache-first behavior, and report endpoint response contract remain compatible.

---

## Task 1: Add Regression Tests For The Yearly Report Contract

**Files:**
- Create: `backend/tests/unit/test_ai_insights_yearly_quality.py`

- [x] **Step 1: Create a test file with fake Wrapped data**

Create `backend/tests/unit/test_ai_insights_yearly_quality.py` with this starter content:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from backend.services import ai_insights_service as svc

pytestmark = pytest.mark.unit


def _conn_with_play_dates(tmp_path: Path, dates: list[str]) -> sqlite3.Connection:
    db_path = tmp_path / "yearly_quality.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE plays (play_id INTEGER PRIMARY KEY, ts_date TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO plays (play_id, ts_date) VALUES (?, ?)",
        [(index + 1, date) for index, date in enumerate(dates)],
    )
    conn.commit()
    return conn


def _wrapped_payload() -> dict[str, Any]:
    return {
        "empty": False,
        "hero": {
            "total_minutes": 29882.0,
            "total_plays": 7860,
            "unique_tracks": 2060,
            "unique_artists": 328,
            "active_days": 174,
            "avg_minutes_per_day": 171.7,
        },
        "personality": {
            "primary": "binger",
            "primary_label": "能量引擎",
            "dimensions": {
                "explorer": {"score": 65.5},
                "loyalist": {"score": 70.9},
                "binger": {"score": 71.6},
                "night_owl": {"score": 24.0},
                "collector": {"score": 11.7},
                "trend_chaser": {"score": 26.8},
                "globetrotter": {"score": 68.3},
            },
        },
        "top_lists": {
            "artists": [
                {"rank": 1, "name": "Taylor Swift", "plays": 1115, "hours": 68.8},
                {"rank": 2, "name": "Olivia Rodrigo", "plays": 769, "hours": 45.8},
            ],
            "tracks": [
                {
                    "rank": 1,
                    "name": "Opalite",
                    "artist_name": "Taylor Swift",
                    "plays": 123,
                    "hours": 7.9,
                },
                {
                    "rank": 2,
                    "name": "drop dead",
                    "artist_name": "Olivia Rodrigo",
                    "plays": 110,
                    "hours": 6.7,
                },
            ],
        },
        "genre_panorama": {
            "top_genres": [
                {"name": "其他流派", "play_share": 19.1},
                {"name": "mandopop", "play_share": 14.4},
                {"name": "c-pop", "play_share": 14.4},
            ]
        },
        "time_story": {"late_night": {"ratio": 12.0}},
        "discovery_returns": {
            "new_artists": [
                {"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}
            ],
            "longest_love": {
                "name": "Nothing New (feat. Phoebe Bridgers) (Taylor's Version)",
                "artist_name": "Taylor Swift",
                "span_days": 1450,
            },
        },
        "special_moments": {
            "most_active_day": {
                "date": "2026-04-03",
                "plays": 143,
                "top_track": {"name": "Changes", "artist_name": "Charlie Puth", "plays": 4},
            }
        },
        "comparison": {
            "last_year": {
                "total_hours_change": -56.1,
                "plays_change": -55.3,
                "tracks_change": -25.3,
                "artists_change": -28.0,
                "active_days_change": -52.2,
            }
        },
    }
```

- [x] **Step 2: Add a failing test for entity names and partial-year period**

Append this test:

```python
def test_gather_yearly_data_preserves_names_and_marks_partial_year(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload())

    data = svc._gather_yearly_data(
        conn,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        year=2026,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
    )

    assert data["reporting_period"]["start_date"] == "2026-01-01"
    assert data["reporting_period"]["end_date"] == "2026-06-23"
    assert data["reporting_period"]["is_partial_year"] is True
    assert data["reporting_period"]["label"] == "2026 年截至 2026-06-23"
    assert data["top_artists"][0]["name"] == "Taylor Swift"
    assert data["top_tracks"][0]["name"] == "Opalite"
    assert data["top_tracks"][0]["artist"] == "Taylor Swift"
    assert data["new_artists"][0]["name"] == "Zhang Zhen Yue"
    assert svc._extract_entities(data) == {
        "artists": ["Taylor Swift", "Olivia Rodrigo"],
        "tracks": ["Opalite", "drop dead"],
    }
```

- [x] **Step 3: Add a failing test for normalized personality and genre caveat**

Append:

```python
def test_gather_yearly_data_normalizes_personality_and_genres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload())

    data = svc._gather_yearly_data(conn, 30000, True, True, 2026)

    top_dimensions = data["personality_summary"]["top_dimensions"]
    assert top_dimensions[0] == {"key": "binger", "label": "能量引擎", "score": 71.6}
    assert {"key": "loyalist", "label": "专一者", "score": 70.9} in top_dimensions
    assert data["genre_summary"]["top_genres"][0] == {"name": "其他流派", "share": 19.1}
    assert data["genre_summary"]["has_other_bucket"] is True
    assert "可能重叠" in data["genre_summary"]["caveat"]
```

- [x] **Step 4: Add a failing test for prompt/validator retry behavior**

Append:

```python
def test_generate_yearly_story_retries_invalid_partial_year_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload())
    monkeypatch.setattr(svc, "_get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "_get_llm", lambda *args, **kwargs: object())

    cached: list[str] = []
    monkeypatch.setattr(svc, "_set_cache", lambda _conn, _key, report: cached.append(report))

    calls: list[str] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        calls.append(user_content)
        if len(calls) == 1:
            return "## 来年寄语\n这一年你少听了 55%，也许某个下雨夜晚改变了你。"
        return "## 2026 年中总结\n截至 2026-06-23，你最常听 Taylor Swift 和 Olivia Rodrigo；同期比较需要按 YTD 口径理解。"

    monkeypatch.setattr(svc, "_llm_chat", fake_llm_chat)

    result = svc.generate_yearly_story(conn, 30000, True, True, 2026, dynamic_threshold=True)

    assert result["success"] is True
    assert "截至 2026-06-23" in result["report"]
    assert "下雨夜晚" not in result["report"]
    assert len(calls) == 2
    assert cached == [result["report"]]
```

- [x] **Step 5: Run the failing tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py -q
```

Expected before implementation: failures for missing `reporting_period`, wrong entity fields, missing normalized summaries, and missing retry validation.

## Task 2: Add The Deterministic Yearly Contract Helper

**Files:**
- Create: `backend/domains/ai_reports/__init__.py`
- Create: `backend/domains/ai_reports/yearly_contract.py`
- Modify: `backend/tests/unit/test_ai_insights_yearly_quality.py`

- [x] **Step 1: Create the package marker**

Create `backend/domains/ai_reports/__init__.py`:

```python
"""Deterministic data contracts for AI-generated reports."""
```

- [x] **Step 2: Implement name extraction, reporting period, personality, genre, and highlight helpers**

Create `backend/domains/ai_reports/yearly_contract.py`:

```python
"""Yearly AI report data contract helpers."""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date
from typing import Any

PERSONALITY_LABELS = {
    "explorer": "探索者",
    "loyalist": "专一者",
    "binger": "能量引擎",
    "night_owl": "夜猫子",
    "collector": "收藏家",
    "trend_chaser": "潮流追踪者",
    "globetrotter": "环球旅人",
}

UNSUPPORTED_SCENE_TERMS = ("下雨", "失眠", "告别", "转折", "崩溃", "治愈了你")


def item_name(item: dict[str, Any], *fallback_keys: str) -> str:
    for key in ("name", *fallback_keys):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def build_reporting_period(conn: sqlite3.Connection, year: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT min(ts_date) AS start_date,
               max(ts_date) AS end_date,
               count(DISTINCT ts_date) AS active_days
          FROM plays
         WHERE ts_date >= ? AND ts_date <= ?
        """,
        (f"{year}-01-01", f"{year}-12-31"),
    ).fetchone()
    start_date = row["start_date"] if row else None
    end_date = row["end_date"] if row else None
    active_days = int(row["active_days"] or 0) if row else 0
    is_partial = bool(end_date and end_date < f"{year}-12-31")
    label = f"{year} 年截至 {end_date}" if is_partial and end_date else f"{year} 年全年"
    return {
        "year": year,
        "start_date": start_date,
        "end_date": end_date,
        "latest_data_date": end_date,
        "active_days": active_days,
        "days_covered": _inclusive_days(start_date, end_date),
        "is_partial_year": is_partial,
        "label": label,
    }


def normalize_top_artists(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "rank": int(item.get("rank") or index + 1),
            "name": item_name(item, "artist_name"),
            "plays": int(item.get("plays") or 0),
            "hours": item.get("hours"),
        }
        for index, item in enumerate(items[:limit])
        if item_name(item, "artist_name")
    ]


def normalize_top_tracks(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "rank": int(item.get("rank") or index + 1),
            "name": item_name(item, "track_name"),
            "artist": item_name(item, "artist_name"),
            "plays": int(item.get("plays") or 0),
            "hours": item.get("hours"),
        }
        for index, item in enumerate(items[:limit])
        if item_name(item, "track_name")
    ]


def normalize_new_artists(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "name": item_name(item, "artist_name"),
            "plays": int(item.get("plays") or 0),
            "first_date": item.get("first_date"),
        }
        for item in items[:limit]
        if item_name(item, "artist_name")
    ]


def summarize_personality(personality: dict[str, Any]) -> dict[str, Any]:
    dimensions = personality.get("dimensions") if isinstance(personality, dict) else {}
    rows: list[dict[str, Any]] = []
    if isinstance(dimensions, dict):
        for key, payload in dimensions.items():
            if not isinstance(payload, dict):
                continue
            score = payload.get("score")
            if isinstance(score, int | float):
                rows.append(
                    {
                        "key": key,
                        "label": PERSONALITY_LABELS.get(key, key),
                        "score": round(float(score), 1),
                    }
                )
    rows.sort(key=lambda row: row["score"], reverse=True)
    primary_key = personality.get("primary")
    return {
        "primary": primary_key,
        "primary_label": personality.get("primary_label") or PERSONALITY_LABELS.get(primary_key, ""),
        "top_dimensions": rows[:4],
        "score_label_rule": "score belongs to the same key in top_dimensions; do not attach it to another label.",
    }


def summarize_genres(items: list[dict[str, Any]], limit: int = 5) -> dict[str, Any]:
    top_genres = [
        {"name": str(item.get("name") or ""), "share": round(float(item.get("play_share") or 0), 1)}
        for item in items[:limit]
        if item.get("name")
    ]
    return {
        "top_genres": top_genres,
        "has_other_bucket": any(item["name"] == "其他流派" for item in top_genres),
        "caveat": "Spotify genre 标签可能重叠，百分比不应被解释为互斥类别。",
    }


def summarize_highlight_strength(most_active_day: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(most_active_day, dict):
        return None
    top_track = most_active_day.get("top_track") if isinstance(most_active_day.get("top_track"), dict) else {}
    top_track_plays = int(top_track.get("plays") or 0)
    day_plays = int(most_active_day.get("plays") or 0)
    share = round(top_track_plays / day_plays * 100, 1) if day_plays else 0.0
    guidance = (
        "当天最高单曲播放不高，不要写成重度单曲循环。"
        if top_track_plays < 8
        else "可以描述为当天有明显单曲重复收听。"
    )
    return {
        **most_active_day,
        "top_track_share_pct": share,
        "interpretation_guidance": guidance,
    }


def build_writing_constraints(reporting_period: dict[str, Any]) -> list[str]:
    constraints = [
        "所有结论必须基于 DATA，不要编造天气、失眠、告别、人生转折等未提供场景。",
        "如果实体名称存在，必须优先写出具体艺人名和歌曲名。",
        "解释人格分数时必须使用 personality_summary.top_dimensions 中同一行的 label 和 score。",
        "解释流派时必须保留 genre_summary.caveat，不要把 genre 百分比写成互斥类别。",
    ]
    if reporting_period.get("is_partial_year"):
        constraints.extend(
            [
                f"这是 partial-year report，必须写明数据截至 {reporting_period.get('end_date')}。",
                "不要使用暗示全年已结束的表达，如“这一年已经”“明年”“来年寄语”。",
                "结尾应写“下半年观察”或“接下来”，而不是“来年寄语”。",
            ]
        )
    return constraints


def _inclusive_days(start_date: str | None, end_date: str | None) -> int:
    if not start_date or not end_date:
        return 0
    return (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1


def same_day_previous_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def pct_change(new_value: float, old_value: float) -> float | None:
    if old_value == 0:
        return None
    return round((new_value - old_value) / old_value * 100, 1)


def summarize_period_frame(df) -> dict[str, Any]:
    if df.empty:
        return {"hours": 0.0, "plays": 0, "tracks": 0, "artists": 0, "active_days": 0}
    return {
        "hours": round(float(df["ms_played"].sum() / 3_600_000), 1),
        "plays": int(len(df)),
        "tracks": int(df["track_id"].nunique()) if "track_id" in df else 0,
        "artists": int(df["artist_name"].dropna().nunique()) if "artist_name" in df else 0,
        "active_days": int(df["ts_date"].nunique()) if "ts_date" in df else 0,
    }
```

- [x] **Step 3: Implement same-period comparison helper**

Append to `yearly_contract.py`:

```python
def build_same_period_comparison(
    conn: sqlite3.Connection,
    *,
    year: int,
    end_date: str | None,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
) -> dict[str, Any] | None:
    if not end_date:
        return None
    from backend.core.db import load_plays

    current_start = date(year, 1, 1)
    current_end = date.fromisoformat(end_date)
    previous_start = date(year - 1, 1, 1)
    previous_end = same_day_previous_year(current_end)

    df = load_plays(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    if df.empty:
        return None

    current_df = df[(df["ts_date"] >= current_start.isoformat()) & (df["ts_date"] <= current_end.isoformat())]
    previous_df = df[(df["ts_date"] >= previous_start.isoformat()) & (df["ts_date"] <= previous_end.isoformat())]
    current = summarize_period_frame(current_df)
    previous = summarize_period_frame(previous_df)
    if previous["plays"] == 0:
        return {
            "mode": "same_period_ytd",
            "current_period": {"start_date": current_start.isoformat(), "end_date": current_end.isoformat()},
            "previous_period": {"start_date": previous_start.isoformat(), "end_date": previous_end.isoformat()},
            "current": current,
            "previous": previous,
            "changes": None,
            "available": False,
            "note": "上一年同期数据不足，不应做强对比。",
        }
    return {
        "mode": "same_period_ytd",
        "current_period": {"start_date": current_start.isoformat(), "end_date": current_end.isoformat()},
        "previous_period": {"start_date": previous_start.isoformat(), "end_date": previous_end.isoformat()},
        "current": current,
        "previous": previous,
        "changes": {
            "hours_change": pct_change(current["hours"], previous["hours"]),
            "plays_change": pct_change(current["plays"], previous["plays"]),
            "tracks_change": pct_change(current["tracks"], previous["tracks"]),
            "artists_change": pct_change(current["artists"], previous["artists"]),
            "active_days_change": pct_change(current["active_days"], previous["active_days"]),
        },
        "available": True,
        "note": "这是同日起止窗口的 YTD 对比，可用于 partial-year report。",
    }
```

- [x] **Step 4: Add direct tests for helper edge cases**

Add these tests to `backend/tests/unit/test_ai_insights_yearly_quality.py`:

```python
def test_same_day_previous_year_handles_leap_day():
    from datetime import date

    from backend.domains.ai_reports.yearly_contract import same_day_previous_year

    assert same_day_previous_year(date(2024, 2, 29)).isoformat() == "2023-02-28"


def test_pct_change_handles_zero_denominator():
    from backend.domains.ai_reports.yearly_contract import pct_change

    assert pct_change(10, 0) is None
    assert pct_change(150, 100) == 50.0
```

- [x] **Step 5: Verify helper tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py::test_same_day_previous_year_handles_leap_day backend/tests/unit/test_ai_insights_yearly_quality.py::test_pct_change_handles_zero_denominator -q
```

Expected: pass.

## Task 3: Wire The Contract Into Yearly Data Gathering

**Files:**
- Modify: `backend/services/ai_insights_service.py`
- Modify: `backend/tests/unit/test_ai_insights_yearly_quality.py`

- [x] **Step 1: Import yearly contract helpers**

In `backend/services/ai_insights_service.py`, add imports near the other backend imports:

```python
from backend.domains.ai_reports.yearly_contract import (
    build_reporting_period,
    build_same_period_comparison,
    build_writing_constraints,
    normalize_new_artists,
    normalize_top_artists,
    normalize_top_tracks,
    summarize_genres,
    summarize_highlight_strength,
    summarize_personality,
)
```

- [x] **Step 2: Replace the yearly payload shaping block**

In `_gather_yearly_data()`, replace the `return { ... }` block with a payload that preserves legacy keys and adds normalized contract fields:

```python
    reporting_period = build_reporting_period(conn, year)
    top_artists = normalize_top_artists(top_lists.get("artists") or [])
    top_tracks = normalize_top_tracks(top_lists.get("tracks") or [])
    new_artists = normalize_new_artists(discovery.get("new_artists") or [])
    genre_summary = summarize_genres(genre_panorama.get("top_genres") or [])
    personality_summary = summarize_personality(personality)
    most_active_day = summarize_highlight_strength(special.get("most_active_day"))
    same_period_comparison = (
        build_same_period_comparison(
            conn,
            year=year,
            end_date=reporting_period.get("end_date"),
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        if reporting_period.get("is_partial_year")
        else None
    )

    return {
        "year": year,
        "reporting_period": reporting_period,
        "hero": {
            "total_minutes": hero.get("total_minutes", 0),
            "total_plays": hero.get("total_plays", 0),
            "unique_tracks": hero.get("unique_tracks", 0),
            "unique_artists": hero.get("unique_artists", 0),
            "active_days": hero.get("active_days", 0),
            "avg_minutes_per_day": hero.get("avg_minutes_per_day", 0),
        },
        "personality": personality,
        "personality_summary": personality_summary,
        "top_artists": top_artists,
        "top_tracks": top_tracks,
        "top_genres": genre_summary["top_genres"],
        "genre_summary": genre_summary,
        "late_night_pct": (time_story.get("late_night") or {}).get("ratio", 0),
        "new_artists": new_artists,
        "longest_love": discovery.get("longest_love"),
        "most_active_day": most_active_day,
        "year_over_year": {
            "comparison_basis": "same_period_ytd"
            if reporting_period.get("is_partial_year")
            else "full_year",
            "same_period": same_period_comparison,
            "full_previous_year_change": None
            if reporting_period.get("is_partial_year")
            else comparison.get("last_year"),
            "note": "partial-year report 必须使用 same_period_ytd，不要引用 full_previous_year_change。"
            if reporting_period.get("is_partial_year")
            else "full-year comparison is available.",
        },
        "change_vs_last_year": None
        if reporting_period.get("is_partial_year")
        else comparison.get("last_year"),
        "writing_constraints": build_writing_constraints(reporting_period),
    }
```

- [x] **Step 3: Keep entity extraction compatible**

Update `_extract_entities()` only if the new object-shaped `new_artists` changes assumptions elsewhere. The existing top artist/track extraction should continue to work once `top_artists` and `top_tracks` use `name`.

Expected final behavior:

```python
def _extract_entities(data: dict) -> dict:
    artists = [a["name"] for a in data.get("top_artists", []) if a.get("name")]
    tracks = [t["name"] for t in data.get("top_tracks", []) if t.get("name")]
    return {"artists": artists[:5], "tracks": tracks[:5]}
```

- [x] **Step 4: Verify Task 1 tests now pass except validator retry**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py -q
```

Expected: entity/period/personality/genre helper tests pass. Retry behavior may still fail until Task 5.

## Task 4: Rewrite The Yearly Story Prompt Around The Contract

**Files:**
- Modify: `backend/services/ai_insights_service.py`
- Modify: `backend/tests/unit/test_ai_insights_yearly_quality.py`

- [x] **Step 1: Replace `YEARLY_STORY_SYSTEM`**

Replace the current yearly prompt with:

```python
YEARLY_STORY_SYSTEM = """你是一位可信的个人音乐年度编辑。根据 DATA 为用户撰写中文 Markdown 年度/年中音乐报告。

写作原则：
1. 先守数据口径，再写情绪。所有事实、日期、对比、艺人名、歌曲名、人格分数都必须来自 DATA。
2. 必须读取 reporting_period。若 is_partial_year=true，开头必须写清“截至 end_date”，并把报告称为年中/阶段性总结；不要把它写成完整全年。
3. 若 is_partial_year=true，不要使用“明年”“来年寄语”“这一年已经结束”等表达，结尾使用“下半年观察”或“接下来可以关注”。
4. 对比上一年时只能使用 year_over_year.same_period；只有 comparison_basis=full_year 时才可使用 full_previous_year_change。
5. 人格画像必须使用 personality_summary.top_dimensions 中同一行的 label 与 score，不得把一个维度的分数套到另一个维度上。
6. TOP 艺人、歌曲、新艺人如果有 name，必须写出具体名称；不要用“某位艺人”“另一首歌”替代。
7. 流派解读必须保留 genre_summary.caveat 的含义；如果 top_genres 中包含“其他流派”，需要说明它也是最大或重要类别之一。
8. 高光日解释必须参考 most_active_day.interpretation_guidance，不要把低播放次数的单曲写成重度循环。
9. 可以有温度，但不要编造 DATA 外的人生事件、天气、失眠、告别、重要转折或心理原因。
10. 输出 Markdown，使用 ## 二级标题。长度 450-750 字。"""
```

- [x] **Step 2: Add a prompt regression assertion**

Add this test:

```python
def test_yearly_prompt_contains_partial_year_and_grounding_rules():
    prompt = svc.YEARLY_STORY_SYSTEM

    assert "reporting_period" in prompt
    assert "is_partial_year=true" in prompt
    assert "year_over_year.same_period" in prompt
    assert "personality_summary.top_dimensions" in prompt
    assert "不要编造" in prompt
```

- [x] **Step 3: Verify prompt test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py::test_yearly_prompt_contains_partial_year_and_grounding_rules -q
```

Expected: pass.

## Task 5: Add Yearly Report Validation And One Retry

**Files:**
- Create: `backend/domains/ai_reports/yearly_validator.py`
- Modify: `backend/services/ai_insights_service.py`
- Modify: `backend/tests/unit/test_ai_insights_yearly_quality.py`
- Modify if needed: `backend/tests/unit/test_ai_report_tasks.py`

- [x] **Step 1: Implement validator models and checks**

Create `backend/domains/ai_reports/yearly_validator.py`:

```python
"""Validation for generated AI yearly reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.domains.ai_reports.yearly_contract import UNSUPPORTED_SCENE_TERMS


@dataclass(frozen=True)
class YearlyReportIssue:
    code: str
    message: str
    severity: str = "high"


@dataclass(frozen=True)
class YearlyReportValidation:
    ok: bool
    issues: tuple[YearlyReportIssue, ...]

    def retry_instructions(self) -> str:
        if self.ok:
            return ""
        lines = ["请修正上一版年度报告中的问题："]
        lines.extend(f"- {issue.code}: {issue.message}" for issue in self.issues)
        return "\n".join(lines)


def validate_yearly_report(report: str, data: dict[str, Any]) -> YearlyReportValidation:
    issues: list[YearlyReportIssue] = []
    period = data.get("reporting_period") if isinstance(data.get("reporting_period"), dict) else {}
    is_partial = bool(period.get("is_partial_year"))
    end_date = str(period.get("end_date") or "")

    if is_partial:
        if end_date and end_date not in report:
            issues.append(
                YearlyReportIssue(
                    "missing_partial_year_cutoff",
                    f"partial-year report must mention the data cutoff date {end_date}",
                )
            )
        forbidden = ("明年", "来年寄语", "全年总结", "这一年已经结束")
        if any(term in report for term in forbidden):
            issues.append(
                YearlyReportIssue(
                    "partial_year_written_as_full_year",
                    "partial-year report uses full-year or next-year phrasing",
                )
            )

    for artist in _required_names(data.get("top_artists"), limit=3):
        if artist not in report:
            issues.append(
                YearlyReportIssue("missing_top_artist", f"report should mention top artist {artist}")
            )
    for track in _required_names(data.get("top_tracks"), limit=3):
        if track not in report:
            issues.append(
                YearlyReportIssue("missing_top_track", f"report should mention top track {track}")
            )

    for term in UNSUPPORTED_SCENE_TERMS:
        if term in report:
            issues.append(
                YearlyReportIssue(
                    "unsupported_scene",
                    f"report introduces unsupported narrative scene term: {term}",
                )
            )

    personality = data.get("personality_summary")
    if isinstance(personality, dict):
        for row in personality.get("top_dimensions") or []:
            label = str(row.get("label") or "")
            score = str(row.get("score") or "")
            if label and score and score in report and label not in report:
                issues.append(
                    YearlyReportIssue(
                        "personality_score_without_label",
                        f"score {score} appears without its paired label {label}",
                    )
                )

    genre_summary = data.get("genre_summary") if isinstance(data.get("genre_summary"), dict) else {}
    if genre_summary.get("has_other_bucket") and "其他流派" not in report:
        issues.append(
            YearlyReportIssue("missing_other_genre_bucket", "report omits the top '其他流派' bucket")
        )

    high_severity = [issue for issue in issues if issue.severity == "high"]
    return YearlyReportValidation(ok=not high_severity, issues=tuple(issues))


def _required_names(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value[:limit]:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
            names.append(item["name"].strip())
    return names
```

- [x] **Step 2: Wire validation and retry into yearly generation**

In `backend/services/ai_insights_service.py`, import:

```python
from backend.domains.ai_reports.yearly_validator import validate_yearly_report
```

Then replace the single LLM call block in `generate_yearly_story()`:

```python
    entities = _extract_entities(data)
    user_content = f"DATA:\n{_data_to_json_safe(data)}"
    report = _llm_chat(YEARLY_STORY_SYSTEM, user_content, temperature=0.6)

    if report is None:
        return {"success": False, "report": None, "cached": False, "error": "LLM 调用失败"}
    if not report.strip():
        return {"success": False, "report": None, "cached": False, "error": "LLM 返回为空"}

    validation = validate_yearly_report(report, data)
    if not validation.ok:
        retry_content = (
            f"{user_content}\n\n"
            f"VALIDATION_FEEDBACK:\n{validation.retry_instructions()}\n\n"
            "请重新输出完整报告，不要解释校验过程。"
        )
        retry_report = _llm_chat(YEARLY_STORY_SYSTEM, retry_content, temperature=0.4)
        if retry_report and retry_report.strip():
            retry_validation = validate_yearly_report(retry_report, data)
            if retry_validation.ok:
                report = retry_report
                validation = retry_validation

    if not validation.ok:
        logger.warning(
            "Yearly AI report failed validation",
            extra={"issues": [issue.code for issue in validation.issues]},
        )
        return {
            "success": False,
            "report": None,
            "cached": False,
            "error": "年度报告质量校验未通过，请重试",
            "entities": entities,
        }
```

Keep the existing cache write and success return after this block.

- [x] **Step 3: Ensure invalid reports are not cached**

Add this test:

```python
def test_generate_yearly_story_does_not_cache_report_after_failed_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload())
    monkeypatch.setattr(svc, "_get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "_get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        svc,
        "_llm_chat",
        lambda *args, **kwargs: "## 来年寄语\n这一年已经结束，你在某个失眠夜晚完成了转折。",
    )
    monkeypatch.setattr(
        svc,
        "_set_cache",
        lambda *args, **kwargs: pytest.fail("invalid report must not be cached"),
    )

    result = svc.generate_yearly_story(conn, 30000, True, True, 2026, dynamic_threshold=True)

    assert result["success"] is False
    assert result["error"] == "年度报告质量校验未通过，请重试"
```

- [x] **Step 4: Verify validator tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py -q
```

Expected: all tests pass.

## Task 6: Preserve AI Task And API Compatibility

**Files:**
- Modify: `backend/tests/unit/test_ai_report_tasks.py`
- Modify if needed: `backend/tests/contract/test_ai_insights_contract.py`

- [x] **Step 1: Add task-level entity preservation coverage**

In `backend/tests/unit/test_ai_report_tasks.py`, add a focused yearly case near existing yearly report task tests:

```python
def test_yearly_report_task_preserves_entities_after_generation(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_yearly_story",
        lambda *args, **kwargs: {
            "success": True,
            "report": "截至 2026-06-23，Taylor Swift 和 Opalite 是你的年度重点。",
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["Taylor Swift"], "tracks": ["Opalite"]},
            "error": None,
        },
    )

    task_id = ai_task_service.create_report_task(
        _base_report_request(report_type="yearly", action="generate", year=2026, force=True)
    )
    ai_task_service.run_report_task(task_id)
    result = ai_task_service.get_task(task_id)

    assert result is not None
    assert result.status == "done"
    assert result.result is not None
    assert result.result["entities"] == {"artists": ["Taylor Swift"], "tracks": ["Opalite"]}
```

If the local task API uses different helper names in the current file, adapt only the invocation wrapper and keep the assertion unchanged.

- [x] **Step 2: Run report task tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_report_tasks.py -q
```

Expected: pass.

- [x] **Step 3: Run AI Insights contract tests**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_ai_insights_contract.py -q
```

Expected: pass. If a response model rejects the optional `entities` field in failure responses, update the model only to allow the existing field shape; do not add frontend-only fields.

## Task 7: Add A Real-Data Yearly Quality Probe

**Files:**
- Create: `scripts/probe_ai_yearly_report_quality.py`

- [x] **Step 1: Create a deterministic probe script**

Create `scripts/probe_ai_yearly_report_quality.py`:

```python
#!/usr/bin/env python3
"""Probe yearly AI report data contract against the local production DB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db  # noqa: E402
from backend.services.ai_insights_service import _gather_yearly_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    conn = get_db(readonly=True)
    try:
        data = _gather_yearly_data(
            conn,
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            year=args.year,
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
        )
    finally:
        conn.close()

    summary = {
        "year": args.year,
        "reporting_period": data.get("reporting_period"),
        "top_artists": data.get("top_artists", [])[:5],
        "top_tracks": data.get("top_tracks", [])[:5],
        "new_artists": data.get("new_artists", [])[:3],
        "personality_summary": data.get("personality_summary"),
        "genre_summary": data.get("genre_summary"),
        "year_over_year": data.get("year_over_year"),
    }

    failures: list[str] = []
    period = summary["reporting_period"] or {}
    if args.year == 2026 and period.get("end_date") != "2026-06-23":
        failures.append(f"expected current 2026 data cutoff 2026-06-23, got {period.get('end_date')}")
    if period.get("is_partial_year") is not True and args.year == 2026:
        failures.append("expected 2026 to be marked partial-year")
    if not all(item.get("name") for item in summary["top_artists"]):
        failures.append("top artist names must be populated")
    if not all(item.get("name") for item in summary["top_tracks"]):
        failures.append("top track names must be populated")
    if summary["year_over_year"].get("comparison_basis") != "same_period_ytd" and period.get("is_partial_year"):
        failures.append("partial-year comparison must use same_period_ytd")

    if args.json_output:
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 2: Run the probe**

Run:

```bash
.venv/bin/python scripts/probe_ai_yearly_report_quality.py --year 2026 --json-output /tmp/spotify_ai_yearly_2026_quality.json
```

Expected: exit code 0, with populated names and `reporting_period.is_partial_year=true`.

## Task 8: Real User-Behavior Verification

**Files:**
- No required code files.
- Optional output: `/tmp/spotify_ai_yearly_2026_quality.json`

- [x] **Step 1: Start or reuse local services**

Run if services are not already available:

```bash
source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend
cd frontend && npm run dev
```

Expected: backend on `http://127.0.0.1:8000`, frontend on `http://localhost:5173`.

- [x] **Step 2: Exercise the report endpoint without relying on cache**

Use the app's AI report task flow from `/ai-insights`, select yearly report for 2026, and manually generate. If direct API probing is needed for debugging, call the task endpoint used by the frontend rather than adding a new endpoint.

Expected user-visible behavior:

- The progress UI shows data gathering and LLM generation stages.
- The final report says data is截至 `2026-06-23`.
- The report names Taylor Swift, Olivia Rodrigo, and the top songs instead of saying only "某位艺人" or "另一首歌".
- The report does not call 2026 a completed full year.
- The report does not claim a full-year 55% decline unless it is explicitly framed as invalid/full-year-unsafe.
- The report does not invent unsupported scenes.

- [x] **Step 3: Check cache behavior**

Generate the same 2026 yearly report again without force.

Expected: cached report returns only if the validated report was stored. Invalid pre-fix cached reports may need manual cache bypass through existing force/manual generation behavior, not a migration.

## Task 9: Documentation And Final Verification

**Files:**
- Modify if needed: `docs/README.md`
- Modify if needed: `docs/CHANGELOG.md`
- Modify if needed: `AGENTS.md`
- Modify if needed: `CLAUDE.md`
- Modify if needed: `backend/CLAUDE.md`

- [x] **Step 1: Decide whether docs are necessary**

Run:

```bash
git diff -- backend/services/ai_insights_service.py backend/domains/ai_reports docs/README.md docs/CHANGELOG.md AGENTS.md CLAUDE.md backend/CLAUDE.md
```

If the implementation changed only internal helpers and tests, docs may be skipped. If it introduced durable AI report contract behavior, add one short changelog bullet and update AGENTS/CLAUDE AI Insights guidance.

- [x] **Step 2: Run focused backend verification**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_insights_service.py backend/tests/unit/test_ai_insights_yearly_quality.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_ai_insights_contract.py -q
```

Expected: all pass.

- [x] **Step 3: Run AI report and harness smoke**

Run:

```bash
.venv/bin/python scripts/probe_ai_yearly_report_quality.py --year 2026 --json-output /tmp/spotify_ai_yearly_2026_quality.json
.venv/bin/python scripts/evaluate_ai_agent_harness.py
```

Expected: yearly probe passes and existing AI Agent harness remains green.

- [x] **Step 4: Run formatting and lint for touched Python files**

Run:

```bash
ruff check backend/domains/ai_reports backend/services/ai_insights_service.py backend/tests/unit/test_ai_insights_yearly_quality.py scripts/probe_ai_yearly_report_quality.py
ruff format --check backend/domains/ai_reports backend/services/ai_insights_service.py backend/tests/unit/test_ai_insights_yearly_quality.py scripts/probe_ai_yearly_report_quality.py
```

Expected: pass.

- [x] **Step 5: Commit only if the user explicitly asks**

If the user asks for commit, use the repository's normal Chinese conventional commit style:

```bash
git add backend/domains/ai_reports backend/services/ai_insights_service.py backend/tests/unit/test_ai_insights_yearly_quality.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_ai_insights_contract.py scripts/probe_ai_yearly_report_quality.py docs/README.md docs/CHANGELOG.md AGENTS.md CLAUDE.md backend/CLAUDE.md
git commit -m "fix: harden AI yearly report quality"
```

If docs were not changed, omit those paths from `git add`.

## Plan Self-Review

- Spec coverage: all non-lyrics review issues are mapped to data contract, prompt, validator, or verification tasks.
- Placeholder scan: no `TBD`, `TODO`, or unspecified "add tests" steps remain.
- Scope check: this is one subsystem, AI Insights yearly reports, and does not require a broader AI Agent rewrite.
- Type consistency: `reporting_period`, `personality_summary`, `genre_summary`, `year_over_year`, `writing_constraints`, and `entities` names are used consistently across tasks.
- Risk note: the same-period comparison helper depends on `load_plays()` and should be tested with monkeypatch or real DB probe because `load_plays()` has cache behavior and uses the standard DB loader.
