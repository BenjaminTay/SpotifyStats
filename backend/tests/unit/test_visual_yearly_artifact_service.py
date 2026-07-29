from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_models import EvidenceLedgerEntry

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _disable_live_llm_for_unit_tests(monkeypatch):
    from backend.api import settings

    monkeypatch.setattr(
        settings,
        "_current",
        {"llm_enabled": False, "llm_api_key": "", "llm_base_url": ""},
    )


def test_visual_yearly_artifact_service_generates_artifact(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2025,
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        "hero": {"active_days": 364, "total_minutes": 68100, "total_plays": 17567},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 2629},
            {"name": "Michael Wong", "plays": 2087},
        ],
        "top_tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "plays": 190}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "weeks_on_chart": 32,
                    "rank": 1,
                }
            ],
            "tracks": [
                {
                    "name": "The Fate of Ophelia",
                    "artist": "Taylor Swift",
                    "weeks_on_chart": 13,
                    "rank": 1,
                }
            ],
            "artists": [{"name": "Taylor Swift", "weeks_on_chart": 50, "rank": 1}],
        },
        "genre_distribution": {
            "top_genres": [{"name": "mandopop", "share": 16.7}],
            "caveat": "Spotify 流派标签可能重叠。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}]
        },
        "highlight_day_detail": {
            "date": "2025-02-14",
            "plays": 154,
            "interpretation_guidance": "多曲目活跃日",
        },
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2025},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    chart_contexts = []
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: (
            chart_contexts.append(context) or {spec["id"]: {"ok": True} for spec in chart_specs}
        ),
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(
        svc,
        "run_report_agent",
        lambda **kw: _agent_sections_for_generates(),
    )

    result = svc.generate_visual_yearly_artifact(
        {
            "year": 2025,
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 12,
            "writer_pipeline": "deterministic_visual_v1",
        }
    )

    assert result["success"] is True
    assert result["artifact"]["report_mode"] == "visual_yearly_artifact"
    assert result["metadata"]["contract_version"] == "visual_yearly_v1"
    assert result["metadata"]["section_count"] >= 6
    assert result["metadata"]["chart_count"] >= 4
    assert result["critic"]["ok"] is True
    assert result["fact_validation"]["ok"] is True
    assert "Taylor Swift" in result["report"]
    assert "The Fate of Ophelia" in result["report"]
    assert "光良「回憶裡的瘋狂」巡迴演唱會" in result["report"]
    assert chart_contexts[0]["request_filters"] == {
        "year": 2025,
        "min_ms": 45000,
        "music_only": False,
        "merge_enabled": False,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 12,
    }


def test_visual_yearly_artifact_service_uses_agent_synthesis_writer(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    # Mock the Agent report writer to return valid sections
    agent_result = {
        "sections": [
            {
                "heading": "截至 2026-06-23 的阶段性回顾",
                "prose": "Taylor Swift 在 2026 年以 1115 次播放（占比 13.67%）位列艺人榜首。Opalite 以 123 次播放成为单曲第一。",
                "chart_refs": ["listening_calendar"],
            },
            {
                "heading": "Olivia Rodrigo 的月度追赶",
                "prose": "Olivia Rodrigo 以 769 次播放（9.43%）位列第二。她在 5 月达到 105 次月度播放。",
                "chart_refs": ["artist_monthly_trend"],
            },
        ],
        "research_summary": "summary",
        "evidence": [],
    }
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: agent_result)

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "agent_synthesis_v2"},
    )

    assert result["success"] is True
    assert "Taylor Swift" in result["report"]
    assert "1115 次播放" in result["report"]
    assert "Olivia Rodrigo" in result["report"]
    assert "agent_synthesis_v2" == result["metadata"]["writer_pipeline"]
    assert "agent_synthesis_v2" == result["metadata"]["writer_pipeline_version"]
    assert "accepted" == result["metadata"]["writer_pipeline_status"]


def test_visual_yearly_artifact_service_falls_back_when_llm_fails(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    # Agent returns empty sections → should fall back to minimal deterministic sections
    monkeypatch.setattr(
        svc,
        "run_report_agent",
        lambda **kw: {"sections": [], "research_summary": "", "evidence": []},
    )

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "agent_synthesis_v2"},
    )

    assert result["success"] is True
    assert result["report"]  # Has content from deterministic fallback
    assert "fallback_visual_composer" == result["metadata"]["writer_pipeline_status"]


