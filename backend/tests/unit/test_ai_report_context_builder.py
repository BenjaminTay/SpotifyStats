from __future__ import annotations

from types import SimpleNamespace

from backend.domains.ai_reports import context_builder


class _Connection:
    def close(self) -> None:
        return None


def test_prepare_context_uses_yearly_review_exact_key(monkeypatch):
    monkeypatch.setattr(context_builder, "get_db", lambda **_kwargs: _Connection())
    monkeypatch.setattr(
        context_builder.SettingsRepository,
        "load_all",
        lambda _self: {
            **context_builder.SETTINGS_DEFAULTS,
            "bb_top_n": 42,
        },
    )
    captured = {}

    def fake_build(_conn, filters):
        captured["filters"] = filters
        return SimpleNamespace(filter_fingerprint="filter-1", max_merge_gap_minutes=7)

    monkeypatch.setattr(context_builder, "build_yearly_review_context", fake_build)
    monkeypatch.setattr(
        context_builder,
        "_prepare_artifact",
        lambda year, filter_context: SimpleNamespace(
            year=year,
            cache_key="yearly-review-exact-key",
            db_revision="source-revision",
            context=filter_context,
        ),
    )

    snapshot_key, source_revision, fingerprint, request_json = (
        context_builder.prepare_yearly_agent_context(
            {
                "year": 2025,
                "min_ms": 12345,
                "max_merge_gap_minutes": 7,
            }
        )
    )

    assert len(snapshot_key) == 64
    assert source_revision == "source-revision"
    assert fingerprint == "filter-1"
    assert captured["filters"].bb_top_n == 42
    assert '"max_merge_gap_minutes":7' in request_json


def test_exact_snapshot_prevents_repeated_heavy_context_build(monkeypatch):
    storage = {}
    calls = {"gather": 0}
    monkeypatch.setattr(
        context_builder,
        "prepare_yearly_agent_context",
        lambda _request: ("snapshot-key", "revision", "fingerprint", _REQUEST_JSON),
    )
    monkeypatch.setattr(context_builder, "load_context_snapshot", storage.get)

    def store(key, value, **_kwargs):
        storage[key] = value

    monkeypatch.setattr(context_builder, "store_context_snapshot", store)
    monkeypatch.setattr(context_builder, "get_db", lambda **_kwargs: _Connection())

    from backend.services import ai_insights_service

    gather_kwargs: list[dict] = []

    def gather(*_args, **kwargs):
        calls["gather"] += 1
        gather_kwargs.append(kwargs)
        return {
            "reporting_period": {
                "year": 2025,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "is_partial_year": False,
            },
            "hero": {"total_plays": 88, "total_minutes": 600},
            "top_artists": [{"name": "Artist", "plays": 30}],
            "top_tracks": [{"name": "Track", "plays": 20}],
            "top_albums": [{"name": "Album", "plays": 10}],
            "billboard_year_end": {"artists": [], "albums": [], "tracks": []},
            "genre_summary": {"top_genres": []},
            "new_artists": [],
            "most_active_day": {},
            "year_over_year": {},
        }

    monkeypatch.setattr(ai_insights_service, "_gather_yearly_data", gather)
    monkeypatch.setattr(context_builder, "build_narrative_brief", lambda _context: {})
    monkeypatch.setattr(context_builder, "chart_coverage", lambda _context: {})
    monkeypatch.setattr(context_builder, "build_visual_brief", lambda *_args: {"chart_specs": []})
    monkeypatch.setattr(context_builder, "build_visual_chart_data", lambda *_args: {})

    cold = context_builder.get_or_build_yearly_agent_context({"year": 2025})
    warm = context_builder.get_or_build_yearly_agent_context({"year": 2025})

    assert cold.built is True
    assert cold.cache_hit is False
    assert warm.built is False
    assert warm.cache_hit is True
    assert calls["gather"] == 1
    assert gather_kwargs[0]["allow_expensive_year_end"] is False
    assert cold.context["hero"]["total_plays"] == 88
    assert len(cold.payload["evidence"]) == len(context_builder.REPORT_RESEARCH_TOOLS)


_REQUEST_JSON = (
    '{"dynamic_threshold":true,"max_merge_gap_minutes":5,"merge_enabled":true,'
    '"min_ms":30000,"music_only":true,"year":2025}'
)
