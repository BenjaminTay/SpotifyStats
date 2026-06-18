from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def _success_report():
    return {
        "success": True,
        "report": "离线契约报告",
        "cached": False,
        "cached_at": None,
        "entities": {"artists": ["Artist A"], "tracks": ["Track A"]},
        "error": None,
    }


@pytest.mark.parametrize(
    ("path", "params", "patched_name"),
    [
        (
            "/api/ai-insights/weekly-digest",
            {"week_start": "2026-05-01", "week_end": "2026-05-07"},
            "generate_weekly_digest",
        ),
        (
            "/api/ai-insights/monthly-personality",
            {"month": "2026-05", "year": 2026},
            "generate_monthly_personality",
        ),
        (
            "/api/ai-insights/yearly-story",
            {"year": 2026},
            "generate_yearly_story",
        ),
    ],
)
def test_ai_insights_report_endpoints_forward_play_filters(
    client, monkeypatch, path, params, patched_name
):
    import backend.api.ai_insights as ai_api

    observed = {}

    def fake_generate(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        *args,
        force=False,
        dynamic_threshold,
        max_merge_gap_minutes,
    ):
        observed.update(
            {
                "min_ms": min_ms,
                "music_only": music_only,
                "merge_enabled": merge_enabled,
                "force": force,
                "dynamic_threshold": dynamic_threshold,
                "max_merge_gap_minutes": max_merge_gap_minutes,
            }
        )
        return _success_report()

    monkeypatch.setattr(ai_api, patched_name, fake_generate)

    response = client.get(
        path,
        params={
            **params,
            "min_ms": 12345,
            "music_only": False,
            "merge_enabled": False,
            "force": True,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 30,
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json()["report"] == "离线契约报告"
    assert observed == {
        "min_ms": 12345,
        "music_only": False,
        "merge_enabled": False,
        "force": True,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 30,
    }


def test_ai_insights_ask_forwards_play_filters(client, monkeypatch):
    import backend.api.ai_insights as ai_api

    observed = {}

    def fake_answer(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        question,
        conversation_history=None,
        *,
        dynamic_threshold,
        max_merge_gap_minutes,
    ):
        observed.update(
            {
                "min_ms": min_ms,
                "music_only": music_only,
                "merge_enabled": merge_enabled,
                "question": question,
                "history": conversation_history,
                "dynamic_threshold": dynamic_threshold,
                "max_merge_gap_minutes": max_merge_gap_minutes,
            }
        )
        return {
            "success": True,
            "answer": "离线契约回答",
            "period_info": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "error": None,
        }

    monkeypatch.setattr(ai_api, "answer_question", fake_answer)

    response = client.post(
        "/api/ai-insights/ask",
        params={
            "min_ms": 12345,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 30,
        },
        json={
            "question": "这个月我听了什么？",
            "conversation_history": [{"role": "user", "content": "先看五月"}],
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json()["answer"] == "离线契约回答"
    assert observed == {
        "min_ms": 12345,
        "music_only": False,
        "merge_enabled": False,
        "question": "这个月我听了什么？",
        "history": [{"role": "user", "content": "先看五月"}],
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 30,
    }


def test_ai_insights_llm_not_configured_maps_to_503(client, monkeypatch):
    import backend.api.ai_insights as ai_api

    monkeypatch.setattr(
        ai_api,
        "generate_yearly_story",
        lambda *args, **kwargs: {
            "success": False,
            "report": None,
            "cached": False,
            "error": "LLM 未配置",
        },
    )

    response = client.get("/api/ai-insights/yearly-story", params={"year": 2026})

    assert response.status_code == 503
    assert response.headers["x-request-id"]
    assert response.json()["detail"] == "LLM 未配置"