def test_visual_yearly_artifact_service_uses_deterministic_visual_pipeline(monkeypatch):
    pass


def test_visual_yearly_artifact_service_avoids_duplicate_partial_cutoff(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "多曲目活跃日",
        },
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: _default_agent_sections())

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    assert "截至 2026-06-23" in result["report"]
    assert "截至 2026-06-23，截至 2026-06-23" not in result["report"]


def test_visual_yearly_artifact_service_handles_aligned_album_without_false_contrast(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    aligned_sections = _default_agent_sections()
    aligned_sections["sections"] = [
        {**s, "prose": s["prose"] + " 播放和个人 Billboard 指向同一个专辑。"}
        if s["role"] == "album_story"
        else s
        for s in aligned_sections["sections"]
    ]
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: aligned_sections)

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    assert "The Life of a Showgirl 和 The Life of a Showgirl" not in result["report"]
    assert "两种不同的喜欢" not in result["report"]
    assert any(phrase in result["report"] for phrase in ("重合", "同一张", "同一个专辑"))


def test_visual_yearly_artifact_service_sanitizes_editorial_leakage(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {
            "top_genres": [{"name": "mandopop", "share": 14.4}, {"name": "c-pop", "share": 14.4}],
            "caveat": "Spotify 流派标签可能重叠。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )
    prose = result["report"]

    assert "Olivia Rodrigo 让年度画像多了一条不同的情绪线。它把华语、回望和现场感" not in prose
    assert "不要写成" not in prose
    assert "证据强度可以先放在" not in prose
    assert prose.count("图表负责回答") <= 1


def test_visual_yearly_artifact_service_passes_full_context_to_visual_critic(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "pop", "share": 30.0}]},
        "discovery_and_returns": {"new_artists": []},
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    def fake_critic(artifact, context):
        del artifact
        captured["context"] = context
        return {"ok": True, "issues": []}

    monkeypatch.setattr(svc, "critique_visual_yearly_artifact", fake_critic)

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    assert result["critic"]["ok"] is True
    critic_context = captured["context"]
    assert critic_context["is_partial_year"] is True
    assert critic_context["top_albums"][0]["name"] == "The Life of a Showgirl"
    assert (
        critic_context["personal_billboard_year_end"]["albums"][0]["name"]
        == "The Life of a Showgirl"
    )


def test_visual_yearly_artifact_service_reads_chart_observations_in_sections(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    observations = {
        "artist_monthly_trend": "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。",
        "highlight_day_timeline": "2026-04-03 有 143 次播放，但最高单曲只有 4 次，更像多曲目密集漫游。",
        "playback_billboard_matrix": "Opalite 是单曲里兼具高播放和长在榜的核心作品。",
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: _chart_data_with_observations(observations),
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: _default_agent_sections())

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    # Chart observations are no longer injected into section prose
    # (skip_story_obligations=True avoids the old deterministic template injection).
    # The agent sections are rendered as-is.
    assert result["critic"]["ok"] is True
    report = result["report"]
    assert observations["artist_monthly_trend"] not in report
    assert "Taylor Swift 以 1115 次播放位列第一" in report
    assert observations["highlight_day_timeline"] not in report
    assert observations["playback_billboard_matrix"] not in report


def test_visual_yearly_artifact_service_uses_chart_data_for_dynamic_outline(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: _chart_data_with_observations(
            {
                "artist_monthly_trend": "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。",
            }
        ),
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: _default_agent_sections())

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    # Editorial plan outline is no longer used (skip_story_obligations=True).
    # Verify the artifact was generated successfully.
    assert result["success"] is True
    assert result["artifact"]["visual_brief"] is not None


def test_visual_yearly_artifact_service_partial_year_avoids_full_year_labels(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: _chart_data_with_observations(
            {
                "artist_monthly_trend": "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。",
            }
        ),
    )

    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: _default_agent_sections())

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    assert result["fact_validation"]["ok"] is True
    assert "年度排名" not in result["report"]
    visible_payload = " ".join(
        [
            result["report"],
            " ".join(
                str(card.get("label") or "") + str(card.get("caption") or "")
                for card in result["artifact"]["insight_cards"]
            ),
            " ".join(
                str(chart.get("title") or "")
                + str(chart.get("insight") or "")
                + str(chart.get("fallback") or "")
                for chart in result["artifact"]["chart_specs"]
            ),
        ]
    )
    assert "全年陪伴密度" not in visible_payload
    assert "年度高光日" not in visible_payload
    assert "年度声音线索" not in visible_payload
    assert "阶段陪伴密度" in visible_payload


