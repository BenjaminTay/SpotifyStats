from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.contract


def test_yearly_story_response_includes_agentic_metadata(monkeypatch):
    monkeypatch.setattr(
        "backend.services.yearly_report_agent_service.generate_agentic_yearly_report",
        lambda request, emit_event=None: {
            "success": True,
            "report": "## Longform\n" + "解释" * 800,
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["Taylor Swift"], "tracks": ["Opalite"]},
            "metadata": {
                "report_mode": "agentic_longform",
                "contract_version": "agentic_yearly_v14",
                "fallback_level": None,
                "tool_calls": 8,
                "data_range": "2026-01-01 to 2026-06-23",
                "is_partial_year": True,
                "critic_passed": True,
                "article_length": 1600,
            },
            "critic": {"ok": True, "issues": []},
            "evidence_ledger": [],
            "error": None,
        },
    )
    client = TestClient(app)

    response = client.get("/api/ai-insights/yearly-story?year=2026&force=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["report"]
    assert payload["metadata"]["report_mode"] == "agentic_longform"
    assert payload["metadata"]["critic_passed"] is True
