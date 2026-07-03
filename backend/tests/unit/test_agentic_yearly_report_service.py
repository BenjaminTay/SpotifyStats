from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_models import (
    AGENTIC_YEARLY_CONTRACT_VERSION,
    AGENTIC_YEARLY_REPORT_MODE,
    AgenticYearlyMetadata,
    DynamicOutline,
    EvidenceLedgerEntry,
    InsightSynthesis,
    OutlineSection,
)

pytestmark = pytest.mark.unit


def test_evidence_ledger_entry_serializes_for_task_payload():
    entry = EvidenceLedgerEntry(
        tool_name="yearly_overview",
        params={"year": 2026, "period_mode": "year_to_date"},
        result_summary="截至 2026-06-23，播放 7,860 次，累计 498 小时。",
        supports=("activity_level", "period_cutoff"),
        questions_raised=("播放下降但曲目增长，是否代表探索扩张？",),
        tool_call_id="tool_1",
    )

    assert entry.to_dict() == {
        "tool_name": "yearly_overview",
        "params": {"year": 2026, "period_mode": "year_to_date"},
        "result_summary": "截至 2026-06-23，播放 7,860 次，累计 498 小时。",
        "supports": ["activity_level", "period_cutoff"],
        "questions_raised": ["播放下降但曲目增长，是否代表探索扩张？"],
        "tool_call_id": "tool_1",
    }


def test_insight_outline_and_metadata_shape_are_stable():
    synthesis = InsightSynthesis(
        main_thesis="Taylor Swift 是稳定中心，Zhang Zhen Yue 打开新入口。",
        supporting_arguments=(
            {
                "claim": "Taylor Swift 是稳定中心",
                "evidence_refs": ["artist_rank_1", "album_rank_1"],
            },
        ),
        billboard_findings=("个人榜单显示 Taylor Swift 三榜联动强。",),
        playback_findings=("播放次数下降但曲目数上升。",),
        tensions=("总量下降与探索扩大并存。",),
        interesting_anomalies=("最活跃日不是单曲循环日。",),
    )
    outline = DynamicOutline(
        title="Taylor Swift 仍是中心，但你的音乐版图正在外扩",
        sections=(
            OutlineSection(
                heading="今年真正的变化",
                question="为什么播放下降不等于热情下降？",
                claims=("探索扩大", "核心循环减少"),
            ),
        ),
    )
    metadata = AgenticYearlyMetadata(
        report_mode="agentic_longform",
        contract_version="agentic_yearly_v14",
        fallback_level=None,
        tool_calls=8,
        data_range="2026-01-01 to 2026-06-23",
        is_partial_year=True,
        critic_passed=True,
        article_length=1650,
    )

    assert synthesis.to_dict()["main_thesis"].startswith("Taylor Swift")
    assert outline.to_dict()["sections"][0]["question"] == "为什么播放下降不等于热情下降？"
    assert metadata.to_dict()["fallback_level"] is None
    assert metadata.to_dict()["contract_version"] == "agentic_yearly_v14"


def test_agentic_yearly_prompts_define_mission_and_boundaries():
    from backend.domains.ai_reports.agentic_prompts import (
        LONGFORM_DRAFT_SYSTEM_PROMPT,
        REPORT_MISSION_SYSTEM_PROMPT,
    )

    assert "只读" in REPORT_MISSION_SYSTEM_PROMPT
    assert "自主调用" in REPORT_MISSION_SYSTEM_PROMPT
    assert "个人 Billboard" in REPORT_MISSION_SYSTEM_PROMPT
    assert "不是外部官方 Billboard" in REPORT_MISSION_SYSTEM_PROMPT
    assert "播放分析年度总结页的文字复述" in REPORT_MISSION_SYSTEM_PROMPT
    assert "1400-2200" in LONGFORM_DRAFT_SYSTEM_PROMPT
    assert "判断 -> 证据 -> 解释" in LONGFORM_DRAFT_SYSTEM_PROMPT
    assert "不要只是罗列" in LONGFORM_DRAFT_SYSTEM_PROMPT