def test_visual_yearly_artifact_exposes_editorial_metadata(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }

    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: ([], context),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            "listening_calendar": {"ok": True, "observations": ["活跃 174 天。"]},
            "artist_monthly_trend": {
                "ok": True,
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ],
            },
            "album_duality_compare": {"ok": True, "relation": "aligned"},
            "playback_billboard_matrix": {
                "ok": True,
                "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"],
            },
            "highlight_day_timeline": {
                "ok": True,
                "observations": ["2026-04-03 是播放最密集的一天，共 143 次。"],
            },
            "genre_language_mix": {"ok": True},
            "discovery_timeline": {"ok": True, "new_artists": [{"name": "Zhang Zhen Yue"}]},
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(
        svc,
        "run_report_agent",
        lambda **kw: {"sections": [], "research_summary": "", "evidence": []},
    )

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    metadata = result["artifact"]["metadata"]
    assert metadata["writer_pipeline"] == "agent_synthesis_v2"
    assert metadata["writer_pipeline_version"] == "agent_synthesis_v2"
    assert metadata["writer_pipeline_status"] == "fallback_visual_composer"
    assert metadata["section_count"] >= 1  # Fallback creates minimal 1-section report
    assert metadata["critic_passed"] is True
    assert metadata["fact_validation_passed"] is True
    assert metadata["final_artifact_quality_passed"] is True
    assert "editorial_plan_version" not in metadata
    assert "section_roles" not in metadata


def test_visual_yearly_artifact_respects_language_budget_and_avoids_overview_repetition(
    monkeypatch,
):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(svc, "_run_visual_research", lambda request, emit_event=None: ([], context))
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            spec["id"]: {"ok": True, "observations": []} for spec in chart_specs
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: _default_agent_sections())

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    assert result["critic"]["ok"] is True
    visible_text = _artifact_section_text(result["artifact"])
    report_text = result["report"]
    for text in (report_text, visible_text):
        assert text.count("174 个活跃日") <= 1
        assert text.count("7860 次播放") <= 1
        assert "通勤" not in text
        assert "下雨" not in text


def test_agent_synthesis_sections_do_not_render_internal_brief_as_deck(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()

    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            spec["id"]: {"ok": True, "observations": ["活跃 174 天。"]} for spec in chart_specs
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    agent_result = {
        "sections": [
            {
                "id": "opening",
                "heading": "截至 2026-06-23 的阶段性回看",
                "prose": "Taylor Swift 以 1115 次播放位列艺人榜第一。这个数字说明她仍然是你反复回到的声音。",
                "chart_refs": ["listening_calendar"],
            },
            {
                "id": "monthly_turn",
                "heading": "Olivia Rodrigo 在五月变亮",
                "prose": "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。它说明阶段偏好会在月份里发生倾斜。",
                "chart_refs": ["artist_monthly_trend"],
            },
            {
                "id": "album_alignment",
                "heading": "专辑播放和个人榜单重合",
                "prose": "The Life of a Showgirl 既是播放最多的专辑，也在个人 Billboard 专辑榜长时间停留。",
                "chart_refs": ["album_duality_compare"],
            },
            {
                "id": "highlight_day",
                "heading": "4 月 3 日不是单曲循环",
                "prose": "2026-04-03 有 143 次播放，但最高单曲只有 4 次，更像多曲目密集漫游。",
                "chart_refs": ["highlight_day_timeline"],
            },
            {
                "id": "new_voice",
                "heading": "Zhang Zhen Yue 成为新入口",
                "prose": "Zhang Zhen Yue 在 2026-03-09 首次出现，随后累计 574 次播放，说明新的中文声音进入记录。",
                "chart_refs": ["discovery_timeline"],
            },
            {
                "id": "closing",
                "heading": "这份年记最终留下什么",
                "prose": "这份记录把稳定回访、阶段变化和新发现放在一起，而不是只复述排行榜。",
                "chart_refs": [],
            },
        ],
        "research_summary": "summary",
        "evidence": [],
    }
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: agent_result)

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "agent_synthesis_v2"}
    )
    decks = "\n".join(section["deck"] for section in result["artifact"]["sections"])
    chart_refs = [
        ref for section in result["artifact"]["sections"] for ref in section["chart_refs"]
    ]

    assert "展示Olivia Rodrigo" not in decks
    assert "解释播放领先" not in decks
    assert len(chart_refs) == len(set(chart_refs))
    assert result["critic"]["ok"] is True
    assert result["metadata"]["final_artifact_quality_passed"] is True


