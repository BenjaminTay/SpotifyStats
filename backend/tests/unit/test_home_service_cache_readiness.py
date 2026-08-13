from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from backend.services import home_service

pytestmark = pytest.mark.unit


def test_composite_cache_refreshes_when_preview_readiness_changes(monkeypatch):
    calls = []
    context = SimpleNamespace(
        model_dump_json=lambda: "{}",
        filter_fingerprint="fp",
    )

    class ContextModel:
        @classmethod
        def model_validate_json(cls, _value):
            return context

    def fake_build(_conn, _context):
        calls.append("build")
        return {"generation": len(calls)}

    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(home_service, "YearlyReviewFilterContext", ContextModel)
    monkeypatch.setattr(home_service, "get_db", lambda readonly=True: conn)
    monkeypatch.setattr(home_service, "build_home_overview", fake_build)
    home_service._get_home_overview_cached.cache_clear()

    first = home_service._get_home_overview_cached("{}", "db", "day", 0, "2026:key:0")
    again = home_service._get_home_overview_cached("{}", "db", "day", 0, "2026:key:0")
    billboard_ready = home_service._get_home_overview_cached("{}", "db", "day", 1, "2026:key:0")
    yearly_ready = home_service._get_home_overview_cached("{}", "db", "day", 1, "2026:key:1")

    assert first == again == {"generation": 1}
    assert billboard_ready == {"generation": 2}
    assert yearly_ready == {"generation": 3}
