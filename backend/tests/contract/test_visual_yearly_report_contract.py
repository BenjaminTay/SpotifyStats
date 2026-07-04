from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.contract


def _visual_result() -> dict:
    return {
        "success": True,
        "report": "你的音乐年记" * 500,
        "artifact": {
            "report_mode": "visual_yearly_artifact",
            "contract_version": "visual_yearly_v1",
            "title": "你的 2025 音乐年记",
            "sections": [],
            "chart_specs": [],
            "chart_data": {},
            "metadata": {
                "report_mode": "visual_yearly_artifact",
                "contract_version": "visual_yearly_v1",
            },
        },
        "cached": False,
        "cached_at": None,
        "entities": {"artists": ["Taylor Swift"], "tracks": ["The Fate of Ophelia"]},
        "metadata": {
            "report_mode": "visual_yearly_artifact",
            "contract_version": "visual_yearly_v1",
        },
        "critic": {"ok": True, "issues": []},
        "fact_validation": {"ok": True, "issues": []},
        "evidence_ledger": [],
        "error": None,
    }


def test_yearly_story_force_visual_artifact_returns_artifact(client, monkeypatch):
    monkeypatch.setattr(
        "backend.domains.ai_reports.visual_yearly_artifact_service.generate_visual_yearly_artifact",
        lambda request, emit_event=None: _visual_result(),
    )

    response = client.get(
        "/api/ai-insights/yearly-story",
        params={"year": 2025, "force": True, "report_mode": "visual_yearly_artifact"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["report_mode"] == "visual_yearly_artifact"
    assert payload["artifact"]["contract_version"] == "visual_yearly_v1"


def test_yearly_story_visual_cache_only_returns_artifact_without_legacy_generation(
    client,
    monkeypatch,
):
    cached_payload = _visual_result()
    cached_payload["cached"] = True
    monkeypatch.setattr(
        "backend.services.ai_insights_service.peek_report_cache",
        lambda *args, **kwargs: {
            "cached": True,
            "report": json.dumps(cached_payload),
            "cached_at": "2026-07-04T00:00:00",
            "entities": None,
        },
    )
    monkeypatch.setattr(
        "backend.api.ai_insights.generate_yearly_story",
        lambda *args, **kwargs: pytest.fail("visual cache-only must not call legacy yearly story"),
    )

    response = client.get(
        "/api/ai-insights/yearly-story",
        params={"year": 2025, "report_mode": "visual_yearly_artifact"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is True
    assert payload["artifact"]["contract_version"] == "visual_yearly_v1"
    assert payload["metadata"]["report_mode"] == "visual_yearly_artifact"


def test_yearly_story_visual_cache_only_returns_needs_generation_without_legacy_generation(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.services.ai_insights_service.peek_report_cache",
        lambda *args, **kwargs: {
            "cached": False,
            "report": None,
            "cached_at": None,
            "entities": None,
        },
    )
    monkeypatch.setattr(
        "backend.api.ai_insights.generate_yearly_story",
        lambda *args, **kwargs: pytest.fail("visual cache-only must not call legacy yearly story"),
    )

    response = client.get(
        "/api/ai-insights/yearly-story",
        params={"year": 2025, "report_mode": "visual_yearly_artifact"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is False
    assert payload["artifact"] is None
    assert payload["metadata"] == {
        "report_mode": "visual_yearly_artifact",
        "needs_generation": True,
    }


def test_report_task_accepts_visual_yearly_mode(client):
    response = client.post(
        "/api/ai/tasks/report",
        json={
            "report_type": "yearly",
            "action": "generate",
            "year": 2025,
            "report_mode": "visual_yearly_artifact",
            "writer_pipeline": "editorial_agent_v1",
            "force": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"]
    assert payload["task_type"] == "ai_report_yearly"