def test_agentic_service_generates_basic_metadata_with_injected_llm(monkeypatch):
    from backend.services import yearly_report_agent_service as svc

    monkeypatch.setattr(
        svc,
        "_run_research_plan",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="播放 7,860 次，累计 498 小时。",
                    supports=("activity_level",),
                ),
                EvidenceLedgerEntry(
                    tool_name="personal_billboard_year_end",
                    params={"year": 2026},
                    result_summary="个人 Billboard 显示 Taylor Swift 三榜联动。",
                    supports=("personal_billboard",),
                ),
            ],
            {
                "year": 2026,
                "reporting_period": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-23",
                    "is_partial_year": True,
                },
                "top_artists": [{"name": "Taylor Swift"}],
                "top_tracks": [{"name": "Opalite"}],
            },
        ),
    )
    monkeypatch.setattr(
        svc,
        "_call_llm_json",
        lambda *args, **kwargs: {
            "main_thesis": "Taylor Swift 是稳定中心，Zhang Zhen Yue 打开新入口。",
            "supporting_arguments": [],
            "billboard_findings": ["个人 Billboard 说明稳定中心。"],
            "playback_findings": ["播放下降但探索扩大。"],
            "tensions": [],
            "interesting_anomalies": [],
            "title": "Taylor Swift 仍是中心",
            "sections": [
                {
                    "heading": "稳定中心",
                    "question": "中心如何成立？",
                    "claims": ["播放和榜单共同支持"],
                }
            ],
        },
    )
    long_report = (
        "## Taylor Swift 仍是中心\n\n"
        + "Taylor Swift 的领先不是单点爆发，而是播放分析和个人 Billboard 共同指向的稳定中心。"
        "播放记录说明核心艺人的稳定，个人 Billboard 又通过在榜能力互相印证这种稳定。"
        "这意味着你的 2026 上半年有明确坐标，同时 Zhang Zhen Yue 打开新入口。" * 24
    )
    monkeypatch.setattr(svc, "_call_llm_text", lambda *args, **kwargs: long_report)
    monkeypatch.setattr(
        svc, "_validate_agentic_fact_safety", lambda *args, **kwargs: {"ok": True, "issues": []}
    )

    result = svc.generate_agentic_yearly_report(
        {
            "year": 2026,
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
        }
    )

    assert result["success"] is True
    assert result["metadata"]["report_mode"] == AGENTIC_YEARLY_REPORT_MODE
    assert result["metadata"]["contract_version"] == AGENTIC_YEARLY_CONTRACT_VERSION
    assert result["metadata"]["fallback_level"] is None
    assert result["metadata"]["tool_calls"] == 2
    assert result["metadata"]["critic_passed"] is True
    assert result["cached"] is False
    assert result["entities"] == {"artists": ["Taylor Swift"], "tracks": ["Opalite"]}


def test_agentic_service_marks_basic_summary_fallback_when_critic_fails(monkeypatch):
    from backend.services import yearly_report_agent_service as svc

    monkeypatch.setattr(
        svc,
        "_run_research_plan",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            {
                "reporting_period": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-23",
                    "is_partial_year": True,
                },
            },
        ),
    )
    monkeypatch.setattr(svc, "_call_llm_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        svc,
        "_call_llm_text",
        lambda *args, **kwargs: "Taylor Swift 以 1115 次播放排在第一。",
    )
    monkeypatch.setattr(
        svc,
        "_build_basic_summary_fallback",
        lambda context, request: "## 基础摘要\nTaylor Swift 是第一。",
    )

    result = svc.generate_agentic_yearly_report({"year": 2026})

    assert result["success"] is True
    assert result["metadata"]["fallback_level"] == "basic_summary"
    assert result["metadata"]["critic_passed"] is False
    assert result["report"].startswith("## 基础摘要")