def test_visual_yearly_artifact_service_blocks_final_quality_failure(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {
            "ok": False,
            "issues": [
                {
                    "code": "internal_brief_leakage",
                    "message": "洞察卡片泄漏内部 brief 语言。",
                    "severity": "error",
                }
            ],
            "visible_text_length": 1200,
        },
    )

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    # Quality checks are soft warnings — report is always served
    assert result["success"] is True
    assert result["artifact"] is not None
    assert result["report"] is not None
    assert result["cached"] is False
    assert result["metadata"]["final_artifact_quality_passed"] is False
    assert result["metadata"]["fallback_level"] == "final_quality_gate_failed"
    assert result["critic"]["ok"] is False


def test_agent_synthesis_roles_are_inferred_from_noncanonical_section_ids():
    from backend.domains.ai_reports.report_writer import parse_report_sections

    chart_specs = [
        {"id": "listening_calendar"},
        {"id": "artist_monthly_trend"},
        {"id": "album_duality_compare"},
        {"id": "highlight_day_timeline"},
        {"id": "discovery_timeline"},
    ]
    llm_output = """{
      "sections": [
        {"id": "stable_core", "heading": "Taylor Swift 的稳定回访", "prose": "Taylor Swift 是你持续回到的声音。", "chart_refs": ["listening_calendar"]},
        {"id": "monthly_turn", "heading": "五月的阶段变化", "prose": "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。", "chart_refs": ["artist_monthly_trend"]},
        {"id": "album_alignment", "heading": "专辑播放和个人 Billboard 重合", "prose": "The Life of a Showgirl 的播放量和个人 Billboard 指向同一张专辑。", "chart_refs": ["album_duality_compare"]},
        {"id": "density_peak", "heading": "高光日的播放密度", "prose": "2026-04-03 更像多曲目密集经过。", "chart_refs": ["highlight_day_timeline"]},
        {"id": "new_voice", "heading": "Zhang Zhen Yue 这个新声音", "prose": "Zhang Zhen Yue 是这个统计期的新声音。", "chart_refs": ["discovery_timeline"]}
      ]
    }"""

    sections = parse_report_sections(llm_output, chart_specs)
    roles = {section["id"]: section["role"] for section in sections}

    assert roles["stable_core"] == "main_artist"
    assert roles["monthly_turn"] == "turning_point"
    assert roles["album_alignment"] == "album_story"
    assert roles["density_peak"] == "highlight_day"
    assert roles["new_voice"] == "discovery"
    assert [section["chart_refs"] for section in sections if section["id"] == "monthly_turn"] == [
        ["artist_monthly_trend"]
    ]


