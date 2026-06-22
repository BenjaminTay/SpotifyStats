from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _report_data():
    return {
        "summary": {"total_plays": 1},
        "top_artists": [{"name": "Artist A", "plays": 1, "hours": 0.1}],
        "top_tracks": [{"name": "Track A - Artist A", "plays": 1, "hours": 0.1}],
    }


def test_generate_weekly_digest_passes_effective_filters_to_gather(monkeypatch):
    from backend.services import ai_insights_service as svc

    observed = {}

    monkeypatch.setattr(svc, "_get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "_get_llm", lambda: object())
    monkeypatch.setattr(svc, "_llm_chat", lambda *args, **kwargs: "weekly report")
    monkeypatch.setattr(svc, "_set_cache", lambda *args, **kwargs: None)

    def fake_gather(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        week_start,
        week_end,
        *,
        dynamic_threshold,
        max_merge_gap_minutes,
    ):
        observed.update(
            {
                "min_ms": min_ms,
                "music_only": music_only,
                "merge_enabled": merge_enabled,
                "week_start": week_start,
                "week_end": week_end,
                "dynamic_threshold": dynamic_threshold,
                "max_merge_gap_minutes": max_merge_gap_minutes,
            }
        )
        return _report_data()

    monkeypatch.setattr(svc, "_gather_weekly_data", fake_gather)

    result = svc.generate_weekly_digest(
        conn=None,
        min_ms=12345,
        music_only=False,
        merge_enabled=False,
        week_start="2026-05-01",
        week_end="2026-05-07",
        dynamic_threshold=True,
        max_merge_gap_minutes=30,
    )

    assert result["success"] is True
    assert observed == {
        "min_ms": 12345,
        "music_only": False,
        "merge_enabled": False,
        "week_start": "2026-05-01",
        "week_end": "2026-05-07",
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 30,
    }


def test_report_cache_key_changes_with_effective_filters(monkeypatch):
    from backend.services import ai_insights_service as svc

    keys = []

    def fake_get_cached(conn, key, ttl_hours):
        keys.append(key)
        return ("cached report", "2026-06-19T00:00:00")

    monkeypatch.setattr(svc, "_get_cached", fake_get_cached)
    monkeypatch.setattr(
        svc, "_safe_extract_entities", lambda *args, **kwargs: {"artists": [], "tracks": []}
    )

    svc.generate_weekly_digest(
        conn=None,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        week_start="2026-05-01",
        week_end="2026-05-07",
        dynamic_threshold=False,
        max_merge_gap_minutes=None,
    )
    svc.generate_weekly_digest(
        conn=None,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        week_start="2026-05-01",
        week_end="2026-05-07",
        dynamic_threshold=True,
        max_merge_gap_minutes=30,
    )

    assert keys[0] != keys[1]


def test_answer_question_passes_effective_filters_to_intent_fetch(monkeypatch):
    from backend.services import ai_insights_service as svc

    observed = {}

    monkeypatch.setattr(svc, "_get_llm", lambda: object())
    monkeypatch.setattr(
        svc,
        "_parse_intent",
        lambda question: {"intent": "general", "time_range": {"type": "all_time"}},
    )
    monkeypatch.setattr(svc, "_llm_chat", lambda *args, **kwargs: "answer")

    def fake_fetch(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        intent_result,
        *,
        dynamic_threshold,
        max_merge_gap_minutes,
        merge_level=1,
    ):
        observed.update(
            {
                "min_ms": min_ms,
                "music_only": music_only,
                "merge_enabled": merge_enabled,
                "intent": intent_result["intent"],
                "dynamic_threshold": dynamic_threshold,
                "max_merge_gap_minutes": max_merge_gap_minutes,
            }
        )
        return {"period": "lifetime", "start_date": None, "end_date": None}

    monkeypatch.setattr(svc, "_fetch_data_for_intent", fake_fetch)

    result = svc.answer_question(
        conn=None,
        min_ms=12345,
        music_only=False,
        merge_enabled=False,
        question="我今年听了什么？",
        dynamic_threshold=True,
        max_merge_gap_minutes=30,
        merge_level=2,
    )

    assert result["success"] is True
    assert observed == {
        "min_ms": 12345,
        "music_only": False,
        "merge_enabled": False,
        "intent": "general",
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 30,
    }