def test_agentic_service_uses_structured_longform_repair_before_basic_summary(monkeypatch):
    from backend.services import yearly_report_agent_service as svc

    monkeypatch.setattr(
        svc,
        "_run_research_plan",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="播放 7,860 次，累计 498 小时。",
                ),
                EvidenceLedgerEntry(
                    tool_name="personal_billboard_year_end",
                    params={"year": 2026},
                    result_summary="个人 Billboard 显示三榜联动。",
                ),
            ],
            {
                "reporting_period": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-23",
                    "is_partial_year": True,
                    "active_days": 174,
                },
                "hero": {
                    "total_plays": 7860,
                    "total_minutes": 29882,
                    "unique_tracks": 2060,
                    "unique_artists": 328,
                },
                "top_artists": [
                    {"name": "Taylor Swift", "plays": 1115, "hours": 68.8},
                    {"name": "Olivia Rodrigo", "plays": 769},
                    {"name": "Zhang Zhen Yue", "plays": 574},
                ],
                "top_tracks": [{"name": "Opalite", "plays": 123}],
                "top_albums": [{"name": "The Life of a Showgirl", "plays": 445}],
                "personal_billboard_year_end": {
                    "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
                    "albums": [
                        {
                            "name": "The Life of a Showgirl",
                            "rank": 1,
                            "weeks_on_chart": 24,
                        }
                    ],
                    "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
                },
                "billboard_yearly_diagnostics": {
                    "dominance": {"artist": "Taylor Swift"},
                    "cross_chart_alignment": [{"entity": "Taylor Swift"}],
                },
                "genre_distribution": {
                    "top_genres": [{"name": "mandopop", "share": 14.4}],
                    "caveat": "Spotify 流派标签可能重叠。",
                },
                "discovery_and_returns": {
                    "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574}],
                    "longest_love": {"track_name": "Nothing New", "days": 1450},
                },
                "highlight_day_detail": {
                    "date": "2026-04-03",
                    "plays": 143,
                    "interpretation_guidance": "多曲目活跃日",
                },
                "yearly_same_period_comparison": {
                    "same_period": {
                        "available": True,
                        "changes": {"plays_change": -10.0, "tracks_change": 23.3},
                    }
                },
            },
        ),
    )
    monkeypatch.setattr(svc, "_call_llm_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        svc,
        "_call_llm_text",
        lambda *args, **kwargs: "Taylor Swift 以 1115 次播放排在第一。",
    )
    monkeypatch.setattr(
        svc,
        "_build_basic_summary_fallback",
        lambda *args, **kwargs: pytest.fail("structured repair should run before basic summary"),
    )

    result = svc.generate_agentic_yearly_report({"year": 2026})

    assert result["success"] is True
    assert result["metadata"]["fallback_level"] is None
    assert result["metadata"]["critic_passed"] is True
    assert result["metadata"]["article_length"] >= 1400
    assert "个人 Billboard" in result["report"]
    assert "共同" in result["report"]


def test_agentic_fact_safety_rejects_unsupported_intent_and_alias():
    from backend.services.yearly_report_agent_service import _validate_agentic_fact_safety

    context = {
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "discovery_and_returns": {"new_artists": [{"name": "Zhang Zhen Yue"}]},
        "genre_distribution": {"top_genres": [{"name": "其他流派", "share": 19.1}]},
        "personal_billboard_year_end": {
            "available": True,
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "albums": [{"name": "The Life of a Showgirl", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
    }
    report = (
        "## 2026 年中音乐报告\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、"
        "张震岳（Zhang Zhen Yue）和其他流派都很突出。"
        "个人 Billboard 是基于本地播放记录的个人榜，不是外部官方 Billboard，"
        "Opalite 第 1 且在榜 19 周。"
        "这说明你主动选择拓宽音乐版图。"
    )

    result = _validate_agentic_fact_safety(report, context)

    codes = {issue["code"] for issue in result["issues"]}
    assert result["ok"] is False
    assert "unsupported_intent_claim" in codes
    assert "unsupported_entity_alias" in codes