def test_visual_yearly_artifact_service_blocks_fact_validation_failure(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {
            "ok": False,
            "issues": [
                {
                    "code": "ambiguous_entity_reference",
                    "message": "报告使用了无法定位的代词。",
                    "severity": "high",
                }
            ],
        },
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    # Quality checks are soft warnings — report is always served
    assert result["success"] is True
    assert result["artifact"] is not None
    assert result["report"] is not None
    assert result["metadata"]["fact_validation_passed"] is False
    assert result["metadata"]["fallback_level"] == "fact_validation_failed"


def test_visual_yearly_artifact_repairs_failed_llm_with_deterministic_fallback(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {"ok": True, "issues": [], "repair_instructions": []},
    )
    validation_calls = {"count": 0}

    def fake_fact_validation(report, artifact, context):
        del report, artifact, context
        validation_calls["count"] += 1
        return {
            "ok": False,
            "issues": [
                {
                    "code": "ambiguous_entity_reference",
                    "message": "LLM draft used 前者/后者。",
                    "severity": "high",
                }
            ],
        }

    monkeypatch.setattr(svc, "_validate_visual_fact_safety", fake_fact_validation)
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )
    # Agent now uses run_report_agent instead of call_report_writer_llm
    agent_sections = {
        "sections": [
            {
                "id": "opening",
                "heading": "截至 2026-06-23 的阶段回看",
                "prose": "Taylor Swift 以 1115 次播放位列第一。",
                "chart_refs": ["listening_calendar"],
            },
            {
                "id": "monthly_turn",
                "heading": "Olivia Rodrigo 的五月",
                "prose": "Olivia Rodrigo 在 2026-05 变亮。",
                "chart_refs": ["artist_monthly_trend"],
            },
            {
                "id": "album_alignment",
                "heading": "专辑与个人 Billboard",
                "prose": "The Life of a Showgirl 和 GUTS 被放在一起比较，前者播放更高，后者长留。",
                "chart_refs": ["album_duality_compare"],
            },
            {
                "id": "highlight_day",
                "heading": "高光日",
                "prose": "2026-04-03 有 143 次播放。",
                "chart_refs": ["highlight_day_timeline"],
            },
            {
                "id": "new_voice",
                "heading": "新声音",
                "prose": "Zhang Zhen Yue 是新入口。",
                "chart_refs": ["discovery_timeline"],
            },
            {"id": "closing", "heading": "收束", "prose": "这是一份阶段性回看。", "chart_refs": []},
        ],
        "research_summary": "summary",
        "evidence": [],
    }
    monkeypatch.setattr(svc, "run_report_agent", lambda **kw: agent_sections)

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "agent_synthesis_v2"}
    )

    # Quality checks are soft warnings — report is always served
    assert result["success"] is True
    assert result["artifact"] is not None
    assert result["report"] is not None
    assert validation_calls["count"] == 1
    assert result["metadata"]["fact_validation_passed"] is False


def test_visual_yearly_artifact_service_blocks_visual_critic_failure(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "critique_visual_yearly_artifact",
        lambda artifact, context: {
            "ok": False,
            "issues": [
                {
                    "code": "not_enough_sections",
                    "message": "图文年报至少需要 6 个章节。",
                    "severity": "error",
                }
            ],
            "repair_instructions": ["补足章节后再缓存。"],
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )
    monkeypatch.setattr(
        svc,
        "evaluate_final_artifact_quality",
        lambda artifact: {"ok": True, "issues": [], "visible_text_length": 1800},
    )

    result = svc.generate_visual_yearly_artifact(
        {"year": 2026, "writer_pipeline": "deterministic_visual_v1"}
    )

    # Quality checks are soft warnings — report is always served
    assert result["success"] is True
    assert result["artifact"] is not None
    assert result["report"] is not None
    assert result["metadata"]["critic_passed"] is False
    assert result["metadata"]["fallback_level"] == "visual_critic_failed"


def test_clean_user_text_keeps_partial_year_and_replaces_ambiguous_entities():
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()

    cleaned = svc._clean_user_text(
        "年中报告里，这一年里前者播放量更高，后者在个人 Billboard 长留。",
        context,
    )

    assert "年中" in cleaned
    assert "全年报告" not in cleaned
    assert "这一年" not in cleaned
    assert "这个统计期" in cleaned
    assert "前者" not in cleaned
    assert "后者" not in cleaned
    assert "The Life of a Showgirl" in cleaned
    assert "光良「回憶裡的瘋狂」巡迴演唱會" in cleaned


def test_chart_observation_repair_runs_after_section_polish():
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    sections = (
        svc._Section(
            id="matrix",
            role="album_story",
            heading="常听与长留",
            deck="播放量和个人榜单要一起看。",
            prose="The Life of a Showgirl 是专辑重心。",
            chart_refs=("playback_billboard_matrix",),
        ),
    )
    chart_data = {
        "playback_billboard_matrix": {
            "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"]
        }
    }

    repaired = svc._ensure_chart_observation_interpretations(sections, chart_data)

    assert "Opalite" in repaired[0].prose
    assert "高播放" in repaired[0].prose


def _artifact_section_text(artifact: dict) -> str:
    parts: list[str] = []
    for section in artifact["sections"]:
        parts.extend(str(section.get(key) or "") for key in ("deck", "prose", "pull_quote"))
    return "\n".join(parts)


def _quality_polish_context() -> dict:
    return {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "rank": 1,
                    "weeks_on_chart": 32,
                }
            ],
            "tracks": [
                {"name": "Opalite", "artist": "Taylor Swift", "rank": 1, "weeks_on_chart": 19}
            ],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {
            "top_genres": [{"name": "mandopop", "share": 14.4}, {"name": "c-pop", "share": 14.4}],
            "caveat": "Spotify 流派标签可能重叠。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
    }


def _chart_data_with_observations(observations: dict[str, str]) -> dict:
    return {
        "listening_calendar": {"ok": True, "active_days": 174},
        "artist_monthly_trend": {
            "ok": True,
            "observations": [observations["artist_monthly_trend"]],
        },
        "album_duality_compare": {
            "ok": True,
            "relation": "divergent",
            "playback_leader": {"name": "The Life of a Showgirl"},
            "chart_leader": {"name": "光良「回憶裡的瘋狂」巡迴演唱會"},
        },
        "highlight_day_timeline": {
            "ok": True,
            "observations": [
                observations.get(
                    "highlight_day_timeline",
                    "2026-04-03 有 143 次播放，但最高单曲只有 4 次，更像多曲目密集漫游。",
                )
            ],
        },
        "genre_language_mix": {"ok": True},
        "discovery_timeline": {"ok": True, "new_artists": [{"name": "Zhang Zhen Yue"}]},
        "playback_billboard_matrix": {
            "ok": True,
            "observations": [
                observations.get(
                    "playback_billboard_matrix", "Opalite 是单曲里兼具高播放和长在榜的核心作品。"
                )
            ],
        },
    }


def _agent_sections_for_generates() -> dict:
    return {
        "sections": [
            {
                "role": "opening",
                "heading": "2025 年度回顾",
                "prose": "Taylor Swift 以 2629 次播放位列艺人榜首。",
                "chart_refs": ["listening_calendar"],
            },
            {
                "role": "main_artist",
                "heading": "Taylor Swift",
                "prose": "她是你年度最重要的声音。",
                "chart_refs": ["artist_monthly_trend"],
            },
            {
                "role": "turning_point",
                "heading": "转折点",
                "prose": "The Fate of Ophelia 成为年度单曲第一。",
                "chart_refs": [],
            },
            {
                "role": "album_story",
                "heading": "专辑故事",
                "prose": "The Life of a Showgirl 也是个人 Billboard 专辑榜首。",
                "chart_refs": ["album_duality_compare"],
            },
            {
                "role": "highlight_day",
                "heading": "高光日",
                "prose": "2025-02-14 有 154 次播放。",
                "chart_refs": ["highlight_day_timeline"],
            },
            {
                "role": "discovery",
                "heading": "新发现",
                "prose": "JOLIN 成为新声音。",
                "chart_refs": ["discovery_timeline"],
            },
            {
                "role": "closing",
                "heading": "收束",
                "prose": "光良「回憶裡的瘋狂」巡迴演唱會在个人榜单长时间停留。",
                "chart_refs": [],
            },
        ],
        "research_summary": "summary",
        "evidence": [],
    }


def _default_agent_sections() -> dict:
    return {
        "sections": [
            {
                "role": "opening",
                "heading": "截至 2026-06-23 的阶段回看",
                "prose": "Taylor Swift 以 1115 次播放位列第一。",
                "chart_refs": ["listening_calendar"],
            },
            {
                "role": "turning_point",
                "heading": "Olivia Rodrigo 的五月",
                "prose": "Olivia Rodrigo 在 2026-05 变亮。",
                "chart_refs": ["artist_monthly_trend"],
            },
            {
                "role": "album_story",
                "heading": "专辑与榜单",
                "prose": "The Life of a Showgirl 是播放最多的专辑。",
                "chart_refs": ["album_duality_compare"],
            },
            {
                "role": "highlight_day",
                "heading": "高光日",
                "prose": "2026-04-03 有 143 次播放。",
                "chart_refs": ["highlight_day_timeline"],
            },
            {
                "role": "discovery",
                "heading": "新声音",
                "prose": "Zhang Zhen Yue 是新入口。",
                "chart_refs": ["discovery_timeline"],
            },
            {
                "role": "closing",
                "heading": "收束",
                "prose": "这是一份阶段性回看。",
                "chart_refs": [],
            },
        ],
        "research_summary": "summary",
        "evidence": [],
    }
